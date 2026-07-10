"""
Action Executor — the engine that runs planned actions against a Discord guild.

Orchestrates dry-run previews, safe execution with error isolation,
and result formatting for Discord message delivery.
"""

from typing import Any, Dict, List, Optional, Union

import discord

from .actions import ChannelActions, RoleActions
from .models import Action, ActionType, PermissionOverwrite, SafetyConfig
from .utils import chunk_text


class ActionExecutor:
    """Execute a batch of actions against a guild with dry-run + safety checks."""

    def __init__(self, guild: discord.Guild, safety_config: SafetyConfig) -> None:
        self.guild = guild
        self.safety = safety_config
        self.channels = ChannelActions(guild)
        self.roles = RoleActions(guild, safety_config)
        self.results: List[str] = []
        self.errors: List[str] = []

    # ── Safety Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_destructive(action: Action) -> bool:
        return action.type in {
            ActionType.DELETE_CATEGORY,
            ActionType.DELETE_TEXT_CHANNEL,
            ActionType.DELETE_VOICE_CHANNEL,
            ActionType.DELETE_FORUM_CHANNEL,
            ActionType.DELETE_ROLE,
            ActionType.SET_CHANNEL_PERMISSIONS,
            ActionType.SET_ROLE_PERMISSIONS,
        }

    def _is_protected_channel(
        self, channel_name: str, category_name: str | None = None
    ) -> bool:
        raw = channel_name.removeprefix("#")
        if raw in self.safety.protected_channels:
            return True
        full = f"{category_name}/{raw}" if category_name else raw
        return full in self.safety.protected_channels

    def _is_protected_role(self, role_name: str) -> bool:
        return role_name in self.safety.protected_roles

    # ── Main Execute ────────────────────────────────────────────────────────

    async def execute(
        self,
        actions: List[Action],
        confirm_destructive: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute (or preview) a list of actions, collecting results per action."""
        self.results.clear()
        self.errors.clear()

        for action in actions:
            try:
                self._check_safety(action, confirm_destructive, dry_run)

                if dry_run:
                    self.results.append(
                        f"[DRY RUN] Would execute: {action.type.value} — {action.reason}"
                    )
                    continue

                outcome = await self._execute_one(action)
                self.results.append(
                    f"✅ {action.type.value}: {action.reason} → {outcome}"
                )

            except Exception as exc:
                self.errors.append(
                    f"❌ {action.type.value}: {action.reason} → {exc}"
                )

        return {
            "success": len(self.errors) == 0,
            "results": self.results,
            "errors": self.errors,
            "summary": f"{len(self.results)} succeeded, {len(self.errors)} failed",
        }

    def _check_safety(
        self, action: Action, confirm_destructive: bool, dry_run: bool
    ) -> None:
        """Raise if the action violates a safety rule."""
        if not self._is_destructive(action):
            return

        params = action.params

        # Channel protection
        if action.type in {
            ActionType.DELETE_TEXT_CHANNEL,
            ActionType.DELETE_VOICE_CHANNEL,
            ActionType.DELETE_FORUM_CHANNEL,
        }:
            if self._is_protected_channel(
                params.get("name", ""), params.get("category")
            ):
                raise ValueError(f"Protected channel: {params.get('name')}")

        # Role protection
        if action.type == ActionType.DELETE_ROLE:
            if self._is_protected_role(params.get("name", "")):
                raise ValueError(f"Protected role: {params.get('name')}")

    # ── Permission Sanitizer ──────────────────────────────────────────────

    @staticmethod
    def _sanitize_permissions(
        perms: Any,
    ) -> Optional[List[PermissionOverwrite]]:
        """Convert raw JSON permissions from AI into PermissionOverwrite objects.

        Handles multiple formats the AI might return:
        - List[PermissionOverwrite] objects → pass through
        - List[dict] → convert to PermissionOverwrite
        - Dict → convert single overwrite or return None
        - None/empty → return None
        """
        if not perms:
            return None
        if isinstance(perms, list):
            result = []
            for item in perms:
                if isinstance(item, PermissionOverwrite):
                    result.append(item)
                elif isinstance(item, dict):
                    result.append(PermissionOverwrite(**item))
                else:
                    return None
            return result
        if isinstance(perms, dict):
            # Maybe it's a single overwrite dict
            if "target_type" in perms:
                return [PermissionOverwrite(**perms)]
            # Unknown dict format — discard
            return None
        return None

    # ── Single Action Dispatch ──────────────────────────────────────────────

    async def _execute_one(self, action: Action) -> str:
        t = action.type
        p = action.params

        # ── Categories ──
        if t is ActionType.CREATE_CATEGORY:
            return (await self.channels.create_category(p["name"], p.get("position"))).name

        if t is ActionType.DELETE_CATEGORY:
            await self.channels.delete_category(p["name"])
            return f"Deleted category '{p['name']}'"

        if t is ActionType.RENAME_CATEGORY:
            return (
                await self.channels.rename_category(p["old_name"], p["new_name"])
            ).name

        # ── Text Channels ──
        if t is ActionType.CREATE_TEXT_CHANNEL:
            ch = await self.channels.create_text_channel(
                p["name"],
                p["category"],
                p.get("topic", ""),
                p.get("slowmode", 0),
                p.get("nsfw", False),
                self._sanitize_permissions(p.get("permissions")),
            )
            return f"#{ch.name} in {p['category']}"

        if t is ActionType.DELETE_TEXT_CHANNEL:
            await self.channels.delete_text_channel(p["name"], p.get("category"))
            return f"Deleted #{p['name']}"

        if t is ActionType.RENAME_TEXT_CHANNEL:
            ch = await self.channels.rename_text_channel(
                p["old_name"], p["new_name"], p.get("category")
            )
            return f"#{p['old_name']} → #{ch.name}"

        if t is ActionType.SET_CHANNEL_TOPIC:
            ch = await self.channels.set_channel_topic(
                p["name"], p["category"], p["topic"]
            )
            return f"Topic set for #{ch.name}"

        if t is ActionType.SET_CHANNEL_PERMISSIONS:
            ch = await self.channels.set_channel_permissions(
                p["name"], p["category"], p["overwrites"]
            )
            return f"Permissions updated for #{ch.name}"

        # ── Voice Channels ──
        if t is ActionType.CREATE_VOICE_CHANNEL:
            vc = await self.channels.create_voice_channel(
                p["name"],
                p["category"],
                p.get("bitrate", 64000),
                p.get("user_limit", 0),
                p.get("video_quality_mode", "auto"),
                self._sanitize_permissions(p.get("permissions")),
            )
            return f"Voice: {vc.name}"

        if t is ActionType.DELETE_VOICE_CHANNEL:
            await self.channels.delete_voice_channel(p["name"], p.get("category"))
            return f"Deleted voice: {p['name']}"

        # ── Forums ──
        if t is ActionType.CREATE_FORUM_CHANNEL:
            fc = await self.channels.create_forum_channel(
                p["name"],
                p["category"],
                p.get("topic", ""),
                p.get("default_reaction_emoji", "📝"),
                p.get("available_tags"),
                p.get("default_layout", "list_view"),
            )
            return f"Forum: {fc.name}"

        if t is ActionType.DELETE_FORUM_CHANNEL:
            await self.channels.delete_forum_channel(p["name"], p.get("category"))
            return f"Deleted forum: {p['name']}"

        # ── Roles ──
        if t is ActionType.CREATE_ROLE:
            return (
                await self.roles.create_role(
                    p["name"],
                    p.get("color", "#99aab5"),
                    p.get("hoist", False),
                    p.get("mentionable", False),
                    p.get("permissions"),
                )
            ).name

        if t is ActionType.DELETE_ROLE:
            await self.roles.delete_role(p["name"])
            return f"Deleted role: {p['name']}"

        if t is ActionType.RENAME_ROLE:
            return (
                await self.roles.rename_role(p["old_name"], p["new_name"])
            ).name

        if t is ActionType.SET_ROLE_PERMISSIONS:
            return (
                await self.roles.set_role_permissions(p["name"], p["permissions"])
            ).name

        if t is ActionType.SET_ROLE_COLOR:
            return (
                await self.roles.set_role_color(p["name"], p["color"])
            ).name

        if t is ActionType.ASSIGN_ROLE:
            m = await self.roles.assign_role(p["user"], p["role"])
            return f"Assigned {p['role']} to {m.display_name}"

        if t is ActionType.REMOVE_ROLE:
            m = await self.roles.remove_role(p["user"], p["role"])
            return f"Removed {p['role']} from {m.display_name}"

        raise ValueError(f"Unknown action type: {t}")

    # ── Output Formatting ───────────────────────────────────────────────────

    def format_results(self) -> List[str]:
        """Return the log as Discord-safe message chunks."""
        text = "\n".join(self.results + self.errors)
        return chunk_text(text)

"""
Channel actions — create, delete, rename, and configure all Discord channel types.
"""

from typing import List, Optional

import discord

from ..models import PermissionOverwrite


class ChannelActions:
    """High-level Discord channel CRUD wrapped in safe, idempotent helpers."""

    def __init__(self, guild: discord.Guild) -> None:
        self.guild = guild

    # ── Lookup Helpers ─────────────────────────────────────────────────────

    def _category(self, name: str) -> Optional[discord.CategoryChannel]:
        return discord.utils.get(self.guild.categories, name=name)

    def _text_ch(
        self, name: str, cat: Optional[discord.CategoryChannel] = None
    ) -> Optional[discord.TextChannel]:
        channels = cat.text_channels if cat else self.guild.text_channels
        return discord.utils.get(channels, name=name)

    def _voice_ch(
        self, name: str, cat: Optional[discord.CategoryChannel] = None
    ) -> Optional[discord.VoiceChannel]:
        channels = cat.voice_channels if cat else self.guild.voice_channels
        return discord.utils.get(channels, name=name)

    def _forum_ch(
        self, name: str, cat: Optional[discord.CategoryChannel] = None
    ) -> Optional[discord.ForumChannel]:
        if cat:
            return discord.utils.get(cat.channels, name=name)
        return discord.utils.get(
            [c for c in self.guild.channels if isinstance(c, discord.ForumChannel)],
            name=name,
        )

    # ── Permission Overwrite Builder ────────────────────────────────────────

    def _build_overwrites(
        self, overwrites: List[PermissionOverwrite]
    ) -> dict:
        result = {}
        for ow in overwrites:
            target = None
            if ow.target_type == "role":
                target = discord.utils.get(self.guild.roles, name=ow.target_id_or_name)
                if not target and ow.target_id_or_name.lower() == "everyone":
                    target = self.guild.default_role
            elif ow.target_type == "member":
                target = self.guild.get_member_named(ow.target_id_or_name)
                if not target:
                    try:
                        target = self.guild.get_member(int(ow.target_id_or_name))
                    except ValueError:
                        pass

            if target:
                allow = discord.Permissions.none()
                deny = discord.Permissions.none()
                for p in ow.allow:
                    if hasattr(allow, p):
                        setattr(allow, p, True)
                for p in ow.deny:
                    if hasattr(deny, p):
                        setattr(deny, p, True)
                result[target] = discord.PermissionOverwrite.from_pair(allow, deny)
        return result

    # ── Categories ──────────────────────────────────────────────────────────

    async def create_category(
        self, name: str, position: Optional[int] = None
    ) -> discord.CategoryChannel:
        existing = self._category(name)
        if existing:
            raise ValueError(f"Category '{name}' already exists")
        return await self.guild.create_category(
            name=name, position=position, reason="Admin bot action"
        )

    async def delete_category(self, name: str) -> bool:
        cat = self._category(name)
        if not cat:
            raise ValueError(f"Category '{name}' not found")
        await cat.delete(reason="Admin bot action")
        return True

    async def rename_category(self, old: str, new: str) -> discord.CategoryChannel:
        cat = self._category(old)
        if not cat:
            raise ValueError(f"Category '{old}' not found")
        await cat.edit(name=new, reason="Admin bot action")
        return cat

    # ── Text Channels ───────────────────────────────────────────────────────

    async def create_text_channel(
        self,
        name: str,
        category: str,
        topic: str = "",
        slowmode: int = 0,
        nsfw: bool = False,
        permissions: Optional[List[PermissionOverwrite]] = None,
    ) -> discord.TextChannel:
        cat = self._category(category)
        if not cat:
            raise ValueError(f"Category '{category}' not found")
        if self._text_ch(name, cat):
            raise ValueError(f"Channel #{name} already exists in {category}")

        overwrites = self._build_overwrites(permissions) if permissions else None
        # discord.py 2.7+: pass overwrites only when we have them, otherwise omit
        # to avoid TypeError when overwrites=None hits the isinstance(overwrites, Mapping) check
        kwargs = {
            "name": name,
            "category": cat,
            "topic": topic,
            "slowmode_delay": slowmode,
            "nsfw": nsfw,
            "reason": "Admin bot action",
        }
        if overwrites:
            kwargs["overwrites"] = overwrites
        return await self.guild.create_text_channel(**kwargs)

    async def delete_text_channel(
        self, name: str, category: Optional[str] = None
    ) -> bool:
        cat = self._category(category) if category else None
        ch = self._text_ch(name, cat)
        if not ch:
            raise ValueError(f"Text channel #{name} not found")
        await ch.delete(reason="Admin bot action")
        return True

    async def rename_text_channel(
        self, old_name: str, new_name: str, category: Optional[str] = None
    ) -> discord.TextChannel:
        cat = self._category(category) if category else None
        ch = self._text_ch(old_name, cat)
        if not ch:
            raise ValueError(f"Text channel #{old_name} not found")
        await ch.edit(name=new_name, reason="Admin bot action")
        return ch

    async def set_channel_topic(
        self, name: str, category: str, topic: str
    ) -> discord.TextChannel:
        cat = self._category(category)
        if not cat:
            raise ValueError(f"Category '{category}' not found")
        ch = self._text_ch(name, cat)
        if not ch:
            raise ValueError(f"Channel #{name} not found in {category}")
        await ch.edit(topic=topic, reason="Admin bot action")
        return ch

    async def set_channel_permissions(
        self,
        name: str,
        category: str,
        overwrites: List[PermissionOverwrite],
    ) -> discord.TextChannel:
        cat = self._category(category)
        if not cat:
            raise ValueError(f"Category '{category}' not found")
        ch = self._text_ch(name, cat)
        if not ch:
            raise ValueError(f"Channel #{name} not found in {category}")

        for ow in overwrites:
            target = None
            if ow.target_type == "role":
                target = discord.utils.get(self.guild.roles, name=ow.target_id_or_name)
                if not target and ow.target_id_or_name.lower() == "everyone":
                    target = self.guild.default_role
            elif ow.target_type == "member":
                target = self.guild.get_member_named(ow.target_id_or_name)
                if not target:
                    try:
                        target = self.guild.get_member(int(ow.target_id_or_name))
                    except ValueError:
                        pass

            if target:
                allow = discord.Permissions.none()
                deny = discord.Permissions.none()
                for p in ow.allow:
                    if hasattr(allow, p):
                        setattr(allow, p, True)
                for p in ow.deny:
                    if hasattr(deny, p):
                        setattr(deny, p, True)
                await ch.set_permissions(
                    target,
                    overwrite=discord.PermissionOverwrite.from_pair(allow, deny),
                    reason="Admin bot action",
                )
        return ch

    # ── Voice Channels ──────────────────────────────────────────────────────

    async def create_voice_channel(
        self,
        name: str,
        category: str,
        bitrate: int = 64000,
        user_limit: int = 0,
        video_quality_mode: str = "auto",
        permissions: Optional[List[PermissionOverwrite]] = None,
    ) -> discord.VoiceChannel:
        cat = self._category(category)
        if not cat:
            raise ValueError(f"Category '{category}' not found")
        if self._voice_ch(name, cat):
            raise ValueError(f"Voice channel '{name}' already exists in {category}")

        overwrites = self._build_overwrites(permissions) if permissions else None
        # discord.py 2.7+: pass overwrites only when we have them, otherwise omit
        vq = (
            discord.VideoQualityMode.full
            if video_quality_mode == "full"
            else discord.VideoQualityMode.auto
        )

        kwargs = {
            "name": name,
            "category": cat,
            "bitrate": bitrate,
            "user_limit": user_limit,
            "video_quality_mode": vq,
            "reason": "Admin bot action",
        }
        if overwrites:
            kwargs["overwrites"] = overwrites
        return await self.guild.create_voice_channel(**kwargs)

    async def delete_voice_channel(
        self, name: str, category: Optional[str] = None
    ) -> bool:
        cat = self._category(category) if category else None
        ch = self._voice_ch(name, cat)
        if not ch:
            raise ValueError(f"Voice channel '{name}' not found")
        await ch.delete(reason="Admin bot action")
        return True

    # ── Forum Channels ──────────────────────────────────────────────────────

    async def create_forum_channel(
        self,
        name: str,
        category: str,
        topic: str = "",
        default_reaction_emoji: str = "📝",
        available_tags: Optional[List[str]] = None,
        default_layout: str = "list_view",
    ) -> discord.ForumChannel:
        cat = self._category(category)
        if not cat:
            raise ValueError(f"Category '{category}' not found")
        if self._forum_ch(name, cat):
            raise ValueError(f"Forum '{name}' already exists in {category}")

        tags = []
        if available_tags:
            tags = [discord.ForumTag(name=t, moderated=False) for t in available_tags]

        layout = (
            discord.ForumLayoutType.list_view
            if default_layout == "list_view"
            else discord.ForumLayoutType.gallery_view
        )

        return await self.guild.create_forum(
            name=name,
            category=cat,
            topic=topic,
            default_reaction_emoji=default_reaction_emoji,
            available_tags=tags or None,
            default_layout=layout,
            reason="Admin bot action",
        )

    async def delete_forum_channel(
        self, name: str, category: Optional[str] = None
    ) -> bool:
        cat = self._category(category) if category else None
        ch = self._forum_ch(name, cat)
        if not ch:
            raise ValueError(f"Forum '{name}' not found")
        await ch.delete(reason="Admin bot action")
        return True

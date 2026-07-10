"""
AdminBot — the main Discord bot that listens for natural language commands,
delegates planning to Hermes (or local LLM), and executes actions with
confirmation gates and safety checks.
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

from .executor import ActionExecutor
from .llm_client import HermesPlannerClient, LocalLLMClient
from .models import Config
from .utils import chunk_text, load_config

logger = logging.getLogger(__name__)


# ── Confirmation UI ──────────────────────────────────────────────────────────

class ConfirmView(View):
    """Buttons shown to users before destructive actions execute."""

    def __init__(self, actions, executor, author, dry_run=False) -> None:
        super().__init__(timeout=60)
        self.actions = actions
        self.executor = executor
        self.author = author
        self.dry_run = dry_run
        self.confirmed = False
        self.cancelled = False

    @discord.ui.button(label="✅ Execute", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _button: Button) -> None:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the command author can confirm.", ephemeral=True
            )
            return
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(content="🔄 Executing...", view=None)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _button: Button) -> None:
        if interaction.user != self.author:
            await interaction.response.send_message(
                "Only the command author can cancel.", ephemeral=True
            )
            return
        self.cancelled = True
        self.stop()
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)


# ── Main Bot ─────────────────────────────────────────────────────────────────

class AdminBot(commands.Bot):
    """Discord bot that interprets natural language as server administration."""

    def __init__(self) -> None:
        self.config: Config = load_config()

        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        intents.messages = True
        intents.message_content = True

        super().__init__(
            command_prefix=self.config.bot.prefix,
            intents=intents,
            help_command=None,
        )

        self.hermes_client = HermesPlannerClient(self.config)
        self.local_client = LocalLLMClient(self.config)

        self.guild_id = int(os.getenv("GUILD_ID", "0"))
        self.admin_ids = [
            int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
        ]
        self.command_channels = [
            int(x)
            for x in os.getenv("COMMAND_CHANNEL_IDS", "").split(",")
            if x.strip()
        ]

        self.user_context = {
            "user_id": os.getenv("HERMES_USER_ID", "unknown"),
            "module": os.getenv("HERMES_MODULE", ""),
            "exam_date": os.getenv("HERMES_EXAM_DATE", ""),
            "study_hours": int(os.getenv("HERMES_STUDY_HOURS", "14")),
            "timezone": os.getenv("HERMES_TIMEZONE", "UTC"),
        }

    # ── Auth ────────────────────────────────────────────────────────────────

    def is_authorized(
        self, user: discord.User, channel: discord.abc.Messageable | None = None
    ) -> bool:
        if user.id not in self.admin_ids:
            return False
        if self.command_channels and hasattr(channel, "id"):
            return channel.id in self.command_channels
        return True

    # ── Guild Snapshot ──────────────────────────────────────────────────────

    @staticmethod
    def get_guild_context(guild: discord.Guild) -> str:
        """Build a text snapshot of the server for the planner."""
        lines = [
            f"Server: {guild.name} ({guild.id})",
            f"Members: {guild.member_count}",
            "",
            "Categories & Channels:",
        ]

        for cat in guild.categories:
            lines.append(f"  📁 {cat.name}")
            for ch in cat.text_channels:
                lines.append(f"    # {ch.name}")
            for vc in cat.voice_channels:
                lines.append(f"    🔊 {vc.name}")
            for ch in cat.channels:
                if isinstance(ch, discord.ForumChannel):
                    lines.append(f"    📋 {ch.name} (forum)")

        for ch in guild.text_channels:
            if not ch.category:
                lines.append(f"  # {ch.name} (no cat)")
        for vc in guild.voice_channels:
            if not vc.category:
                lines.append(f"  🔊 {vc.name} (no cat)")

        lines.append("\nRoles (top→bottom):")
        for role in sorted(guild.roles, key=lambda r: r.position, reverse=True):
            if not role.is_default() and not role.managed:
                perms = [p[0] for p in role.permissions if p[1]]
                lines.append(
                    f"  @{role.name} (pos={role.position}, "
                    f"color=#{role.color.value:06x}, perms={len(perms)})"
                )

        return "\n".join(lines)

    # ── Lifecycle ───────────────────────────────────────────────────────────

    async def on_ready(self) -> None:
            logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
            await self.change_presence(
                activity=discord.Game(name=self.config.bot.status)
            )
            try:
                # Register slash command
                @self.tree.command(
                    name="admin",
                    description="Execute a natural-language admin command for this server.",
                )
                @app_commands.describe(prompt='e.g. "Create a study category with schedule and help channels"')
                async def admin_slash(interaction: discord.Interaction, prompt: str) -> None:
                    await interaction.response.defer(ephemeral=True)

                    admin_ids = [
                        int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
                    ]
                    if interaction.user.id not in admin_ids:
                        await interaction.followup.send("❌ Not authorized.")
                        return

                    await interaction.followup.send(
                        "Slash command handler — use `!command` prefix for now."
                    )

                synced = await self.tree.sync()
                logger.info("Synced %d slash command(s)", len(synced))
            except Exception as exc:
                logger.error("Slash command sync failed: %s", exc)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not self.is_authorized(message.author, message.channel):
            return

        content = message.content.strip()

        # Must start with prefix or mention the bot
        if not (
            content.startswith(self.config.bot.prefix)
            or self.user.mentioned_in(message)
        ):
            return

        if content.startswith(self.config.bot.prefix):
            prompt = content[len(self.config.bot.prefix) :].strip()
        else:
            prompt = (
                content.replace(f"<@{self.user.id}>", "")
                .replace(f"<@!{self.user.id}>", "")
                .strip()
            )

        if not prompt:
            return
        await self._process(message, prompt)

    # ── Core Command Pipeline ───────────────────────────────────────────────

    async def _process(self, source: discord.Message, prompt: str) -> None:
        guild = self.get_guild(self.guild_id)
        if not guild:
            await source.reply("❌ Target guild not found. Check `GUILD_ID`.")
            return

        async with source.channel.typing():
            try:
                context = self.get_guild_context(guild)

                # ── Plan ────────────────────────────────────────────────────
                plan = await self._plan(prompt, context)
                if plan is None:
                    return
                if plan.clarification_needed:
                    await source.reply(
                        f"🤔 {plan.explanation}\n\n**Question:** {plan.clarification_question}"
                    )
                    return
                if not plan.actions:
                    await source.reply("🤷 No actions generated. Try being more specific.")
                    return
                if len(plan.actions) > self.config.execution.max_actions_per_prompt:
                    await source.reply(
                        f"⚠️ Too many actions ({len(plan.actions)}). "
                        f"Max is {self.config.execution.max_actions_per_prompt}."
                    )
                    return

                # ── Dry-run preview ─────────────────────────────────────────
                executor = ActionExecutor(guild, self.config.safety)
                dry = await executor.execute(
                    plan.actions, confirm_destructive=False, dry_run=True
                )

                embed = discord.Embed(
                    title="🔍 Proposed Changes",
                    description=plan.explanation,
                    color=0x3498DB,
                )
                preview = "\n".join(dry["results"])
                if len(preview) > 1000:
                    preview = preview[:1000] + "\n… (truncated)"
                embed.add_field(name="Actions", value=preview or "—", inline=False)
                if dry["errors"]:
                    embed.add_field(
                        name="⚠️ Dry-run warnings",
                        value="\n".join(dry["errors"][:5]),
                        inline=False,
                    )

                # ── Confirmation gate ───────────────────────────────────────
                needs_confirm = any(
                    self.config.execution.confirm_destructive
                    and a.type.value in self.config.safety.require_confirmation_for
                    for a in plan.actions
                )

                if needs_confirm:
                    embed.set_footer(
                        text="⚠️ Destructive actions — confirmation required"
                    )
                    view = ConfirmView(plan.actions, executor, source.author)
                    msg = await source.reply(embed=embed, view=view)
                    await view.wait()
                    if view.cancelled or not view.confirmed:
                        if not view.cancelled:
                            await msg.edit(
                                content="⏱️ Timed out.", embed=None, view=None
                            )
                        return
                else:
                    exec_btn = Button(label="▶️ Execute", style=discord.ButtonStyle.success)
                    cancel_btn = Button(label="❌ Cancel", style=discord.ButtonStyle.danger)

                    async def _exec_cb(interaction: discord.Interaction) -> None:
                        if interaction.user != source.author:
                            await interaction.response.send_message(
                                "Only the command author can execute.", ephemeral=True
                            )
                            return
                        await interaction.response.edit_message(
                            content="🔄 Executing…", embed=None, view=None
                        )
                        res = await executor.execute(
                            plan.actions, confirm_destructive=False, dry_run=False
                        )
                        await self._send_results(interaction.followup, res)

                    async def _cancel_cb(interaction: discord.Interaction) -> None:
                        if interaction.user != source.author:
                            await interaction.response.send_message(
                                "Only the command author can cancel.", ephemeral=True
                            )
                            return
                        await interaction.response.edit_message(
                            content="❌ Cancelled.", embed=None, view=None
                        )

                    exec_btn.callback = _exec_cb
                    cancel_btn.callback = _cancel_cb

                    view = View(timeout=60)
                    view.add_item(exec_btn)
                    view.add_item(cancel_btn)
                    await source.reply(embed=embed, view=view)
                    return  # execution happens on button click

                # ── Execute (confirmation path) ─────────────────────────────
                result = await executor.execute(
                    plan.actions, confirm_destructive=False, dry_run=False
                )
                await self._send_results(source, result)

            except Exception:
                logger.exception("Command processing failed")
                await source.reply(f"❌ Internal error — check logs.")

    async def _plan(self, prompt: str, context: str):
        """Try Hermes Planner first, fall back to local LLM."""
        try:
            plan = await self.hermes_client.plan(prompt, context, self.user_context)
            logger.info("Planned via Hermes Planner")
            return plan
        except Exception as exc:
            logger.warning("Hermes Planner failed, falling back to local: %s", exc)
            if self.config.hermes.fallback_to_local:
                return await self.local_client.parse_intent(prompt, context)
            raise

    async def _send_results(self, destination, result: dict) -> None:
        text = (
            result["summary"]
            + "\n\n"
            + "\n".join(result["results"] + result["errors"])
        )
        for chunk in chunk_text(text):
            if hasattr(destination, "send"):
                await destination.send(chunk)
            else:
                await destination.send(chunk)


# ── Slash Command ────────────────────────────────────────────────────────────

# Register slash command in on_ready instead (tree is instance-only)
async def admin_slash(interaction: discord.Interaction, prompt: str) -> None:
    await interaction.response.defer(ephemeral=True)

    admin_ids = [
        int(x) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
    ]
    if interaction.user.id not in admin_ids:
        await interaction.followup.send("❌ Not authorized.")
        return

    await interaction.followup.send(
        "Slash command handler — use `!command` prefix for now."
    )


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    import asyncio

    bot = AdminBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set in .env")

    try:
        asyncio.run(bot.start(token))
    except KeyboardInterrupt:
        asyncio.run(bot.close())

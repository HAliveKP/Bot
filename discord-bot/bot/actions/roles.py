"""
Role actions — create, delete, rename, assign permissions, and color roles.
"""

from typing import List, Optional

import discord

from ..models import SafetyConfig


class RoleActions:
    """Safe, idempotent role management with built-in protection checks."""

    def __init__(self, guild: discord.Guild, safety_config: SafetyConfig) -> None:
        self.guild = guild
        self.safety = safety_config

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _role(self, name: str) -> Optional[discord.Role]:
        return discord.utils.get(self.guild.roles, name=name)

    @staticmethod
    def _parse_permissions(perms: List[str]) -> discord.Permissions:
        p = discord.Permissions.none()
        for perm in perms:
            if hasattr(p, perm):
                setattr(p, perm, True)
        return p

    def _is_protected(self, role: discord.Role) -> bool:
        return (
            role.name in self.safety.protected_roles
            or role.managed
            or role.is_default()
        )

    # ── CRUD ────────────────────────────────────────────────────────────────

    async def create_role(
        self,
        name: str,
        color: str = "#99aab5",
        hoist: bool = False,
        mentionable: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> discord.Role:
        if self._role(name):
            raise ValueError(f"Role '{name}' already exists")
        perms = (
            self._parse_permissions(permissions)
            if permissions
            else discord.Permissions.none()
        )
        return await self.guild.create_role(
            name=name,
            color=discord.Color(parse_color(color)),
            hoist=hoist,
            mentionable=mentionable,
            permissions=perms,
            reason="Admin bot action",
        )

    async def delete_role(self, name: str) -> bool:
        role = self._role(name)
        if not role:
            raise ValueError(f"Role '{name}' not found")
        if self._is_protected(role):
            raise ValueError(f"Cannot delete protected role: {name}")
        await role.delete(reason="Admin bot action")
        return True

    async def rename_role(self, old_name: str, new_name: str) -> discord.Role:
        role = self._role(old_name)
        if not role:
            raise ValueError(f"Role '{old_name}' not found")
        if self._is_protected(role):
            raise ValueError(f"Cannot rename protected role: {old_name}")
        await role.edit(name=new_name, reason="Admin bot action")
        return role

    async def set_role_permissions(
        self, name: str, permissions: List[str]
    ) -> discord.Role:
        role = self._role(name)
        if not role:
            raise ValueError(f"Role '{name}' not found")
        if self._is_protected(role):
            raise ValueError(f"Cannot modify protected role: {name}")
        await role.edit(
            permissions=self._parse_permissions(permissions),
            reason="Admin bot action",
        )
        return role

    async def set_role_color(self, name: str, color: str) -> discord.Role:
        role = self._role(name)
        if not role:
            raise ValueError(f"Role '{name}' not found")
        return await role.edit(
            color=discord.Color(parse_color(color)), reason="Admin bot action"
        )

    async def assign_role(self, user: str, role: str) -> discord.Member:
        target_role = self._role(role)
        if not target_role:
            raise ValueError(f"Role '{role}' not found")

        member = self.guild.get_member_named(user)
        if not member:
            try:
                member = self.guild.get_member(int(user))
            except ValueError:
                raise ValueError(f"User '{user}' not found")

        if target_role in member.roles:
            raise ValueError(f"User already has role '{role}'")

        await member.add_roles(target_role, reason="Admin bot action")
        return member

    async def remove_role(self, user: str, role: str) -> discord.Member:
        target_role = self._role(role)
        if not target_role:
            raise ValueError(f"Role '{role}' not found")

        member = self.guild.get_member_named(user)
        if not member:
            try:
                member = self.guild.get_member(int(user))
            except ValueError:
                raise ValueError(f"User '{user}' not found")

        if target_role not in member.roles:
            raise ValueError(f"User doesn't have role '{role}'")

        await member.remove_roles(target_role, reason="Admin bot action")
        return member


def parse_color(color_str: str) -> int:
    """Parse a hex color string (#fff, #ffffff, 0xff0000) to an int."""
    clean = color_str.lstrip("#0x")
    return int(clean, 16)

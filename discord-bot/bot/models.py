"""
Pydantic models for the Discord Admin Bot.

Defines the data contracts between:
  - Discord Bot ↔ Hermes Planner (API)
  - Discord Bot ↔ Local LLM (fallback)
  - Action Executor ↔ Discord API
"""

from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field
from enum import Enum


# ─── Action Types ─────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    """Every action the bot can execute against Discord."""
    CREATE_CATEGORY = "create_category"
    DELETE_CATEGORY = "delete_category"
    RENAME_CATEGORY = "rename_category"
    CREATE_TEXT_CHANNEL = "create_text_channel"
    DELETE_TEXT_CHANNEL = "delete_text_channel"
    RENAME_TEXT_CHANNEL = "rename_text_channel"
    SET_CHANNEL_TOPIC = "set_channel_topic"
    SET_CHANNEL_PERMISSIONS = "set_channel_permissions"
    CREATE_VOICE_CHANNEL = "create_voice_channel"
    DELETE_VOICE_CHANNEL = "delete_voice_channel"
    CREATE_FORUM_CHANNEL = "create_forum_channel"
    DELETE_FORUM_CHANNEL = "delete_forum_channel"
    CREATE_ROLE = "create_role"
    DELETE_ROLE = "delete_role"
    RENAME_ROLE = "rename_role"
    SET_ROLE_PERMISSIONS = "set_role_permissions"
    SET_ROLE_COLOR = "set_role_color"
    ASSIGN_ROLE = "assign_role"
    REMOVE_ROLE = "remove_role"


# ─── Permissions ─────────────────────────────────────────────────────────────

class PermissionOverwrite(BaseModel):
    """Targeted permission overwrite for a role or member."""
    target_type: Literal["role", "member"]
    target_id_or_name: str
    allow: List[str] = Field(default_factory=list, description="Permissions to explicitly allow")
    deny: List[str] = Field(default_factory=list, description="Permissions to explicitly deny")


# ─── Actions ──────────────────────────────────────────────────────────────────

class Action(BaseModel):
    """A single Discord API action with typed params and human-readable reason."""
    type: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


# ─── LLM Response ────────────────────────────────────────────────────────────

class LLMResponse(BaseModel):
    """Structured response from the planner (Hermes or local fallback)."""
    actions: List[Action] = Field(max_length=50)
    explanation: str = ""
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


# ─── Configuration Models ─────────────────────────────────────────────────────

class BotConfig(BaseModel):
    prefix: str = "!"
    status: str = "🛠️ Hermes-linked admin"
    command_cooldown: int = 5


class LLMConfig(BaseModel):
    temperature: float = 0.1
    max_tokens: int = 4000
    timeout: int = 30


class ExecutionConfig(BaseModel):
    confirm_destructive: bool = True
    max_actions_per_prompt: int = 20
    dry_run_default: bool = False


class SafetyConfig(BaseModel):
    """Safety boundaries — actions outside these are blocked."""
    protected_roles: List[str] = ["👑 Owner", "🛡️ Admin"]
    protected_channels: List[str] = ["#rules-and-info", "#announcements"]
    require_confirmation_for: List[str] = [
        "delete_channel", "delete_category", "delete_role",
        "modify_permissions", "ban_member", "kick_member",
    ]


class HermesConfig(BaseModel):
    """Connection settings for the Hermes Planner API."""
    planner_url: str = "http://hermes-planner:8000"
    timeout: int = 30
    fallback_to_local: bool = True


class Config(BaseModel):
    """Top-level config assembled from config.yaml + environment overrides."""
    bot: BotConfig = BotConfig()
    llm: LLMConfig = LLMConfig()
    execution: ExecutionConfig = ExecutionConfig()
    safety: SafetyConfig = SafetyConfig()
    hermes: HermesConfig = HermesConfig()

"""
Pydantic models for the Hermes Planner microservice.

Defines the request/response contracts for the `/plan` endpoint
and the server-state persistence schema.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    """Every action the Discord bot can execute."""
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


class PermissionOverwrite(BaseModel):
    """Discord permission overwrite — allow/deny on a role or member."""
    target_type: str  # "role" | "member"
    target_id_or_name: str
    allow: List[str] = Field(default_factory=list)
    deny: List[str] = Field(default_factory=list)


class Action(BaseModel):
    """A single actionable step for the Discord bot."""
    type: ActionType
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""


class PlanRequest(BaseModel):
    """Inbound request from the Discord bot."""
    prompt: str
    guild_context: str
    user_context: Dict[str, Any]


class PlanResponse(BaseModel):
    """Structured plan returned to the Discord bot."""
    actions: List[Action] = Field(max_length=50)
    explanation: str = ""
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


class ServerState(BaseModel):
    """Persistent snapshot of a Discord server stored in Redis."""
    guild_id: str
    schema: Dict[str, Any] = Field(default_factory=dict)
    study_plan: Dict[str, Any] = Field(default_factory=dict)
    projects: Dict[str, Any] = Field(default_factory=dict)
    members: Dict[str, Any] = Field(default_factory=dict)
    decision_log: List[Dict[str, Any]] = Field(default_factory=list)

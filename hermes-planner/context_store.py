"""
Context Store — Redis-backed persistence for server state, study plans, projects,
and decision history. Survives container restarts.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import redis

from models import ServerState

logger = logging.getLogger(__name__)


class ContextStore:
    """Persistent context layer shared between Hermes Planner and Discord Bot."""

    def __init__(self) -> None:
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.client = redis.from_url(self.redis_url, decode_responses=True)
        self.ttl = 86_400 * 30  # 30 days

    # ── Key helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _key(guild_id: str, namespace: str) -> str:
        return f"hermes:{guild_id}:{namespace}"

    # ── Server State ────────────────────────────────────────────────────────

    def save_server_state(self, guild_id: str, state: ServerState) -> None:
        self.client.setex(self._key(guild_id, "state"), self.ttl, state.model_dump_json())

    def load_server_state(self, guild_id: str) -> Optional[ServerState]:
        data = self.client.get(self._key(guild_id, "state"))
        return ServerState.model_validate_json(data) if data else None

    # ── Schema Snapshot ─────────────────────────────────────────────────────

    def save_schema(self, guild_id: str, schema: Dict[str, Any]) -> None:
        self.client.setex(self._key(guild_id, "schema"), self.ttl, json.dumps(schema))

    def load_schema(self, guild_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.get(self._key(guild_id, "schema"))
        return json.loads(data) if data else None

    # ── Decision Log ────────────────────────────────────────────────────────

    def append_decision(self, guild_id: str, decision: Dict[str, Any]) -> None:
        key = self._key(guild_id, "decisions")
        self.client.lpush(key, json.dumps(decision))
        self.client.ltrim(key, 0, 999)
        self.client.expire(key, self.ttl)

    def get_recent_decisions(self, guild_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        items = self.client.lrange(self._key(guild_id, "decisions"), 0, limit - 1)
        return [json.loads(x) for x in items]

    # ── Study Plan ──────────────────────────────────────────────────────────

    def save_study_plan(self, guild_id: str, plan: Dict[str, Any]) -> None:
        self.client.setex(self._key(guild_id, "study_plan"), self.ttl, json.dumps(plan))

    def load_study_plan(self, guild_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.get(self._key(guild_id, "study_plan"))
        return json.loads(data) if data else None

    # ── Projects ────────────────────────────────────────────────────────────

    def save_projects(self, guild_id: str, projects: Dict[str, Any]) -> None:
        self.client.setex(self._key(guild_id, "projects"), self.ttl, json.dumps(projects))

    def load_projects(self, guild_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.get(self._key(guild_id, "projects"))
        return json.loads(data) if data else None

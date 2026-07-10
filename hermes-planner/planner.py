"""
Hermes Planner — the AI strategy engine that converts natural language requests
into structured, context-aware Discord administration plans.

It loads server state + decision history from Redis, enriches the prompt,
calls OpenRouter, and returns a batch of executable actions.
"""

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from context_store import ContextStore
from models import PlanRequest, PlanResponse

logger = logging.getLogger(__name__)


class HermesPlanner:
    """Strategic planner that generates Discord server actions."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv(
            "OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-free"
        )
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.system_prompt = self._load_system_prompt()
        self.context_store = ContextStore()

    @staticmethod
    def _load_system_prompt() -> str:
        path = os.path.join(
            os.path.dirname(__file__), "prompts", "planner_system.md"
        )
        with open(path, "r") as f:
            return f.read()

    async def create_plan(self, request: PlanRequest) -> PlanResponse:
        """Enrich context, call OpenRouter, store decision, return plan."""
        guild_id = request.user_context.get("guild_id", "unknown")

        # Load persistent knowledge
        stored_state = self.context_store.load_server_state(guild_id)
        recent_decisions = self.context_store.get_recent_decisions(guild_id, 5)
        study_plan = self.context_store.load_study_plan(guild_id)
        projects = self.context_store.load_projects(guild_id)

        enriched = self._build_enriched_context(
            request.guild_context,
            request.user_context,
            stored_state,
            recent_decisions,
            study_plan,
            projects,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"{enriched}\n\nUser request: {request.prompt}"},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/HAliveKP/Bot",
            "X-Title": "Hermes Planner",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]

        # Strip markdown fences
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Robust JSON parsing — try multiple repair strategies
        plan_data = None
        try:
            plan_data = json.loads(content)
        except json.JSONDecodeError:
            # Strategy 1: progressive truncation — find outermost { }
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                # Try progressively shorter content by moving end brace backward
                for cut in range(end, start, -1):
                    if content[cut] == "}":
                        try:
                            plan_data = json.loads(content[start:cut+1])
                            break
                        except json.JSONDecodeError:
                            continue
            # Strategy 2: if all repairs fail, raise a clear error
            if plan_data is None:
                raise json.JSONDecodeError(
                    f"Could not parse AI response as JSON even after repair. "
                    f"Content length={len(content)}. First 500 chars: {content[:500]}",
                    content, 0
                )

        plan_response = PlanResponse(**plan_data)

        # Persist decision for future context
        decision = {
            "prompt": request.prompt,
            "actions": [a.model_dump() for a in plan_response.actions],
            "explanation": plan_response.explanation,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.context_store.append_decision(guild_id, decision)

        return plan_response

    # ------------------------------------------------------------------
    # Context enrichment
    # ------------------------------------------------------------------

    @staticmethod
    def _build_enriched_context(
        guild_context: str,
        user_context: dict,
        stored_state,
        recent_decisions: List[dict],
        study_plan: Optional[dict],
        projects: Optional[dict],
    ) -> str:
        parts = [
            "=== CURRENT SERVER STATE ===",
            guild_context,
            "",
            "=== USER CONTEXT ===",
            f"Module: {user_context.get('module', 'N/A')}",
            f"Exam: {user_context.get('exam_date', 'N/A')}",
            f"Study hours/day: {user_context.get('study_hours', 'N/A')}",
            f"Timezone: {user_context.get('timezone', 'N/A')}",
        ]

        if study_plan:
            parts.append(f"\n=== ACTIVE STUDY PLAN ===\n{json.dumps(study_plan, indent=2)}")

        if projects:
            parts.append(f"\n=== ACTIVE PROJECTS ===\n{json.dumps(projects, indent=2)}")

        if recent_decisions:
            parts.append("\n=== RECENT DECISIONS (last 5) ===")
            for d in recent_decisions:
                parts.append(
                    f"- [{d.get('timestamp', '?')}] {d.get('prompt', '?')} → "
                    f"{d.get('explanation', '?')[:120]}"
                )

        return "\n".join(parts)

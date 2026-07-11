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

        # ── Repair truncated JSON ────────────────────────────────────────
        import re

        def _repair_json(text: str) -> dict:
            """Try to repair truncated JSON from an AI response.
            
            Handles: unterminated strings, unclosed braces/brackets,
            trailing commas, and progressive truncation.
            """
            # Try direct parse first
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

            start = text.find("{")
            if start < 0:
                raise json.JSONDecodeError("No JSON object found in response", text, 0)

            # Strategy 1: close unterminated strings + brace structure
            repaired = text
            in_string = False
            escape = False
            brace_depth = 0     # { }
            bracket_depth = 0   # [ ]
            for ch in repaired:
                if escape:
                    escape = False
                    continue
                if ch == "\\" and in_string:
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == "{":
                        brace_depth += 1
                    elif ch == "}":
                        brace_depth -= 1
                    elif ch == "[":
                        bracket_depth += 1
                    elif ch == "]":
                        bracket_depth -= 1

            if in_string:
                repaired += '"'
            if bracket_depth > 0:
                repaired += "]" * bracket_depth
            if brace_depth > 0:
                repaired += "}" * brace_depth

            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

            # Strategy 2: progressive truncation — try each '}' right-to-left
            end_positions = [
                i for i in range(len(repaired) - 1, start - 1, -1)
                if repaired[i] == "}"
            ]
            for end in end_positions:
                candidate = repaired[start:end+1]
                # Strip trailing comma (invalid JSON before closing)
                candidate = re.sub(r",\s*$", "", candidate)

                # Count unmatched braces in candidate and close them
                in_str = False
                esc = False
                ob, obr = 0, 0
                for ch in candidate:
                    if esc:
                        esc = False
                        continue
                    if ch == "\\" and in_str:
                        esc = True
                        continue
                    if ch == '"':
                        in_str = not in_str
                        continue
                    if not in_str:
                        if ch == "{":
                            ob += 1
                        elif ch == "}":
                            ob -= 1
                        elif ch == "[":
                            obr += 1
                        elif ch == "]":
                            obr -= 1
                if ob > 0:
                    candidate += "}" * ob
                if obr > 0:
                    candidate += "]" * obr

                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

            raise json.JSONDecodeError(
                f"Could not repair JSON. Length={len(repaired)}. "
                f"First 300: {repaired[:300]}",
                repaired, 0,
            )

        plan_data = _repair_json(content)

        # ── Cap actions to max allowed ───────────────────────────────────
        field_info = PlanResponse.model_fields["actions"]
        max_actions = getattr(field_info, "max_length", None)
        if max_actions and isinstance(plan_data, dict) and "actions" in plan_data:
            if len(plan_data["actions"]) > max_actions:
                plan_data["actions"] = plan_data["actions"][:max_actions]

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

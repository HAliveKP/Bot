"""
LLM clients — primary Hermes Planner (HTTP) + fallback local OpenRouter.
"""

import json
import logging
import re
import os

import httpx

from .models import Config, LLMResponse
from .utils import load_config

logger = logging.getLogger(__name__)


# ─── Hermes Planner Client (Primary) ──────────────────────────────────────────

class HermesPlannerClient:
    """Calls the Hermes Planner microservice over HTTP."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.base_url = config.hermes.planner_url.rstrip("/")
        self.timeout = config.hermes.timeout

    async def plan(
        self, prompt: str, guild_context: str, user_context: dict
    ) -> LLMResponse:
        """Send a planning request to the Hermes Planner API."""
        payload = {
            "prompt": prompt,
            "guild_context": guild_context,
            "user_context": user_context,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(f"{self.base_url}/plan", json=payload)
                resp.raise_for_status()
                return LLMResponse(**resp.json())
            except httpx.TimeoutException:
                logger.error("Hermes planner timed out after %ss", self.timeout)
                raise
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Hermes planner HTTP %s: %s",
                    exc.response.status_code,
                    exc.response.text,
                )
                raise
            except Exception:
                logger.exception("Hermes planner call failed")
                raise


# ─── Local LLM Client (Fallback) ─────────────────────────────────────────────

class LocalLLMClient:
    """Direct OpenRouter call when Hermes Planner is unavailable."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv(
            "OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-free"
        )
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
        path = os.path.join(prompts_dir, "system_prompt.md")
        with open(path, "r") as f:
            return f.read()

    async def parse_intent(self, user_prompt: str, guild_context: str) -> LLMResponse:
        """Parse a user command via OpenRouter directly."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Server context:\n{guild_context}\n\nUser request: {user_prompt}",
            },
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.llm.temperature,
            "max_tokens": 8000,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/HAliveKP/Bot",
            "X-Title": "Hermes Discord Admin Bot",
        }

        async with httpx.AsyncClient(timeout=self.config.llm.timeout) as client:
            resp = await client.post(self.base_url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # ── Repair truncated JSON ────────────────────────────────────────
        def _repair_json(text: str) -> dict:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

            start = text.find("{")
            if start < 0:
                raise json.JSONDecodeError("No JSON object", text, 0)

            # Strategy 1: close unterminated strings + brace structure
            repaired = text
            in_string = False
            escape = False
            brace_depth = 0
            bracket_depth = 0
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
                    if ch == "{": brace_depth += 1
                    elif ch == "}": brace_depth -= 1
                    elif ch == "[": bracket_depth += 1
                    elif ch == "]": bracket_depth -= 1

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

            # Strategy 2: progressive truncation with auto-close
            end_positions = [
                i for i in range(len(repaired) - 1, start - 1, -1)
                if repaired[i] == "}"
            ]
            for end in end_positions:
                candidate = repaired[start:end+1]
                candidate = re.sub(r",\s*$", "", candidate)

                in_str = False
                esc = False
                ob, obr = 0, 0
                for ch in candidate:
                    if esc: esc = False; continue
                    if ch == "\\" and in_str: esc = True; continue
                    if ch == '"': in_str = not in_str; continue
                    if not in_str:
                        if ch == "{": ob += 1
                        elif ch == "}": ob -= 1
                        elif ch == "[": obr += 1
                        elif ch == "]": obr -= 1
                if ob > 0: candidate += "}" * ob
                if obr > 0: candidate += "]" * obr

                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue

            raise json.JSONDecodeError("Could not repair JSON", text, 0)

        parsed = _repair_json(content)

        # ── Cap actions to max allowed ───────────────────────────────────
        field_info = LLMResponse.model_fields["actions"]
        max_len = getattr(field_info, "max_length", None)
        if max_len and isinstance(parsed, dict) and "actions" in parsed:
            if len(parsed["actions"]) > max_len:
                parsed["actions"] = parsed["actions"][:max_len]

        return LLMResponse(**parsed)

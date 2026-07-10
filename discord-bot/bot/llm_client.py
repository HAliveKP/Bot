"""
LLM clients — primary Hermes Planner (HTTP) + fallback local OpenRouter.
"""

import json
import logging
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

        # Robust JSON parsing — progressive truncation repair
        parsed = None
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                for cut in range(end, start, -1):
                    if content[cut] == "}":
                        try:
                            parsed = json.loads(content[start:cut+1])
                            break
                        except json.JSONDecodeError:
                            continue
            if parsed is None:
                logger.error("Failed to parse LLM response as JSON. Length=%d", len(content))
                raise

        return LLMResponse(**parsed)

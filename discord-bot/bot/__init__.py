"""
Discord Hermes Admin Bot — Package root.

A natural-language Discord server administration bot powered by
Hermes Planner (LLM strategist) + Discord API executor.
"""

from .core import AdminBot
from .models import Config, Action, LLMResponse, SafetyConfig
from .llm_client import HermesPlannerClient, LocalLLMClient
from .executor import ActionExecutor

__all__ = [
    "AdminBot", "Config", "Action", "LLMResponse", "SafetyConfig",
    "HermesPlannerClient", "LocalLLMClient", "ActionExecutor",
]

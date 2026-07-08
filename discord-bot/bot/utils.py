"""
Utility helpers — config loading, color parsing, message chunking.
"""

import os
from pathlib import Path

import yaml

from .models import Config


def load_config(path: str = "config.yaml") -> Config:
    """Load `config.yaml` and overlay environment overrides."""
    p = Path(path)
    if not p.exists():
        return Config()

    with p.open("r") as f:
        data = yaml.safe_load(f) or {}

    # Allow env-var override of planner URL (Docker Compose injects this)
    if "HERMES_PLANNER_URL" in os.environ:
        data.setdefault("hermes", {})["planner_url"] = os.environ["HERMES_PLANNER_URL"]

    return Config(**data)


def parse_color(color_str: str) -> int:
    """Parse a hex color string into an integer Discord can use."""
    clean = color_str.lstrip("#0x")
    return int(clean, 16)


def chunk_text(text: str, limit: int = 1900) -> list[str]:
    """Split a long string into Discord-message-safe chunks (~1900 chars)."""
    if len(text) <= limit:
        return [text]
    return [text[i : i + limit] for i in range(0, len(text), limit)]

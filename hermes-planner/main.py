"""
FastAPI application entry point — Hermes Planner microservice.

Endpoints:
  GET  /health   — health check
  POST /plan     — generate a context-aware server administration plan
"""

import logging
import os
import re

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)

from models import PlanRequest, PlanResponse
from planner import HermesPlanner

app = FastAPI(
    title="Hermes Planner",
    description="AI-powered Discord server administration planning engine.",
    version="1.0.0",
)

planner = HermesPlanner()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "hermes-planner", "version": "1.0.0"}


# ── Plan ─────────────────────────────────────────────────────────────────────

@app.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest):
    """Plan a set of Discord administration actions from a natural language prompt."""
    try:
        # Extract guild_id from guild_context if not provided in user_context
        if "guild_id" not in request.user_context:
            match = re.search(r"\((\d+)\)", request.guild_context)
            if match:
                request.user_context["guild_id"] = match.group(1)

        response = await planner.create_plan(request)
        return response

    except httpx.HTTPStatusError as exc:
        logger.error("OpenRouter HTTP %s: %s", exc.response.status_code, exc.response.text)
        raise HTTPException(
            status_code=502,
            detail=f"LLM API error (HTTP {exc.response.status_code})",
        )

    except httpx.TimeoutException:
        logger.error("OpenRouter request timed out")
        raise HTTPException(status_code=504, detail="LLM API timed out")

    except Exception:
        logger.exception("Unhandled planner error")
        raise HTTPException(status_code=500, detail="Internal planner error")


# ── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("LOG_LEVEL", "").upper() == "DEBUG",
    )

"""
main.py — Talent-Audit-Env
FastAPI application serving the OpenEnv HTTP interface.

Endpoints
---------
GET  /health                      → liveness check
GET  /manifest                    → openenv.yaml as JSON
POST /reset?task_id=<id>          → start episode, returns Observation
POST /step                        → apply action, returns StepResponse
GET  /state                       → current environment state
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from env import TalentAuditEnv
from models import Action, Observation, Reward
from tasks import list_tasks

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Talent-Audit-Env",
    description="OpenEnv-compliant HR Data Compliance environment.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single global env instance (stateless per-request design is overkill here)
_env = TalentAuditEnv()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class StepResponse(BaseModel):
    observation: Dict[str, Any]
    reward:      Dict[str, Any]
    done:        bool
    info:        Dict[str, Any]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> Dict[str, str]:
    return {"status": "ok", "env": TalentAuditEnv.ENV_NAME, "version": TalentAuditEnv.ENV_VERSION}


@app.get("/manifest", tags=["meta"])
def manifest() -> Dict[str, Any]:
    manifest_path = Path(__file__).parent / "openenv.yaml"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="openenv.yaml not found.")
    with manifest_path.open() as f:
        return yaml.safe_load(f)


@app.get("/tasks", tags=["meta"])
def tasks() -> Dict[str, Any]:
    return {"tasks": list_tasks()}


@app.post("/reset", tags=["env"], response_model=Dict[str, Any])
def reset(task_id: str = Query("pii_easy", description="Task ID to initialise.")) -> Dict[str, Any]:
    try:
        obs: Observation = _env.reset(task_id)
        return obs.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/step", tags=["env"], response_model=StepResponse)
def step(action: Action) -> StepResponse:
    try:
        obs, reward, done, info = _env.step(action)
        return StepResponse(
            observation=obs.model_dump(),
            reward=reward.model_dump(),
            done=done,
            info=info,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/state", tags=["env"])
def state() -> Dict[str, Any]:
    return _env.state()

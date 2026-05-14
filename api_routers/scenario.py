"""Scenario / target optimizer read API (Queue 28d)."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from scenario_optimizer import build_scenario_suggestions

router = APIRouter(prefix="/api/scenario", tags=["scenario"])


def _scenario_enabled() -> bool:
    return os.getenv("SCENARIO_OPTIMIZER_ENABLED", "0").lower() in ("1", "true", "yes")


@router.get("/suggestions")
def get_scenario_suggestions() -> dict:
    """Return deterministic scenario presets + target hints from paper rows + portfolio."""
    if not _scenario_enabled():
        raise HTTPException(
            status_code=404,
            detail="Scenario optimizer disabled; set SCENARIO_OPTIMIZER_ENABLED=1",
        )
    return build_scenario_suggestions()

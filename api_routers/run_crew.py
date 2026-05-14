"""HTTP trigger and status polling for daily crew runs."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/run-crew", tags=["run-crew"])

_REPO_ROOT = Path(__file__).resolve().parents[1]
_crew_run_lock = asyncio.Lock()
_crew_run_state: dict[str, Any] = {
    "status": "idle",
    "job_id": None,
    "started_at": None,
    "finished_at": None,
    "error": None,
}


def _crew_run_auth_ok(request: Request) -> bool:
    key = os.getenv("CREW_HTTP_API_KEY", "").strip()
    if not key:
        return True
    sent = request.headers.get("X-Crew-Api-Key", "").strip()
    return sent == key


def _parse_iso_utc(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _crew_status_stale_after_seconds() -> int:
    raw = os.getenv("CREW_STATUS_STALE_SEC", "1800")
    try:
        return max(60, int(float(raw)))
    except (TypeError, ValueError):
        return 1800


def _status_with_observability() -> dict[str, Any]:
    state = dict(_crew_run_state)
    stale_after = _crew_status_stale_after_seconds()
    anchor = _parse_iso_utc(state.get("started_at")) or _parse_iso_utc(state.get("finished_at"))
    age_seconds = 0
    if anchor is not None:
        age_seconds = max(0, int((datetime.now(timezone.utc) - anchor).total_seconds()))
    state["age_seconds"] = age_seconds
    state["stale_after_seconds"] = stale_after
    state["is_stale"] = state.get("status") == "running" and age_seconds > stale_after
    return state


async def _run_crew_background(job_id: str) -> None:
    """Background coroutine: run main pipeline and update state when done."""
    import subprocess  # noqa: PLC0415 - lazy import for optional feature

    _crew_run_state.update({"status": "running", "job_id": job_id, "error": None})
    try:
        # Run main.py as a subprocess so it inherits the full environment (API keys, BQ creds)
        # and does not block the FastAPI event loop.
        result = await asyncio.create_subprocess_exec(
            "python",
            str(_REPO_ROOT / "main.py"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(_REPO_ROOT),
        )
        _, _ = await result.communicate()
        if result.returncode == 0:
            _crew_run_state.update({"status": "done", "error": None})
        else:
            _crew_run_state.update({"status": "error", "error": f"exit code {result.returncode}"})
    except Exception as exc:  # noqa: BLE001
        logger.error("crew run %s failed: %s", job_id, exc)
        _crew_run_state.update({"status": "error", "error": str(exc)})
    finally:
        _crew_run_state["finished_at"] = datetime.now(timezone.utc).isoformat()
        _crew_run_lock.release()


@router.post("")
async def post_run_crew(request: Request) -> dict[str, Any]:
    """Trigger the daily research pipeline (Q29). Disabled unless ``CREW_HTTP_ENABLED=1``."""
    if os.getenv("CREW_HTTP_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Crew HTTP trigger disabled; set CREW_HTTP_ENABLED=1")
    if not _crew_run_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing crew API key")
    if _crew_run_lock.locked():
        return {
            "ok": False,
            "status": "running",
            "job_id": _crew_run_state.get("job_id"),
            "message": "Crew run already in progress",
        }
    await _crew_run_lock.acquire()
    job_id = uuid.uuid4().hex[:12]
    _crew_run_state["started_at"] = datetime.now(timezone.utc).isoformat()
    _crew_run_state["finished_at"] = None
    asyncio.create_task(_run_crew_background(job_id))
    return {"ok": True, "status": "started", "job_id": job_id}


@router.get("/status")
async def get_run_crew_status() -> dict[str, Any]:
    """Poll crew run state (Q29). Always available regardless of ``CREW_HTTP_ENABLED``."""
    return _status_with_observability()

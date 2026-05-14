"""Execution intent APIs and gate-hint read models."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

import bigquery_writer
from execution_intents import (
    ALLOWED_INTENT_STATUSES,
    CLIENT_PATCHABLE_STATUSES,
    append_execution_intent_row,
    latest_execution_intents,
    update_execution_intent_status,
)
from signal_quality import enrich_signal_quality

router = APIRouter(prefix="/api/execution-intents", tags=["execution-intents"])


class ExecutionIntentStatusBody(BaseModel):
    """Human / War Room workflow: advance intent lifecycle (no order placement)."""

    status: str = Field(..., description="One of CLIENT_PATCHABLE_STATUSES (case-insensitive).")
    note: str = Field(default="", max_length=2000)
    reference_entry_price: float | None = None
    reference_target_price: float | None = None
    reference_stop_price: float | None = None


class ExecutionIntentCreateBody(BaseModel):
    """Manual signal intake for paper lifecycle review. Does **not** place orders."""

    category: str = Field(default="AI", max_length=40)
    regime: str = Field(default="", max_length=120)
    asset: str = Field(..., min_length=1, max_length=24)
    direction: str = Field(..., description="LONG or SHORT")
    star_rating: int = Field(default=1, ge=1, le=2)
    thesis_one_liner: str = Field(default="", max_length=500)
    reference_entry_price: float | None = None
    reference_target_price: float | None = None
    reference_stop_price: float | None = None

    @field_validator("asset")
    @classmethod
    def normalize_asset(cls, value: str) -> str:
        normalized = str(value or "").strip().upper().lstrip("$")
        if not normalized:
            raise ValueError("asset is required")
        if not re.fullmatch(r"[A-Z0-9.\-]{1,24}", normalized):
            raise ValueError("asset must be an uppercase ticker-like symbol")
        return normalized

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in {"LONG", "SHORT"}:
            raise ValueError("direction must be LONG or SHORT")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = str(value or "AI").strip().upper()
        return normalized or "AI"


class ExecutionIntentRow(BaseModel):
    signal_id: str
    created_at: str
    category: str
    regime: str = ""
    asset: str
    direction: str
    star_rating: int
    thesis_one_liner: str = ""
    status: str
    status_updated_at: str = ""
    status_note: str = ""
    reference_entry_price: float | None = None
    reference_target_price: float | None = None
    reference_stop_price: float | None = None
    paper_fill_price: float | None = None
    paper_exit_price: float | None = None
    gate_issue_hints: list[str] = Field(default_factory=list)
    quality_score: int | None = None
    quality_grade: str | None = None
    quality_reasons: list[str] = Field(default_factory=list)
    quality_model: str | None = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return json.loads(raw) if raw else None
    except (OSError, json.JSONDecodeError):
        return None


def _latest_gate_failure_summary() -> dict[str, Any] | None:
    out_dir = _repo_root() / ".qsilicon" / "last_gate_failure"
    summary = _read_json_if_exists(out_dir / "validation_summary.json")
    if summary is None:
        return None
    issues_path = out_dir / "issues.txt"
    return {
        **summary,
        "issues_path": str(issues_path) if issues_path.is_file() else None,
        "artifact_dir": str(out_dir),
    }


def _gate_line_matches_intent(line: str, asset_u: str, signal_id: str) -> bool:
    """Avoid substring false positives (e.g. ``ASSET`` inside ``PASSSETS``) where possible."""
    if not asset_u:
        return False
    lu = line.upper()
    if len(asset_u) >= 2:
        try:
            if re.search(rf"\b{re.escape(asset_u)}\b", lu):
                return True
        except re.error:
            pass
    sid = (signal_id or "").upper()
    parts = {p for p in re.split(r"[^A-Z0-9]+", sid) if len(p) >= 2}
    if asset_u in parts and asset_u in lu:
        return True
    return asset_u in lu


def _enrich_intents_with_gate_hints(
    intents: list[dict[str, Any]],
    gate_failure: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Read-only cross-hints (T5b): match gate issue lines to ``asset`` / ``signal_id`` segments."""
    issues_raw = (gate_failure or {}).get("issues") if isinstance(gate_failure, dict) else None
    if not intents or not isinstance(issues_raw, list) or not issues_raw:
        return intents
    issues = [str(x).strip() for x in issues_raw if str(x).strip()]
    if not issues:
        return intents
    out: list[dict[str, Any]] = []
    for row in intents:
        asset = str(row.get("asset") or "").strip().upper()
        sid = str(row.get("signal_id") or "").strip()
        if not asset:
            out.append(row)
            continue
        matched = [line for line in issues if _gate_line_matches_intent(line, asset, sid)]
        if not matched:
            out.append(row)
            continue
        merged = {**row, "gate_issue_hints": matched[:8]}
        out.append(merged)
    return out


@router.get("/gate-index")
def get_gate_intent_readonly_index(
    limit: int = Query(default=200, ge=1, le=200),
) -> dict[str, Any]:
    """T5b read-only index: last gate-failure issue lines × latest intents (hint matches only)."""
    gate = _latest_gate_failure_summary()
    rows = latest_execution_intents(
        limit=limit,
        dedupe=True,
        sort_by="updated_desc",
    )
    hinted = _enrich_intents_with_gate_hints(rows, gate)
    matches: list[dict[str, Any]] = []
    for r in hinted:
        hints = r.get("gate_issue_hints")
        if isinstance(hints, list) and hints:
            matches.append(
                {
                    "signal_id": r.get("signal_id"),
                    "asset": r.get("asset"),
                    "status": r.get("status"),
                    "hint_count": len(hints),
                    "gate_issue_hints": hints,
                }
            )
    preview: list[str] = []
    issue_total: int | None = None
    if isinstance(gate, dict):
        raw_issues = gate.get("issues")
        if isinstance(raw_issues, list):
            preview = [str(x).strip() for x in raw_issues if str(x).strip()][:12]
        ic = gate.get("issue_count")
        if ic is not None:
            try:
                issue_total = int(ic)
            except (TypeError, ValueError):
                issue_total = None
    return {
        "schema_version": "qsi_gate_intent_index_v1",
        "readme": (
            "Read-only hygiene crosswalk (gate issues × intent assets). "
            "Not OMS; does not assert fills or prices."
        ),
        "gate_artifact_present": bool(gate),
        "gate_issue_preview": preview,
        "gate_issue_count": issue_total if issue_total is not None else len(preview),
        "intent_scanned": len(hinted),
        "intent_rows_with_hints": len(matches),
        "matches": matches[:80],
    }


@router.get("", response_model=list[ExecutionIntentRow])
def list_execution_intents(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(
        default=None,
        description="Optional case-insensitive substring filter on intent status (e.g. PAPER).",
    ),
    category: str | None = Query(
        default=None,
        description="Optional prefix filter: CRYPTO or AI (case-insensitive).",
    ),
    sort_by: str = Query(
        default="updated_desc",
        description="Sort: updated_desc (default), created_desc, asset_asc.",
    ),
) -> list[dict[str, Any]]:
    """Latest execution intent per ``signal_id`` (append-only JSONL collapsed for Terminal blotter)."""
    sort_key = (sort_by or "updated_desc").strip().lower()
    if sort_key not in {"updated_desc", "created_desc", "asset_asc"}:
        raise HTTPException(
            status_code=400,
            detail="sort_by must be one of: updated_desc, created_desc, asset_asc",
        )
    rows = latest_execution_intents(
        limit=limit,
        dedupe=True,
        status=status,
        category=category,
        sort_by=sort_key,
    )
    gate = _latest_gate_failure_summary()
    hinted = _enrich_intents_with_gate_hints(rows, gate)
    return [enrich_signal_quality(row) for row in hinted]


@router.get("/allowed-statuses")
def execution_intent_allowed_statuses() -> dict[str, Any]:
    return {
        "statuses": sorted(ALLOWED_INTENT_STATUSES),
        "client_patchable": sorted(CLIENT_PATCHABLE_STATUSES),
    }


@router.post("", response_model=ExecutionIntentRow)
def create_execution_intent(body: ExecutionIntentCreateBody) -> dict[str, Any]:
    """Create one manual paper-review intent. Append-only; no broker/order side effects."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    signal_id = f"manual-{body.asset.lower()}-{body.direction.lower()}-{uuid.uuid4().hex[:8]}"
    row = {
        "signal_id": signal_id,
        "created_at": now,
        "category": body.category,
        "regime": body.regime.strip(),
        "asset": body.asset,
        "direction": body.direction,
        "star_rating": body.star_rating,
        "thesis_one_liner": body.thesis_one_liner.strip(),
        "status": "PENDING_REVIEW",
        "status_updated_at": now,
        "status_note": "",
        "reference_entry_price": body.reference_entry_price,
        "reference_target_price": body.reference_target_price,
        "reference_stop_price": body.reference_stop_price,
        "paper_fill_price": None,
        "paper_exit_price": None,
    }
    if not append_execution_intent_row(row):
        raise HTTPException(status_code=500, detail="Could not append execution intent")
    return row


@router.patch("/{signal_id}", response_model=ExecutionIntentRow)
def patch_execution_intent_status(
    signal_id: str,
    body: ExecutionIntentStatusBody,
) -> dict[str, Any]:
    """Append-only status transition (review / paper handoff). Does **not** send orders."""
    out = update_execution_intent_status(
        signal_id,
        body.status,
        note=body.note,
        reference_entry_price=body.reference_entry_price,
        reference_target_price=body.reference_target_price,
        reference_stop_price=body.reference_stop_price,
    )
    if out is None:
        raise HTTPException(
            status_code=404,
            detail="signal_id not found, invalid status, or malformed prior row",
        )
    updated, prev_for_audit = out
    if prev_for_audit is not None:
        note_s = (body.note or "").strip()
        reason = note_s[:240] if note_s else f"patch:{prev_for_audit}->{updated.get('status')}"
        bigquery_writer.write_paper_execution_audit_row(
            signal_id=str(updated.get("signal_id") or signal_id),
            new_status=str(updated.get("status") or ""),
            reason=reason,
            quote_as_of="",
            asset=str(updated.get("asset") or ""),
            direction=str(updated.get("direction") or ""),
            source="http_patch",
            prev_status=prev_for_audit,
        )
    return updated

"""Read-only Track Record API for paper recommendation outcomes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from track_record import build_track_record_payload, filter_records_by_tag, load_track_record_records

router = APIRouter(prefix="/api/track-record", tags=["track-record"])


@router.get("/summary")
def get_track_record_summary(limit: int = Query(default=500, ge=1, le=2000)) -> dict[str, Any]:
    records, source = load_track_record_records(limit=limit)
    payload = build_track_record_payload(records, source=source)
    return {
        **payload["summary"],
        "source": payload["source"],
        "source_row_count": payload["total"],
    }


@router.get("/closed")
def get_track_record_closed(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    records, source = load_track_record_records(limit=max(limit + offset, 500))
    return build_track_record_payload(records, limit=limit, offset=offset, source=source)


@router.get("/by-tag")
def get_track_record_by_tag(
    tag: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    all_records, source = load_track_record_records(limit=1000)
    records = filter_records_by_tag(all_records, tag)
    payload = build_track_record_payload(records, limit=limit, offset=offset, source=source)
    return {**payload, "tag": tag.strip().upper()}

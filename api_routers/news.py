"""Firestore-backed Tech Pulse news API."""

from __future__ import annotations

import os
import re
from collections import Counter
from datetime import date as date_type
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/news", tags=["news"])

DEFAULT_COLLECTION = "tech_pulse_memory_items"
_firestore_client: Any | None = None


def _collection_name() -> str:
    configured = (os.getenv("TECH_PULSE_FIRESTORE_COLLECTION") or DEFAULT_COLLECTION).strip()
    return configured or DEFAULT_COLLECTION


def _get_firestore_client() -> Any:
    """Lazy import so local tests and API startup do not require Firestore credentials."""
    global _firestore_client
    if _firestore_client is None:
        try:
            from google.cloud import firestore
        except ImportError as exc:
            raise RuntimeError("google-cloud-firestore is not installed") from exc
        project = (os.getenv("TECH_PULSE_FIRESTORE_PROJECT") or "").strip() or None
        _firestore_client = firestore.Client(project=project) if project else firestore.Client()
    return _firestore_client


def _collection() -> Any:
    return _get_firestore_client().collection(_collection_name())


def _to_dict(doc: Any) -> tuple[str, dict[str, Any]]:
    data = doc.to_dict() if hasattr(doc, "to_dict") else dict(doc)
    doc_id = str(getattr(doc, "id", data.get("id") or data.get("item_id") or "")).strip()
    return doc_id, data


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _as_iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, date_type):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    text = str(value).strip()
    return text


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = re.split(r"[,/|]", str(value))
    items: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if text and text not in items:
            items.append(text)
    return items


def _source_fields(data: dict[str, Any]) -> tuple[str, str]:
    source = data.get("source")
    source_url = _first_text(data, ("source_url", "url", "link", "canonical_url"))
    source_name = _first_text(data, ("source_domain", "domain", "source_name", "publisher"))
    if isinstance(source, dict):
        source_url = source_url or _first_text(source, ("url", "link", "href"))
        source_name = source_name or _first_text(source, ("domain", "name", "source_name", "publisher"))
    elif source is not None:
        source_name = source_name or str(source).strip()

    hostname = urlparse(source_url).hostname if source_url else ""
    source_domain = (hostname or source_name).strip().lower()
    if source_domain.startswith("www."):
        source_domain = source_domain[4:]
    return source_domain, source_url


def _normalize_item(
    data: dict[str, Any],
    doc_id: str = "",
    *,
    include_deep: bool = False,
) -> dict[str, Any] | None:
    item_id = _first_text(data, ("id", "item_id", "slug")) or doc_id
    headline = _first_text(data, ("headline", "title", "name"))
    take = _first_text(
        data,
        ("gemini_take", "take", "one_sentence_take", "one_liner", "summary", "snippet"),
    )
    source_domain, source_url = _source_fields(data)
    if not item_id or not headline or not source_domain:
        return None

    published_at = _as_iso(
        data.get("published_at")
        or data.get("created_at")
        or data.get("timestamp")
        or data.get("updated_at")
        or data.get("date")
    )
    tags = _as_list(data.get("tags") or data.get("topics") or data.get("categories"))
    pillar = _first_text(data, ("pillar", "theme", "primary_theme"))
    if pillar and pillar not in tags:
        tags.append(pillar)

    item: dict[str, Any] = {
        "id": item_id,
        "headline": headline,
        "gemini_take": take,
        "source_domain": source_domain,
        "source_url": source_url,
        "published_at": published_at,
        "date": _first_text(data, ("date",)) or published_at[:10],
        "tags": tags,
        "pillar": pillar,
        "confidence": _as_float(data.get("confidence") or data.get("confidence_score")),
    }
    if include_deep:
        thesis = data.get("thesis_breakdown") or data.get("thesis") or data.get("bullets") or []
        item.update(
            {
                "deep_brief": _first_text(data, ("deep_brief", "brief", "analysis", "body")),
                "thesis_breakdown": _as_list(thesis),
                "tickers": _as_list(data.get("tickers") or data.get("symbols")),
            }
        )
    return item


def _sort_key(item: dict[str, Any]) -> str:
    return str(item.get("published_at") or item.get("date") or "")


def _matches_date(item: dict[str, Any], date_filter: str | None) -> bool:
    if not date_filter:
        return True
    item_date = str(item.get("date") or "").strip()
    published = str(item.get("published_at") or "").strip()
    return item_date == date_filter or published.startswith(date_filter)


def _query_stream(limit: int, date_filter: str | None = None) -> list[Any]:
    collection = _collection()
    attempts: list[Any] = []
    if date_filter:
        attempts.append(collection.where("date", "==", date_filter).limit(limit))
    try:
        attempts.append(collection.order_by("published_at", direction="DESCENDING").limit(limit))
    except TypeError:
        attempts.append(collection.order_by("published_at").limit(limit))
    attempts.append(collection.limit(limit))

    last_error: Exception | None = None
    for query in attempts:
        try:
            docs = list(query.stream())
            if docs or not date_filter:
                return docs
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return []


def _load_digest_items(limit: int, date_filter: str | None = None) -> list[dict[str, Any]]:
    docs = _query_stream(max(limit * 3, limit), date_filter)
    items: list[dict[str, Any]] = []
    for doc in docs:
        doc_id, data = _to_dict(doc)
        item = _normalize_item(data, doc_id)
        if item and _matches_date(item, date_filter):
            items.append(item)
    return sorted(items, key=_sort_key, reverse=True)[:limit]


def _theme_counts(items: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for item in items:
        for tag in item.get("tags") or []:
            label = str(tag).strip()
            if not label:
                continue
            key = label.casefold()
            counts[key] += 1
            labels.setdefault(key, label)
    return [
        {"id": re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", labels[key]).strip("-"), "label": labels[key], "count": count}
        for key, count in counts.most_common(limit)
    ]


def _firestore_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"news firestore unavailable: {exc}")


@router.get("/digest")
def get_news_digest(
    date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    try:
        items = _load_digest_items(limit, date)
    except Exception as exc:
        raise _firestore_unavailable(exc) from exc
    return {
        "date": date,
        "limit": limit,
        "items": items,
        "themes": _theme_counts(items),
        "source": f"firestore:{_collection_name()}",
        "available": True,
    }


@router.get("/deep/{item_id}")
def get_news_deep(item_id: str) -> dict[str, Any]:
    ident = item_id.strip()
    if not ident:
        raise HTTPException(status_code=404, detail="news item not found")
    try:
        doc = _collection().document(ident).get()
        if getattr(doc, "exists", True):
            doc_id, data = _to_dict(doc)
            item = _normalize_item(data, doc_id, include_deep=True)
            if item:
                return item

        for candidate in _query_stream(100):
            doc_id, data = _to_dict(candidate)
            item = _normalize_item(data, doc_id, include_deep=True)
            if item and item["id"] == ident:
                return item
    except Exception as exc:
        raise _firestore_unavailable(exc) from exc
    raise HTTPException(status_code=404, detail="news item not found")


@router.get("/themes")
def get_news_themes(limit: int = Query(default=80, ge=1, le=200)) -> dict[str, Any]:
    try:
        items = _load_digest_items(limit)
    except Exception as exc:
        raise _firestore_unavailable(exc) from exc
    return {"themes": _theme_counts(items), "source": f"firestore:{_collection_name()}"}

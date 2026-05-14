"""Industry themes API (M5) — static cards + execution_intents regime sample."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import APIRouter, Query

from api_routers.industry_themes_static import INDUSTRY_THEMES_STATIC
from execution_intents import latest_execution_intents

router = APIRouter(prefix="/api/industries", tags=["industries"])


@router.get("/themes")
def list_industry_themes_m5(
    limit: int = Query(default=80, ge=1, le=200),
) -> dict[str, Any]:
    """Industry themes (M5): static cards + dominant ``regime`` sample from execution intents."""
    intents = latest_execution_intents(limit=limit, dedupe=True, sort_by="updated_desc")
    regimes = [str(r.get("regime") or "").strip() for r in intents if str(r.get("regime") or "").strip()]
    regime_sample = Counter(regimes).most_common(1)[0][0] if regimes else None
    rotation = sorted(
        INDUSTRY_THEMES_STATIC,
        key=lambda row: (float(row.get("regime_score") or 0), len(row.get("symbols") or [])),
        reverse=True,
    )
    return {
        "themes": INDUSTRY_THEMES_STATIC,
        "rotation": [
            {
                "id": row["id"],
                "label": row["label"],
                "regime_score": row.get("regime_score", 0),
                "risk_level": row.get("risk_level", "medium"),
                "symbols": row.get("symbols", []),
            }
            for row in rotation
        ],
        "intent_sample_regime": regime_sample,
        "intent_count": len(intents),
        "source": "static+execution_intents.jsonl",
    }

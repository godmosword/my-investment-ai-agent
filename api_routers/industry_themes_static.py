"""Static industry theme cards for M5 ``GET /api/industries/themes`` (no live paid feeds)."""

from __future__ import annotations

from typing import Any

INDUSTRY_THEMES_STATIC: list[dict[str, Any]] = [
    {
        "id": "ai-semis",
        "label": "AI 半導體",
        "symbols": ["NVDA", "AMD", "AVGO"],
        "pillar": "semiconductor",
        "regime_score": 4,
        "risk_level": "medium",
        "thesis": "AI capex and accelerator demand remain the primary relative-strength driver.",
    },
    {
        "id": "mega-cap-tech",
        "label": "大型科技",
        "symbols": ["MSFT", "GOOGL", "META", "AAPL"],
        "pillar": "ai",
        "regime_score": 3,
        "risk_level": "low",
        "thesis": "Cash-flow quality offsets valuation pressure when rates are stable.",
    },
    {
        "id": "digital-assets",
        "label": "數位資產",
        "symbols": ["BTC", "ETH", "SOL"],
        "pillar": "crypto",
        "regime_score": 2,
        "risk_level": "high",
        "thesis": "ETF flow and dollar liquidity dominate near-term beta.",
    },
    {
        "id": "enterprise-software",
        "label": "企業軟體",
        "symbols": ["ORCL", "CRM", "NOW"],
        "pillar": "ai",
        "regime_score": 1,
        "risk_level": "medium",
        "thesis": "AI monetization helps, but seat expansion remains selective.",
    },
]

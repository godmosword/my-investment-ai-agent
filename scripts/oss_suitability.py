"""Heuristic 1–5 fit score for OSS repos vs Q-Silicon integration (no LLM)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _days_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        # GitHub: 2024-01-02T12:00:00Z
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
    except ValueError:
        return None


def score_repo(repo: dict[str, Any]) -> tuple[int, str]:
    """Return (1–5, short rationale)."""
    if repo.get("error"):
        return 1, f"fetch_error:{repo.get('error')}"
    if repo.get("archived"):
        return 1, "archived"

    stars = int(repo.get("stargazers_count") or 0)
    days = _days_since(repo.get("pushed_at") or repo.get("updated_at"))
    lic = repo.get("license_spdx") or ""
    readme = repo.get("readme_excerpt") or ""
    topics = repo.get("topics") or []

    score = 0
    bits: list[str] = []

    if stars >= 2000:
        score += 2
        bits.append("stars≥2k")
    elif stars >= 200:
        score += 1
        bits.append("stars≥200")
    elif stars >= 20:
        bits.append("stars≥20")

    if days is not None:
        if days <= 90:
            score += 1
            bits.append("pushed≤90d")
        elif days <= 365:
            score += 1
            bits.append("pushed≤365d")

    if lic and lic not in ("NOASSERTION", "NONE"):
        score += 1
        bits.append(f"license:{lic}")

    if len(readme) >= 400:
        score += 1
        bits.append("readme≥400c")
    elif len(readme) < 80:
        bits.append("readme thin")

    # Domain hints (quant / ML / data pipeline)
    blob = " ".join(
        [
            (repo.get("description") or "").lower(),
            " ".join(topics).lower(),
            readme[:1200].lower(),
        ]
    )
    if any(k in blob for k in ("quant", "trading", "portfolio", "backtest", "crypto", "btc")):
        score += 1
        bits.append("domain_overlap")

    final = max(1, min(5, score))
    rationale = "｜".join(bits) if bits else "neutral"
    return final, rationale


def label_for_score(s: int) -> str:
    if s >= 5:
        return "建議優先評估"
    if s >= 4:
        return "高適配"
    if s >= 3:
        return "中適配"
    if s >= 2:
        return "低適配"
    return "暫緩"

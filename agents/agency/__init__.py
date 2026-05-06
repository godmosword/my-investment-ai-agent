"""Agency 模板載入（Phase 1）：預設不啟用研究路徑；見 ``docs/architecture/agency_agents_research.md`` §12。"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_AGENCY_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class AgencyTemplate:
    raw: str = ""
    core_mission: str = ""
    critical_rules: tuple[str, ...] = ()
    deliverables: tuple[str, ...] = ()
    fallback: bool = False

    def summary(self, *, max_chars: int = 900) -> str:
        parts: list[str] = []
        if self.core_mission:
            parts.append(f"Core Mission: {self.core_mission}")
        if self.critical_rules:
            parts.append("Critical Rules: " + " | ".join(self.critical_rules[:4]))
        if self.deliverables:
            parts.append("Deliverables: " + " | ".join(self.deliverables[:4]))
        out = "\n".join(parts).strip()
        return out[:max_chars].rstrip()


def agency_research_enabled() -> bool:
    return os.getenv("AGENCY_RESEARCH_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def _load_agency_template(relative_path: str) -> str:
    """讀取 ``agents/agency/`` 下 markdown；失敗回空字串（供上層 fallback）。"""
    if not agency_research_enabled():
        return ""
    try:
        p = (_AGENCY_DIR / relative_path).resolve()
        if not str(p).startswith(str(_AGENCY_DIR)):
            return ""
        if not p.is_file():
            logger.warning("agency template missing: %s", relative_path)
            return ""
        return p.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("agency template read failed %s: %s", relative_path, exc)
        return ""


def _section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        re.MULTILINE,
    )
    m = pattern.search(markdown or "")
    return m.group(1).strip() if m else ""


def _bullet_lines(body: str) -> tuple[str, ...]:
    out: list[str] = []
    for raw in (body or "").splitlines():
        line = raw.strip()
        line = re.sub(r"^(?:[-*]|\d+\.)\s*", "", line).strip()
        if line:
            out.append(line)
    return tuple(out)


def _fallback_template() -> AgencyTemplate:
    return AgencyTemplate(
        core_mission="Supplement public filing/tool context without inventing objective data.",
        critical_rules=(
            "Use DATA_MISSING markers for absent facts.",
            "Do not replace validated price/source tooling.",
        ),
        deliverables=("Validated assumptions and next-step evidence checklist.",),
        fallback=True,
    )


def load_agency_template(relative_path: str = "investment_researcher.md") -> AgencyTemplate:
    """Load and parse an Agency markdown template into graph/crew-friendly fields."""
    if not agency_research_enabled():
        return AgencyTemplate()
    raw = _load_agency_template(relative_path)
    if not raw:
        return _fallback_template()
    core = " ".join(_section(raw, "Core Mission").split())
    rules = _bullet_lines(_section(raw, "Critical Rules"))
    deliverables = _bullet_lines(_section(raw, "Deliverables"))
    if not (core or rules or deliverables):
        return _fallback_template()
    return AgencyTemplate(
        raw=raw,
        core_mission=core,
        critical_rules=rules,
        deliverables=deliverables,
        fallback=False,
    )

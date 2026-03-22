"""Jinja2 rendering: DailyBriefReport → Telegram HTML (whitelist tags in template)."""

from __future__ import annotations

import html
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schemas import AISection, CryptoSection, DailyBriefReport


def tg_escape(value: object) -> str:
    """Escape dynamic text for Telegram HTML (no raw < > & in user strings)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def assemble_daily_brief_report(
    crypto: CryptoSection,
    ai: AISection,
    *,
    previous_recs_html: str,
    source_observability_block: str,
    report_tier_partial_news: bool,
) -> DailyBriefReport:
    return DailyBriefReport(
        crypto=crypto,
        ai=ai,
        previous_recs_html=(previous_recs_html or "").strip(),
        source_observability_block=(source_observability_block or "").strip(),
        report_tier_partial_news=report_tier_partial_news,
    )


def render_telegram_daily_brief(report: DailyBriefReport) -> str:
    root = Path(__file__).resolve().parent
    env = Environment(
        loader=FileSystemLoader(str(root / "templates")),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tg_escape"] = tg_escape

    qsrec_list = [r.model_dump(exclude_none=True) for r in report.all_qsrec()]
    return env.get_template("telegram_report.j2").render(
        crypto=report.crypto,
        ai=report.ai,
        previous_recs_html=report.previous_recs_html,
        source_observability_block=report.source_observability_block,
        report_tier_partial_news=report.report_tier_partial_news,
        tagged_news_count=report.tagged_news_count(),
        qsrec_json=json.dumps(qsrec_list, ensure_ascii=False),
    )

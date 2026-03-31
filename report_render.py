"""Jinja2 rendering: DailyBriefReport → Telegram HTML (whitelist tags in template)."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

from schemas import AISection, CryptoSection, DailyBriefReport, QSREC_JSON_EXCLUDE_FIELDS
from validation_rules import (
    ensure_crypto_risk_budget_regime_token,
    normalize_authoritative_regime_tokens_multiline,
    normalize_leading_repeat_pick_phrase,
    sanitize_lines_with_us_treasury_keyword,
)

_AGREED_REGIME_TOKENS = frozenset({"risk_on", "risk_off", "neutral"})

# Anchored pattern: strip leading 若 (with or without trailing space) only at the
# start of the invalidation string.  Using an anchored sub avoids corrupting Chinese
# compound words such as 如若, 假若, 縱若 that contain 若 mid-string.
_INVALIDATION_LEADING_RUO_RE = re.compile(r"^若\s*")


def _clean_invalidation(text: object) -> str:
    """Normalize invalidation text for Telegram display.

    - Strip leading conditional marker 若 (with/without space) using an anchored
      regex so compound words like 如若 are preserved.
    - Strip 則失效 / 則失效。 wherever it appears (unanchored: handles both trailing
      and mid-string occurrences, e.g. "若跌破則失效。反之突破則看漲").
    - Collapse double Chinese full-stops (。。 → 。).
    """
    if text is None:
        return ""
    s = str(text).strip()
    s = _INVALIDATION_LEADING_RUO_RE.sub("", s)
    s = s.replace("則失效。", "").replace("則失效", "")
    s = s.replace("。。", "。")
    return s.strip()


def tg_escape(value: object) -> str:
    """Escape dynamic text for Telegram HTML (no raw < > & in user strings)."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def _flatten_brief_text_for_na_gate(crypto: CryptoSection, ai: AISection) -> str:
    """Approximate HTML N/A density for the same Gate threshold as validate_report."""
    parts: list[str] = []
    for row in crypto.dashboard:
        parts.extend((row.label, row.value))
    for row in ai.dashboard:
        parts.extend((row.label, row.value))
    for line in crypto.macro_framework_lines:
        parts.append(line)
    for line in ai.macro_bridge_lines:
        parts.append(line)
    parts.extend(
        (
            crypto.narrative_of_day,
            crypto.pick_reason,
            crypto.risk_budget_summary,
            crypto.signal_conflict_summary,
            ai.pick_reason,
            ai.signal_conflict_summary,
        )
    )
    if ai.us_equity_allocation_note:
        parts.append(ai.us_equity_allocation_note)
    for leg in crypto.trade_legs:
        for f in (
            leg.current_price,
            leg.entry,
            leg.target,
            leg.stop,
            leg.trigger,
            leg.invalidation,
            leg.narrative,
        ):
            parts.append(str(f))
    for leg in ai.trade_legs:
        for f in (
            leg.current_price,
            leg.entry,
            leg.target,
            leg.stop,
            leg.trigger,
            leg.invalidation,
            leg.narrative,
        ):
            parts.append(str(f))
    for r in list(crypto.qsrec) + list(ai.qsrec):
        parts.append(r.narrative or "")
        parts.append(r.trigger or "")
    for n in crypto.news:
        parts.extend((n.title, n.summary, n.investment_takeaway, n.editor_consensus))
    for n in ai.news:
        parts.extend((n.title, n.summary, n.investment_takeaway, n.editor_consensus))
    for c in crypto.chatter:
        parts.append(c.text)
    for c in ai.chatter:
        parts.append(c.text)
    return "\n".join(parts)


def _low_confidence_disclaimer_plain(crypto: CryptoSection, ai: AISection) -> str:
    blob = _flatten_brief_text_for_na_gate(crypto, ai)
    na_count = len(re.findall(r"\bN/A\b", blob))
    has_low_conf = bool(re.search(r"低置信度|低信心", blob))
    has_proxy = bool(
        re.search(
            r"資料缺失原因[\s\S]{0,800}?替代指標|替代指標[\s\S]{0,800}?資料缺失原因",
            blob,
            re.IGNORECASE,
        )
    )
    if na_count <= 3 or (has_low_conf and has_proxy):
        return ""
    return (
        "⚠️ 低置信度聲明\n"
        "資料缺失原因：本日部分數據源（yfinance / CoinGlass / NewsAPI）未回應，"
        "相關欄位以 N/A 標示。\n"
        "替代指標：N/A 欄位請參考 Binance 備援數據或 CME FedWatch Tool 補充。\n"
    )


def _coerce_sections_for_gate(
    crypto: CryptoSection,
    ai: AISection,
    *,
    agreed_regime: str | None,
) -> tuple[CryptoSection, AISection]:
    """Align structured sections with scorecard regime and macro outlier rules (P1)."""
    if agreed_regime and agreed_regime in _AGREED_REGIME_TOKENS:
        nr = agreed_regime
        m = crypto.market.model_copy(update={"regime": nr})
        m = m.model_copy(
            update={
                "scorecard_lines": [
                    normalize_authoritative_regime_tokens_multiline(x, nr) for x in m.scorecard_lines
                ],
            }
        )
        crypto = crypto.model_copy(
            update={
                "market": m,
                "narrative_of_day": normalize_authoritative_regime_tokens_multiline(
                    crypto.narrative_of_day, nr
                ),
                "pick_reason": normalize_authoritative_regime_tokens_multiline(crypto.pick_reason, nr),
                "risk_budget_summary": normalize_authoritative_regime_tokens_multiline(
                    crypto.risk_budget_summary, nr
                ),
                "macro_framework_lines": [
                    normalize_authoritative_regime_tokens_multiline(x, nr)
                    for x in crypto.macro_framework_lines
                ],
            }
        )
        ai_updates: dict = {
            "pick_reason": normalize_authoritative_regime_tokens_multiline(ai.pick_reason, nr),
            "macro_bridge_lines": [
                normalize_authoritative_regime_tokens_multiline(x, nr) for x in ai.macro_bridge_lines
            ],
        }
        if ai.us_equity_allocation_note:
            ai_updates["us_equity_allocation_note"] = normalize_authoritative_regime_tokens_multiline(
                ai.us_equity_allocation_note, nr
            )
        ai = ai.model_copy(update=ai_updates)
    if crypto.macro_framework_lines:
        sm = sanitize_lines_with_us_treasury_keyword(list(crypto.macro_framework_lines))
        if sm != crypto.macro_framework_lines:
            crypto = crypto.model_copy(update={"macro_framework_lines": sm})
    if ai.macro_bridge_lines:
        sm = sanitize_lines_with_us_treasury_keyword(list(ai.macro_bridge_lines))
        if sm != ai.macro_bridge_lines:
            ai = ai.model_copy(update={"macro_bridge_lines": sm})
    # Schema / STRICT_CONSISTENCY: risk_budget_summary must surface market.regime token
    # (models sometimes emit Chinese-only lines after normalize_authoritative_regime_tokens_multiline).
    _rb = ensure_crypto_risk_budget_regime_token(
        crypto.risk_budget_summary or "", crypto.market.regime
    )
    if _rb != crypto.risk_budget_summary:
        crypto = crypto.model_copy(update={"risk_budget_summary": _rb})
    return crypto, ai


def _normalize_pick_reason_repeat_headers(crypto: CryptoSection, ai: AISection) -> tuple[CryptoSection, AISection]:
    """Remove duplicate 「重複選用理由：」 after Jinja 「本日選擇理由：」; align with 連日維持 when repeat-day."""
    from report_html_gates import (  # noqa: PLC0415
        _fetch_yesterday_qsrec_canonical_set,
        _qsrec_canonical_set_for_category,
    )

    recs = [r.model_dump(mode="json") for r in crypto.qsrec + ai.qsrec]

    def _same(cat: str) -> bool:
        y = _fetch_yesterday_qsrec_canonical_set(cat)
        t = _qsrec_canonical_set_for_category(recs, cat)
        return y is not None and bool(t) and bool(y) and t == y

    cr = normalize_leading_repeat_pick_phrase(crypto.pick_reason or "", same_as_yesterday=_same("CRYPTO"))
    if cr != (crypto.pick_reason or ""):
        crypto = crypto.model_copy(update={"pick_reason": cr})
    ar = normalize_leading_repeat_pick_phrase(ai.pick_reason or "", same_as_yesterday=_same("EQUITY"))
    if ar != (ai.pick_reason or ""):
        ai = ai.model_copy(update={"pick_reason": ar})
    return crypto, ai


def _apply_repeat_pick_disclaimer_if_needed(crypto: CryptoSection, ai: AISection) -> tuple[CryptoSection, AISection]:
    """When today's QSREC canonical set matches yesterday BQ and override is allowed, prepend a rotation-safe phrase if missing.

    Uses wording that matches ``_REPEAT_PICK_REASON_RE`` (e.g. 連日維持) so the gate passes without duplicating
    「本日選擇理由：」+「重複選用理由：」兩層抬頭。 Opt out: AUTO_REPEAT_PICK_DISCLAIMER=0.
    """
    if os.getenv("AUTO_REPEAT_PICK_DISCLAIMER", "1").lower() in ("0", "false", "no"):
        return crypto, ai
    from report_html_gates import (  # noqa: PLC0415 — late import avoids cycles at module load
        _REPEAT_PICK_REASON_RE,
        _allow_repeat_pick_override,
        _fetch_yesterday_qsrec_canonical_set,
        _qsrec_canonical_set_for_category,
        _strict_pick_rotation,
    )

    if not _strict_pick_rotation() or not _allow_repeat_pick_override():
        return crypto, ai
    recs = [r.model_dump(mode="json") for r in crypto.qsrec + ai.qsrec]
    prefix = (
        "連日維持（同昨日 BQ QSREC）；pipeline 自動補註——主編次日應依催化改選或於理由內詳述。"
    )
    for cat in ("CRYPTO", "EQUITY"):
        y = _fetch_yesterday_qsrec_canonical_set(cat)
        t = _qsrec_canonical_set_for_category(recs, cat)
        if y is None or not t or not y or t != y:
            continue
        if cat == "CRYPTO":
            reason = crypto.pick_reason or ""
            if _REPEAT_PICK_REASON_RE.search(reason):
                continue
            crypto = crypto.model_copy(update={"pick_reason": prefix + reason})
        else:
            reason = ai.pick_reason or ""
            if _REPEAT_PICK_REASON_RE.search(reason):
                continue
            ai = ai.model_copy(update={"pick_reason": prefix + reason})
    return crypto, ai


def assemble_daily_brief_report(
    crypto: CryptoSection,
    ai: AISection,
    *,
    previous_recs_html: str,
    source_observability_block: str,
    report_tier_partial_news: bool,
    agreed_regime: str | None = None,
) -> DailyBriefReport:
    crypto, ai = _coerce_sections_for_gate(crypto, ai, agreed_regime=agreed_regime)
    crypto, ai = _normalize_pick_reason_repeat_headers(crypto, ai)
    crypto, ai = _apply_repeat_pick_disclaimer_if_needed(crypto, ai)
    disclaimer = _low_confidence_disclaimer_plain(crypto, ai)
    return DailyBriefReport(
        crypto=crypto,
        ai=ai,
        previous_recs_html=(previous_recs_html or "").strip(),
        source_observability_block=(source_observability_block or "").strip(),
        report_tier_partial_news=report_tier_partial_news,
        low_confidence_disclaimer=disclaimer,
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
    env.filters["clean_invalidation"] = _clean_invalidation

    qsrec_list = [
        r.model_dump(exclude_none=True, exclude=QSREC_JSON_EXCLUDE_FIELDS)
        for r in report.all_qsrec()
    ]
    try:
        tmpl = env.get_template("telegram_report.j2")
    except TemplateNotFound as exc:
        expected = root / "templates" / "telegram_report.j2"
        raise RuntimeError(
            f"Jinja2 template not found: telegram_report.j2 "
            f"(expected at {expected})"
        ) from exc
    try:
        return tmpl.render(
            crypto=report.crypto,
            ai=report.ai,
            previous_recs_html=report.previous_recs_html,
            source_observability_block=report.source_observability_block,
            report_tier_partial_news=report.report_tier_partial_news,
            tagged_news_count=report.tagged_news_count(),
            low_confidence_disclaimer=report.low_confidence_disclaimer or "",
            qsrec_json=json.dumps(qsrec_list, ensure_ascii=False),
        )
    except TemplateError as exc:
        expected = root / "templates" / "telegram_report.j2"
        raise RuntimeError(
            f"Jinja2 template error in telegram_report.j2 "
            f"(path: {expected}): {exc}"
        ) from exc

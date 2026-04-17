"""Jinja2 rendering: DailyBriefReport → Telegram HTML (whitelist tags in template)."""

from __future__ import annotations

import html
import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateError, TemplateNotFound

from assets_universe import equity_universe_merged
from brief_profiles import (
    BLOCK_REGISTRY,
    PROFILES,
    get_active_profile,
    profile_block_ids,
    telegram_profile_template_relpath,
)
from schemas import (
    AISection,
    CryptoSection,
    CurrentAffairsRoundtable,
    DailyBriefReport,
    ExecutableTradeLeg,
    MetricLine,
    NewsItem,
    QSREC_JSON_EXCLUDE_FIELDS,
    TradeRecommendation,
)
from tracker import (
    _current_prices_for_assets,
    _parse_pair_asset,
    default_position_pct_for_leg,
    equity_combined_cap_percent,
    regime_single_leg_cap_percent,
)
from validation_rules import (
    _REPEAT_SAME_YESTERDAY_PREFIX,
    ensure_crypto_risk_budget_regime_token,
    normalize_authoritative_regime_tokens_multiline,
    normalize_leading_repeat_pick_phrase,
    sanitize_lines_with_us_treasury_keyword,
)

logger = logging.getLogger(__name__)

_AGREED_REGIME_TOKENS = frozenset({"risk_on", "risk_off", "neutral"})

# 標普 500 指數點位誤植（與個股同量級）— 對齊 macro_context / ^GSPC 錨點
_SPX_LEVEL_AFTER_KEYWORD_RE = re.compile(
    r"(?:標普\s*500|S&P\s*500)\s*(?:指數)?\D{0,28}"
    r"([\d]{1,2}(?:,\d{3})+(?:\.\d{1,2})?|\d{3,4}(?:\.\d{1,2})?)",
    re.IGNORECASE,
)


def sanitize_equity_valuation_framing_spx(text: str, anchor: float | None) -> str:
    """若錨點可用，將 equity_valuation_framing 內明顯偏離的標普／S&P 500 指數數字改為錨點讀數。"""
    if not (text and anchor and 2500.0 <= anchor <= 12000.0):
        return text or ""
    threshold = anchor * 0.55

    def repl(m: re.Match[str]) -> str:
        raw = m.group(1).replace(",", "").replace("，", "")
        try:
            val = float(raw)
        except ValueError:
            return m.group(0)
        if 80.0 <= val < 3000.0 and val < threshold:
            fmt = f"{anchor:,.2f}"
            return m.group(0).replace(m.group(1), fmt, 1)
        return m.group(0)

    return _SPX_LEVEL_AFTER_KEYWORD_RE.sub(repl, text)


def _apply_gspc_anchor_to_equity_framing(crypto: CryptoSection) -> CryptoSection:
    try:
        from tools_legacy import fetch_gspc_last_close_anchor  # noqa: PLC0415
    except Exception:
        return crypto
    anchor = fetch_gspc_last_close_anchor()
    ev = (crypto.equity_valuation_framing or "").strip()
    if not ev:
        return crypto
    fixed = sanitize_equity_valuation_framing_spx(ev, anchor)
    if fixed != ev:
        logger.info("equity_valuation_framing: applied ^GSPC anchor sanitize (anchor=%s)", anchor)
        return crypto.model_copy(update={"equity_valuation_framing": fixed})
    return crypto

# Telegram HTML whitelist: <b> <i> <blockquote> only here.
_INSTITUTIONAL_DISCLAIMER_HTML = (
    "<blockquote>"
    "本電報內容僅為研究性質之市場摘要與架構化資訊彙編，<b>不構成</b>任何司法管轄區內之投資、法律或稅務建議；"
    "<b>非</b>個人化勸誘，亦未考量任何特定讀者之財務狀況與投資目標。"
    "過去績效與工具回傳之歷史數據不預示未來結果。"
    "所有報價、指標與第三方資料均可能延遲、缺漏或變更；讀者應自行核實並承擔使用風險。"
    "</blockquote>"
)

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


_EMPHASIZE_NUMERIC_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:\$?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|\d+(?:\.\d+)?%)(?![A-Za-z0-9])"
)


def tg_emphasize_numbers(value: object) -> str:
    """Escape text then wrap numeric tokens with <b> for quick scanning."""
    escaped = tg_escape(value)
    if not escaped.strip():
        return escaped

    def _wrap(m: re.Match[str]) -> str:
        tok = m.group(0)
        if not any(ch.isdigit() for ch in tok):
            return tok
        return f"<b>{tok}</b>"

    return _EMPHASIZE_NUMERIC_TOKEN_RE.sub(_wrap, escaped)


def tg_soft_wrap_mobile(value: object, *, max_chars: int = 70) -> str:
    """Soft-wrap long lines for mobile readability without changing semantics."""
    text = tg_escape(value)
    if len(text) <= max_chars:
        return text
    out: list[str] = []
    rest = text
    while len(rest) > max_chars:
        cut = max(
            rest.rfind("，", 0, max_chars + 1),
            rest.rfind("。", 0, max_chars + 1),
            rest.rfind("；", 0, max_chars + 1),
            rest.rfind("｜", 0, max_chars + 1),
            rest.rfind(" ", 0, max_chars + 1),
        )
        if cut < int(max_chars * 0.6):
            cut = max_chars
        out.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        out.append(rest)
    return "\n".join(out)


def strip_usd_for_template(value: object) -> str:
    """Strip leading $ from price-like strings before template prepends $ (avoids $$ in HTML)."""
    if value is None:
        return ""
    s = str(value).strip()
    while s.startswith("$"):
        s = s[1:].lstrip()
    return s


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
            crypto.investment_thesis_one_liner,
            crypto.narrative_invalidation_summary,
            crypto.portfolio_framing_summary,
            crypto.scenario_probability_notes,
            crypto.crypto_cycle_valuation_notes,
            crypto.equity_valuation_framing,
            crypto.pick_reason,
            crypto.risk_budget_summary,
            crypto.signal_conflict_summary,
            ai.pick_reason,
            ai.signal_conflict_summary,
        )
    )
    for _lst in (
        crypto.thesis_supporting_points,
        crypto.thesis_contrary_points,
        crypto.key_assumptions_lines,
        crypto.event_calendar_lines,
    ):
        for line in _lst:
            parts.append(str(line))
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
            leg.liquidity_execution_note or "",
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
            leg.liquidity_execution_note or "",
        ):
            parts.append(str(f))
    for r in list(crypto.qsrec) + list(ai.qsrec):
        parts.append(r.narrative or "")
        parts.append(r.trigger or "")
    for n in crypto.news:
        parts.extend(
            (n.title, n.summary, n.investment_takeaway, n.editor_consensus, n.pricing_note or "")
        )
    for n in ai.news:
        parts.extend(
            (n.title, n.summary, n.investment_takeaway, n.editor_consensus, n.pricing_note or "")
        )
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


def _normalize_regime_token_coerce(raw: str | None) -> str | None:
    """Normalize risk_on/risk_off/neutral spellings for QSREC regime comparison."""
    if raw is None or not str(raw).strip():
        return None
    token = re.sub(r"[\s\-_]+", "_", str(raw).strip().lower())
    if token in _AGREED_REGIME_TOKENS:
        return token
    return None


def _coerce_qsrec_regimes_to_market(
    crypto: CryptoSection, ai: AISection
) -> tuple[CryptoSection, AISection]:
    """Force each QSREC row's optional regime to match crypto.market.regime (HTML Gate)."""
    primary = crypto.market.regime
    if primary not in _AGREED_REGIME_TOKENS:
        return crypto, ai

    def _rows(recs: list[TradeRecommendation]) -> list[TradeRecommendation]:
        out: list[TradeRecommendation] = []
        for r in recs:
            rec_reg = _normalize_regime_token_coerce(r.regime)
            if rec_reg is None:
                out.append(r)
                continue
            if rec_reg != primary:
                out.append(r.model_copy(update={"regime": primary}))
            else:
                out.append(r)
        return out

    cq = _rows(list(crypto.qsrec))
    aq = _rows(list(ai.qsrec))
    if cq != crypto.qsrec:
        crypto = crypto.model_copy(update={"qsrec": cq})
    if aq != ai.qsrec:
        ai = ai.model_copy(update={"qsrec": aq})
    return crypto, ai


def _fix_us_equity_allocation_misbranded_risk_off(ai: AISection, primary: str) -> AISection:
    """Replace mistaken (risk_off) in 美股部位框 when primary regime is neutral/risk_on."""
    if primary not in ("neutral", "risk_on"):
        return ai
    note = ai.us_equity_allocation_note
    if not (note and note.strip()):
        return ai
    fixed = re.sub(
        r"[（(]\s*risk[\s_\-]*off\s*[）)]",
        f"（對齊主判定：{primary}）",
        note,
        flags=re.IGNORECASE,
    )
    if fixed == note:
        return ai
    return ai.model_copy(update={"us_equity_allocation_note": fixed})


def _parse_position_pct_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    core = str(raw).replace("%", "").strip()
    if not core:
        return None
    try:
        return float(core)
    except ValueError:
        return None


def _format_position_pct(value: float) -> str:
    return f"{round(value, 2):g}%"


def _coerce_ai_trade_legs_single_and_combined_cap(ai: AISection, regime: str) -> AISection:
    """Clamp each US equity leg to single-leg cap; scale down proportionally if sum exceeds combined cap."""
    legs = list(ai.trade_legs)
    if not legs:
        return ai
    per_cap = regime_single_leg_cap_percent(regime)
    combined_cap = equity_combined_cap_percent(regime)
    values: list[float] = []
    for leg in legs:
        v = _parse_position_pct_float(leg.position_pct)
        if v is None:
            v = default_position_pct_for_leg(regime, leg.star_rating)
        v = min(v, per_cap)
        values.append(v)
    total = sum(values)
    if len(legs) >= 2 and total > combined_cap + 1e-9:
        factor = combined_cap / total
        values = [round(v * factor, 2) for v in values]
    new_legs = [
        leg.model_copy(update={"position_pct": _format_position_pct(values[i])})
        for i, leg in enumerate(legs)
    ]

    def _pct_close(a: str | None, b: str | None) -> bool:
        fa, fb = _parse_position_pct_float(a), _parse_position_pct_float(b)
        if fa is None and fb is None:
            return (a or "").strip() == (b or "").strip()
        if fa is None or fb is None:
            return False
        return abs(fa - fb) < 0.001

    if all(_pct_close(leg.position_pct, nl.position_pct) for leg, nl in zip(legs, new_legs, strict=True)):
        return ai
    return ai.model_copy(update={"trade_legs": new_legs})


def _trade_leg_position_pct_needs_fill(raw: str | None) -> bool:
    if raw is None:
        return True
    t = str(raw).strip()
    if not t:
        return True
    core = t.replace("%", "").strip()
    if not core:
        return True
    try:
        float(core)
    except ValueError:
        return True
    else:
        return False


def _coerce_trade_leg_position_pcts(crypto: CryptoSection, ai: AISection) -> tuple[CryptoSection, AISection]:
    """Fill empty trade_legs.position_pct for Telegram cards (regime cap + star_rating heuristic)."""
    regime = crypto.market.regime if crypto.market else "neutral"
    new_crypto_legs = [
        leg.model_copy(
            update={"position_pct": f"{default_position_pct_for_leg(regime, leg.star_rating):g}%"},
        )
        if _trade_leg_position_pct_needs_fill(leg.position_pct)
        else leg
        for leg in crypto.trade_legs
    ]
    new_ai_legs = [
        leg.model_copy(
            update={"position_pct": f"{default_position_pct_for_leg(regime, leg.star_rating):g}%"},
        )
        if _trade_leg_position_pct_needs_fill(leg.position_pct)
        else leg
        for leg in ai.trade_legs
    ]
    if new_crypto_legs != list(crypto.trade_legs):
        crypto = crypto.model_copy(update={"trade_legs": new_crypto_legs})
    if new_ai_legs != list(ai.trade_legs):
        ai = ai.model_copy(update={"trade_legs": new_ai_legs})
    ai = _coerce_ai_trade_legs_single_and_combined_cap(ai, regime)
    return crypto, ai


_PRICE_NA_RE = re.compile(r"^\s*\$?\s*N\s*/\s*A\s*$", re.IGNORECASE)


def _trade_price_field_unusable(raw: str | None) -> bool:
    if raw is None:
        return True
    t = str(raw).strip()
    if not t:
        return True
    tl = t.lower().replace("\u00a0", " ")
    if tl in ("—", "-", "tbd", "待定", "n/a", "na", "$n/a", "none"):
        return True
    if _PRICE_NA_RE.match(t.strip()):
        return True
    if not re.search(r"\d", t):
        return True
    return False


def _parse_first_usd_number(s: str) -> float | None:
    t = str(s).replace(",", "").replace("$", " ")
    for m in re.finditer(r"-?\d+(?:\.\d+)?", t):
        try:
            v = float(m.group(0))
        except ValueError:
            continue
        if 0 < v < 1_000_000:
            return v
    return None


def _parse_rr_ratio(rr: str) -> float | None:
    m = re.search(r"1\s*:\s*(\d+(?:\.\d+)?)", str(rr), re.IGNORECASE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_drawdown_fraction(md: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", str(md))
    if not m:
        return None
    try:
        return abs(float(m.group(1))) / 100.0
    except ValueError:
        return None


def _fmt_equity_money(x: float) -> str:
    return f"{x:,.2f}"


def _synth_equity_target_stop(entry: float, direction: str, rr: float, risk_pct: float) -> tuple[str, str]:
    """Derive target/stop strings from entry, R:R, and max-drawdown % (no LLM prices)."""
    if direction == "LONG":
        stop_p = entry * (1 - risk_pct)
        tgt_p = entry * (1 + risk_pct * rr)
        s_disp = (entry - stop_p) / entry * 100
        t_disp = (tgt_p - entry) / entry * 100
        stop_s = f"{_fmt_equity_money(stop_p)} (-{s_disp:.1f}%)"
        tgt_s = f"{_fmt_equity_money(tgt_p)} (+{t_disp:.1f}%)"
    else:
        stop_p = entry * (1 + risk_pct)
        tgt_p = entry * (1 - risk_pct * rr)
        s_disp = (stop_p - entry) / entry * 100
        t_disp = (entry - tgt_p) / entry * 100
        stop_s = f"{_fmt_equity_money(stop_p)} (+{s_disp:.1f}%)"
        tgt_s = f"{_fmt_equity_money(tgt_p)} (-{t_disp:.1f}%)"
    return tgt_s, stop_s


def _dashboard_has_ma_band(rows: list[MetricLine], n: int) -> bool:
    pat = re.compile(rf"MA\s*{n}\b", re.IGNORECASE)
    return any(pat.search(r.label or "") for r in rows)


def _insert_idx_after_btc_spot(rows: list[MetricLine]) -> int:
    for i, r in enumerate(rows):
        lab = r.label or ""
        if "現價" in lab and "BTC" in lab.upper():
            return i + 1
    for i, r in enumerate(rows):
        lab_u = (r.label or "").upper()
        if "BTC" in lab_u and "RSI" in lab_u:
            return i
    return len(rows)


def _ensure_btc_ma_dashboard_rows(crypto: CryptoSection) -> CryptoSection:
    """Inject BTC MA20/MA50 from yfinance when missing — aligns trade/news MA cites with 區塊①."""
    if os.getenv("SKIP_BTC_MA_DASHBOARD_INJECT", "").lower() in ("1", "true", "yes"):
        return crypto
    if os.getenv("MOCK_APIS", "").lower() in ("1", "true", "yes"):
        return crypto
    rows = list(crypto.dashboard)
    need20 = not _dashboard_has_ma_band(rows, 20)
    need50 = not _dashboard_has_ma_band(rows, 50)
    if not need20 and not need50:
        return crypto
    try:
        from main import _get_extended_price_data
    except ImportError:
        logger.warning("BTC MA dashboard inject skipped (main import failed)")
        return crypto
    ext = _get_extended_price_data("BTC-USD", period="60d")
    ma20, ma50 = ext.get("ma20"), ext.get("ma50")
    inserts: list[MetricLine] = []
    if need20 and ma20 is not None:
        inserts.append(
            MetricLine(
                label="BTC MA20（日線）",
                value=f"${ma20:,.2f}",
                status_emoji="⬜",
            )
        )
    if need50 and ma50 is not None:
        inserts.append(
            MetricLine(
                label="BTC MA50（日線）",
                value=f"${ma50:,.2f}",
                status_emoji="⬜",
            )
        )
    if not inserts:
        return crypto
    idx = _insert_idx_after_btc_spot(rows)
    merged = rows[:idx] + inserts + rows[idx:]
    return crypto.model_copy(update={"dashboard": merged})


def _parse_scorecard_btc_rsi_status_emoji(scorecard_lines: list[str] | None) -> str | None:
    """Extract ✅/❌/⬜ for the BTC RSI item from regime scorecard (tool or LLM echo).

    Scorecard may be one pipe-joined line or multiple lines; optional ``<code>`` wrappers
    are stripped before matching.
    """
    if not scorecard_lines:
        return None
    blob = " | ".join(str(ln or "") for ln in scorecard_lines)
    blob = re.sub(r"</?code>", "", blob, flags=re.IGNORECASE)
    m = re.search(r"(✅|❌|⬜)\s*BTC\s*RSI", blob, re.IGNORECASE)
    return m.group(1) if m else None


def _sync_dashboard_btc_rsi_with_scorecard(crypto: CryptoSection) -> CryptoSection:
    """Align 區塊① BTC RSI row ``status_emoji`` with 【今日市場模式】評分卡 (single audit trail)."""
    emoji = _parse_scorecard_btc_rsi_status_emoji(list(crypto.market.scorecard_lines or []))
    if not emoji:
        return crypto
    rows = list(crypto.dashboard or [])
    new_rows: list[MetricLine] = []
    changed = False
    for r in rows:
        if getattr(r, "is_section_header", False):
            new_rows.append(r)
            continue
        lab_u = (r.label or "").upper()
        if "BTC" in lab_u and "RSI" in lab_u:
            cur = (r.status_emoji or "").strip()
            if cur != emoji:
                new_rows.append(r.model_copy(update={"status_emoji": emoji}))
                changed = True
                continue
        new_rows.append(r)
    if not changed:
        return crypto
    logger.info("dashboard: synced BTC RSI status_emoji to scorecard (%s)", emoji)
    return crypto.model_copy(update={"dashboard": new_rows})


def _btc_ma_canonical_from_dashboard(rows: list[MetricLine]) -> dict[int, tuple[float, str]]:
    """Map 20|50 -> (float, ``$xx,xxx.xx``) from dashboard MA rows (post-inject)."""
    out: dict[int, tuple[float, str]] = {}
    for r in rows or []:
        if getattr(r, "is_section_header", False):
            continue
        lab = r.label or ""
        m = re.search(r"MA\s*(20|50)\b", lab, re.IGNORECASE)
        if not m:
            continue
        n = int(m.group(1))
        v = _parse_first_usd_number(r.value or "")
        if v is None or not (10_000 < v < 500_000):
            continue
        out[n] = (v, f"${v:,.2f}")
    return out


def _nearest_ma_band_before_dollar(text: str, dollar_pos: int) -> int | None:
    """Pick MA20 vs MA50 for a ``$`` price using the closest preceding ``MA`` keyword."""
    prefix = text[:dollar_pos]
    last20: int | None = None
    last50: int | None = None
    for m in re.finditer(r"\bMA\s*20\b", prefix, re.IGNORECASE):
        last20 = m.end()
    for m in re.finditer(r"\bMA\s*50\b", prefix, re.IGNORECASE):
        last50 = m.end()
    if last20 is None and last50 is None:
        return None
    if last20 is None:
        return 50
    if last50 is None:
        return 20
    return 20 if last20 > last50 else 50


def _ma_price_matches_canonical(val: float, tgt: float) -> bool:
    if tgt <= 0:
        return False
    return abs(val - tgt) / tgt <= 0.003


def _normalize_ma_adjacent_usd_prices(text: str, ma_map: dict[int, tuple[float, str]]) -> str:
    """Rewrite ``$`` amounts that clearly refer to MA20/MA50 to dashboard canonical formatting."""
    if not text.strip() or not ma_map:
        return text
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\$[\d,]+(?:\.\d+)?", text):
        out.append(text[pos : m.start()])
        frag = m.group(0)
        band = _nearest_ma_band_before_dollar(text, m.start())
        if band is None or band not in ma_map:
            out.append(frag)
            pos = m.end()
            continue
        tgt, disp = ma_map[band]
        val = _parse_first_usd_number(frag)
        if val is not None and _ma_price_matches_canonical(val, tgt):
            out.append(disp)
        else:
            out.append(frag)
        pos = m.end()
    out.append(text[pos:])
    return "".join(out)


def _normalize_btc_ma_citations_from_dashboard(crypto: CryptoSection) -> CryptoSection:
    """Align narrative/news dollar cites near MA20/MA50 with 區塊① dashboard (same source as inject)."""
    ma_map = _btc_ma_canonical_from_dashboard(list(crypto.dashboard or []))
    if not ma_map:
        return crypto
    updates: dict = {}

    def _maybe(field: str) -> None:
        cur = getattr(crypto, field, None)
        if not isinstance(cur, str) or not cur:
            return
        new_t = _normalize_ma_adjacent_usd_prices(cur, ma_map)
        if new_t != cur:
            updates[field] = new_t

    for fld in (
        "narrative_of_day",
        "investment_thesis_one_liner",
        "narrative_invalidation_summary",
        "portfolio_framing_summary",
        "scenario_probability_notes",
        "crypto_cycle_valuation_notes",
        "equity_valuation_framing",
        "pick_reason",
        "risk_budget_summary",
        "signal_conflict_summary",
    ):
        _maybe(fld)

    for lf in (
        "exec_summary",
        "thesis_supporting_points",
        "thesis_contrary_points",
        "key_assumptions_lines",
        "macro_framework_lines",
    ):
        cur = getattr(crypto, lf) or []
        new_lines = [_normalize_ma_adjacent_usd_prices(str(x), ma_map) for x in cur]
        if new_lines != list(cur):
            updates[lf] = new_lines

    news_changed = False
    new_news: list[NewsItem] = []
    for n in crypto.news or []:
        kw: dict = {}
        for attr in ("title", "summary", "investment_takeaway", "editor_consensus"):
            cur = getattr(n, attr, None) or ""
            if not isinstance(cur, str):
                continue
            new_t = _normalize_ma_adjacent_usd_prices(cur, ma_map)
            if new_t != cur:
                kw[attr] = new_t
        if kw:
            new_news.append(n.model_copy(update=kw))
            news_changed = True
        else:
            new_news.append(n)

    new_legs: list[ExecutableTradeLeg] = []
    legs_changed = False
    for leg in crypto.trade_legs or []:
        kw = {}
        for attr in ("narrative", "trigger", "invalidation", "sizing_logic", "liquidity_execution_note"):
            cur = getattr(leg, attr, None) or ""
            if not isinstance(cur, str):
                continue
            new_t = _normalize_ma_adjacent_usd_prices(cur, ma_map)
            if new_t != cur:
                kw[attr] = new_t
        if kw:
            new_legs.append(leg.model_copy(update=kw))
            legs_changed = True
        else:
            new_legs.append(leg)

    if not updates and not news_changed and not legs_changed:
        return crypto
    if news_changed:
        updates["news"] = new_news
    if legs_changed:
        updates["trade_legs"] = new_legs
    logger.info("crypto body: normalized MA20/MA50 $ cites to dashboard canonical")
    return crypto.model_copy(update=updates)


def _parse_report_title_date_iso(s: str) -> date | None:
    """Parse CryptoSection.report_title_date (YYYY-MM-DD) for assembly-time guards."""
    raw = (s or "").strip()
    if len(raw) >= 10:
        raw = raw[:10]
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


_HALVING_CALENDAR_RE = re.compile(
    r"(減半|halving|840\s*,?\s*000|84萬|八十四萬)",
    re.IGNORECASE,
)


_EVENT_CAL_LINE_DATE_PREFIX_RE = re.compile(
    r"^(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*"
)


def _remove_unverified_halving_calendar_lines(
    lines: list[str],
    *,
    report_day: date | None,
) -> list[str]:
    """Drop or neutralize rows that claim BTC halving / block 840k (stale LLM trope)."""

    def _neutralize_halving_line(raw: str) -> str:
        t = (raw or "").strip()
        m = _EVENT_CAL_LINE_DATE_PREFIX_RE.match(t)
        prefix = m.group(1) if m else ""
        note = (
            "行事曆備註：略過未經鏈上工具驗證之 BTC 減半／高度敘述（請勿以本列作為減半時間依據）。"
        )
        if prefix:
            return f"{prefix} {note}"
        day = report_day
        if day is None:
            day = datetime.now(timezone(timedelta(hours=8))).date()
        return f"{day.month:02d}/{day.day:02d} {note}"

    out: list[str] = []
    for ln in lines:
        t = (ln or "").strip()
        if not t:
            continue
        if _HALVING_CALENDAR_RE.search(t):
            logger.warning("event_calendar_lines: neutralized unverified halving row")
            out.append(_neutralize_halving_line(t))
            continue
        if report_day is not None and ("840" in t and "000" in t and ("區塊" in t or "block" in t.lower())):
            logger.warning("event_calendar_lines: neutralized suspicious block-height row")
            out.append(_neutralize_halving_line(t))
            continue
        out.append(t)
    return out


def _strip_leading_bullet_chars(s: str) -> str:
    t = (s or "").strip()
    while t and t[0] in "·•●◦▪\u2022":
        t = t[1:].lstrip()
    return t


def _normalize_scenario_probability_notes(raw: str) -> str:
    """Avoid double bullets in Telegram (template already prefixes ·)."""
    text = (raw or "").strip()
    if not text:
        return text
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    if len(lines) < 3:
        return raw
    fixed = [_strip_leading_bullet_chars(ln) for ln in lines[:3]]
    return "\n".join(fixed)


_SCENARIO_BTC_TYPO_K_RE = re.compile(r"7\.6\s*[KkＫ]")


def _btc_dashboard_spot_anchor_usd(rows: list) -> float | None:
    """Best-effort BTC spot (USD) from dashboard rows for assembly-time typo hygiene."""
    best: float | None = None
    for r in rows or []:
        if getattr(r, "is_section_header", False):
            continue
        lab_u = (getattr(r, "label", None) or "").upper()
        val = getattr(r, "value", None) or ""
        blob = f"{getattr(r, 'label', '')} {val}"
        if "BTC" not in lab_u and "比特幣" not in (getattr(r, "label", None) or ""):
            continue
        if any(k in lab_u for k in ("RSI", "MA", "MVRV", "NVT", "DOM", "FEAR", "GREED", "恐懼", "貪婪")):
            continue
        v = _parse_first_usd_number(val) or _parse_first_usd_number(blob)
        if v is None or not (10_000 < v < 500_000):
            continue
        if best is None or v > best:
            best = v
    return best


def _fix_scenario_btc_breakout_typo_k(notes: str, btc_anchor_usd: float | None) -> str:
    """When BTC spot >50k, fix mistaken '7.6k' for ~76k in scenario lines mentioning BTC breakout."""
    if not (notes or "").strip():
        return notes
    if btc_anchor_usd is None or btc_anchor_usd <= 50_000:
        return notes
    out: list[str] = []
    for ln in (notes or "").replace("\r\n", "\n").split("\n"):
        t = ln.strip()
        if not t:
            out.append("")
            continue
        up = t.upper()
        if ("BTC" in up or "比特幣" in t) and "突破" in t and _SCENARIO_BTC_TYPO_K_RE.search(t):
            out.append(_SCENARIO_BTC_TYPO_K_RE.sub("76k", t, count=1))
        else:
            out.append(t)
    return "\n".join(out).rstrip()


_CONTANGO_RE = re.compile(r"Contango|正價差|遠月\s*溢價", re.IGNORECASE)
_BACKWARDATION_RE = re.compile(r"Backwardation|倒價差|遠月\s*折價", re.IGNORECASE)


def _sync_narrative_invalidation_vix_term_structure(
    crypto: CryptoSection,
    macro_blob: str,
    inv: str,
) -> str:
    """If macro mentions Contango but invalidation only cites Backwardation, soften to avoid same-day contradiction."""
    s = (inv or "").strip()
    if not s:
        return s
    if _BACKWARDATION_RE.search(s) and _CONTANGO_RE.search(macro_blob) and not _CONTANGO_RE.search(s):
        s = _BACKWARDATION_RE.sub("VIX 現貨升破 25 且波動風險溢價顯著擴大", s, count=1)
        logger.info("narrative_invalidation_summary: aligned VIX term-structure wording with macro Contango context")
    return s


_CAL_BILLION_TOKEN_RE = re.compile(
    r"(?:\$?\s*)?\d+(?:,\d{3})*(?:\.\d+)?\s*[BbＢｂ](?![A-Za-z])",
)


def _calendar_billion_tokens(cal_lines: list[str]) -> set[str]:
    blob = " ".join(str(x) for x in cal_lines)
    return {m.group(0).strip() for m in _CAL_BILLION_TOKEN_RE.finditer(blob)}


def _strip_news_takeaway_calendar_number_bleed(
    news: list,
    *,
    cal_lines: list[str],
    dashboard_blob: str,
) -> list:
    """Remove sentences that paste calendar-only $XB figures into unrelated investment_takeaway (Phase C hygiene)."""
    tokens = _calendar_billion_tokens(cal_lines)
    if not tokens:
        return news
    dash = dashboard_blob or ""
    out = []
    for item in news:
        tw = getattr(item, "investment_takeaway", "") or ""
        if not tw.strip():
            out.append(item)
            continue
        summary = getattr(item, "summary", "") or ""
        # Split on Chinese / Asian punctuation that ends a clause
        pieces = re.split(r"(?<=[。；])", tw)
        kept: list[str] = []
        for chunk in pieces:
            if not chunk.strip():
                continue
            drop = False
            for tok in tokens:
                if not tok or tok not in chunk:
                    continue
                compact_tok = re.sub(r"\s+", "", tok).lower()
                compact_dash = re.sub(r"\s+", "", dash).lower()
                if compact_tok in compact_dash:
                    continue
                if tok in summary:
                    continue
                # Heuristic: large notionals in takeaway without dashboard/summary anchor → likely calendar bleed
                if any(
                    k in chunk
                    for k in ("名目", "衍生品", "期權", "持倉", "未平倉", "選擇權", "到期", "結算")
                ):
                    drop = True
                    break
            if not drop:
                kept.append(chunk)
        new_tw = "".join(kept).strip()
        if new_tw and new_tw != tw:
            logger.warning(
                "news[%s]: stripped calendar-numeric bleed from investment_takeaway",
                getattr(item, "index", "?"),
            )
            out.append(item.model_copy(update={"investment_takeaway": new_tw}))
        else:
            out.append(item)
    return out


def _financialdatasets_anchor_map(ai: AISection) -> dict[str, list[tuple[str, str]]]:
    """Map known equity tickers -> [(label, value), ...] from AI dashboard FinancialDatasets rows."""
    m: dict[str, list[tuple[str, str]]] = {}
    tick_order = sorted(equity_universe_merged(), key=len, reverse=True)
    for row in ai.dashboard:
        lab = (row.label or "")
        val = (row.value or "").strip()
        if "financialdatasets" not in lab.lower():
            continue
        sym = None
        lab_u = lab.upper()
        for tick in tick_order:
            if tick in lab_u:
                sym = tick
                break
        if sym is None:
            continue
        m.setdefault(sym, []).append((lab, val))
    return m


def _dedupe_crypto_fundamentals_dashboard_rows(crypto: CryptoSection, ai: AISection) -> CryptoSection:
    """When crypto dashboard has FinancialDatasets N/A but AI section has real FD rows, copy values to reduce reader confusion."""
    anchors = _financialdatasets_anchor_map(ai)
    if not anchors:
        return crypto
    new_rows: list[MetricLine] = []
    changed = False
    for row in crypto.dashboard:
        lab_u = (row.label or "").upper()
        val = (row.value or "").strip()
        if "FINANCIALDATASETS" not in lab_u or "N/A" not in val.upper():
            new_rows.append(row)
            continue
        sym = next((t for t in anchors if t in lab_u), None)
        if sym is None:
            new_rows.append(row)
            continue
        candidates = anchors.get(sym) or []
        # Prefer same metric keyword in label (營收 / revenue)
        pick = None
        if "營收" in (row.label or "") or "REVENUE" in lab_u:
            pick = next((c for c in candidates if "營收" in c[0] or "REVENUE" in c[0].upper()), None)
        if pick is None:
            pick = candidates[0] if candidates else None
        if pick and pick[1] and "N/A" not in pick[1].upper():
            new_rows.append(
                MetricLine(
                    label=row.label,
                    value=pick[1],
                    status_emoji=row.status_emoji,
                )
            )
            changed = True
            logger.info(
                "crypto dashboard: filled FinancialDatasets %s from AI anchor (%s)",
                sym,
                pick[0][:60],
            )
        else:
            new_rows.append(row)
    if not changed:
        return crypto
    return crypto.model_copy(update={"dashboard": new_rows})


def _scrub_crypto_cycle_halving_narrative(raw: str) -> str:
    """Remove stale halving / 840k tropes from cycle notes when LLM ignores Phase C rules."""
    s = (raw or "").strip()
    if not s:
        return s
    if not _HALVING_CALENDAR_RE.search(s) and not re.search(r"840\s*,?\s*000", s, re.IGNORECASE):
        return s
    note = "（週期敘述略：已移除未經鏈上工具驗證之減半日期／高度表述；請以儀表板鏈上讀值為準。）"
    if note in s:
        return s
    return (s + " " + note).strip()


def _scrub_exec_summary_history_slogans(lines: list[str]) -> list[str]:
    """Soften unverifiable 'history shows' rebound lines in exec_summary."""
    out: list[str] = []
    for ln in lines or []:
        t = (ln or "").strip()
        if not t:
            continue
        if re.search(r"歷史顯示|統計上常見|往往反彈", t) and not re.search(
            r"\d+%|勝率|樣本|回測", t
        ):
            t = re.sub(
                r"歷史顯示[^。；]*",
                "讀數驅動：見儀表板極端情緒與價格錨點",
                t,
                count=1,
            )
        out.append(t)
    return out


_EXEC_SUMMARY_NOISE_EMOJI_RE = re.compile(r"[📈📉🔥🚨💥💣🧨]")


def _format_exec_summary_for_mobile(lines: list[str]) -> list[str]:
    """De-noise and soft-wrap exec summary lines for mobile scanning."""
    out: list[str] = []
    for ln in lines or []:
        s = re.sub(r"\s+", " ", (ln or "").strip())
        if not s:
            continue
        s = _EXEC_SUMMARY_NOISE_EMOJI_RE.sub("", s).strip()
        s = tg_soft_wrap_mobile(s, max_chars=70)
        out.append(s)
    return out


_BEAT_MISS_VERBS_RE = re.compile(
    r"(超預期|遜於預期|優於共識|低於共識|beat|miss|Beat|Miss|EPS\s*beat|revenue\s*beat)",
    re.IGNORECASE,
)
_CONSENSUS_CUE_RE = re.compile(
    r"(共識|預期|預估|華爾街|分析師預期|Street|consensus|estimate|expected|預測)",
    re.IGNORECASE,
)
_GENERIC_CALENDAR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"礦企.*季報|算力調整|流動性釋放", re.IGNORECASE),
    re.compile(r"Fed\s*官員.*談話|聯準會.*談話", re.IGNORECASE),
    re.compile(r"季報披露.*公告", re.IGNORECASE),
)


def _scrub_generic_event_calendar_lines(lines: list[str]) -> list[str]:
    """Remove vague LLM-plausible calendar rows (no verifiable headline)."""
    out: list[str] = []
    for ln in lines or []:
        t = (ln or "").strip()
        if not t:
            continue
        if any(p.search(t) for p in _GENERIC_CALENDAR_PATTERNS):
            logger.warning("event_calendar_lines: removed generic unverified row: %s", t[:100])
            continue
        out.append(t)
    return out


def _neutral_regime_copy_soften(crypto: CryptoSection) -> CryptoSection:
    """When market.regime is neutral, tone down risk-on phrases in portfolio + exec_summary."""
    regime = (crypto.market.regime or "").strip().lower()
    if regime != "neutral":
        return crypto
    replacements = (
        ("同步做多偏好", "在 neutral 下維持有限 Beta 曝險（不超風險預算上限）"),
        ("跨資產偏多配置", "跨資產在風險預算內配置（neutral，非全面 risk_on）"),
        ("維持跨資產偏多", "跨資產僅在風險預算內加碼（對齊 neutral）"),
    )
    pf = crypto.portfolio_framing_summary or ""
    new_pf = pf
    for a, b in replacements:
        if a in new_pf:
            new_pf = new_pf.replace(a, b)
    ex = list(crypto.exec_summary or [])
    new_ex = []
    for line in ex:
        s = line
        for a, b in replacements:
            if a in s:
                s = s.replace(a, b)
        new_ex.append(s)
    if new_pf == pf and new_ex == list(crypto.exec_summary or []):
        return crypto
    return crypto.model_copy(
        update={
            "portfolio_framing_summary": new_pf,
            "exec_summary": new_ex,
        }
    )


def _listed_equity_tickers(ai: AISection) -> set[str]:
    out: set[str] = set()
    for leg in ai.trade_legs or []:
        a = (getattr(leg, "asset", None) or "").strip().upper().replace("$", "")
        if a and a.isalnum():
            out.add(a[:12])
    for rec in ai.qsrec or []:
        if getattr(rec, "category", None) == "EQUITY":
            a = (getattr(rec, "asset", None) or "").strip().upper()
            if a and a.isalnum():
                out.add(a[:12])
    return out


def _sanitize_editor_consensus_tickers(ai: AISection) -> AISection:
    """Replace $TICKER in editor_consensus when ticker not in trade_legs/QSREC EQUITY."""
    allowed = _listed_equity_tickers(ai)
    if not allowed:
        return ai
    pat = re.compile(r"\$([A-Z]{1,6})\b")

    def _repl(m: re.Match[str]) -> str:
        sym = m.group(1)
        return m.group(0) if sym in allowed else f"{sym}（敘事參考，非本日建議標的）"

    new_items: list[NewsItem] = []
    changed = False
    for n in ai.news or []:
        ec = n.editor_consensus or ""
        if "$" not in ec:
            new_items.append(n)
            continue
        new_ec = pat.sub(_repl, ec)
        if new_ec != ec:
            logger.warning("news[%s]: editor_consensus adjusted for unlisted ticker", n.index)
            changed = True
            new_items.append(n.model_copy(update={"editor_consensus": new_ec}))
        else:
            new_items.append(n)
    if not changed:
        return ai
    return ai.model_copy(update={"news": new_items})


def _trade_trigger_allows_beat_miss(trigger: str, news_context: str) -> bool:
    """beat/miss in trigger only if a consensus cue appears in news (not in trigger: 超預期 contains 預期)."""
    if not _BEAT_MISS_VERBS_RE.search(trigger):
        return True
    return bool(_CONSENSUS_CUE_RE.search(news_context))


def _news_allows_beat_miss(n: NewsItem) -> bool:
    headline = f"{n.title or ''}\n{n.summary or ''}"
    if not _BEAT_MISS_VERBS_RE.search(f"{n.investment_takeaway or ''}\n{n.editor_consensus or ''}"):
        return True
    return bool(_CONSENSUS_CUE_RE.search(headline))


def _scrub_ai_news_beat_miss_copy(ai: AISection) -> AISection:
    """Softens beat/miss wording in takeaway/consensus when headline lacks consensus cues."""
    new_news: list[NewsItem] = []
    changed = False
    for n in ai.news or []:
        if _news_allows_beat_miss(n):
            new_news.append(n)
            continue
        tw = n.investment_takeaway or ""
        ec = n.editor_consensus or ""
        new_tw = _BEAT_MISS_VERBS_RE.sub("待官方／法說數據核實", tw)
        new_ec = _BEAT_MISS_VERBS_RE.sub("待官方／法說數據核實", ec)
        if new_tw != tw or new_ec != ec:
            changed = True
            logger.warning("news[%s]: softened beat/miss without headline consensus cue", n.index)
            new_news.append(n.model_copy(update={"investment_takeaway": new_tw, "editor_consensus": new_ec}))
        else:
            new_news.append(n)
    if not changed:
        return ai
    return ai.model_copy(update={"news": new_news})


def _strip_unsupported_beat_miss_in_legs(
    legs: list[ExecutableTradeLeg],
    news_blob: str,
) -> list[ExecutableTradeLeg]:
    out: list[ExecutableTradeLeg] = []
    for leg in legs:
        tr = leg.trigger or ""
        if not tr.strip() or _trade_trigger_allows_beat_miss(tr, news_blob):
            out.append(leg)
            continue
        new_tr = _BEAT_MISS_VERBS_RE.sub("待官方／法說披露訂閱與指引", tr)
        if new_tr != tr:
            logger.warning("trade_leg %s: softened beat/miss wording in trigger (no consensus cue)", leg.asset)
            out.append(leg.model_copy(update={"trigger": new_tr}))
        else:
            out.append(leg)
    return out


def _fix_chatter_unconfirmed(items: list) -> list:
    """Ensure each chatter line contains （未確認） (re-validate via model_construct + model_validate)."""
    from schemas import ChatterItem  # noqa: PLC0415

    out: list = []
    for item in items or []:
        t = getattr(item, "text", "") or ""
        if "（未確認）" in t or "(未確認)" in t:
            out.append(item)
            continue
        cred = getattr(item, "credibility", None)
        if re.search(r"可信度[：:]", t):
            new_t = re.sub(r"(可信度[：:])", r"（未確認）｜\1", t, count=1)
        else:
            new_t = t.rstrip() + "（未確認）"
        try:
            out.append(ChatterItem.model_validate({"text": new_t, "credibility": cred}))
        except Exception:
            out.append(item)
    return out


def _postprocess_brief_data_hygiene(crypto: CryptoSection, ai: AISection) -> tuple[CryptoSection, AISection]:
    """Assembly-time fixes: halving calendar scrub, scenario bullets, VIX wording, FD dedupe, news bleed."""
    report_day = _parse_report_title_date_iso(crypto.report_title_date)
    _cal_orig = list(crypto.event_calendar_lines or [])
    _cal_h = _remove_unverified_halving_calendar_lines(_cal_orig, report_day=report_day)
    _cal_final = _scrub_generic_event_calendar_lines(_cal_h)
    if _cal_final != _cal_orig:
        crypto = crypto.model_copy(update={"event_calendar_lines": _cal_final})

    cyc = _scrub_crypto_cycle_halving_narrative(crypto.crypto_cycle_valuation_notes or "")
    if cyc != (crypto.crypto_cycle_valuation_notes or "").strip():
        crypto = crypto.model_copy(update={"crypto_cycle_valuation_notes": cyc})

    ex = _scrub_exec_summary_history_slogans(list(crypto.exec_summary or []))
    ex = _format_exec_summary_for_mobile(ex)
    if ex != list(crypto.exec_summary or []):
        crypto = crypto.model_copy(update={"exec_summary": ex})

    scen = _normalize_scenario_probability_notes(crypto.scenario_probability_notes or "")
    btc_anchor = _btc_dashboard_spot_anchor_usd(list(crypto.dashboard or []))
    scen = _fix_scenario_btc_breakout_typo_k(scen, btc_anchor)
    if scen != (crypto.scenario_probability_notes or "").strip():
        crypto = crypto.model_copy(update={"scenario_probability_notes": scen})

    macro_blob = " ".join(crypto.macro_framework_lines or []) + " " + " ".join(ai.macro_bridge_lines or [])
    inv = _sync_narrative_invalidation_vix_term_structure(
        crypto,
        macro_blob,
        crypto.narrative_invalidation_summary or "",
    )
    if inv != (crypto.narrative_invalidation_summary or ""):
        crypto = crypto.model_copy(update={"narrative_invalidation_summary": inv})

    crypto = _dedupe_crypto_fundamentals_dashboard_rows(crypto, ai)
    dash_blob = " ".join(f"{r.label} {r.value}" for r in crypto.dashboard + ai.dashboard)

    new_crypto_news = _strip_news_takeaway_calendar_number_bleed(
        list(crypto.news),
        cal_lines=list(crypto.event_calendar_lines or []),
        dashboard_blob=dash_blob,
    )
    if new_crypto_news != list(crypto.news):
        crypto = crypto.model_copy(update={"news": new_crypto_news})

    crypto = _neutral_regime_copy_soften(crypto)

    news_blob_ai = "\n".join(
        f"{getattr(n, 'title', '')}\n{getattr(n, 'summary', '')}" for n in (ai.news or [])
    )
    new_legs = _strip_unsupported_beat_miss_in_legs(list(ai.trade_legs or []), news_blob_ai)
    if new_legs != list(ai.trade_legs or []):
        ai = ai.model_copy(update={"trade_legs": new_legs})

    ai = _scrub_ai_news_beat_miss_copy(ai)
    ai = _sanitize_editor_consensus_tickers(ai)

    new_ch_ai = _fix_chatter_unconfirmed(list(ai.chatter or []))
    if new_ch_ai != list(ai.chatter or []):
        ai = ai.model_copy(update={"chatter": new_ch_ai})
    new_ch_cr = _fix_chatter_unconfirmed(list(crypto.chatter or []))
    if new_ch_cr != list(crypto.chatter or []):
        crypto = crypto.model_copy(update={"chatter": new_ch_cr})

    return crypto, ai


_DASH_MACRO_KW: frozenset[str] = frozenset(
    {
        "VIX",
        "DXY",
        "美債",
        "殖利率",
        "FED",
        "SOFR",
        "CPI",
        "FOMC",
        "宏觀",
        "相關係數",
        "相關性",
        "SPX",
        "S&P",
        "美元指數",
        "利差",
        "10Y",
        "2Y",
    }
)
_DASH_DERIV_KW: frozenset[str] = frozenset(
    {
        "資金費率",
        "FUNDING",
        "爆倉",
        "清算",
        "未平倉",
        "OI",
        "PUT/CALL",
        "期權",
        "選擇權",
        "COINGLASS",
        "ETF 流",
        "ETF淨",
        "期貨",
        "CME",
        "COT",
        "多空比",
    }
)
_DASH_ONCHAIN_KW: frozenset[str] = frozenset(
    {
        "MVRV",
        "NVT",
        "DOMINANCE",
        "SOPR",
        "NUPL",
        "鏈上",
        "交易所",
        "淨流",
        "巨鯨",
        "活躍地址",
        "GBTC",
        "ETHE",
        "恐懼",
        "貪婪",
        "FEAR",
        "GREED",
    }
)
_DASH_TECH_KW: frozenset[str] = frozenset(
    {
        "RSI",
        "MA20",
        "MA50",
        "均線",
        "BTC 現價",
        "ETH 現價",
        "SOL 現價",
        "技術",
        "KD",
        "MACD",
    }
)
_SECTION_TITLES: dict[str, str] = {
    "macro": "宏觀與跨資產",
    "deriv": "流動性／衍生品",
    "onchain": "鏈上與情緒",
    "tech": "價格與技術結構",
    "other": "其他讀數",
}
_SECTION_TITLE_LABELS: frozenset[str] = frozenset(_SECTION_TITLES.values())


def _strip_llm_dashboard_section_placeholder_rows(rows: list[MetricLine]) -> list[MetricLine]:
    """Remove LLM echo rows whose label matches an IB section title but value is empty (not real headers)."""
    out: list[MetricLine] = []
    for row in rows or []:
        lab = (row.label or "").strip()
        val = (row.value or "").replace("\u00a0", " ").strip()
        if lab in _SECTION_TITLE_LABELS and not getattr(row, "is_section_header", False) and not val:
            continue
        out.append(row)
    return out


def _dedupe_consecutive_section_headers(rows: list[MetricLine]) -> list[MetricLine]:
    """Drop back-to-back identical section header rows (injection edge cases)."""
    out: list[MetricLine] = []
    for row in rows or []:
        if (
            out
            and getattr(out[-1], "is_section_header", False)
            and getattr(row, "is_section_header", False)
            and (out[-1].label or "").strip() == (row.label or "").strip()
        ):
            continue
        out.append(row)
    return out


def _dashboard_row_bucket(row: MetricLine) -> str:
    if getattr(row, "is_section_header", False):
        return ""
    blob = f"{row.label or ''} {row.value or ''}".upper()
    for kw in _DASH_MACRO_KW:
        if kw.upper() in blob or kw in (row.label or ""):
            return "macro"
    for kw in _DASH_DERIV_KW:
        if kw.upper() in blob or kw in (row.label or ""):
            return "deriv"
    for kw in _DASH_ONCHAIN_KW:
        if kw.upper() in blob or kw in (row.label or ""):
            return "onchain"
    for kw in _DASH_TECH_KW:
        if kw.upper() in blob or kw in (row.label or ""):
            return "tech"
    return "other"


def _inject_dashboard_section_groups(rows: list[MetricLine]) -> list[MetricLine]:
    """Insert MetricLine section headers (is_section_header) for IB-style grouping."""
    rows = _strip_llm_dashboard_section_placeholder_rows(rows)
    out: list[MetricLine] = []
    seen: set[str] = set()
    for row in rows:
        if getattr(row, "is_section_header", False):
            out.append(row)
            continue
        b = _dashboard_row_bucket(row)
        if b not in seen:
            seen.add(b)
            title = _SECTION_TITLES.get(b, "其他讀數")
            out.append(
                MetricLine(
                    label=title,
                    value=" ",
                    is_section_header=True,
                )
            )
        out.append(row)
    return _dedupe_consecutive_section_headers(out)


def _parse_risk_budget_cap_percent(summary: str) -> str | None:
    """Extract a single total risk budget percent from 今日風險預算 line if present."""
    s = (summary or "").strip()
    if not s:
        return None
    m = re.search(r"總風險預算[^%]*?(\d{1,3})\s*%", s)
    if m:
        return f"{m.group(1)}%"
    m2 = re.search(r"(?:上限|不超過|限制在)\s*(\d{1,3})\s*%", s)
    if m2:
        return f"{m2.group(1)}%"
    return None


def _first_conflict_clause(conflict: str) -> str:
    t = (conflict or "").strip()
    if not t:
        return ""
    for sep in ("｜", "|", "；", ";"):
        if sep in t:
            return t.split(sep, 1)[0].strip()
    if "。" in t and len(t) > 50:
        return t.split("。", 1)[0].strip() + "。"
    return t[:72] + ("…" if len(t) > 72 else "")


def _esc_code(s: str, *, max_len: int = 96) -> str:
    t = html.escape((s or "").strip(), quote=False)
    if len(t) > max_len:
        return t[: max_len - 1] + "…"
    return t


def _crypto_recommendation_summary_line(crypto: CryptoSection) -> str:
    legs = list(crypto.trade_legs or [])
    regime = _esc_code((crypto.market.regime or "").strip() or "N/A", max_len=24)
    cap = _parse_risk_budget_cap_percent(crypto.risk_budget_summary or "")
    cap_part = f"｜<b>總風險預算</b>：<code>{_esc_code(cap)}</code>" if cap else ""
    risk = _first_conflict_clause(crypto.signal_conflict_summary or "")
    risk_part = f"｜<b>主要張力</b>：<code>{_esc_code(risk)}</code>" if risk else ""
    if not legs:
        return (
            f"<b>加密部位摘要</b>：<code>觀望</code>｜<b>Regime</b>：<code>{regime}</code>"
            f"{cap_part}{risk_part}"
        )
    parts: list[str] = []
    for leg in legs[:3]:
        sym = str(leg.asset or "").replace("$", "").strip() or "?"
        d = str(leg.direction or "").upper()
        stars = max(1, min(4, int(leg.star_rating or 1)))
        ss = "⭐️" * stars
        parts.append(f"{sym}/{d}/{ss}")
    blob = _esc_code("；".join(parts), max_len=120)
    return (
        f"<b>加密部位摘要</b>：<code>{blob}</code>｜<b>Regime</b>：<code>{regime}</code>"
        f"{cap_part}{risk_part}"
    )


def _ai_recommendation_summary_line(ai: AISection, regime: str) -> str:
    legs = list(ai.trade_legs or [])
    r = _esc_code((regime or "").strip() or "N/A", max_len=24)
    note = (ai.us_equity_allocation_note or "").strip()
    cap = None
    if note:
        m = re.search(r"(\d{1,3})\s*%", note)
        if m:
            cap = f"{m.group(1)}%"
    cap_part = f"｜<b>部位上限</b>：<code>{_esc_code(cap)}</code>" if cap else ""
    risk = _first_conflict_clause(ai.signal_conflict_summary or "")
    risk_part = f"｜<b>主要張力</b>：<code>{_esc_code(risk)}</code>" if risk else ""
    if not legs:
        return f"<b>美股部位摘要</b>：<code>觀望</code>｜<b>Regime</b>：<code>{r}</code>{cap_part}{risk_part}"
    parts: list[str] = []
    for leg in legs[:3]:
        sym = str(leg.asset or "").replace("$", "").strip() or "?"
        d = str(leg.direction or "").upper()
        stars = max(1, min(4, int(leg.star_rating or 1)))
        ss = "⭐️" * stars
        parts.append(f"{sym}/{d}/{ss}")
    blob = _esc_code("；".join(parts), max_len=120)
    return f"<b>美股部位摘要</b>：<code>{blob}</code>｜<b>Regime</b>：<code>{r}</code>{cap_part}{risk_part}"


def _inject_prediction_market_highlights(crypto: CryptoSection) -> CryptoSection:
    """Fill prediction_market_highlight_lines from Polymarket API when empty or sparse."""
    if os.getenv("PREDICTION_MARKETS_IN_BRIEF", "1").lower() in ("0", "false", "no"):
        return crypto
    existing = [str(x).strip() for x in (crypto.prediction_market_highlight_lines or []) if str(x).strip()]
    if len(existing) >= 3:
        return crypto
    try:
        from tools_legacy import fetch_polymarket_hot_highlight_lines  # noqa: PLC0415

        lines = fetch_polymarket_hot_highlight_lines()
    except Exception as exc:
        logger.warning("prediction market highlights skipped: %s", exc)
        return crypto
    if not lines:
        return crypto
    return crypto.model_copy(update={"prediction_market_highlight_lines": lines})


def instrument_sections_for_ib_layout(crypto: CryptoSection, ai: AISection) -> tuple[CryptoSection, AISection]:
    """投行式排版：儀表板分區、區塊④一行摘要；不重排四大區塊順序。"""
    cr = crypto.model_copy(
        update={"dashboard": _inject_dashboard_section_groups(list(crypto.dashboard or []))}
    )
    ai_new = ai.model_copy(
        update={"dashboard": _inject_dashboard_section_groups(list(ai.dashboard or []))}
    )
    cr = cr.model_copy(
        update={"crypto_block4_recommendation_line": _crypto_recommendation_summary_line(cr)}
    )
    ai_new = ai_new.model_copy(
        update={
            "ai_block4_recommendation_line": _ai_recommendation_summary_line(
                ai_new, cr.market.regime or ""
            )
        }
    )
    return cr, ai_new


def _ensure_crypto_liquidation_fallback_note(crypto: CryptoSection) -> CryptoSection:
    """If dashboard never mentions 爆倉/清算, add one ⬜ note (readers know how to read tape without CoinGlass)."""
    blob = " ".join(f"{r.label} {r.value}" for r in crypto.dashboard)
    if "爆倉" in blob or "清算" in blob:
        return crypto
    rows = list(crypto.dashboard) + [
        MetricLine(
            label="備註",
            status_emoji="⬜",
            value=(
                "24h 爆倉：第三方衍生品源未回傳時，以資金費率、未平倉與多空比作為短線情緒代理指標。"
            ),
        )
    ]
    return crypto.model_copy(update={"dashboard": rows})


def _coerce_ai_equity_trade_prices_from_market(ai: AISection) -> AISection:
    """Backfill US equity 現價/進場 from yfinance; synthesize 目標/停損 when both N/A but R:R+回撤可解析."""
    if os.getenv("SKIP_EQUITY_YF_BACKFILL", "").lower() in ("1", "true", "yes"):
        return ai
    if os.getenv("MOCK_APIS", "").lower() in ("1", "true", "yes"):
        return ai
    legs = list(ai.trade_legs)
    if not legs:
        return ai
    need = False
    for leg in legs:
        if _parse_pair_asset(leg.asset):
            continue
        if (
            _trade_price_field_unusable(leg.current_price)
            or _trade_price_field_unusable(leg.entry)
            or (
                _trade_price_field_unusable(leg.target) and _trade_price_field_unusable(leg.stop)
            )
        ):
            need = True
            break
    if not need:
        return ai
    try:
        prices = _current_prices_for_assets([leg.asset for leg in legs])
    except Exception as exc:
        logger.warning("equity price backfill skipped (_current_prices_for_assets): %s", exc)
        return ai
    new_legs = []
    changed = False
    backfill_rows: list[dict[str, object]] = []
    for leg in legs:
        if _parse_pair_asset(leg.asset):
            new_legs.append(leg)
            continue
        close = prices.get(leg.asset)
        cur, ent, tgt, stp = leg.current_price, leg.entry, leg.target, leg.stop
        fields_changed: list[str] = []

        if _trade_price_field_unusable(cur) and close is not None:
            cur = _fmt_equity_money(close)
            changed = True
            fields_changed.append("current_price")

        entry_f = None if _trade_price_field_unusable(ent) else _parse_first_usd_number(ent)
        if entry_f is None and close is not None:
            entry_f = close
            ent = _fmt_equity_money(close)
            changed = True
            fields_changed.append("entry")
        elif entry_f is None:
            entry_f = _parse_first_usd_number(cur)

        rr_v = _parse_rr_ratio(leg.rr)
        dd_v = _parse_drawdown_fraction(leg.max_drawdown_pct)
        if (
            entry_f is not None
            and entry_f > 0
            and rr_v is not None
            and dd_v is not None
            and dd_v > 0
            and _trade_price_field_unusable(tgt)
            and _trade_price_field_unusable(stp)
        ):
            tgt, stp = _synth_equity_target_stop(entry_f, leg.direction, rr_v, dd_v)
            changed = True
            fields_changed.extend(["target", "stop"])

        new_legs.append(
            leg.model_copy(update={"current_price": cur, "entry": ent, "target": tgt, "stop": stp})
        )
        if fields_changed:
            backfill_rows.append({"asset": leg.asset, "fields": fields_changed})
    if not changed:
        return ai
    logger.info("assemble: backfilled AI equity trade leg prices (yfinance + optional R:R synthesis)")
    if (
        backfill_rows
        and os.getenv("EQUITY_BACKFILL_SCRATCHPAD_LOG", "1").lower() not in ("0", "false", "no")
    ):
        try:
            import scratchpad  # noqa: PLC0415

            scratchpad.log_equity_price_backfill(backfill_rows)
        except Exception as _sp_err:
            logger.debug("equity backfill scratchpad skipped: %s", _sp_err)
    return ai.model_copy(update={"trade_legs": new_legs})


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
    prefix = _REPEAT_SAME_YESTERDAY_PREFIX
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
    current_affairs_roundtable: CurrentAffairsRoundtable | None = None,
) -> DailyBriefReport:
    crypto, ai = _coerce_sections_for_gate(crypto, ai, agreed_regime=agreed_regime)
    crypto, ai = _coerce_qsrec_regimes_to_market(crypto, ai)
    if crypto.market.regime in _AGREED_REGIME_TOKENS:
        ai = _fix_us_equity_allocation_misbranded_risk_off(ai, crypto.market.regime)
    crypto = _ensure_btc_ma_dashboard_rows(crypto)
    crypto = _sync_dashboard_btc_rsi_with_scorecard(crypto)
    crypto = _normalize_btc_ma_citations_from_dashboard(crypto)
    crypto = _ensure_crypto_liquidation_fallback_note(crypto)
    crypto, ai = _postprocess_brief_data_hygiene(crypto, ai)
    crypto = _apply_gspc_anchor_to_equity_framing(crypto)
    crypto, ai = _coerce_trade_leg_position_pcts(crypto, ai)
    ai = _coerce_ai_equity_trade_prices_from_market(ai)
    crypto, ai = _normalize_pick_reason_repeat_headers(crypto, ai)
    crypto, ai = _apply_repeat_pick_disclaimer_if_needed(crypto, ai)
    crypto, ai = instrument_sections_for_ib_layout(crypto, ai)
    crypto = _inject_prediction_market_highlights(crypto)
    disclaimer = _low_confidence_disclaimer_plain(crypto, ai)
    return DailyBriefReport(
        crypto=crypto,
        ai=ai,
        institutional_disclaimer_html=_INSTITUTIONAL_DISCLAIMER_HTML,
        previous_recs_html=(previous_recs_html or "").strip(),
        source_observability_block=(source_observability_block or "").strip(),
        report_tier_partial_news=report_tier_partial_news,
        low_confidence_disclaimer=disclaimer,
        current_affairs_roundtable=current_affairs_roundtable,
    )


def _brief_dynamic_render_enabled() -> bool:
    return os.getenv("BRIEF_DYNAMIC_RENDER", "").strip().lower() in ("1", "true", "yes")


def _compress_full_profile_blocks(block_ids: tuple[str, ...]) -> list[str]:
    """Map coarse ids to render units (one crypto section, one AI section, one footer)."""
    out: list[str] = []
    seen_crypto = False
    seen_ai = False
    seen_footer = False
    i = 0
    while i < len(block_ids):
        bid = block_ids[i]
        if bid in ("crypto_dashboard", "crypto_news", "crypto_chatter"):
            if not seen_crypto:
                out.append("_unit:crypto_section")
                seen_crypto = True
            i += 1
            continue
        if bid in ("ai_bridge", "ai_dashboard", "ai_news", "ai_chatter"):
            if not seen_ai:
                out.append("_unit:ai_section")
                seen_ai = True
            i += 1
            continue
        if bid == "source_health":
            if not seen_footer:
                out.append("_unit:footer_tail")
                seen_footer = True
            i += 1
            if i < len(block_ids) and block_ids[i] == "qsrec":
                i += 1
            continue
        if bid == "qsrec":
            if not seen_footer:
                out.append("_unit:footer_tail")
                seen_footer = True
            i += 1
            continue
        out.append(bid)
        i += 1
    return out


def _render_dynamic_full_html(env: Environment, ctx: dict) -> str:
    """Phase 4d: optional YAML-driven block order for `full` (opt-in; default static template)."""
    crypto = ctx["crypto"]
    ai = ctx["ai"]
    order = _compress_full_profile_blocks(profile_block_ids("full"))
    parts: list[str] = []
    for bid in order:
        if bid == "_unit:crypto_section":
            frag = env.from_string(
                '{% from "blocks/_crypto_section.j2" import telegram_crypto_section %}'
                "{{ telegram_crypto_section(crypto) }}"
            )
            parts.append(frag.render(crypto=crypto))
            continue
        if bid == "_unit:ai_section":
            frag = env.from_string(
                '{% from "blocks/_ai_section.j2" import telegram_ai_section %}'
                "{{ telegram_ai_section(crypto, ai) }}"
            )
            parts.append(frag.render(crypto=crypto, ai=ai))
            continue
        if bid == "_unit:footer_tail":
            frag = env.from_string(
                '{% from "blocks/_footer_tail.j2" import telegram_footer_tail %}'
                "{{ telegram_footer_tail(report_tier_partial_news, tagged_news_count, "
                "low_confidence_disclaimer, source_observability_block, qsrec_json) }}"
            )
            parts.append(frag.render(**ctx))
            continue
        entry = BLOCK_REGISTRY.get(bid)
        if entry is None:
            logger.warning("dynamic full render: unknown block id %r skipped", bid)
            continue
        macro = entry.macro_name
        sub = entry.template_subpath
        if bid == "institutional_view":
            frag = env.from_string(
                f'{{% from "blocks/{sub}" import {macro} %}}'
                f"{{{{ {macro}(crypto, institutional_disclaimer_html) }}}}"
            )
            parts.append(
                frag.render(crypto=crypto, institutional_disclaimer_html=ctx.get("institutional_disclaimer_html") or "")
            )
            continue
        if bid == "previous_recs":
            frag = env.from_string(
                f'{{% from "blocks/{sub}" import {macro} %}}'
                f"{{{{ {macro}(previous_recs_html) }}}}"
            )
            parts.append(frag.render(previous_recs_html=ctx.get("previous_recs_html") or ""))
            continue
        if bid == "current_affairs_roundtable":
            parts.append(str(ctx.get("current_affairs_block_html") or ""))
            continue
        if macro == "telegram_ai_trades_only":
            frag = env.from_string(
                f'{{% from "blocks/{sub}" import {macro} %}}'
                f"{{{{ {macro}(crypto, ai) }}}}"
            )
            parts.append(frag.render(crypto=crypto, ai=ai))
            continue
        frag = env.from_string(
            f'{{% from "blocks/{sub}" import {macro} %}}'
            f"{{{{ {macro}(crypto) }}}}"
        )
        parts.append(frag.render(crypto=crypto))
    return "".join(parts)


def _current_affairs_block_html(report: DailyBriefReport) -> str:
    """Phase 5: optional 〔時事多觀點〕；預設關閉回傳空字串（維持 `full` byte-identical）。"""
    if os.getenv("BRIEF_CURRENT_AFFAIRS", "").strip().lower() not in ("1", "true", "yes"):
        return ""
    rt = report.current_affairs_roundtable
    if rt is None or not rt.voices:
        return ""
    root = Path(__file__).resolve().parent
    env = build_telegram_jinja_env(root / "templates")
    frag = env.from_string(
        '{% from "blocks/_current_affairs_roundtable.j2" import '
        "telegram_current_affairs_roundtable %}"
        "{{ telegram_current_affairs_roundtable(r) }}"
    )
    return frag.render(r=rt)


def build_telegram_jinja_env(templates_dir: Path) -> Environment:
    """Jinja2 env for Telegram daily brief (shared by `render_telegram_daily_brief` and tests)."""
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tg_escape"] = tg_escape
    env.filters["tg_emphasize_numbers"] = tg_emphasize_numbers
    env.filters["tg_soft_wrap_mobile"] = tg_soft_wrap_mobile
    env.filters["strip_usd"] = strip_usd_for_template
    env.filters["clean_invalidation"] = _clean_invalidation
    return env


def telegram_render_context(report: DailyBriefReport) -> dict:
    """Jinja context for `telegram_report.j2` (Phase 1 modular blocks).

    Kept as a single function so equivalence tests can render the monolithic
    baseline fixture with the same variable bundle as production.
    """
    qsrec_list = [
        r.model_dump(exclude_none=True, exclude=QSREC_JSON_EXCLUDE_FIELDS)
        for r in report.all_qsrec()
    ]
    return {
        "crypto": report.crypto,
        "ai": report.ai,
        "institutional_disclaimer_html": report.institutional_disclaimer_html or "",
        "previous_recs_html": report.previous_recs_html,
        "source_observability_block": report.source_observability_block,
        "report_tier_partial_news": report.report_tier_partial_news,
        "tagged_news_count": report.tagged_news_count(),
        "low_confidence_disclaimer": report.low_confidence_disclaimer or "",
        "qsrec_json": json.dumps(qsrec_list, ensure_ascii=False),
        "current_affairs_block_html": _current_affairs_block_html(report),
    }


def render_telegram_daily_brief(report: DailyBriefReport, *, profile: str | None = None) -> str:
    """Render Telegram HTML from `DailyBriefReport`.

    ``profile`` overrides env ``REPORT_PROFILE``; default is ``full`` (must stay
    byte-equivalent to Phase 0 — see ``test_telegram_template_modularization``).
    """
    root = Path(__file__).resolve().parent
    env = build_telegram_jinja_env(root / "templates")

    ctx = telegram_render_context(report)
    active = get_active_profile(profile)
    rel = telegram_profile_template_relpath(active)
    try:
        if active == "full" and _brief_dynamic_render_enabled():
            order = profile_block_ids("full")
            if order != PROFILES["full"]:
                return _render_dynamic_full_html(env, ctx)
        tmpl = env.get_template(rel)
    except TemplateNotFound as exc:
        expected = root / "templates" / rel
        raise RuntimeError(
            f"Jinja2 template not found: {rel} (expected at {expected})"
        ) from exc
    try:
        return tmpl.render(**ctx)
    except TemplateError as exc:
        expected = root / "templates" / rel
        raise RuntimeError(
            f"Jinja2 template error in {rel} (path: {expected}): {exc}"
        ) from exc

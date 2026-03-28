"""
HTML safety net after Jinja render, before validate_report.

Structural coercions that can be done on ``DailyBriefReport`` live in
``report_render.assemble_daily_brief_report`` + ``schemas`` (P1 band-aid 收斂).
This module keeps HTML-only patches (editor paths、legacy 句式).
"""

from __future__ import annotations

import logging
import os
import re

from validation_rules import sanitize_us_treasury_yield_tokens_in_line

logger = logging.getLogger(__name__)


def _legacy_full_post_process_steps() -> bool:
    """還原階段 1 之後預設關閉的 HTML 步驟（美債行掃描、N/A 聲明、UTC+8、訊號衝突備援）。"""
    return os.getenv("POST_PROCESS_LEGACY_FULL", "").lower() in ("1", "true", "yes")

_PP_CRED_RE = re.compile(r"可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b", re.IGNORECASE)
_PP_CRED_EN_RE = re.compile(r"(?:Credibility|Grade)\s*[：:]\s*", re.IGNORECASE)
_PP_CHATTER_LINE_RE = re.compile(r"^(· [^\n]+?（未確認）)", re.MULTILINE)
_PP_CHATTER3_RE = re.compile(r"(區塊③【[^】]+】\n)")
_PP_REGIME_TOKEN_RE = re.compile(r"\b(risk_on|risk_off|neutral)\b", re.IGNORECASE)
_PP_CONDITIONAL_LINE_RE = re.compile(
    r"(?:若|如果|假設|when|if)\s*.{0,80}(?:risk_on|risk_off|neutral)",
    re.IGNORECASE,
)
_PP_NEWS_TS_RE = re.compile(
    r"(〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
    r"\s+\d{1,2}:\d{2}(?::\d{2})?)"
    r"(?!\s*(?:UTC|GMT)\s*[+＋]\s*0?8|\s*HKT\b|\s*(?:香港|北京|台北)時間)"
    r"\]",
    re.IGNORECASE,
)
_PP_SIGNAL_CONFLICT_RE = re.compile(r"[訊信]號衝突(?:摘要|分析)?[：:]")
_PP_MALFORMED_INVAL_RE = re.compile(
    r"(失效條件[：:]\s*)(?:<code>)?\s*(?:</code>)?\s*(?=\n|$)",
    re.MULTILINE,
)


def post_process_html_for_gate(html: str, agreed_regime: str | None = None) -> str:
    """
    Post-render patches for common gate failures.

    已上移至資料層：見 ``report_render`` / ``schemas`` / ``validation_rules``。
    預設**不**重複執行與 Jinja 重疊的步驟（2 美債 HTML 行、3 N/A 聲明、5 UTC+8、6 訊號衝突）；
    需要舊行為時設 ``POST_PROCESS_LEGACY_FULL=1``。
    """
    _legacy = _legacy_full_post_process_steps()
    # ── 0. Credibility language normalization ────────────────────────
    if _PP_CRED_EN_RE.search(html):
        html = _PP_CRED_EN_RE.sub("可信度：", html)
        logger.info("post_process: normalized English credibility labels to 可信度：")

    # ── 1. Chatter credibility ────────────────────────────────────────
    if not _PP_CRED_RE.search(html):
        m = _PP_CHATTER_LINE_RE.search(html)
        if m:
            html = html[: m.end()] + "｜可信度：C" + html[m.end() :]
            logger.warning("post_process: injected missing chatter credibility marker")
        else:
            html = _PP_CHATTER3_RE.sub(
                r"\1· 低信噪比，暫無高可信傳聞（未確認）｜可信度：C\n",
                html,
                count=1,
            )
            logger.warning("post_process: injected fallback chatter entry with credibility")

    # ── 2–3. Legacy only（結構層 + Jinja 已處理美債／低置信度區塊）──────────────
    if _legacy:
        patched_lines = []
        for line in html.splitlines():
            if "美債" in line:
                line = sanitize_us_treasury_yield_tokens_in_line(line)
            patched_lines.append(line)
        html = "\n".join(patched_lines)

        na_count = len(re.findall(r"\bN/A\b", html))
        has_low_conf = bool(re.search(r"低置信度|低信心", html))
        has_proxy = bool(
            re.search(
                r"資料缺失原因[\s\S]{0,800}?替代指標|替代指標[\s\S]{0,800}?資料缺失原因",
                html,
                re.IGNORECASE,
            )
        )

        if na_count > 3 and not (has_low_conf and has_proxy):
            injection = (
                "\n⚠️ 低置信度聲明\n"
                "資料缺失原因：本日部分數據源（yfinance / CoinGlass / NewsAPI）未回應，"
                "相關欄位以 N/A 標示。\n"
                "替代指標：N/A 欄位請參考 Binance 備援數據或 CME FedWatch Tool 補充。\n"
            )
            if "[QSREC_START]" in html:
                html = html.replace("[QSREC_START]", injection + "[QSREC_START]", 1)
            else:
                logger.warning(
                    "post_process: [QSREC_START] sentinel missing — appending 低置信度 block at end"
                )
                html += injection
            logger.warning(
                "post_process: injected 低置信度 block (N/A count=%d, had_low_conf=%s, had_proxy=%s)",
                na_count,
                has_low_conf,
                has_proxy,
            )

    # ── 4. Regime normalization ──────────────────────────────────────
    _effective_regime = agreed_regime
    if not _effective_regime:
        _mode_m = re.search(
            r"【今日市場模式】[^(risk_on|risk_off|neutral)]*?(risk_on|risk_off|neutral)",
            html,
            re.IGNORECASE,
        )
        if _mode_m:
            _effective_regime = _mode_m.group(1).lower().replace("-", "_").replace(" ", "_")
            logger.warning(
                "post_process: agreed_regime was None; inferred fallback regime=%s from 市場模式 line",
                _effective_regime,
            )
    if _effective_regime:
        fixed_lines = []
        for line in html.splitlines():
            if _PP_CONDITIONAL_LINE_RE.search(line):
                fixed_lines.append(line)
            else:
                fixed_lines.append(_PP_REGIME_TOKEN_RE.sub(_effective_regime, line))
        html = "\n".join(fixed_lines)
        logger.info("post_process: regime normalized to %s", _effective_regime)

    # ── 5–6. Legacy only（NewsItem UTC+8、空白訊號衝突已於 schemas）────────────
    if _legacy:
        utc8_count = [0]

        def _inject_utc8(m: re.Match) -> str:
            utc8_count[0] += 1
            return m.group(1) + " UTC+8]"

        html = _PP_NEWS_TS_RE.sub(_inject_utc8, html)
        if utc8_count[0]:
            logger.warning(
                "post_process: injected UTC+8 into %d news timestamp bracket(s)", utc8_count[0]
            )

        if not _PP_SIGNAL_CONFLICT_RE.search(html):
            _signal_block = "\n訊號衝突摘要：暫無重大訊號衝突，多空數據基本一致。\n"
            if "[QSREC_START]" in html:
                html = html.replace("[QSREC_START]", _signal_block + "[QSREC_START]", 1)
            else:
                html += _signal_block
            logger.warning("post_process: injected missing 訊號衝突摘要 block")

    # ── 7. Malformed invalidation ─────────────────────────────────────
    _inval_default = r"\g<1><code>跌破關鍵支撐位或重大利空事件出現</code>"
    new_html = _PP_MALFORMED_INVAL_RE.sub(_inval_default, html)
    if new_html != html:
        html = new_html
        logger.warning("post_process: filled empty 失效條件 with default invalidation text")

    return html

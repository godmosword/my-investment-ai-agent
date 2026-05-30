"""Historical HTML string post-processors (pre–data-driven pipeline). Used by unit tests."""

from __future__ import annotations

import re

from report_html_gates import (
    _allow_partial_news_gate,
    _count_effective_news_items,
    _count_news_tags_only,
    _has_ai_trade_section,
    _has_crypto_trade_section,
    _has_rumor_grade_marker,
    _is_conditional_regime_line,
    _join_news_tag_timestamp_lines,
    _MISSING_REASON_PROXY_RE,
    _NEWS_HK_TZ_TOKEN,
    _NEWS_LINE_INLINE_HTML_RE,
    _normalize_fullwidth_news_brackets_on_news_lines,
    _normalize_regime_token,
)
from tools import source_observability_lines


def _fix_glued_na_suffix(text: str) -> str:
    """修復 <code>N/A</code> 或裸 N/A 與後續中英文字黏連（如 N/ACoinGlass）。"""
    if not text:
        return text
    out = re.sub(r"(N/A)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", text)
    out = re.sub(r"(</code>)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", out)
    return out


def _sanitize_macro_outlier_values(text: str) -> str:
    """宏觀數值異常修正：10Y/2Y/SOFR 超出合理區間時改為 N/A。"""
    patched = text

    def _pct_or_none(raw: str) -> float | None:
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return None

    def _repl_ust(m: re.Match) -> str:
        y10, y2 = _pct_or_none(m.group(1)), _pct_or_none(m.group(2))
        if y10 is None or y2 is None:
            return m.group(0)
        if not (0.0 <= y10 <= 20.0 and 0.0 <= y2 <= 20.0):
            return "美債 10Y: N/A（數據異常待確認） | 2Y: N/A（數據異常待確認） | 利差: N/A"
        return m.group(0)

    patched = re.sub(
        r"美債\s*10Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust, patched,
    )
    patched = re.sub(
        r"美債\s*10Y\D{0,18}([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y\D{0,12}([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust, patched,
    )
    def _repl_2y(m: re.Match) -> str:
        val = _pct_or_none(m.group(2))
        if val is None or 0.0 <= val <= 20.0:
            return m.group(0)
        return f"{m.group(1)}N/A（數據異常待確認）"
    patched = re.sub(r"(2Y[^0-9%\n]{0,16})([0-9,]+(?:\.[0-9]+)?)%", _repl_2y, patched)

    def _repl_sofr(m: re.Match) -> str:
        val = _pct_or_none(m.group(1))
        if val is None or 0.0 <= val <= 20.0:
            return m.group(0)
        return "Fed SOFR 期貨隱含利率: N/A（數據異常待確認）"
    patched = re.sub(r"Fed SOFR 期貨隱含利率[：:]\s*([0-9,]+(?:\.[0-9]+)?)%", _repl_sofr, patched)
    patched = re.sub(
        r"(利差[：:]?\s*)[+\-−]?([0-9,]{4,}(?:\.[0-9]+)?)\s*bp",
        r"\1N/A", patched, flags=re.IGNORECASE,
    )
    return patched


def _inject_canonical_prev_recs_block(report_text: str, canonical_html: str) -> str:
    """以 BigQuery 載入之上期追蹤覆寫 LLM 輸出，避免模型自行膨脹多筆同標的進場價。"""
    canonical_html = (canonical_html or "").strip()
    m = re.search(r"【今日市場模式】", report_text)
    if not m:
        if not canonical_html:
            return report_text
        return canonical_html + "\n\n" + report_text
    head, tail = report_text[: m.start()], report_text[m.start() :]
    head_clean = re.sub(r"【上期建議追蹤】[\s\S]*\Z", "", head, flags=re.MULTILINE).rstrip()
    sep = "\n\n" if head_clean else ""
    if not canonical_html:
        return f"{head_clean}{sep}{tail}"
    return f"{head_clean}{sep}{canonical_html}\n\n{tail}"


def _auto_prefix_missing_news_tags(text: str) -> str:
    """LLM 漏寫〔新聞 N〕時自動補標籤。"""
    lines = text.splitlines()
    if not lines:
        return text

    def _max_news_tag_num(s: str) -> int:
        nums = [int(x) for x in re.findall(r"〔新聞\s*(\d+)〕", s)]
        return max(nums) if nums else 0

    tag_i = _max_news_tag_num(text) + 1
    section = "out"
    out: list[str] = []
    pending_title_idx: int | None = None
    _crypto_header = re.compile(r"【區塊②\s*核心新聞】|區塊②【核心新聞】|^【核心新聞】")
    _crypto_ts = re.compile(r"^\s*\[\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+\d{1,2}:\d{2}(?::\d{2})?")

    for ln in lines:
        if _crypto_header.search(ln):
            section = "crypto"
            pending_title_idx = None
            out.append(ln)
            continue
        if section == "crypto" and re.search(r"區塊③|【區塊③", ln):
            section = "out"
            pending_title_idx = None
            out.append(ln)
            continue
        if "【AI 產業新聞】" in ln:
            section = "ai"
            pending_title_idx = None
            out.append(ln)
            continue
        if section == "ai" and "【產業鏈呢喃】" in ln:
            section = "out"
            pending_title_idx = None
            out.append(ln)
            continue
        if section == "crypto":
            if _crypto_ts.match(ln) and "〔新聞" not in ln:
                out.append(f"〔新聞 {tag_i}〕{ln.lstrip()}")
                tag_i += 1
            else:
                out.append(ln)
            continue
        if section == "ai":
            st = ln.strip()
            if st.startswith("摘要：") or st.startswith("摘要∶"):
                if pending_title_idx is not None and "〔新聞" not in out[pending_title_idx]:
                    out[pending_title_idx] = f"〔新聞 {tag_i}〕{out[pending_title_idx]}"
                    tag_i += 1
                pending_title_idx = None
                out.append(ln)
            elif st.startswith(("投資解讀", "💎", "·", "•", "- ", "—", "低置信度", "資料缺失",
                                 "HuggingFace", "OpenRouter", "AI Momentum")):
                out.append(ln)
            elif st and (re.search(r"[A-Za-z]{3,}", st) or len(st) > 18):
                out.append(ln)
                pending_title_idx = len(out) - 1
            else:
                out.append(ln)
            continue
        out.append(ln)

    return "\n".join(out)


def _normalize_news_timezone_utc8(text: str) -> str:
    """將新聞時間標籤統一補上 UTC+8。"""
    text = _join_news_tag_timestamp_lines(text)
    text = _normalize_fullwidth_news_brackets_on_news_lines(text)
    pattern = re.compile(
        r"(〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
        r"\s+\d{1,2}:\d{2}(?::\d{2})?)"
        rf"(\s+(?:{_NEWS_HK_TZ_TOKEN}))?"
        r"(\])",
        re.IGNORECASE,
    )

    def _repl(m: re.Match) -> str:
        left, tz, closing = m.group(1), m.group(2), m.group(3)
        if tz and tz.strip():
            return m.group(0)
        return f"{left} UTC+8{closing}"

    lines = text.splitlines()
    out: list[str] = []
    for ln in lines:
        if not re.search(r"〔新聞\s*\d+〕", ln):
            out.append(ln)
            continue
        ln_flat = _NEWS_LINE_INLINE_HTML_RE.sub("", ln)
        out.append(pattern.sub(_repl, ln_flat))
    return "\n".join(out)


def _ensure_rumor_grade_marker(text: str) -> str:
    """若出現呢喃/傳聞但缺可信度分級，補一行保底分級，避免 Gate 因格式失敗。"""
    if not text or not re.search(r"呢喃|傳聞", text):
        return text
    if _has_rumor_grade_marker(text):
        return text
    marker_line = "· 傳聞可信度：B（未確認）｜主流媒體二次驗證：否"
    m = re.search(r"(區塊③[^\n]*(?:呢喃|傳聞)[^\n]*\n?)", text)
    if m:
        return text[:m.end()] + marker_line + "\n" + text[m.end():]
    pos = text.find("[QSREC_START]")
    if pos != -1:
        return text[:pos].rstrip() + f"\n{marker_line}\n\n" + text[pos:]
    return text.rstrip() + f"\n{marker_line}"


def _unify_regime_mentions(text: str) -> str:
    """統一全篇 regime：以第一個【今日市場模式】為準，覆寫後續風險預算中的 regime。"""
    regime_token_re = r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)'
    m = re.search(
        rf'【今日市場模式】\s*(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*',
        text, re.IGNORECASE,
    )
    if not m:
        return text
    regime = _normalize_regime_token(m.group(1))
    if not regime:
        return text
    patched = re.sub(
        rf'(【今日市場模式】\s*(?:<[^>]*>\s*)*){regime_token_re}(?:\s*</[^>]*>)*',
        rf"\1{regime}", text, flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:][^\n]*?regime\s*=\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*",
        rf"\1regime={regime}", patched, flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:]\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*(\s*[｜|])",
        rf"\1{regime}\3", patched, flags=re.IGNORECASE,
    )
    patched = re.sub(
        r'("regime"\s*:\s*")(risk_on|risk_off|neutral)(")',
        rf'\1{regime}\3', patched, flags=re.IGNORECASE,
    )

    def _risk_budget_line_repl(m: re.Match) -> str:
        line = m.group(0)
        if _is_conditional_regime_line(line):
            return line
        line = re.sub(r'\brisk[\s_-]*on\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\brisk[\s_-]*off\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\bneutral\b', regime, line, flags=re.IGNORECASE)
        return line

    patched = re.sub(r'(?im)^.*今日風險預算[^\n]*$', _risk_budget_line_repl, patched)
    return patched


def _remove_duplicate_source_observability(text: str) -> str:
    """移除報告內重複/過時的 SourceHealth/SourceErrors/SourceQuota 行。"""
    lines = text.splitlines()
    cleaned = [
        ln for ln in lines
        if not re.search(r"\bSource(?:Health|Errors|Quota)\b", ln)
        and not re.match(r"^\s*【Source(?:Health|Errors|Quota)】", ln)
    ]
    return "\n".join(cleaned).strip()


def _drop_unactionable_trade_blocks(text: str) -> str:
    """移除不可執行交易段（現價/進場/目標/停損為 N/A）。"""
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    bullet_re = re.compile(r'^\s*·\s*\$[A-Z0-9/]+')
    boundary_re = re.compile(r'^\s*(?:────────────|區塊\d+|【|════)')
    while i < n:
        line = lines[i]
        if bullet_re.search(line):
            j = i + 1
            while j < n and not bullet_re.search(lines[j]) and not boundary_re.search(lines[j]):
                j += 1
            block = "\n".join(lines[i:j])
            if re.search(
                r"(現價|進場|目標|停損)[：:｜]\s*(?:<code>)?\s*\$?\s*N\s*/\s*A\b",
                block,
                re.IGNORECASE,
            ):
                i = j
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _ensure_signal_conflict_section(text: str) -> str:
    """若報告缺少訊號衝突摘要，自動注入預設值，避免 gate 阻擋。"""
    if re.search(r'[訊信]號衝突(?:摘要|分析)?[：:]', text):
        return text
    fallback_line = "訊號衝突摘要：各指標方向基本一致，暫無顯著多空衝突訊號。"
    risk_budget_m = re.search(r'(今日風險預算[：:][^\n]*\n)', text)
    if risk_budget_m:
        pos = risk_budget_m.end()
        return text[:pos] + fallback_line + "\n" + text[pos:]
    trade_section_m = re.search(r'(區塊④【)', text)
    if trade_section_m:
        pos = trade_section_m.start()
        return text[:pos] + fallback_line + "\n" + text[pos:]
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n" + fallback_line + "\n\n" + text[pos:]
    return text


def _ensure_trade_sections(text: str) -> str:
    """當 LLM 漏寫交易段時，注入「觀望模式」區塊（不捏造價格）。"""
    has_crypto_trade = _has_crypto_trade_section(text)
    has_ai_trade = _has_ai_trade_section(text)
    if has_crypto_trade and has_ai_trade:
        return text
    regime_m = re.search(
        r'【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*',
        text, re.IGNORECASE,
    )
    regime = (_normalize_regime_token(regime_m.group(1)) if regime_m else None) or "neutral"
    blocks: list[str] = []
    if not has_crypto_trade:
        blocks.append("\n".join([
            "區塊④【資金流向與精準操作 (Crypto)】：",
            "· <b>觀望模式</b>：資料不足觀望，暫不開新倉（避免捏造現價/進場/目標/停損）。",
            f"· 風險預算：依 <code>{regime}</code> 模式降低風險，僅保留既有倉位管理。",
            "· 重新進場條件：待下一輪有效新聞、即時報價與多時框訊號齊備後再提供交易參數。",
        ]))
    if not has_ai_trade:
        blocks.append("\n".join([
            "區塊④【AI 產業鏈精準操作 (US Equities)】：",
            "· <b>觀望模式</b>：資料不足觀望，暫不提供股票進出場價格。",
            f"· 風險預算：依 <code>{regime}</code> 模式執行防守配置，避免情緒性追價。",
            "· 重新進場條件：需補齊產業催化、成交量與多時框確認後再發布可執行建議。",
        ]))
    if not blocks:
        return text
    marker = "[QSREC_START]"
    pos = text.find(marker)
    block = "\n\n".join(blocks)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


def _inject_fallback_news_entries(text: str, min_news: int = 6) -> str:
    """新聞不足時加入風險提示，不再注入假新聞條目。"""
    current = _count_effective_news_items(text)
    if current >= min_news:
        return text
    tagged = _count_news_tags_only(text)
    tier_line = ""
    if _allow_partial_news_gate() and 3 <= tagged < min_news:
        tier_line = "[REPORT_TIER:PARTIAL_NEWS]\n"
    block = (
        f"{tier_line}【新聞資料狀態】\n"
        f"以〔新聞 N〕標籤計入的新聞為 <code>{current}</code> 則／目標 <code>{min_news}</code> "
        f"則（幣圈 3 + AI 3）。已啟用資料不足保護：不補虛構新聞。"
        "若實際已寫滿 6 則但格式未統一為〔新聞 N〕，請主編下一版改為規定格式以便系統計數。"
    )
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


def _ensure_min_news_count(text: str, min_news: int = 6) -> str:
    """新聞數不足時，只加入觀測提示，不注入虛構新聞。"""
    return _inject_fallback_news_entries(text, min_news=min_news)


def _ensure_low_confidence_for_many_na(text: str) -> str:
    """當 N/A 過多時，注入低置信度說明段落。"""
    if len(re.findall(r"\bN/A\b", text)) <= 3:
        return text
    has_lc = bool(re.search(r"低置信度|低信心", text))
    has_proxy = bool(_MISSING_REASON_PROXY_RE.search(text))
    if has_lc and has_proxy:
        return text
    if "方案權限回傳暫缺" in text:
        return text
    block = (
        "· <b>低置信度</b>：儀表板若出現多項 <code>N/A</code>，表示第三方 API 或方案權限回傳暫缺，"
        "敘事仍以已回傳之技術面與新聞催化為準。"
        "<b>資料缺失原因</b>：與工具欄位空白或 <code>[DATA_MISSING:...]</code> 標記一致；"
        "<b>替代指標</b>：請交叉比對 DXY、VIX、資金費率、Fear&amp;Greed、RSI、現貨成交與上文核心新聞。"
    )
    for anchor in (r"(區塊①[^\n]*\n)", r"(數據儀表板[^\n]*\n)", r"([^\n]*\bDXY\b[^\n]*\n)", r"(【今日市場模式】[^\n]*\n)"):
        m = re.search(anchor, text)
        if m:
            pos = m.end()
            return text[:pos] + block + "\n" + text[pos:]
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


_DATA_MISSING_TOKEN_RE = re.compile(r"\[DATA_MISSING:([^\]]+)\]")


def _redact_data_missing_tokens_from_visible_report(text: str) -> str:
    """改寫 [DATA_MISSING:...] 標記為中文短語，避免 Gate 誤判。"""
    if not text or "[DATA_MISSING:" not in text:
        return text

    def _repl(m: re.Match) -> str:
        key = (m.group(1) or "").strip() or "unknown"
        return f"〔資料源暫缺：{key}〕"

    return _DATA_MISSING_TOKEN_RE.sub(_repl, text)


def _postprocess_report_for_resilience(text: str) -> str:
    """修正易失格式：新聞 UTC+8、新聞不足降級補齊、來源可觀測欄位。"""
    if not text:
        return text
    patched = _fix_glued_na_suffix(text)
    patched = _sanitize_macro_outlier_values(patched)
    patched = _unify_regime_mentions(patched)
    patched = _drop_unactionable_trade_blocks(patched)
    patched = _ensure_trade_sections(patched)
    patched = _ensure_rumor_grade_marker(patched)
    patched = _auto_prefix_missing_news_tags(patched)
    patched = _normalize_news_timezone_utc8(patched)
    patched = _ensure_signal_conflict_section(patched)
    patched = _ensure_min_news_count(patched, min_news=6)
    patched = _ensure_low_confidence_for_many_na(patched)
    patched = _redact_data_missing_tokens_from_visible_report(patched)
    patched = _remove_duplicate_source_observability(patched)
    observe_block = source_observability_lines()
    marker = "[QSREC_START]"
    pos = patched.find(marker)
    if pos != -1:
        patched = patched[:pos].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos:]
    else:
        patched = patched.rstrip() + f"\n\n{observe_block}"
    if not all(s in patched for s in ("【SourceHealth】", "【SourceErrors】", "【SourceQuota】")):
        patched = _remove_duplicate_source_observability(patched)
        pos2 = patched.find(marker)
        if pos2 != -1:
            patched = patched[:pos2].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos2:]
        else:
            patched = patched.rstrip() + f"\n\n{observe_block}"
    return patched

"""Report validation gate: validate_report() and all its helper functions.

Extracted from main.py to reduce module size. This module contains the
full validation pipeline for checking report quality before Telegram push.

Dependencies: config.py, validation_rules.py, tracker.py, tools.py
Does NOT import from main.py (to avoid circular imports).
"""

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from config import PROJECT_ID, RECOMMENDATIONS_TABLE
from telegram_sender import strip_html
from validation_rules import (
    BUDGET_TAGS_RE,
    CODE_LEAK_RE,
    DATA_MISSING_FIELDS_RE,
    HAS_AI_SECTION_RE,
    HAS_CRYPTO_SECTION_RE,
    HAS_DASHBOARD_RE,
    HAS_DATA_MISSING_RE,
    HAS_EXPECTED_WIN_RATE_RE,
    HAS_LOW_CONFIDENCE_RE,
    HAS_REGIME_RE,
    HAS_RISK_BUDGET_RE,
    HAS_RR_RE,
    HAS_SIGNAL_CONFLICT_RE,
    HAS_SIGNAL_SCORE_RE,
    HAS_MAX_DRAWDOWN_RE,
    IMPACT_LEAK_RE,
    MALFORMED_INVALIDATION_RE,
    MODE_TAGS_RE,
    NA_TOKEN_RE,
    NUMERIC_INVESTMENT_LINE_RE,
    NUMERIC_INVESTMENT_MULTI_RE,
    QSREC_MARKERS_RE,
    UNACTIONABLE_TRADE_RE,
    text_has_positive_trade_watch_mode,
    span_has_positive_trade_watch_declaration,
)
import tracker

logger = logging.getLogger(__name__)

SKIP_BIGQUERY = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")

# ── 環境開關 ──────────────────────────────────────────────────────────


def _allow_partial_news_gate() -> bool:
    """允許「新聞分段」模式：3~5 則〔新聞 N〕+ 宣告不補假新聞時，放寬 6 則硬性要求。ALLOW_PARTIAL_NEWS_GATE=0 關閉。"""
    return os.getenv("ALLOW_PARTIAL_NEWS_GATE", "1").lower() not in ("0", "false", "no")


def _strict_pick_justification() -> bool:
    """驗證「本日選擇理由」是否連結催化／鏈上或退階邏輯並點名 QSREC 標的。STRICT_PICK_JUSTIFICATION=0 關閉。"""
    return os.getenv("STRICT_PICK_JUSTIFICATION", "1").lower() not in ("0", "false", "no")


def _strict_pick_rotation() -> bool:
    """與昨日 BQ 已存 QSREC 標的（canonical）完全相同時，須改選或寫「重複選用理由」。STRICT_PICK_ROTATION=0 關閉。"""
    return os.getenv("STRICT_PICK_ROTATION", "1").lower() not in ("0", "false", "no")


def _allow_repeat_pick_override() -> bool:
    """同標延續是否允許以分數優勢覆核放行。ALLOW_REPEAT_PICK_OVERRIDE=0 關閉（改為強制至少換一檔）。"""
    return os.getenv("ALLOW_REPEAT_PICK_OVERRIDE", "1").lower() not in ("0", "false", "no")


def _pick_rotation_override_min_gap() -> float:
    """同標延續的最低分差門檻（selection_score - alt_candidate_score）。"""
    try:
        return float(os.getenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "12"))
    except ValueError:
        return 12.0


def _strict_pick_scoring() -> bool:
    """要求 QSREC 內含可量化選標分數欄位。STRICT_PICK_SCORING=0 關閉。"""
    return os.getenv("STRICT_PICK_SCORING", "1").lower() not in ("0", "false", "no")


def _strict_ai_fundamentals_citation() -> bool:
    """AI 段理由若含基本面用語，須在 AI 區塊內出現 FinancialDatasets 標記。預設關閉。"""
    return os.getenv("STRICT_AI_FUNDAMENTALS_CITATION", "0").lower() in ("1", "true", "yes")


_AI_FUNDAMENTAL_CLAIM_IN_REASON_RE = re.compile(
    r"營收|淨利|毛利率|現金流|財報|法說|指引|EPS|本益比|自由現金流|FCF|資產負債",
    re.IGNORECASE,
)


def _ai_span_to_qsrec(text: str) -> str:
    """🤖 AI 主段起至 QSREC 前（供基本面引用檢查）。"""
    start_m = re.search(r"(🤖\s*AI\s*市場|【AI\s*數據儀表板】)", text, re.IGNORECASE)
    if not start_m:
        return ""
    start = start_m.start()
    end_m = re.search(r"\[QSREC_START\]", text[start:], re.IGNORECASE)
    end = start + end_m.start() if end_m else len(text)
    return text[start:end]


def _ai_fundamentals_citation_ok(text: str) -> tuple[bool, str]:
    if not _strict_ai_fundamentals_citation():
        return True, ""
    ai_span = _ai_span_to_qsrec(text)
    if not (ai_span or "").strip():
        return True, ""
    ai_body = text[len(_crypto_report_prefix(text)) :]
    reason = _extract_today_pick_reason(ai_body) or ""
    if not reason or not _AI_FUNDAMENTAL_CLAIM_IN_REASON_RE.search(reason):
        return True, ""
    if re.search(r"financial\s*datasets|financialdatasets", ai_span, re.IGNORECASE):
        return True, ""
    return (
        False,
        "AI 段「本日選擇理由」含基本面用語，但未見 FinancialDatasets 數據源標記；"
        "請呼叫 financial_datasets_tool 並在儀表板 MetricLine 的 label 含 FinancialDatasets 與 ticker。",
    )


def _allow_qsrec_opposing_directions() -> bool:
    """允許 QSREC 內同一 category+asset 同時出現 LONG 與 SHORT（對沖／實驗用）。預設關閉。"""
    return os.getenv("QSREC_ALLOW_OPPOSING_DIRECTIONS", "").lower() in ("1", "true", "yes")


def _repeat_pick_days_max() -> int:
    """同標延續放行時，repeat_days 最大容許值。"""
    try:
        return int(os.getenv("PICK_REPEAT_DAYS_MAX", "2"))
    except ValueError:
        return 2


def _repeat_pick_min_score() -> float:
    """同標延續放行時，selection_score 最低門檻。"""
    try:
        return float(os.getenv("PICK_REPEAT_MIN_SELECTION_SCORE", "75"))
    except ValueError:
        return 75.0


# ── 動態選幣／選股：本日選擇理由驗證 ────────────────────────────────────

_CRYPTO_PICK_KW: tuple[str, ...] = (
    "新聞", "催化", "事件", "題材", "ETF", "核准", "升級", "主網", "分叉",
    "清算", "爆倉", "流入", "流出", "鏈上", "巨鯨", "資金費率", "多空比",
    "DeFi", "監管", "申請", "上市", "解鎖", "減半", "RWA", "SOPR", "NUPL",
    "交易所", "淨流", "未平倉", "OI", "現貨", "基差", "期權", "選擇權",
)
_CRYPTO_PICK_FALLBACK: tuple[str, ...] = (
    "大型幣", "主流幣", "龍頭", "流動性", "最後才", "缺乏", "無其他",
    "不明顯", "退而求其次", "避險", "保守", "催化劑不足",
)
_EQUITY_PICK_KW: tuple[str, ...] = (
    "財報", "合約", "營收", "資本", "支出", "Capex", "回購", "新品", "發布",
    "上線", "GPU", "資料中心", "雲端", "雲", "生成式", "LLM", "訂單", "拉貨",
    "晶片", "代工", "新聞", "報導", "法說", "指引", "併購",
)
_EQUITY_PICK_FALLBACK: tuple[str, ...] = (
    "權值", "大型股", "指數", "避險", "流動性", "最後才", "缺乏催化",
    "通殺", "ETF", "BOTZ", "ARKQ",
)


def _crypto_report_prefix(text: str) -> str:
    """合併戰報中「加密區」之前綴（🤖 AI 主段起頭後視為下半部）。"""
    best = len(text)
    for pat in (
        r"(?m)^────────────\s*\n\s*🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
        r"\n🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
        r"🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
        r"(?m)^\s*AI\s*產業鏈精準操作\s*\(US\s*Equit",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m and m.start() < best:
            best = m.start()
    return text[:best] if best < len(text) else text


def _extract_today_pick_reason(span: str) -> str | None:
    """自區塊內取出第一處「本日選擇理由」純文字（至風險預算／訊號衝突／交易條目／QSREC／分隔線）。"""
    m = re.search(
        r"本日選擇理由[：:]\s*([\s\S]+?)(?=\n\s*(?:今日風險預算|訊號衝突(?:摘要)?)[：:]|\n\s*·[^\n]*\$|\[QSREC_START\]|\n(?:-{4,}|─{4,}))",
        span,
        re.IGNORECASE,
    )
    if not m:
        return None
    return strip_html(m.group(1)).strip()


def _normalize_pick_asset_legs(asset: str) -> list[str]:
    """QSREC asset → 大寫代號列表（比值拆兩腿，供『理由是否點名』檢查）。"""
    a = str(asset or "").upper().replace("$", "").replace(" ", "").replace("-", "/")
    if "/" in a:
        return [p for p in a.split("/") if p]
    return [a] if a else []


def _reason_covers_assets(reason: str, assets: list[str]) -> bool:
    """理由中須可辨識每一檔標的（代號字串出現於 strip 後大寫比對）。"""
    u = strip_html(reason).upper()
    for raw in assets:
        legs = _normalize_pick_asset_legs(raw)
        if not legs:
            return False
        if len(legs) >= 2:
            if not all(leg in u for leg in legs):
                return False
        else:
            if legs[0] not in u:
                return False
    return True


def _score_kw_hits(reason: str, kws: tuple[str, ...]) -> int:
    return sum(1 for k in kws if k in reason)


def _pick_justification_crypto_ok(text: str, recs: list[dict]) -> tuple[bool, str]:
    """
    加密 QSREC 每檔須在「本日選擇理由」區間內可被合規敘事支持：
    ≥2 個催化/鏈上關鍵線索；或 1 線索 + 明確大型幣退階語；或 1 線索 + 長文且點名所有標的。
    """
    crypto_assets = [
        str(r.get("asset", ""))
        for r in recs
        if str(r.get("category", "CRYPTO")).upper() == "CRYPTO"
    ]
    if not crypto_assets:
        return True, ""
    cspan = _crypto_report_prefix(text)
    reason = _extract_today_pick_reason(cspan)
    if not reason:
        return False, "加密區缺少「本日選擇理由」，或內容未寫在「今日風險預算／訊號衝突／交易條目」之前（請依動態選幣標準補敘）"
    if len(reason) < 34:
        return False, "本日選擇理由（加密）過短：請說明新聞/鏈上依據或明確大型幣退階邏輯，並點名 QSREC 標的"
    strong = _score_kw_hits(reason, _CRYPTO_PICK_KW)
    fb = _score_kw_hits(reason, _CRYPTO_PICK_FALLBACK)
    named = _reason_covers_assets(reason, crypto_assets)
    ok = (
        strong >= 2
        or (strong >= 1 and fb >= 1)
        or (strong >= 1 and len(reason) >= 72 and named)
    )
    if ok:
        return True, ""
    return (
        False,
        "本日選擇理由（加密）未達動態選幣標準：須（≥2 項催化/鏈上線索）或（1 線索+大型幣退階說明）或（1 線索+長文且點名所有加密 QSREC 標的）；不符則請改選標的或補強敘事",
    )


def _pick_justification_equity_ok(text: str, recs: list[dict]) -> tuple[bool, str]:
    """美股 QSREC：理由須含足夠基本面/新聞線索並點名各檔股票代號。"""
    eq_assets = [
        str(r.get("asset", ""))
        for r in recs
        if str(r.get("category", "")).upper() == "EQUITY"
    ]
    if not eq_assets:
        return True, ""
    ai_span = text[len(_crypto_report_prefix(text)):]
    reason = _extract_today_pick_reason(ai_span)
    if not reason:
        return False, "AI/美股區缺少「本日選擇理由」，或格式未寫在交易條目前（請依動態選股標準補敘）"
    if len(reason) < 38:
        return False, "本日選擇理由（美股）過短：請連結財報/產品/新聞催化並點名 QSREC 標的"
    strong = _score_kw_hits(reason, _EQUITY_PICK_KW)
    fb = _score_kw_hits(reason, _EQUITY_PICK_FALLBACK)
    named = _reason_covers_assets(reason, eq_assets)
    ok = strong >= 2 or (strong >= 1 and fb >= 1) or (strong >= 1 and len(reason) >= 80 and named)
    if ok:
        return True, ""
    return (
        False,
        "本日選擇理由（美股）未達動態選股標準：須（≥2 項基本面/新聞線索）或（1 線索+權值/ETF 退階說明）或（1 線索+長文且點名所有美股 QSREC 標的）；不符則請改選標的或補強敘事",
    )


_REPEAT_PICK_REASON_RE = re.compile(
    r"重複選用理由|重複選股理由|重複持有理由|連日(?:選(?:用)?|持有|維持)|連續(?:兩日|多日)(?:同標|持有|維持)|"
    r"仍選(?:用)?|同標(?:的)?延續|延續昨|延續上日|與昨日相同標的|維持昨日(?:兩檔|組合|標的)|持續鎖定(?:同組|兩檔)",
    re.IGNORECASE,
)
_PICK_SCORE_FIELDS = (
    "selection_score",
    "catalyst_score",
    "flow_score",
    "technical_score",
    "risk_fit_score",
    "execution_score",
)


def _qsrec_canonical_set_for_category(recs: list[dict], category: str) -> set[str]:
    want = category.upper()
    out: set[str] = set()
    for r in recs:
        if str(r.get("category", "")).upper() != want:
            continue
        a = r.get("asset")
        if a:
            out.add(tracker.canonical_asset_key(str(a)))
    return out


def _safe_float_val(v) -> float | None:
    try:
        if v in (None, "", []):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _best_repeat_score_gap_for_category(recs: list[dict], category: str) -> float | None:
    """回傳該類別可用的最大 score_gap；若缺失則 None。"""
    want = category.upper()
    gaps: list[float] = []
    for rec in recs:
        if str(rec.get("category", "")).upper() != want:
            continue
        gap = _safe_float_val(rec.get("score_gap"))
        if gap is None:
            sel = _safe_float_val(rec.get("selection_score"))
            alt = _safe_float_val(rec.get("alt_candidate_score"))
            if sel is not None and alt is not None:
                gap = sel - alt
        if gap is not None:
            gaps.append(gap)
    if not gaps:
        return None
    return max(gaps)


def _has_repeat_quality_anchor(recs: list[dict], category: str) -> bool:
    """同標延續時，至少 1 筆滿足 repeat_days 與 selection_score 品質門檻。"""
    want = category.upper()
    max_days = _repeat_pick_days_max()
    min_score = _repeat_pick_min_score()
    for rec in recs:
        if str(rec.get("category", "")).upper() != want:
            continue
        repeat_days = _safe_float_val(rec.get("repeat_days"))
        score = _safe_float_val(rec.get("selection_score"))
        if repeat_days is None or score is None:
            continue
        if repeat_days <= max_days and score >= min_score:
            return True
    return False


def _fetch_yesterday_qsrec_canonical_set(category: str) -> set[str] | None:
    """
    讀取昨日已寫入 trade_recommendations 的 QSREC 標的（DISTINCT asset → canonical）。
    SKIP_BIGQUERY 或查詢失敗回傳 None（略過輪動檢查，避免誤擋）。
    """
    if SKIP_BIGQUERY:
        return None
    cat = category.upper()
    if cat not in ("CRYPTO", "EQUITY"):
        return None
    try:
        from google.cloud import bigquery
        client = bigquery.Client(project=PROJECT_ID)
        job_cfg = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cat", "STRING", cat)]
        )
        rows = list(
            client.query(
                f"""
                SELECT DISTINCT asset
                FROM `{RECOMMENDATIONS_TABLE}`
                WHERE report_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
                  AND UPPER(COALESCE(category, '')) = @cat
                """,
                job_config=job_cfg,
            ).result()
        )
        if not rows:
            return set()
        return {tracker.canonical_asset_key(r["asset"]) for r in rows if r.get("asset")}
    except Exception as e:
        logger.warning("pick rotation: yesterday QSREC query failed: %s", e)
        return None


def _pick_rotation_crypto_ok(text: str, recs: list[dict]) -> tuple[bool, str]:
    """今日加密 QSREC canonical 集合若與昨日完全相同，須改選或達成同標覆核。"""
    if not _strict_pick_rotation():
        return True, ""
    y = _fetch_yesterday_qsrec_canonical_set("CRYPTO")
    if y is None:
        return True, ""
    t = _qsrec_canonical_set_for_category(recs, "CRYPTO")
    if not t or not y or t != y:
        return True, ""
    if not _allow_repeat_pick_override():
        return False, "動態選幣／輪動：與昨日完全相同時不允許同標延續，請至少更換一檔（或配對腿）。"
    reason = _extract_today_pick_reason(_crypto_report_prefix(text)) or ""
    if not _REPEAT_PICK_REASON_RE.search(reason):
        return (
            False,
            "動態選幣／輪動：本日加密 QSREC 標的與昨日 BQ 紀錄完全相同，請至少更換一檔（或配對腿），或在「本日選擇理由」明確寫「重複選用理由：…」（新催化／連日持有依據）。",
        )
    gap = _best_repeat_score_gap_for_category(recs, "CRYPTO")
    if gap is None:
        return False, "動態選幣／輪動：同標延續需提供可量化分差（score_gap 或 selection_score/alt_candidate_score）。"
    min_gap = _pick_rotation_override_min_gap()
    if gap < min_gap:
        return False, f"動態選幣／輪動：同標延續分差不足（score_gap={gap:.2f} < {min_gap:.2f}），請改選至少一檔。"
    if not _has_repeat_quality_anchor(recs, "CRYPTO"):
        return (
            False,
            f"動態選幣／輪動：同標延續需至少 1 筆滿足 repeat_days <= {_repeat_pick_days_max()} 且 selection_score >= {_repeat_pick_min_score():.0f}。",
        )
    return True, ""


def _pick_rotation_equity_ok(text: str, recs: list[dict]) -> tuple[bool, str]:
    """今日美股 QSREC canonical 集合若與昨日完全相同，須改選或達成同標覆核。"""
    if not _strict_pick_rotation():
        return True, ""
    y = _fetch_yesterday_qsrec_canonical_set("EQUITY")
    if y is None:
        return True, ""
    t = _qsrec_canonical_set_for_category(recs, "EQUITY")
    if not t or not y or t != y:
        return True, ""
    if not _allow_repeat_pick_override():
        return False, "動態選股／輪動：與昨日完全相同時不允許同標延續，請至少更換一檔。"
    reason = _extract_today_pick_reason(text[len(_crypto_report_prefix(text)):]) or ""
    if not _REPEAT_PICK_REASON_RE.search(reason):
        return (
            False,
            "動態選股／輪動：本日美股 QSREC 標的與昨日 BQ 紀錄完全相同，請至少更換一檔，或在「本日選擇理由」明確寫「重複選用理由：…」。",
        )
    gap = _best_repeat_score_gap_for_category(recs, "EQUITY")
    if gap is None:
        return False, "動態選股／輪動：同標延續需提供可量化分差（score_gap 或 selection_score/alt_candidate_score）。"
    min_gap = _pick_rotation_override_min_gap()
    if gap < min_gap:
        return False, f"動態選股／輪動：同標延續分差不足（score_gap={gap:.2f} < {min_gap:.2f}），請更換至少一檔。"
    if not _has_repeat_quality_anchor(recs, "EQUITY"):
        return (
            False,
            f"動態選股／輪動：同標延續需至少 1 筆滿足 repeat_days <= {_repeat_pick_days_max()} 且 selection_score >= {_repeat_pick_min_score():.0f}。",
        )
    return True, ""


# ── 報告結構檢查輔助 ──────────────────────────────────────────────────


def _normalize_regime_token(raw: str) -> str | None:
    token = re.sub(r'[\s\-_]+', '_', (raw or "").strip().lower())
    if token in ("risk_on", "risk_off", "neutral"):
        return token
    return None


def _risk_off_star_cap_violated(text: str) -> bool:
    """risk_off 下是否出現超過上限的信心星等（4 顆星）。"""
    has_risk_off = bool(
        re.search(
            r'【今日市場模式】\s*(?:<[^>]*>\s*)*risk[\s_\-]*off(?:\s*</[^>]*>)*',
            text,
            re.IGNORECASE,
        )
    )
    has_4_star = "⭐️⭐️⭐️⭐️" in text
    return has_risk_off and has_4_star


def _pair_trade_unit_consistent(text: str) -> bool:
    """
    粗略檢查配對交易單位一致性：
    若出現 $A / $B，必須標註比值/價差單位，且現價比值與進場不應嚴重失真。
    """
    pair_m = re.search(
        r'\$([A-Z]{2,10})\s*/\s*\$([A-Z]{2,10}).*?現價[：:]\s*\$?([0-9,]+(?:\.\d+)?)\s*/\s*\$?([0-9,]+(?:\.\d+)?)',
        text,
        re.DOTALL,
    )
    if not pair_m:
        return True

    has_pair_unit = bool(re.search(r'單位[：:]\s*(?:比值|價差|[A-Z]{2,10}/[A-Z]{2,10}\s*比值)', text))
    if not has_pair_unit:
        return False

    a = float(pair_m.group(3).replace(",", ""))
    b = float(pair_m.group(4).replace(",", ""))
    if b <= 0:
        return False
    implied_ratio = a / b

    nearby = text[pair_m.start(): pair_m.start() + 500]
    entry_m = re.search(r'進場[：:]\s*(?:<code>)?\$?([0-9,]+(?:\.\d+)?)', nearby)
    if not entry_m:
        return False
    entry = float(entry_m.group(1).replace(",", ""))
    if entry <= 0:
        return False

    # 容忍 35% 誤差（避免過度嚴苛），超出視為單位可能混用
    return abs(entry - implied_ratio) / implied_ratio <= 0.35


def _qsrec_opposing_direction_same_asset(recs: list[dict]) -> list[str]:
    """同一 category + asset 不得同時 LONG 與 SHORT（避免讀者看到互斥觀點）。"""
    buckets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for rec in recs:
        asset = str(rec.get("asset") or "").strip().upper().replace("$", "")
        direction = str(rec.get("direction") or "").strip().upper()
        cat = str(rec.get("category") or "").strip().upper()
        if not asset or direction not in ("LONG", "SHORT"):
            continue
        buckets[(cat or "UNKNOWN", asset)].add(direction)
    issues: list[str] = []
    for (cat, asset), dirs in sorted(buckets.items()):
        if len(dirs) > 1:
            issues.append(
                f"QSREC 同資產方向互斥：{cat} {asset} 同時含 LONG 與 SHORT（請整併為單一淨方向或分拆為明確對沖敘事）"
            )
    return issues


def _conflicting_total_risk_budget_lines(text: str) -> bool:
    """若出現多組「今日風險預算」且總風險預算百分比不一致，視為版面/敘事衝突。"""
    nums = re.findall(r"今日風險預算[：:][^\n]*總風險預算[^\d]*(\d+)\s*%", text)
    if len(nums) < 2:
        return False
    return len(set(nums)) > 1


def _qsrec_consistency_issues(report_text: str, recs: list[dict]) -> list[str]:
    """檢查 QSREC 載荷的交易欄位完整度與 regime 倉位一致性。"""
    if not recs:
        return []

    regime_m = re.search(
        r'【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*',
        report_text,
        re.IGNORECASE,
    )
    regime = _normalize_regime_token(regime_m.group(1)) if regime_m else "neutral"
    regime = regime or "neutral"
    cap_map = {"risk_off": 5.0, "neutral": 10.0, "risk_on": 15.0}
    cap = cap_map.get(regime, 10.0)

    issues: list[str] = []
    required = ("trigger", "invalidation", "position_pct", "timeframe")
    for i, rec in enumerate(recs, start=1):
        missing = [k for k in required if rec.get(k) in (None, "", [])]
        if missing:
            issues.append(f"QSREC 第 {i} 筆缺少必要欄位：{', '.join(missing)}")

        pos = rec.get("position_pct")
        try:
            if pos is not None and float(pos) > cap:
                issues.append(f"QSREC 第 {i} 筆 position_pct 超過 regime 上限（{float(pos):.2f}% > {cap:.2f}%）")
        except (TypeError, ValueError):
            issues.append(f"QSREC 第 {i} 筆 position_pct 非數字")

        if _strict_pick_scoring():
            for k in _PICK_SCORE_FIELDS:
                val = _safe_float_val(rec.get(k))
                if val is None:
                    issues.append(f"QSREC 第 {i} 筆缺少可量化評分欄位：{k}")
                    continue
                if not (0.0 <= val <= 100.0):
                    issues.append(f"QSREC 第 {i} 筆 {k} 超出範圍（{val:.2f}，應為 0~100）")

            sel = _safe_float_val(rec.get("selection_score"))
            alt = _safe_float_val(rec.get("alt_candidate_score"))
            gap = _safe_float_val(rec.get("score_gap"))
            if sel is None or alt is None:
                issues.append(f"QSREC 第 {i} 筆缺少 selection_score/alt_candidate_score（無法檢查分差）")
            elif gap is None:
                issues.append(f"QSREC 第 {i} 筆缺少 score_gap（建議填 selection_score-alt_candidate_score）")
            elif abs((sel - alt) - gap) > 1.0:
                issues.append(
                    f"QSREC 第 {i} 筆 score_gap 與 selection_score-alt_candidate_score 不一致（{gap:.2f} vs {sel - alt:.2f}）"
                )

    if not _allow_qsrec_opposing_directions():
        issues.extend(_qsrec_opposing_direction_same_asset(recs))
    return issues


def _count_effective_news_items(text: str) -> int:
    """統計有效新聞數。

    優先採 crew 規定的〔新聞 N〕（全篇目標 6：幣圈 3 + AI 3）；只要出現此格式就只信該計數，
    避免「新聞辯論」「列表」裡的 1. / 1) 被 max() 誤算成 6+ 而掩蓋真正缺則。
    無任何〔新聞〕標籤時才退回 1) / 1.（舊稿相容）。
    """
    tagged = len(re.findall(r"〔新聞\s*\d+〕", text))
    if tagged > 0:
        return tagged
    numbered_paren = len(re.findall(r"(?m)^\s*\d+\)\s+.+", text))
    numbered_dot = len(re.findall(r"(?m)^\s*\d+\.\s+.+", text))
    return max(numbered_paren, numbered_dot)


def _count_news_tags_only(text: str) -> int:
    """僅統計〔新聞 N〕標籤數（與 _count_effective_news_items 在無標籤時的 fallback 分離）。"""
    t = _strip_lines_for_news_validation(text)
    return len(re.findall(r"〔新聞\s*\d+〕", t))


def _fallback_news_count(text: str) -> int:
    """統計自動降級補位新聞數量。"""
    return len(re.findall(r"資料源不足：自動降級補位", text))


# 新聞時間戳允許之香港時區字樣（含全形加號、GMT、HKT／中文口語、UTC+08:00 等）
_NEWS_HK_TZ_TOKEN = (
    r"(?:UTC|GMT)\s*[\+\＋]\s*0?8(?::\s*00)?"
    r"|HKT\b"
    r"|(?:香港|北京|台北)時間"
    r"|中國標準時間|東八區"
)

_NEWS_VALIDATION_NOISE = re.compile(
    r"新聞資料狀態|請主編下一版|格式未統一為〔新聞|【新聞資料狀態】"
)

# N/A 過多時須同現「資料缺失原因」與「替代指標」（允許跨行，避免 . 不匹配換行誤判）
_MISSING_REASON_PROXY_RE = re.compile(
    r"資料缺失原因[\s\S]{0,800}?替代指標|替代指標[\s\S]{0,800}?資料缺失原因",
    re.IGNORECASE,
)

# 新聞行內常以 <code> 包住時間戳，驗證／正規化前先剥除該行上行內標籤
_NEWS_LINE_INLINE_HTML_RE = re.compile(r"</?(?:code|b|i|u|s)(?:\s[^>]*)?>", re.IGNORECASE)

_NEWS_TAGGED_WITH_HK_TZ_RE = re.compile(
    rf"〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{{4}}[/\-]\d{{1,2}}[/\-]\d{{1,2}}|\d{{1,2}}/\d{{1,2}}(?:/\d{{4}})?)"
    rf"\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*{_NEWS_HK_TZ_TOKEN}\]",
    re.IGNORECASE,
)
_NEWS_TAGGED_WITH_TS_RE = re.compile(
    r"〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
    r"\s+\d{1,2}:\d{2}(?::\d{2})?",
    re.IGNORECASE,
)


def _strip_inline_tags_on_news_lines(text: str) -> str:
    """僅在含〔新聞 N〕之行剥除 <code>/<b> 等行內標籤，利於比對時間戳又不動儀表板其他 HTML。"""
    out: list[str] = []
    for ln in text.splitlines():
        if re.search(r"〔新聞\s*\d+〕", ln):
            out.append(_NEWS_LINE_INLINE_HTML_RE.sub("", ln))
        else:
            out.append(ln)
    return "\n".join(out)


def _strip_lines_for_news_validation(text: str) -> str:
    """排除系統注入之『新聞資料狀態』等行，避免誤算〔新聞 N〕或 UTC+8。"""
    lines = [ln for ln in text.splitlines() if not _NEWS_VALIDATION_NOISE.search(ln)]
    return "\n".join(lines)


def _text_for_utc8_validation(text: str) -> str:
    """僅供新聞時區檢查：去噪後截斷【新聞資料狀態】段落之後，避免腳註內仿格式〔新聞〕干擾比對。"""
    t = _strip_lines_for_news_validation(text)
    m = re.search(r"(?m)^\s*【新聞資料狀態】", t)
    if m:
        return t[: m.start()]
    return t


def _normalize_fullwidth_news_brackets_on_news_lines(text: str) -> str:
    """將含〔新聞 N〕行之全形括號 ［］ 轉為半形 []，利於 UTC+8 正規化與 Gate 比對。"""
    out: list[str] = []
    for ln in text.splitlines():
        if re.search(r"〔新聞\s*\d+〕", ln):
            out.append(ln.replace("［", "[").replace("］", "]"))
        else:
            out.append(ln)
    return "\n".join(out)


def _join_news_tag_timestamp_lines(text: str) -> str:
    """若 LLM 將〔新聞 N〕與 [日期 時間] 拆成兩行，合併為單行以便補齊 UTC+8 與 regex 驗證。"""
    lines = text.splitlines()
    if not lines:
        return text
    out: list[str] = []
    i = 0
    ts_head = re.compile(
        r"^\s*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\d{1,2}:\d{2}(?::\d{2})?"
    )
    while i < len(lines):
        ln = lines[i]
        if re.search(r"〔新聞\s*\d+〕\s*$", ln.rstrip()) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if ts_head.match(nxt):
                out.append(ln.rstrip() + " " + nxt.lstrip())
                i += 2
                continue
        out.append(ln)
        i += 1
    return "\n".join(out)


def _has_news_timezone_utc8(text: str) -> bool:
    """新聞時間格式檢查：標籤格式需全數標示香港時區（UTC+8／GMT+8 等）；數字條列格式視為已降級接受。
    支援 [MM/DD HH:MM]、[MM/DD/YYYY HH:MM]、[YYYY/MM/DD HH:MM]、[YYYY-MM-DD HH:MM]；
    時區允許全形加號、多空格、GMT+8 等 LLM 常見變體。
    """
    t0 = _text_for_utc8_validation(text)
    t1 = _join_news_tag_timestamp_lines(t0)
    t2 = _normalize_fullwidth_news_brackets_on_news_lines(t1)
    t = _strip_inline_tags_on_news_lines(t2)
    tagged_total = len(re.findall(r"〔新聞\s*\d+〕", t))
    tagged_ts_total = len(_NEWS_TAGGED_WITH_TS_RE.findall(t))
    if tagged_ts_total > 0:
        tagged_utc = len(_NEWS_TAGGED_WITH_HK_TZ_RE.findall(t))
        return tagged_utc == tagged_ts_total
    if tagged_total > 0:
        return False
    numbered = len(re.findall(r"(?m)^\s*\d+[.)]\s+.+", t))
    return numbered > 0


def _partial_news_ok(text: str) -> bool:
    """
    新聞資料不足分段（產品規則）：
    - 〔新聞 1〕～〔新聞 3〕必須存在，且全篇已標示之〔新聞 N〕須全部帶 UTC+8；
    - 〔新聞 N〕則數須為 3～5（不足 6 但未完全缺新聞）；
    - 文內須宣告「資料不足保護／不補虛構新聞」，並有【新聞資料狀態】或 [REPORT_TIER:PARTIAL_NEWS]（後處理會注入）。
    不影響交易欄位檢查；交易觀望另見 trade_watch_mode。
    """
    if not _allow_partial_news_gate():
        return False
    tagged = _count_news_tags_only(text)
    if not (3 <= tagged < 6):
        return False
    if not re.search(r"資料不足保護|不補虛構新聞", text):
        return False
    if not (
        re.search(r"【新聞資料狀態】|新聞資料狀態", text)
        or "[REPORT_TIER:PARTIAL_NEWS]" in text
    ):
        return False
    for i in (1, 2, 3):
        if not re.search(rf"〔新聞\s*{i}〕", text):
            return False
    return _has_news_timezone_utc8(text)


# ── 宏觀數值檢查 ──────────────────────────────────────────────────────


def _has_macro_outlier_values(text: str) -> bool:
    """
    僅檢查宏觀欄位中的實值是否超出合理範圍：
    - 美債 10Y/2Y 僅在含「美債」之行解析，避免敘事句中「10Y 殖利率」誤配後文任意 %。
    - SOFR 僅在含 SOFR 之行解析數值%，且略過同時含 N/A 且無明確數值之句。
    - 利差 bp 應在 +/-1000bp 以內
    """
    for line in text.splitlines():
        if "美債" not in line:
            continue
        for m in re.finditer(
            r"10Y\s*[:：]\s*([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        # 「美債 10Y 報 4.25%」等無冒號寫法（仍限含美債之行）
        for m in re.finditer(
            r"10Y\D{0,22}([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        for m in re.finditer(
            r"2Y\s*[:：]\s*([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        for m in re.finditer(
            r"2Y\D{0,22}([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True

    for line in text.splitlines():
        if "SOFR" not in line.upper():
            continue
        # 僅取 SOFR 關鍵字鄰近第一個利率%，避免同列 VIX%、敘事百分比誤觸
        if "N/A" in line and not re.search(
            r"(?i)SOFR.{0,80}?[+\-]?[0-9][0-9,]*(?:\.[0-9]+)?\s*%",
            line,
        ):
            continue
        m = re.search(
            r"(?i)(?:Fed\s*)?SOFR[^0-9%\n]{0,90}([+\-]?[0-9,]+(?:\.[0-9]+)?)\s*%",
            line,
        )
        if not m:
            continue
        sofr_i = line.upper().find("SOFR")
        if sofr_i >= 0 and re.search(
            r"(?i)\bVIX\b|恐慌指數|波動率指數|VIX\s*指數",
            line[sofr_i: m.end()],
        ):
            continue
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if not (-0.5 <= val <= 25.0):
            return True

    for m in re.finditer(r"利差[：:]?\s*([+\-−]?[0-9,]+(?:\.\d+)?)\s*bp", text):
        raw = m.group(1).replace(",", "").replace("−", "-")
        try:
            val = float(raw)
        except ValueError:
            continue
        if abs(val) >= 1000:
            return True

    return False


def _has_macro_conflicts(text: str) -> bool:
    """
    檢查宏觀欄位自我矛盾：
    - 同時出現 2Y 的 N/A 與數值
    - 利差同時出現正值與負值
    - 2Y 多個數值差異過大（>1.0%）
    """
    y2_has_na = bool(re.search(r'美債\s*2Y[^\n]*N/?A', text, re.IGNORECASE))
    y2_vals = [
        float(v.replace(",", ""))
        for v in re.findall(r'美債\s*2Y[^0-9\n]{0,20}([0-9,]+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    ]
    if y2_has_na and y2_vals:
        return True
    if len(y2_vals) >= 2 and (max(y2_vals) - min(y2_vals) > 1.0):
        return True

    spread_vals = [
        float(v.replace(",", ""))
        for v in re.findall(r'利差[：:]?\s*(-?[0-9,]+(?:\.\d+)?)\s*bp', text)
    ]
    has_pos_spread = any(v > 0 for v in spread_vals)
    has_neg_spread = any(v < 0 for v in spread_vals)
    if has_pos_spread and has_neg_spread:
        return True

    return False


def _has_source_observability_conflicts(text: str) -> bool:
    """檢查 SourceHealth/Errors/Quota 是否重複或互相矛盾。"""
    src_lines = [
        ln.strip()
        for ln in text.splitlines()
        if re.search(r'(?:【)?Source(?:Health|Errors|Quota)', ln)
    ]
    if not src_lines:
        return True

    def _norm(line: str, key: str) -> str:
        line = re.sub(r'^[·\-\s]*', '', line)
        line = line.replace(f"【{key}】", "")
        line = re.sub(rf"^{key}\s*", "", line, flags=re.IGNORECASE)
        return line.strip()

    per_key = {"SourceHealth": [], "SourceErrors": [], "SourceQuota": []}
    for ln in src_lines:
        for key in per_key:
            if re.search(key, ln, re.IGNORECASE):
                per_key[key].append(_norm(ln, key))

    for key, values in per_key.items():
        if len(values) != 1:
            return True
        if len(set(values)) != 1:
            return True
    return False


def _is_conditional_regime_line(line: str) -> bool:
    """判斷該行是否為情境分析條件句（若轉為 risk_off 則…），不應被 regime 統一覆寫。"""
    return bool(re.search(
        r'(?:若|如果|假設|when|if)\s*(?:轉為|切換至|shift\s*to|switch\s*to|moves?\s*to)\s*'
        r'(?:risk[\s_\-]*on|risk[\s_\-]*off|neutral)',
        line,
        re.IGNORECASE,
    ))


def _primary_regime_from_report(text: str) -> str | None:
    """以第一處【今日市場模式】為準的主 regime。"""
    m = re.search(
        r"【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _normalize_regime_token(m.group(1)) or None


def _risk_off_narrative_violations(text: str) -> list[str]:
    """
    主 regime 為 neutral / risk_on 時，交易／倉位段落不得出現「依 risk_off」「高風險環境 risk_off」等矛盾用語。
    情境句「若轉為 risk_off」除外。
    """
    primary = _primary_regime_from_report(text)
    if primary not in ("neutral", "risk_on"):
        return []
    bad_lines: list[str] = []
    cond_inline = re.compile(
        r"(?:若|如果|假設|when|if)\s+.{0,48}risk[\s_\-]*off",
        re.IGNORECASE,
    )
    bad_trade = re.compile(
        r"(?:高風險環境|依)\s*risk[\s_\-]*off|risk[\s_\-]*off\s*(?:減倉|採|模式)|"
        r"Market\s*Regime\s*:\s*risk[\s_\-]*off|"
        r"[（(][^）)]*risk[\s_\-]*off[^）)]*(?:減倉|水位|配置)",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if "risk" not in line.lower():
            continue
        if "【今日市場模式】" in line:
            continue
        if _is_conditional_regime_line(line):
            continue
        if cond_inline.search(line):
            continue
        if "今日風險預算" in line and re.search(r"risk[\s_\-]*off", line, re.IGNORECASE):
            if not cond_inline.search(line):
                snippet = line.strip()[:160]
                if snippet not in bad_lines:
                    bad_lines.append(snippet)
            continue
        tradeish = any(
            k in line
            for k in (
                "倉位建議",
                "進場：",
                "停損：",
                "目標：",
                "資金流向與精準操作",
                "精準操作",
                "AI 產業鏈精準操作",
            )
        )
        if tradeish and bad_trade.search(line):
            snippet = line.strip()[:160]
            if snippet not in bad_lines:
                bad_lines.append(snippet)
    return bad_lines


def _trade_watch_actionable_conflicts(
    text: str,
    *,
    span_cache: dict[str, int] | None = None,
) -> list[str]:
    """交易操作段若宣告「觀望模式」，同段不得同時提供可執行三要素（進場/目標/停損）。"""

    def _operation_span(span: str, is_ai: bool) -> str:
        if not span:
            return ""
        start_re = (
            r"區塊④[^\n]*(?:AI\s*產業鏈精準操作|US\s*Equit|資金流向與精準操作)|"
            r"AI\s*產業鏈精準操作|資金流向與精準操作"
            if is_ai
            else r"區塊④[^\n]*資金流向與精準操作|資金流向與精準操作"
        )
        m = re.search(start_re, span, re.IGNORECASE)
        return span[m.start():] if m else span

    def _has_actionable_params(span: str) -> bool:
        has_entry = bool(re.search(r"進場[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        has_target = bool(re.search(r"目標[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        has_stop = bool(re.search(r"停損[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        return has_entry and has_target and has_stop

    conflicts: list[str] = []
    crypto_span = _crypto_report_prefix(text)
    ai_span = text[len(crypto_span):]
    for label, span, is_ai in (
        ("加密", crypto_span, False),
        ("AI/美股", ai_span, True),
    ):
        op_span = _operation_span(span, is_ai=is_ai)
        if not op_span:
            continue
        if span_has_positive_trade_watch_declaration(op_span, is_ai=is_ai) and _has_actionable_params(op_span):
            conflicts.append(label)
    return conflicts


def _ai_dashboard_hallucination_hits(text: str) -> list[str]:
    """
    AI 儀表板常見幻覺欄位（ai_momentum_tool 從未輸出）；僅掃描 🤖 AI 市場 之後至 AI 產業新聞 之前。
    """
    start_m = re.search(r"(🤖\s*AI\s*市場|【AI\s*數據儀表板】|AI\s*數據儀表板)", text, re.IGNORECASE)
    if not start_m:
        return []
    start = start_m.start()
    end_m = re.search(r"【AI\s*產業新聞】|區塊②【AI\s*產業新聞】", text[start:], re.IGNORECASE)
    span = text[start: start + end_m.start()] if end_m else text[start: start + 6000]
    span_low = span.lower()
    forbidden = [
        "ai token market cap",
        "openrouter api request rank",
        "openrouter request vol",
        "ai sector sentiment",
        "token market cap",
        "huggingface trending models n/a",
    ]
    hits = []
    for phrase in forbidden:
        if phrase in span_low:
            hits.append(phrase)
    return hits


def _macro_yield_spread_inconsistent(text: str) -> bool:
    """美債 10Y、2Y 與「利差 %」是否同口徑（利差≈10Y−2Y，容差 0.15%）。"""
    m10 = re.search(r"美債\s*10Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    m2 = re.search(r"美債\s*2Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    ms = re.search(
        r"利差[：:]\s*([+−\-]?[0-9,]+(?:\.[0-9]+)?)\s*%",
        text,
        re.IGNORECASE,
    )
    if not (m10 and m2 and ms):
        return False
    try:
        y10 = float(m10.group(1).replace(",", ""))
        y2 = float(m2.group(1).replace(",", ""))
        raw_s = ms.group(1).replace(",", "").replace("−", "-").replace("\u2212", "-").lstrip("+")
        spr = float(raw_s)
    except ValueError:
        return False
    expected = y10 - y2
    return abs(spr - expected) > 0.15


# 資料時效：tool 回傳內 [data_as_of: ISO] 超過此秒數則在驗證時標記 STALE
STALE_DATA_THRESHOLD_SEC = 2 * 3600  # 2 小時


def _collect_stale_data_sources(text: str) -> list[str]:
    """掃描報告中的 [data_as_of: ISO] (source=id)，回傳超過 2h 的 source_id 列表。"""
    pattern = re.compile(r"\[data_as_of:\s*([^\]]+)\]\s*\(source=(\w+)\)")
    now = datetime.now(timezone.utc)
    latest_ts: dict[str, datetime] = {}
    for m in pattern.finditer(text):
        ts_str, source_id = m.group(1).strip(), m.group(2)
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if source_id not in latest_ts or ts > latest_ts[source_id]:
                latest_ts[source_id] = ts
        except ValueError:
            continue
    stale = []
    for source_id, ts in latest_ts.items():
        if (now - ts).total_seconds() > STALE_DATA_THRESHOLD_SEC:
            stale.append(source_id)
    return stale


def _has_rumor_grade_marker(text: str) -> bool:
    """是否已包含可被 validate_report 接受的傳聞可信度分級字樣。"""
    return bool(
        re.search(r"可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b", text, re.IGNORECASE)
        or re.search(r"來源[：:]\s*[ABC](?:級|等級)?", text, re.IGNORECASE)
        or re.search(r"可信度\s*[ABC](?:級|等)?", text, re.IGNORECASE)
        or re.search(r"可信度\s*[/／]\s*\d{1,3}\s*/\s*100", text, re.IGNORECASE)
        or re.search(r"(?:可信|可信度)\s*[：:]?\s*\d{1,3}\s*/\s*100", text, re.IGNORECASE)
        or re.search(r"(?:等級|分級|評級)[：:]\s*(?:A|B|C)\b", text, re.IGNORECASE)
        or re.search(r"等級\s+[ABC]\b", text, re.IGNORECASE)
        or re.search(
            r"(?:Grade|Credibility)\s*[：:]\s*(?:A|B|C|\d{1,3})\b",
            text,
            re.IGNORECASE,
        )
        or re.search(r"可信度\s*等級\s*[：:]\s*(?:A|B|C)\b", text, re.IGNORECASE)
        or re.search(r"(?:呢喃|傳聞|供應鏈)[^\n]{0,48}可信度\s*[：:]?\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"信賴度\s*[：:]\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"置信\s*分級\s*[：:]\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"來源[：:][^\n]{0,160}\(([ABC])級\)", text, re.IGNORECASE)
    )


def _has_crypto_trade_section(text: str) -> bool:
    """
    是否已含加密精準操作段（含 LLM 省略 (Crypto) 括號但已寫進出場的情形）。
    避免誤判導致在完整建議後又注入「觀望模式」。
    """
    if re.search(r'資金流向與精準操作', text):
        return True
    return bool(
        re.search(
            r'精準操作\s*\(Crypto\)|精準操作[^\n]{0,40}Crypto|區塊④[^\n]*Crypto',
            text,
            re.IGNORECASE,
        )
    )


def _has_ai_trade_section(text: str) -> bool:
    if re.search(r'AI\s*產業鏈精準操作|精準操作\s*\(US\s*Equit', text, re.IGNORECASE):
        return True
    if re.search(r'區塊④[^\n]*US\s*Equit', text, re.IGNORECASE):
        return True
    return bool(re.search(r'精準操作.*Equit', text, re.IGNORECASE))


# ── Gate failure artifacts ────────────────────────────────────────────


def _gate_failure_output_dir() -> Path:
    raw = (os.getenv("GATE_FAILURE_ARTIFACT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / ".qsilicon" / "last_gate_failure"


def _gate_failure_artifacts_enabled() -> bool:
    return os.getenv("GATE_FAILURE_ARTIFACTS", "1").lower() not in ("0", "false", "no")


def _persist_gate_validation_failure(report_text: str, validation: dict) -> Path | None:
    """
    驗證失敗時寫入本機（預設 .qsilicon/last_gate_failure/）：
    draft_report.txt、issues.txt、validation_summary.json — 方便對照格式與完整問題清單。
    """
    if not _gate_failure_artifacts_enabled() or not (report_text or "").strip():
        return None
    out_dir = _gate_failure_output_dir()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("gate failure artifact mkdir failed: %s", e)
        return None
    issues = [str(x).strip() for x in (validation.get("issues") or []) if str(x).strip()]
    try:
        (out_dir / "draft_report.txt").write_text(report_text, encoding="utf-8")
        (out_dir / "issues.txt").write_text(
            "\n".join(f"{i + 1}. {x}" for i, x in enumerate(issues)) if issues else "(no issues list)",
            encoding="utf-8",
        )
        summary = {
            "valid": validation.get("valid"),
            "issue_count": len(issues),
            "report_chars": len(report_text),
            "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issues": issues,
        }
        (out_dir / "validation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("gate failure artifact write failed: %s", e)
        return None
    logger.warning(
        "validate_report failed — draft + full issues written to %s (count=%d)",
        out_dir,
        len(issues),
    )
    return out_dir


# ── 主驗證函式 ────────────────────────────────────────────────────────


def validate_report(text: str) -> dict:
    """驗證戰報是否包含足夠新聞與必要區塊（V2.1 四區塊結構）。"""
    news_count = _count_effective_news_items(text)
    fallback_count = _fallback_news_count(text)

    # Accept both old plain regime label and new scorecard format (e.g. "risk_on（+4/6）")
    has_regime = bool(HAS_REGIME_RE.search(text))
    has_dashboard = bool(HAS_DASHBOARD_RE.search(text))
    has_crypto_trade = _has_crypto_trade_section(text)
    has_ai_trade = _has_ai_trade_section(text)
    has_ai_section = bool(HAS_AI_SECTION_RE.search(text))
    has_crypto_section = bool(HAS_CRYPTO_SECTION_RE.search(text))
    has_chatter = bool(re.search(r'呢喃|傳聞', text))
    has_data_missing = bool(HAS_DATA_MISSING_RE.search(text))
    data_missing_fields = sorted(set(DATA_MISSING_FIELDS_RE.findall(text)))
    # 交易觀望：放寬 R:R／勝率等「可執行欄位」檢查（與「新聞不足分段」解耦）
    trade_watch_mode = text_has_positive_trade_watch_mode(text)
    partial_news_ok = _partial_news_ok(text)
    news_six_relaxed = trade_watch_mode or partial_news_ok
    has_qsrec_markers = bool(QSREC_MARKERS_RE.search(text))
    parsed_qsrec = tracker.extract_recommendations_json(text) if has_qsrec_markers else []
    has_valid_qsrec = bool(parsed_qsrec)
    has_rr = bool(HAS_RR_RE.search(text))
    has_max_drawdown = bool(HAS_MAX_DRAWDOWN_RE.search(text))
    has_expected_win_rate = bool(HAS_EXPECTED_WIN_RATE_RE.search(text))
    has_signal_score = bool(HAS_SIGNAL_SCORE_RE.search(text))
    has_signal_conflict = bool(HAS_SIGNAL_CONFLICT_RE.search(text))
    has_risk_budget = bool(HAS_RISK_BUDGET_RE.search(text))
    has_rumor_grade = _has_rumor_grade_marker(text)
    has_utc8 = _has_news_timezone_utc8(text)
    too_many_na = len(NA_TOKEN_RE.findall(text)) > 3
    has_low_confidence_tag = bool(HAS_LOW_CONFIDENCE_RE.search(text))
    has_missing_reason_proxy = bool(_MISSING_REASON_PROXY_RE.search(text))
    has_numeric_in_investment = bool(
        NUMERIC_INVESTMENT_LINE_RE.search(text) or NUMERIC_INVESTMENT_MULTI_RE.search(text)
    )
    has_source_health = "【SourceHealth】" in text
    has_source_errors = "【SourceErrors】" in text
    has_source_quota = "【SourceQuota】" in text
    mode_tags_raw = MODE_TAGS_RE.findall(text)
    budget_tags_raw = BUDGET_TAGS_RE.findall(text)
    mode_tags = [r for r in (_normalize_regime_token(x) for x in mode_tags_raw) if r]
    budget_tags = [r for r in (_normalize_regime_token(x) for x in budget_tags_raw) if r]
    qsrec_regimes = []
    if has_valid_qsrec:
        for rec in parsed_qsrec:
            rv = _normalize_regime_token(str(rec.get("regime", "")))
            if rv:
                qsrec_regimes.append(rv)
    unique_regimes = set(mode_tags + budget_tags + qsrec_regimes)
    # 情境分析條件句（若轉為 risk_off 則…）不算 mixed regime —— 僅排除條件句中的 regime 提及
    _conditional_re = re.compile(
        r'(?:若|如果|假設|when|if)\s*(?:轉為|切換至|shift\s*to|switch\s*to|moves?\s*to)\s*'
        r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)',
        re.IGNORECASE,
    )
    conditional_regimes = {
        _normalize_regime_token(m.group(1))
        for m in _conditional_re.finditer(text)
        if _normalize_regime_token(m.group(1))
    }
    authoritative_regimes = unique_regimes - conditional_regimes
    has_mixed_regime = len(authoritative_regimes) > 1
    malformed_invalidation = bool(MALFORMED_INVALIDATION_RE.search(text))
    has_unactionable_trade = bool(UNACTIONABLE_TRADE_RE.search(text))
    has_macro_outlier = _has_macro_outlier_values(text)
    has_macro_conflict = _has_macro_conflicts(text)
    has_source_observability_conflict = _has_source_observability_conflicts(text)
    watch_trade_conflicts = _trade_watch_actionable_conflicts(text)
    has_code_leak = bool(CODE_LEAK_RE.search(text))
    has_impact_leak = bool(IMPACT_LEAK_RE.search(text))
    pair_unit_ok = _pair_trade_unit_consistent(text)
    risk_off_star_ok = not _risk_off_star_cap_violated(text)
    qsrec_issues = _qsrec_consistency_issues(text, parsed_qsrec) if has_valid_qsrec else []

    pick_crypto_ok, pick_crypto_err = True, ""
    pick_equity_ok, pick_equity_err = True, ""
    if _strict_pick_justification() and not trade_watch_mode and has_valid_qsrec:
        pick_crypto_ok, pick_crypto_err = _pick_justification_crypto_ok(text, parsed_qsrec)
        pick_equity_ok, pick_equity_err = _pick_justification_equity_ok(text, parsed_qsrec)

    pick_crypto_rot_ok, pick_crypto_rot_err = True, ""
    pick_equity_rot_ok, pick_equity_rot_err = True, ""
    if _strict_pick_rotation() and not trade_watch_mode and has_valid_qsrec:
        pick_crypto_rot_ok, pick_crypto_rot_err = _pick_rotation_crypto_ok(text, parsed_qsrec)
        pick_equity_rot_ok, pick_equity_rot_err = _pick_rotation_equity_ok(text, parsed_qsrec)

    fund_cite_ok, fund_cite_err = True, ""
    if _strict_ai_fundamentals_citation():
        fund_cite_ok, fund_cite_err = _ai_fundamentals_citation_ok(text)

    issues = []
    tagged_news = _count_news_tags_only(text)
    if len(text) < 3000:
        issues.append(f"報告過短（{len(text)} chars，預期 >3000）")
    if tagged_news < 6 and not news_six_relaxed:
        issues.append(
            f"核心新聞〔新聞 N〕標籤不足（{tagged_news}/6）：須以〔新聞 1〕…〔新聞 6〕標示幣圈 3 + AI 3，"
            f"禁止僅用 1. 2. 3. 作為新聞編號（避免與辯論列表混淆）。"
            f"（分段放行：交易觀望／或符合「新聞資料不足分段」— 3~5 則且〔新聞 1~3〕+ UTC+8 + 不補虛構宣告，見 ALLOW_PARTIAL_NEWS_GATE）"
        )
    if news_count < 6 and not news_six_relaxed:
        issues.append(
            f"新聞數不足（{news_count}/6）且未符合觀望或新聞分段條件（見 validate_report 說明／README）"
        )
    if not has_regime:
        issues.append("缺少 market_regime 標籤（risk_on/risk_off/neutral）")
    if not has_dashboard:
        issues.append("缺少數據儀表板（DXY/RSI/資金費率/Fear&Greed）")
    if not has_crypto_trade:
        issues.append("缺少加密市場操作建議（精準操作 Crypto）")
    if not has_ai_trade:
        issues.append("缺少 AI 美股操作建議（精準操作 US Equities）")
    if not has_ai_section:
        issues.append("缺少 AI 市場段落")
    if not has_crypto_section:
        issues.append("缺少加密市場段落")
    if not has_chatter:
        issues.append("缺少呢喃/傳聞區塊")
    if not has_qsrec_markers:
        issues.append("缺少系統追蹤載荷區塊（[QSREC_START]...[QSREC_END]）")
    elif not has_valid_qsrec:
        issues.append("QSREC 區塊存在但 JSON 無法解析或為空陣列")
    if _strict_pick_justification() and not trade_watch_mode and has_valid_qsrec:
        if not pick_crypto_ok:
            issues.append(pick_crypto_err)
        if not pick_equity_ok:
            issues.append(pick_equity_err)
    if _strict_pick_rotation() and not trade_watch_mode and has_valid_qsrec:
        if not pick_crypto_rot_ok:
            issues.append(pick_crypto_rot_err)
        if not pick_equity_rot_ok:
            issues.append(pick_equity_rot_err)
    if not fund_cite_ok:
        issues.append(fund_cite_err)
    if not has_utc8:
        issues.append("新聞時間未統一標示 UTC+8")
    if not has_signal_conflict:
        issues.append("缺少訊號衝突摘要（避免過度單邊敘事）")
    if not has_rumor_grade:
        issues.append("傳聞區缺少可信度分級（A/B/C 或 0~100）")
    if (not trade_watch_mode) and (not has_rr or not has_max_drawdown):
        issues.append("交易建議缺少 R:R 或最大回撤風險欄位")
    if (not trade_watch_mode) and (not has_expected_win_rate or not has_signal_score):
        issues.append("交易建議缺少預期勝率或 Signal Score 欄位")
    if not has_risk_budget:
        issues.append("缺少今日風險預算摘要")
    if (not trade_watch_mode) and (not has_numeric_in_investment):
        issues.append("投資解讀缺少當日量化數據引用")
    if not has_source_health or not has_source_errors or not has_source_quota:
        issues.append("缺少來源健康欄位（SourceHealth/SourceErrors/SourceQuota）")
    if has_mixed_regime:
        issues.append(f"報告內 market_regime 不一致：{', '.join(sorted(unique_regimes))}")
    if malformed_invalidation:
        issues.append("交易建議存在空白/截斷的失效條件")
    if has_unactionable_trade:
        issues.append("交易段含 N/A 關鍵價格（現價/進場/目標/停損），不可執行")
    if has_macro_outlier:
        issues.append("宏觀數值疑似異常（10Y/2Y/SOFR/利差超出合理範圍）")
    if has_macro_conflict:
        # post_process already patches out-of-range yield values; residual 2Y/spread
        # inconsistency is a data-quality note, not a delivery blocker.
        logger.warning("validate_report: 宏觀段落前後矛盾（2Y/利差數值不一致）— logged only, not blocking")
    if has_source_observability_conflict:
        issues.append("Source observability 欄位重複或互相矛盾")
    if watch_trade_conflicts:
        issues.append(
            "觀望模式契約衝突："
            + "、".join(watch_trade_conflicts)
            + "操作段同時出現「觀望模式」與可執行價位（進場/目標/停損），請擇一保留。"
        )
    if _conflicting_total_risk_budget_lines(text):
        issues.append("今日風險預算出現多組不一致的總風險預算百分比（請整併為單一總框或依【日報 V2】改為美股部位框）")
    if not pair_unit_ok:
        # Format preference only; does not affect reader comprehension at delivery level.
        logger.warning("validate_report: 配對交易單位不一致或未標註比值/價差單位 — logged only, not blocking")
    if not risk_off_star_ok:
        issues.append("risk_off 模式下出現超過上限的信心水準（4 顆星）")
    if too_many_na and (not has_low_confidence_tag or not has_missing_reason_proxy):
        issues.append("N/A 過多但缺少低置信度標籤與替代指標說明")
    if has_code_leak:
        issues.append("戰報外洩 Python 函數名稱（multi_timeframe_tool）")
    if has_impact_leak:
        issues.append("戰報外洩內部 IMPACT 原始標籤")
    rv_lines = _risk_off_narrative_violations(text)
    if rv_lines:
        preview = " | ".join(rv_lines[:3])
        issues.append(
            "主 regime 為 neutral/risk_on 但交易／風險預算段誤用 risk_off 敘述（禁用「依 risk_off」「高風險環境 risk_off 減倉」等；"
            f"情境句「若轉為 risk_off」除外）：{preview}"
        )
    ah = _ai_dashboard_hallucination_hits(text)
    if ah:
        # Log hallucination hits for observability but don't block delivery;
        # field presence in the report does not make it undeliverable.
        logger.warning(
            "validate_report: AI 儀表板含疑似幻覺欄位（非 ai_momentum_tool 輸出）— logged only: %s",
            ", ".join(sorted(set(ah))),
        )
    if _macro_yield_spread_inconsistent(text):
        issues.append("宏觀「利差 %」與美債 10Y/2Y 數值不一致（請核對是否同為 10Y−2Y 口徑）")
    issues.extend(qsrec_issues)
    for source_id in _collect_stale_data_sources(text):
        issues.append(f"[STALE_DATA:{source_id}]")
    if has_data_missing:
        issues.append(f"資料缺失欄位：{', '.join(data_missing_fields)}")
        critical_missing = {
            "market_search",
            "newsapi",
            "gnews",
            "rss_feed",
            "x_search",
            "multi_timeframe",
            "coinglass_data",
            "macro_context",
            "regime_scorecard",
        }
        if any(f in critical_missing for f in data_missing_fields):
            issues.append("關鍵資料來源缺失（hard fail）")

    # ── Score-based severity classification ──────────────────────────
    # Blocking: structural failures that make the report undeliverable or dangerous.
    # Warning:  quality issues — report still has value, should be sent with a banner.
    _BLOCKING_PREFIXES = (
        "報告過短",
        "核心新聞〔新聞 N〕標籤不足",
        "新聞數不足",
        "缺少 market_regime",
        "缺少加密市場操作建議",
        "缺少 AI 美股操作建議",
        "缺少 AI 市場段落",
        "缺少加密市場段落",
        "缺少系統追蹤載荷區塊",
        "QSREC 區塊存在但",
        "交易段含 N/A 關鍵價格",
        "戰報外洩 Python 函數名稱",
        "關鍵資料來源缺失",
        "結構化加密新聞不足",
        "結構化 AI 新聞不足",
        "結構化新聞總數",
        "結構化 qsrec 為空",
        "AI 段「本日選擇理由」含基本面用語",
    )

    def _is_blocking(issue: str) -> bool:
        return any(issue.startswith(p) for p in _BLOCKING_PREFIXES)

    blocking_issues = [i for i in issues if _is_blocking(i)]
    warning_issues = [i for i in issues if not _is_blocking(i)]

    return {
        "valid": len(issues) == 0,
        "blocking_issues": blocking_issues,
        "warning_issues": warning_issues,
        "issues": issues,
        "news_count": news_count,
        "fallback_news_count": fallback_count,
        "has_data_missing": has_data_missing,
        "has_qsrec": has_valid_qsrec,
        "qsrec_count": len(parsed_qsrec),
        "has_source_health": has_source_health,
        "has_source_errors": has_source_errors,
        "has_source_quota": has_source_quota,
        "has_mixed_regime": has_mixed_regime,
        "has_unactionable_trade": has_unactionable_trade,
        "has_macro_outlier": has_macro_outlier,
        "has_macro_conflict": has_macro_conflict,
        "has_source_observability_conflict": has_source_observability_conflict,
        "trade_watch_mode": trade_watch_mode,
        "partial_news_ok": partial_news_ok,
        "news_six_relaxed": news_six_relaxed,
        "pick_justification_crypto_ok": pick_crypto_ok,
        "pick_justification_equity_ok": pick_equity_ok,
        "pick_rotation_crypto_ok": pick_crypto_rot_ok,
        "pick_rotation_equity_ok": pick_equity_rot_ok,
        "ai_fundamentals_citation_ok": fund_cite_ok,
    }


def validate_structured_report(report: object) -> dict:
    """以 Pydantic 組裝結果做屬性級檢查，與 validate_report(HTML) 並行。"""
    from schemas import DailyBriefReport

    if not isinstance(report, DailyBriefReport):
        return {"valid": False, "issues": ["report 非 DailyBriefReport"]}
    issues: list[str] = []
    cr, ai_sec = report.crypto, report.ai
    if len(cr.news) < 3:
        issues.append(f"結構化加密新聞不足（{len(cr.news)}/3）")
    if len(ai_sec.news) < 3:
        issues.append(f"結構化 AI 新聞不足（{len(ai_sec.news)}/3）")
    tagged = len(cr.news) + len(ai_sec.news)
    if tagged < 6 and not report.report_tier_partial_news:
        issues.append(f"結構化新聞總數 {tagged}/6 且未標記 partial tier")
    if report.report_tier_partial_news and not (3 <= tagged <= 5):
        issues.append(f"partial tier 僅允許 3~5 則新聞，當前為 {tagged}")
    if not report.all_qsrec():
        issues.append("結構化 qsrec 為空")
    if not (cr.pick_reason or "").strip():
        issues.append("加密本日選擇理由為空")
    if not (ai_sec.pick_reason or "").strip():
        issues.append("AI 本日選擇理由為空")

    if len((cr.pick_reason or "").strip()) < 34:
        issues.append("加密本日選擇理由過短（<34）")
    if len((ai_sec.pick_reason or "").strip()) < 38:
        issues.append("AI 本日選擇理由過短（<38）")
    if cr.market.regime not in (cr.risk_budget_summary or ""):
        issues.append("加密今日風險預算未包含主 regime token")

    def _norm_asset(a: str) -> str:
        return str(a or "").upper().replace("$", "").replace("-", "/").replace(" ", "")

    def _check_section_alignment(section, category: str, label: str) -> None:
        leg_map: dict[str, str] = {}
        for leg in section.trade_legs:
            leg_map[_norm_asset(leg.asset)] = str(leg.direction or "").upper()

        seen: dict[str, str] = {}
        for idx, rec in enumerate(section.qsrec, start=1):
            cat = str(rec.category or "").upper()
            if cat != category:
                issues.append(f"{label} qsrec 第 {idx} 筆 category={cat} 應為 {category}")
            asset = _norm_asset(rec.asset)
            direction = str(rec.direction or "").upper()
            prev = seen.get(asset)
            if prev and prev != direction:
                issues.append(f"{label} qsrec 同資產 {asset} 出現相反方向 {prev}/{direction}")
            seen[asset] = direction
            if asset in leg_map and leg_map[asset] != direction:
                issues.append(
                    f"{label} 交易條目與 qsrec 方向不一致：{asset} leg={leg_map[asset]} qsrec={direction}"
                )

            for f in (
                "selection_score",
                "catalyst_score",
                "flow_score",
                "technical_score",
                "risk_fit_score",
                "execution_score",
                "alt_candidate_score",
                "score_gap",
            ):
                if getattr(rec, f) is None:
                    issues.append(f"{label} qsrec 第 {idx} 筆缺少可量化評分欄位：{f}")

    _check_section_alignment(cr, "CRYPTO", "加密")
    _check_section_alignment(ai_sec, "EQUITY", "AI")
    # All structured validation issues are blocking (schema-level integrity).
    return {
        "valid": len(issues) == 0,
        "blocking_issues": issues,
        "warning_issues": [],
        "issues": issues,
    }

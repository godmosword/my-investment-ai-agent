"""Unit tests for validate_report() and its helper functions in main.py."""

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from tracker import extract_recommendations_json

from report_html_gates import (
    _chatter_msm_verify_ok,
    _count_effective_news_items,
    _investment_takeaway_dashboard_numeric_ok,
    _normalize_regime_token,
    _pick_justification_crypto_ok,
    _qsrec_consistency_issues,
    _risk_off_narrative_violations,
)

from schemas import validate_structured_report

from main import (
    validate_report,
    strip_html,
    _crypto_report_prefix,
    _fallback_news_count,
    _has_news_timezone_utc8,
    _has_macro_outlier_values,
    _has_macro_conflicts,
    _risk_off_star_cap_violated,
    _pair_trade_unit_consistent,
    _has_crypto_trade_section,
    _partial_news_ok,
    _pick_rotation_crypto_ok,
    _pick_rotation_equity_ok,
    _pick_rotation_override_min_gap,
    _has_rumor_grade_marker,
    _conflicting_total_risk_budget_lines,
    _qsrec_opposing_direction_same_asset,
)
from report_postprocess_legacy import (
    _auto_prefix_missing_news_tags,
    _ensure_rumor_grade_marker,
    _fix_glued_na_suffix,
    _inject_canonical_prev_recs_block,
    _normalize_news_timezone_utc8,
    _postprocess_report_for_resilience,
    _sanitize_macro_outlier_values,
)


# ── Minimal valid report template ──
# Enough sections / keywords to pass most checks; tests override specific parts.
_PHASE_A_HTML_FOR_GATE_TESTS = (
    "<blockquote>"
    "本電報內容僅為研究性質之市場摘要與架構化資訊彙編，<b>不構成</b>任何司法管轄區內之投資、法律或稅務建議；"
    "<b>非</b>個人化勸誘。"
    "過去績效不預示未來結果；資料可能延遲，讀者自行核實。"
    "</blockquote>\n"
    "<b>【投資命題】</b>\n"
    "測試主命題一句涵蓋加密與美股主軸及跨資產邏輯。\n"
    "<b>【支持論點】</b>\n"
    "· 論點甲：BTC 結構與 ETF 流與儀表板讀數一致\n"
    "· 論點乙：NVDA 基本面與資料中心 Capex 敘事\n"
    "· 論點丙：宏觀流動性與 regime 評分卡方向對齊\n"
    "<b>【反駁論點】</b>\n"
    "· 反駁甲：槓桿與清算導致急性回撤\n"
    "· 反駁乙：利率路徑重訂壓縮估值\n"
    "· 反駁丙：監管與地緣不確定性升溫\n"
    "<b>【關鍵假設】</b>\n"
    "· 假設一：短期利率大致符合市場隱含路徑\n"
    "· 假設二：主要標的維持合理流動性\n"
    "<b>【敘事失效】</b>\n"
    "若通膨預期顯著重訂或現貨 ETF 資金流持續逆轉，應重估本日主命題。\n"
)

_PHASE_B_HTML_FOR_GATE_TESTS = (
    "<b>【組合與曝險框架】</b>\n"
    "加密與美股合計採風險預算內雙軸配置；淨曝險偏多但保留宏觀對沖空間；"
    "與 SPY 相關性中高、與 BTC 同向風險偏好；未使用額外衍生對沖僅以倉位縮放管理。\n"
    "<b>【三情境機率】</b>\n"
    "· 樂觀：風險資產延續（機率 30%）\n"
    "· 基準：區間震盪（機率 45%）\n"
    "· 悲觀：流動性收縮（機率 25%）\n"
)


def _make_report(
    *,
    length: int = 5000,
    news_count: int = 8,
    regime: str = "risk_on",
    include_dashboard: bool = True,
    include_crypto_trade: bool = True,
    include_ai_trade: bool = True,
    include_ai_section: bool = True,
    include_crypto_section: bool = True,
    include_chatter: bool = True,
    include_qsrec: bool = True,
    include_source_health: bool = True,
    include_exec_summary: bool = True,
    include_phase_a_institutional: bool = True,
    include_phase_b_institutional: bool = False,
    include_signal_conflict: bool = True,
    include_rumor_grade: bool = True,
    include_rr: bool = True,
    include_risk_budget: bool = True,
    include_numeric_investment: bool = True,
    extra: str = "",
    inject_before_qsrec: str = "",
) -> str:
    news = ""
    for i in range(1, news_count + 1):
        pricing_line = ""
        if include_phase_b_institutional:
            if i <= 3:
                canon = "未定價／增量資訊"
            elif i <= 6:
                canon = "大致已定價"
            else:
                canon = "已高度反應"
            pricing_line = f"\n市場定價：{canon}"
        news += (
            f"〔新聞 {i}〕[03/{i:02d} 10:00 UTC+8] 來源\n"
            f"測試新聞標題 {i} 內容夠長超過十字元{pricing_line}\n\n"
        )

    sections = [f"【今日市場模式】 {regime}"]
    if include_dashboard:
        sections.append("DXY 104.5 ｜ BTC OI $18.5B ｜ 資金費率 0.01% ｜ RSI 55 ｜ Fear & Greed 45")
    if include_crypto_trade:
        sections.append(
            "區塊④ 資金流向與精準操作 (Crypto)\n"
            "本日選擇理由：現貨 ETF 淨流入與監管新聞構成催化，鏈上資金費率與多空比同步支持偏多結構，選 BTC 作為單邊主倉。\n"
            "· $BTC (LONG)｜現價：$95000｜進場：$94500｜目標：$100000｜停損：$91000"
        )
    if include_ai_section:
        sections.append("────────────\n🤖 AI 市場\nAI 數據儀表板\n· FinancialDatasets NVDA 年度損益：營收 $61B")
    if include_ai_trade:
        sections.append(
            "AI 產業鏈精準操作 (US Equities)\n"
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。\n"
            "· $NVDA (LONG)｜現價：$890"
        )
    if include_crypto_section:
        sections.append("加密市場核心新聞")
    if include_chatter:
        sections.append("呢喃與傳聞掃描")
    if include_signal_conflict:
        sections.append("訊號衝突摘要：短期動能與中期結構分歧")
    if include_rumor_grade:
        sections.append("可信度：B")
    if include_rr:
        sections.append("R:R = 1:2.5\n最大回撤風險：<code>-3.7%</code>\n預期勝率：55%\nSignal Score：72/100")
    if include_risk_budget:
        sections.append(f"今日風險預算：{regime} 模式下總倉位上限 15%")
    if include_numeric_investment:
        sections.append("投資解讀：BTC 日線 RSI 55，ETF 流入 $120M")
    if include_source_health:
        sections.append("【SourceHealth】 5/5 正常\n【SourceErrors】 0 次\n【SourceQuota】 NewsAPI 82%")
    if include_qsrec:
        sections.append(
            "[QSREC_START]\n"
            "["
            '{"asset":"BTC","direction":"LONG","current_price":95000,"entry":94500,'
            '"target":100000,"stop":91000,"confidence":4,"category":"CRYPTO",'
            f'"narrative":"test","trigger":"x","invalidation":"y","position_pct":5,"timeframe":"3d","regime":"{regime}",'
            '"selection_score":78,"catalyst_score":80,"flow_score":76,"technical_score":75,"risk_fit_score":74,"execution_score":79,"alt_candidate_score":63,"score_gap":15,"repeat_days":1'
            "},"
            '{"asset":"NVDA","direction":"LONG","current_price":890,"entry":885,'
            '"target":950,"stop":860,"confidence":4,"category":"EQUITY",'
            f'"narrative":"test","trigger":"x","invalidation":"y","position_pct":5,"timeframe":"5d","regime":"{regime}",'
            '"selection_score":81,"catalyst_score":84,"flow_score":78,"technical_score":80,"risk_fit_score":77,"execution_score":82,"alt_candidate_score":65,"score_gap":16,"repeat_days":1'
            "}]\n"
            "[QSREC_END]"
        )

    joined = "\n".join(sections)
    if inject_before_qsrec:
        joined = joined.replace("[QSREC_START]", inject_before_qsrec + "\n[QSREC_START]", 1)
    exec_hdr = ""
    if include_exec_summary:
        exec_hdr = (
            "【執行摘要】\n"
            "· 測試摘要甲：風險可控延續觀察 BTC 偏多結構\n"
            "→ 測試摘要乙：美股以 NVDA 財報催化為主軸\n\n"
        )
    phase_a = _PHASE_A_HTML_FOR_GATE_TESTS if include_phase_a_institutional else ""
    phase_b = _PHASE_B_HTML_FOR_GATE_TESTS if include_phase_b_institutional else ""
    body = news + exec_hdr + phase_a + phase_b + joined + "\n" + extra
    # Pad to requested length
    if len(body) < length:
        body += "\n" + "x" * (length - len(body))
    return body


def _make_minimal_structured_report_dbr(
    *,
    crypto_news: int = 3,
    ai_news: int = 3,
    has_qsrec_recs: bool = True,
    partial_tier: bool = False,
    portfolio_framing_summary: str = "",
    scenario_probability_notes: str = "",
):
    """Build minimal valid DailyBriefReport for structured gate tests."""
    from schemas import (
        AISection,
        CryptoSection,
        DailyBriefReport,
        MarketRegimeBlock,
        MetricLine,
        NewsItem,
        TradeRecommendation,
    )

    _pn_cycle = ("未定價／增量資訊", "大致已定價", "已高度反應")

    def _ni(idx: int) -> NewsItem:
        return NewsItem(
            index=idx,
            timestamp_line=f"[03/{idx:02d} 10:00 UTC+8]",
            title=f"Headline {idx}",
            source_and_nature="Source confirmed",
            summary=f"Summary line {idx}.",
            investment_takeaway=f"BTC RSI 55, takeaway {idx}.",
            editor_consensus="Positive on BTC.",
            pricing_note=_pn_cycle[(idx - 1) % 3],
        )

    _scores = {
        "selection_score": 80.0,
        "catalyst_score": 70.0,
        "flow_score": 75.0,
        "technical_score": 72.0,
        "risk_fit_score": 68.0,
        "execution_score": 77.0,
        "alt_candidate_score": 60.0,
        "score_gap": 20.0,
    }
    qsrec = (
        [
            TradeRecommendation(
                asset="BTC",
                direction="LONG",
                current_price=95000,
                entry=94500,
                target=100000,
                stop=91000,
                confidence=4,
                category="CRYPTO",
                narrative="ETF 流入延續偏多。",
                trigger="突破前高",
                invalidation="跌破支撐",
                position_pct=5.0,
                timeframe="3d",
                bull_scenario="量能延續看 100k。",
                base_scenario="區間震盪機率 50%。",
                bear_scenario="跌破 91k 退場。",
                **_scores,
            )
        ]
        if has_qsrec_recs
        else []
    )
    crypto = CryptoSection(
        report_title_date="2026-03-24",
        market=MarketRegimeBlock(regime="risk_on"),
        narrative_of_day="BTC 上漲",
        portfolio_framing_summary=portfolio_framing_summary,
        scenario_probability_notes=scenario_probability_notes,
        dashboard=[MetricLine(label="BTC", value="$95000")],
        news=[_ni(i) for i in range(1, crypto_news + 1)],
        pick_reason=(
            "ETF 淨流入超過 12 億美元且鏈上 SOPR 回升，短期風險偏好延續有利風險資產配置"
        ),
        risk_budget_summary="risk_on 模式下總倉位 15%",
        signal_conflict_summary="無顯著衝突",
        qsrec=qsrec,
    )
    ai_sec = AISection(
        dashboard=[MetricLine(label="NVDA", value="$890")],
        news=[_ni(i) for i in range(4, 4 + ai_news)],
        pick_reason=(
            "NVDA 財報前瞻與 GPU 拉貨動能見於主流媒體，資料中心 Capex 敘事強化，故優先佈局 NVDA 核心部位"
        ),
        signal_conflict_summary="無衝突",
    )
    return DailyBriefReport(
        crypto=crypto,
        ai=ai_sec,
        report_tier_partial_news=partial_tier,
    )


class TestStripHtml(unittest.TestCase):
    def test_removes_tags(self):
        self.assertEqual(strip_html("<b>hello</b>"), "hello")

    def test_no_tags(self):
        self.assertEqual(strip_html("plain text"), "plain text")


class TestCountEffectiveNewsItems(unittest.TestCase):
    def test_tagged_news(self):
        text = "〔新聞 1〕title\n〔新聞 2〕title\n〔新聞 3〕title"
        self.assertEqual(_count_effective_news_items(text), 3)

    def test_numbered_dot(self):
        text = "1. First news\n2. Second news\n3. Third news"
        self.assertEqual(_count_effective_news_items(text), 3)

    def test_numbered_paren(self):
        text = "1) First\n2) Second"
        self.assertEqual(_count_effective_news_items(text), 2)

    def test_empty(self):
        self.assertEqual(_count_effective_news_items(""), 0)

    def test_tagged_wins_over_numbered_lists(self):
        """辯論區的 1. 2. 不應與〔新聞〕一起被 max() 誤算。"""
        text = (
            "〔新聞 1〕[03/01 10:00 UTC+8] <b>A</b>\n"
            "〔新聞 2〕[03/01 11:00 UTC+8] <b>B</b>\n"
            "〔新聞 3〕[03/01 12:00 UTC+8] <b>C</b>\n"
            "1. 反向觀點甲\n"
            "2. 反向觀點乙\n"
            "3. 反向觀點丙\n"
        )
        self.assertEqual(_count_effective_news_items(text), 3)


class TestFallbackNewsCount(unittest.TestCase):
    def test_counts_fallback_markers(self):
        text = "資料源不足：自動降級補位\n其他\n資料源不足：自動降級補位"
        self.assertEqual(_fallback_news_count(text), 2)

    def test_no_fallbacks(self):
        self.assertEqual(_fallback_news_count("normal report"), 0)


class TestNormalizeRegimeToken(unittest.TestCase):
    def test_risk_on(self):
        self.assertEqual(_normalize_regime_token("risk_on"), "risk_on")
        self.assertEqual(_normalize_regime_token("Risk On"), "risk_on")
        self.assertEqual(_normalize_regime_token("RISK-OFF"), "risk_off")

    def test_neutral(self):
        self.assertEqual(_normalize_regime_token("neutral"), "neutral")

    def test_invalid(self):
        self.assertIsNone(_normalize_regime_token("bullish"))
        self.assertIsNone(_normalize_regime_token(""))


class TestInjectCanonicalPrevRecs(unittest.TestCase):
    def test_replaces_llm_tracker_block(self):
        prev = "<b>【上期建議追蹤】</b>\n<i>（2026-03-20）</i>\nONE"
        report = (
            "TITLE\n\n【上期建議追蹤】\nFAKE ROW 1\nFAKE ROW 2\n\n【今日市場模式】 neutral"
        )
        out = _inject_canonical_prev_recs_block(report, prev)
        self.assertIn("ONE", out)
        self.assertNotIn("FAKE ROW", out)
        self.assertIn("【今日市場模式】", out)

    def test_strips_llm_tracker_when_canonical_empty(self):
        """無 BigQuery 上期資料時仍應移除模型幻覺之多列追蹤。"""
        report = "H\n\n【上期建議追蹤】\nFAKE\n\n【今日市場模式】 neutral"
        out = _inject_canonical_prev_recs_block(report, "")
        self.assertNotIn("FAKE", out)
        self.assertIn("【今日市場模式】", out)


class TestAutoPrefixNewsTags(unittest.TestCase):
    def test_prefixes_crypto_timestamp_and_ai_summary_blocks(self):
        raw = (
            "【區塊② 核心新聞】\n"
            "[03/21 10:00 UTC+8] Crypto headline\n"
            "投資解讀：x\n"
            "【AI 產業新聞】\n"
            "English AI Title Here Long Enough\n"
            "摘要：body\n"
        )
        out = _auto_prefix_missing_news_tags(raw)
        self.assertIn("〔新聞 1〕[03/21 10:00 UTC+8]", out)
        self.assertIn("〔新聞 2〕English AI Title", out)


class TestHasNewsTimezoneUtc8(unittest.TestCase):
    def test_tagged_with_utc8(self):
        text = "〔新聞 1〕[03/20 10:00 UTC+8] Source\n〔新聞 2〕[2026/03/20 11:00 UTC+8] Source"
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_tagged_gmt8_and_fullwidth_plus(self):
        text = (
            "〔新聞 1〕[03/20/2026 9:05 GMT+8] A\n"
            "〔新聞 2〕[2026-03-20 11:00 UTC＋8] B"
        )
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_tagged_utc08_colon_accepted(self):
        text = "〔新聞 1〕[03/20/2026 9:05 UTC+08:00] A\n〔新聞 2〕[2026-03-20 11:00 中國標準時間] B"
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_fullwidth_brackets_then_normalize(self):
        raw = "〔新聞 1〕［03/20 10:00］ Src\n"
        out = _normalize_news_timezone_utc8(raw)
        self.assertIn("UTC+8", out)
        self.assertTrue(_has_news_timezone_utc8(out))

    def test_split_line_news_tag_merged(self):
        raw = "〔新聞 1〕\n[03/20 10:00] headline\n"
        out = _normalize_news_timezone_utc8(raw)
        self.assertIn("〔新聞 1〕", out)
        self.assertIn("UTC+8", out)
        self.assertTrue(_has_news_timezone_utc8(out))

    def test_mixed_tagged_timestamp_and_ai_title_only(self):
        """AI 標題被補上〔新聞 N〕但未含時間戳時，不應拖累已標示 UTC+8 的時間戳新聞。"""
        text = (
            "〔新聞 1〕[03/20 10:00 UTC+8] Crypto\n"
            "〔新聞 2〕AI Title Only\n"
            "摘要：something\n"
        )
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_tagged_timestamp_without_timezone_still_fails(self):
        text = "〔新聞 1〕[03/20 10:00] Source\n"
        self.assertFalse(_has_news_timezone_utc8(text))

    def test_tagged_hkt_and_code_wrapped_timestamp(self):
        """Telegram 戰報常在時間外層包 <code>；亦接受 HKT／香港時間。"""
        text = (
            "〔新聞 1〕[<code>03/20 10:00 HKT</code>] Src\n"
            "〔新聞 2〕[2026/03/20 11:00 香港時間] Src"
        )
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_tagged_without_utc8(self):
        text = "〔新聞 1〕Source\ntitle"
        self.assertFalse(_has_news_timezone_utc8(text))

    def test_footer_noise_ignored_for_tag_count(self):
        """【新聞資料狀態】行內若含範例〔新聞 1〕字樣，不應破壞 UTC+8 全數比對。"""
        text = (
            "〔新聞 1〕[03/20 10:00 UTC+8] A\n"
            "【新聞資料狀態】若〔新聞 1〕格式未統一請主編修正\n"
        )
        self.assertTrue(_has_news_timezone_utc8(text))

    def test_numbered_fallback_accepted(self):
        text = "1) First news item\n2) Second news"
        self.assertTrue(_has_news_timezone_utc8(text))


class TestPickRotation(unittest.TestCase):
    """與昨日 BQ QSREC 標的完全相同時須改選或寫「重複選用理由」。"""

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_crypto_same_as_yesterday_fails_without_phrase(self, mock_y):
        mock_y.return_value = {"BTC", "BTC/SOL"}
        recs = [
            {"asset": "BTC", "category": "CRYPTO", "selection_score": 78, "alt_candidate_score": 64, "score_gap": 14, "repeat_days": 1},
            {"asset": "BTC/SOL", "category": "CRYPTO", "selection_score": 75, "alt_candidate_score": 62, "score_gap": 13, "repeat_days": 2},
        ]
        body = (
            "區塊④\n本日選擇理由：現貨 ETF 與監管敘事支持 BTC，鏈上資金費率與多空比佐證，選 BTC 與 BTC/SOL 比值。\n"
            "今日風險預算：x"
        )
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("輪動", err)

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_crypto_same_ok_with_repeat_phrase(self, mock_y):
        mock_y.return_value = {"BTC", "BTC/SOL"}
        recs = [
            {"asset": "BTC", "category": "CRYPTO", "selection_score": 78, "alt_candidate_score": 64, "score_gap": 14, "repeat_days": 1},
            {"asset": "BTC/SOL", "category": "CRYPTO", "selection_score": 75, "alt_candidate_score": 62, "score_gap": 13, "repeat_days": 2},
        ]
        body = (
            "區塊④\n本日選擇理由：重複選用理由：Hyperliquid ETF 為全新催化；現貨敘事延續。\n"
            "今日風險預算：x"
        )
        ok, _ = _pick_rotation_crypto_ok(body, recs)
        self.assertTrue(ok)

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_equity_rotation(self, mock_y):
        mock_y.return_value = {"NVDA", "MSFT"}
        recs = [
            {"asset": "NVDA", "category": "EQUITY", "selection_score": 82, "alt_candidate_score": 65, "score_gap": 17, "repeat_days": 1},
            {"asset": "MSFT", "category": "EQUITY", "selection_score": 79, "alt_candidate_score": 63, "score_gap": 16, "repeat_days": 2},
        ]
        base = "加密區尾\n\n🤖 AI 市場\n"
        bad = base + "本日選擇理由：新聞點名 NVDA MSFT 財報產品催化。\n今日風險預算："
        self.assertFalse(_pick_rotation_equity_ok(bad, recs)[0])
        good = base + "本日選擇理由：重複選用理由：政策面仍主導故連日維持；\n今日風險預算："
        self.assertTrue(_pick_rotation_equity_ok(good, recs)[0])

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_equity_same_ok_with_repeat_stock_phrase_synonym(self, mock_y):
        mock_y.return_value = {"NVDA", "MSFT"}
        recs = [
            {"asset": "NVDA", "category": "EQUITY", "selection_score": 82, "alt_candidate_score": 65, "score_gap": 17, "repeat_days": 1},
            {"asset": "MSFT", "category": "EQUITY", "selection_score": 79, "alt_candidate_score": 63, "score_gap": 16, "repeat_days": 2},
        ]
        base = "加密區尾\n\n🤖 AI 市場\n"
        good = base + "本日選擇理由：重複選股理由：財報週期主導故維持 NVDA／MSFT。\n訊號衝突摘要：無顯著多空衝突。"
        self.assertTrue(_pick_rotation_equity_ok(good, recs)[0])

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_repeat_requires_min_score_gap(self, mock_y):
        mock_y.return_value = {"BTC"}
        recs = [{"asset": "BTC", "category": "CRYPTO", "selection_score": 72, "alt_candidate_score": 66, "score_gap": 6, "repeat_days": 1}]
        body = "區塊④\n本日選擇理由：重複選用理由：新催化延續。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("分差不足", err)
        self.assertGreater(_pick_rotation_override_min_gap(), 0)

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_repeat_requires_quality_anchor(self, mock_y):
        mock_y.return_value = {"BTC"}
        recs = [{"asset": "BTC", "category": "CRYPTO", "selection_score": 74, "alt_candidate_score": 61, "score_gap": 13, "repeat_days": 3}]
        body = "區塊④\n本日選擇理由：重複選用理由：催化延續。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("repeat_days", err)

    # Bug 4: LLM omits `repeat_days` from QSREC JSON — schema default is 0, so
    # _has_repeat_quality_anchor should treat absence as repeat_days=0 (still fresh).
    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_repeat_ok_when_repeat_days_absent_defaults_to_zero(self, mock_y):
        mock_y.return_value = {"BTC"}
        # repeat_days intentionally omitted — LLM output may not include optional fields
        recs = [{"asset": "BTC", "category": "CRYPTO", "selection_score": 80, "alt_candidate_score": 65, "score_gap": 15}]
        body = "區塊④\n本日選擇理由：重複選用理由：現貨 ETF 首次核准為全新催化。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertTrue(ok, f"should pass when repeat_days absent (defaults to 0): {err}")

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_equity_repeat_ok_when_repeat_days_absent_defaults_to_zero(self, mock_y):
        mock_y.return_value = {"NVDA", "MSFT"}
        # repeat_days intentionally omitted on both records
        recs = [
            {"asset": "NVDA", "category": "EQUITY", "selection_score": 85, "alt_candidate_score": 70, "score_gap": 15},
            {"asset": "MSFT", "category": "EQUITY", "selection_score": 82, "alt_candidate_score": 68, "score_gap": 14},
        ]
        base = "加密區尾\n\n🤖 AI 市場\n"
        good = base + "本日選擇理由：重複選用理由：高利率環境下技術面訊號延續，維持空頭部位。\n今日風險預算："
        ok, err = _pick_rotation_equity_ok(good, recs)
        self.assertTrue(ok, f"should pass when repeat_days absent (defaults to 0): {err}")

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_score_gap_boundary_11_fails(self, mock_y):
        """gap=11 嚴格低於門檻 12，應 fail。"""
        mock_y.return_value = {"BTC", "SOL"}
        recs = [
            {"asset": "BTC", "category": "CRYPTO", "selection_score": 83, "alt_candidate_score": 72,
             "score_gap": 11, "repeat_days": 1},
            {"asset": "SOL", "category": "CRYPTO", "selection_score": 78, "alt_candidate_score": 67,
             "score_gap": 11, "repeat_days": 1},
        ]
        body = "區塊④\n本日選擇理由：重複選用理由：機構持續增持 BTC，SOL 生態系更新。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("分差不足", err)

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_score_gap_boundary_12_passes(self, mock_y):
        """gap=12 剛好達標，應 pass（邊界值）。"""
        mock_y.return_value = {"BTC", "SOL"}
        recs = [
            {"asset": "BTC", "category": "CRYPTO", "selection_score": 85, "alt_candidate_score": 73,
             "score_gap": 12, "repeat_days": 1},
            {"asset": "SOL", "category": "CRYPTO", "selection_score": 78, "alt_candidate_score": 66,
             "score_gap": 12, "repeat_days": 1},
        ]
        body = "區塊④\n本日選擇理由：重複選用理由：ETF 核准預期支撐 BTC，SOL 鏈上活躍度新高。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertTrue(ok, f"gap=12 should pass boundary: {err}")


class TestPickJustification(unittest.TestCase):
    def test_vague_crypto_reason_fails(self):
        report = _make_report(news_count=8)
        report = report.replace(
            "本日選擇理由：現貨 ETF 淨流入與監管新聞構成催化，鏈上資金費率與多空比同步支持偏多結構，選 BTC 作為單邊主倉。",
            "本日選擇理由：技術面偏多。",
        )
        r = validate_report(report)
        self.assertFalse(r["pick_justification_crypto_ok"])
        self.assertTrue(any("動態選幣" in i or "本日選擇理由（加密）" in i for i in r["issues"]))


class TestPartialNewsGate(unittest.TestCase):
    """新聞資料不足分段 vs 交易觀望解耦。"""

    def test_partial_news_ok_with_footer_and_three_tags(self):
        report = _make_report(news_count=3)
        report += "\n【新聞資料狀態】\n已啟用資料不足保護：不補虛構新聞。\n"
        self.assertTrue(_partial_news_ok(report))
        result = validate_report(report)
        self.assertTrue(result["partial_news_ok"])
        self.assertTrue(result["news_six_relaxed"])
        self.assertFalse(any("標籤不足" in i for i in result["issues"]))

    def test_partial_news_fails_without_protection_declaration(self):
        report = _make_report(news_count=3)
        self.assertFalse(_partial_news_ok(report))
        result = validate_report(report)
        self.assertFalse(result["partial_news_ok"])
        self.assertTrue(any("標籤不足" in i for i in result["issues"]))

    @patch.dict(os.environ, {"ALLOW_PARTIAL_NEWS_GATE": "0"}, clear=False)
    def test_partial_news_disabled_via_env(self):
        report = _make_report(news_count=3)
        report += "\n【新聞資料狀態】\n已啟用資料不足保護：不補虛構新聞。\n"
        self.assertFalse(_partial_news_ok(report))

    def test_trade_watch_relaxes_rr_not_news_when_partial_off(self):
        """交易觀望放寬 R:R；若無觀望且無分段，仍要求 R:R。"""
        report = _make_report(include_rr=False, extra="\n觀望模式\n")
        result = validate_report(report)
        self.assertTrue(result["trade_watch_mode"])
        self.assertFalse(any("R:R" in i and "缺少" in i for i in result["issues"]))


class TestMacroOutlier(unittest.TestCase):
    def test_normal_values(self):
        self.assertFalse(_has_macro_outlier_values("美債 10Y: 4.25% | 2Y: 4.10%"))

    def test_prose_without_treasury_line_not_flagged(self):
        """敘事句單獨出現 10Y 25%（無美債行）不應觸發誤判。"""
        self.assertFalse(_has_macro_outlier_values("承上宏觀，10Y 殖利率極端飆升與 VIX 26.78"))

    def test_outlier_rate(self):
        self.assertTrue(_has_macro_outlier_values("美債 10Y: 25.00%"))

    def test_outlier_spread(self):
        self.assertTrue(_has_macro_outlier_values("利差：+1500bp"))

    def test_sofr_line_ignores_distant_percent_not_rates(self):
        """同列遠端敘事 %（如情緒指標）不應與 SOFR 利率混檢。"""
        self.assertFalse(
            _has_macro_outlier_values(
                "宏觀摘要：VIX 相關敘事 85.0% 投資人悲觀；Fed SOFR 期貨隱含利率：3.81%"
            )
        )

    def test_sofr_near_rate_still_outlier(self):
        self.assertTrue(
            _has_macro_outlier_values("儀表板｜Fed SOFR 期貨隱含利率：120.5%（錯誤）")
        )

    def test_sofr_line_with_vix_percent_not_flagged(self):
        """同列敘事『SOFR 與 VIX xx%』勿將 VIX 誤當 SOFR 利率。"""
        self.assertFalse(
            _has_macro_outlier_values(
                "宏觀摘要：Fed SOFR 期貨無報價與 VIX 26.78% 同列（僅說明市場情緒）"
            )
        )

    def test_treasury_10y_without_colon_on_meizhai_line(self):
        self.assertFalse(_has_macro_outlier_values("美債 10Y 報 4.25%｜2Y 4.10%"))

    def test_sanitize_handles_fullwidth_pipe(self):
        src = "美債 10Y：25.00%｜2Y：4.10%"
        out = _sanitize_macro_outlier_values(src)
        self.assertIn("N/A", out)


class TestMacroConflicts(unittest.TestCase):
    def test_no_conflict(self):
        self.assertFalse(_has_macro_conflicts("美債 2Y 4.25%"))

    def test_2y_na_and_value(self):
        self.assertTrue(_has_macro_conflicts("美債 2Y N/A\n美債 2Y 4.25%"))


class TestRiskOffStarCap(unittest.TestCase):
    def test_risk_off_with_4_stars(self):
        text = "【今日市場模式】 risk_off\n信心：⭐️⭐️⭐️⭐️"
        self.assertTrue(_risk_off_star_cap_violated(text))

    def test_risk_on_with_4_stars(self):
        text = "【今日市場模式】 risk_on\n信心：⭐️⭐️⭐️⭐️"
        self.assertFalse(_risk_off_star_cap_violated(text))

    def test_risk_off_with_3_stars(self):
        text = "【今日市場模式】 risk_off\n信心：⭐️⭐️⭐️"
        self.assertFalse(_risk_off_star_cap_violated(text))


class TestPairTradeUnitConsistent(unittest.TestCase):
    def test_no_pair_trade(self):
        self.assertTrue(_pair_trade_unit_consistent("normal text"))

    def test_pair_with_unit(self):
        text = (
            "$BTC / $ETH 現價：$95000 / $3200\n"
            "單位：BTC/ETH 比值\n"
            "進場：29.69"
        )
        self.assertTrue(_pair_trade_unit_consistent(text))


class TestValidateReport(unittest.TestCase):
    """Integration tests for validate_report()."""

    def test_valid_report_passes(self):
        report = _make_report()
        result = validate_report(report)
        # Should have no issues except possibly 呢喃/傳聞 related
        non_chatter_issues = [i for i in result["issues"] if "呢喃" not in i and "傳聞" not in i]
        self.assertTrue(result["valid"], f"Unexpected issues: {non_chatter_issues}")

    def test_too_short_report(self):
        report = _make_report(length=100)
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("報告過短" in i for i in result["issues"]))

    def test_insufficient_news(self):
        report = _make_report(news_count=2)
        result = validate_report(report)
        self.assertTrue(any("新聞數不足" in i for i in result["issues"]))

    def test_missing_regime(self):
        report = _make_report(regime="unknown_mode")
        result = validate_report(report)
        self.assertTrue(any("market_regime" in i for i in result["issues"]))

    def test_missing_dashboard(self):
        report = _make_report(include_dashboard=False)
        # Scrub all dashboard-triggering keywords from the report
        for kw in ("DXY", "BTC OI", "資金費率", "模型排名", "RSI", "Fear", "Greed", "儀表板"):
            report = report.replace(kw, "___")
        result = validate_report(report)
        self.assertTrue(any("數據儀表板" in i for i in result["issues"]))

    def test_missing_qsrec(self):
        report = _make_report(include_qsrec=False)
        result = validate_report(report)
        self.assertTrue(any("QSREC" in i for i in result["issues"]))

    def test_missing_source_health_does_not_block(self):
        """讀者版戰報不強制出現 Source 三行；僅後台 logger 追蹤。"""
        report = _make_report(include_source_health=False)
        result = validate_report(report)
        self.assertFalse(any("SourceHealth" in i for i in result["issues"]))

    def test_missing_signal_conflict(self):
        report = _make_report(include_signal_conflict=False)
        result = validate_report(report)
        self.assertTrue(any("訊號衝突" in i for i in result["issues"]))

    def test_missing_rumor_grade(self):
        report = _make_report(include_rumor_grade=False)
        result = validate_report(report)
        self.assertTrue(any("可信度" in i for i in result["issues"]))

    def test_rumor_grade_slash_100_passes(self):
        report = _make_report(include_rumor_grade=False, extra="產業鏈呢喃：供應鏈消息 可信度 72/100\n")
        result = validate_report(report)
        self.assertFalse(
            any("傳聞區缺少可信度" in i for i in result["issues"]),
            f"expected slash-100 rumor grade accepted, got: {result['issues']}",
        )

    def test_rumor_xinlaidu_passes(self):
        report = _make_report(include_rumor_grade=False, extra="呢喃與傳聞掃描\n信賴度：B\n")
        result = validate_report(report)
        self.assertFalse(any("傳聞區缺少可信度" in i for i in result["issues"]))

    def test_neutral_regime_forbids_risk_off_trade_language(self):
        report = _make_report(
            regime="neutral",
            extra="\n· 倉位建議：4%（高風險環境 risk_off 減倉至極低水位）\n",
        )
        result = validate_report(report)
        self.assertTrue(any("risk_off 敘述" in i or "誤用 risk_off" in i for i in result["issues"]))

    def test_neutral_regime_forbids_us_equity_frame_risk_off_paren(self):
        """美股部位框括號內誤標（risk_off）應與「依 risk_off」一併被敘事 Gate 擋下。"""
        report = _make_report(
            regime="neutral",
            extra="\n· <b>美股部位框</b>：兩檔合計不超過 10%（risk_off）\n",
        )
        result = validate_report(report)
        self.assertTrue(any("risk_off 敘述" in i or "誤用 risk_off" in i for i in result["issues"]))

    def test_crypto_pick_futures_and_cme_count_as_catalyst_keywords(self):
        """期貨／CME 類敘述須計入動態選幣「強關鍵詞」。"""
        reason = "CME 機構期貨淨多單變化與監管新聞同向，故維持 BTC 為單邊主倉。"
        recs = [{"asset": "BTC", "category": "CRYPTO"}]
        old = (
            "本日選擇理由：現貨 ETF 淨流入與監管新聞構成催化，鏈上資金費率與多空比同步支持偏多結構，選 BTC 作為單邊主倉。\n"
        )
        report = _make_report(regime="risk_on").replace(old, "本日選擇理由：" + reason + "\n")
        ok, err = _pick_justification_crypto_ok(report, recs)
        self.assertTrue(ok, err)

    def test_qsrec_regime_mismatch_reported_in_consistency_issues(self):
        """QSREC regime 與【今日市場模式】不一致時應列入 qsrec_issues，而非僅依 mixed regime。"""
        report = _make_report(regime="neutral")
        j = report.index('"asset":"BTC"')
        k = report.index('"regime":"neutral"', j)
        report = report[:k] + '"regime":"risk_off"' + report[k + len('"regime":"neutral"') :]
        recs = extract_recommendations_json(report)
        issues = _qsrec_consistency_issues(report, recs)
        self.assertTrue(any("regime=risk_off" in i and "主判定 neutral" in i for i in issues))

    def test_has_mixed_regime_ignores_qsrec_only_divergence(self):
        """正文 mode／budget 一致時，僅 QSREC JSON regime 錯誤不應觸發 has_mixed_regime。"""
        report = _make_report(regime="neutral")
        j = report.index('"asset":"BTC"')
        k = report.index('"regime":"neutral"', j)
        report = report[:k] + '"regime":"risk_off"' + report[k + len('"regime":"neutral"') :]
        result = validate_report(report)
        self.assertFalse(result["has_mixed_regime"])

    def test_risk_off_narrative_flags_us_equity_frame(self):
        lines = _risk_off_narrative_violations(
            "【今日市場模式】 neutral\n· <b>美股部位框</b>：10%（risk_off）\n"
        )
        self.assertTrue(any("美股部位框" in ln for ln in lines))


class TestRumorGradePostprocess(unittest.TestCase):
    def test_injects_marker_when_missing(self):
        src = "區塊③【市場呢喃與傳聞】\n· 傳聞 A（未確認）\n[QSREC_START]\n[]\n[QSREC_END]"
        out = _ensure_rumor_grade_marker(src)
        self.assertTrue(_has_rumor_grade_marker(out))
        self.assertIn("傳聞可信度", out)

    def test_noop_when_grade_exists(self):
        src = "區塊③【市場呢喃與傳聞】\n· 傳聞 A（未確認）｜可信度：B\n"
        out = _ensure_rumor_grade_marker(src)
        self.assertEqual(src, out)

    def test_missing_rr_and_drawdown(self):
        report = _make_report(include_rr=False)
        result = validate_report(report)
        self.assertTrue(any("R:R" in i or "回撤" in i for i in result["issues"]))

    def test_missing_risk_budget(self):
        report = _make_report(include_risk_budget=False)
        result = validate_report(report)
        self.assertTrue(any("風險預算" in i for i in result["issues"]))

    def test_risk_off_star_violation(self):
        report = _make_report(regime="risk_off", extra="信心：⭐️⭐️⭐️⭐️")
        result = validate_report(report)
        self.assertTrue(any("信心水準" in i or "star" in i.lower() for i in result["issues"]))

    def test_data_missing_critical(self):
        report = _make_report(extra="[DATA_MISSING:newsapi] [DATA_MISSING:coinglass_data]")
        result = validate_report(report)
        self.assertTrue(result["has_data_missing"])
        self.assertTrue(any("關鍵資料來源缺失" in i for i in result["issues"]))

    def test_too_many_na_without_tag(self):
        report = _make_report(extra="N/A N/A N/A N/A N/A")
        result = validate_report(report)
        self.assertTrue(any("N/A 過多" in i for i in result["issues"]))

    def test_too_many_na_multiline_disclosure_passes(self):
        """資料缺失原因與替代指標跨行時仍應通過 Gate（舊版 . 不匹配換行會誤擋）。"""
        extra = (
            "N/A N/A N/A N/A N/A\n"
            "<b>低置信度</b>：儀表板部分欄位暫缺。\n"
            "<b>資料缺失原因</b>：API 限流。\n"
            "<b>替代指標</b>：參考 RSI 與資金費率。\n"
        )
        report = _make_report(extra=extra)
        result = validate_report(report)
        self.assertFalse(any("N/A 過多" in i for i in result["issues"]))

    def test_postprocess_injects_na_disclosure(self):
        report = _make_report(extra="N/A N/A N/A N/A N/A")
        out = _postprocess_report_for_resilience(report)
        result = validate_report(out)
        self.assertFalse(any("N/A 過多" in i for i in result["issues"]))
        self.assertIn("低置信度", out)
        self.assertIn("替代指標", out)

    def test_postprocess_redacts_data_missing_tokens(self):
        """LLM 誤貼 [DATA_MISSING:...] 時應改寫，避免 validate_report 資料缺失欄位誤判。"""
        report = _make_report(extra="某段敘述 [DATA_MISSING:x_search] 不應留在正文。\n")
        out = _postprocess_report_for_resilience(report)
        self.assertNotIn("[DATA_MISSING:", out)
        self.assertIn("〔資料源暫缺：x_search〕", out)
        vr = validate_report(out)
        self.assertFalse(vr["has_data_missing"])

    def test_code_leak_detected(self):
        report = _make_report(extra="multi_timeframe_tool (arg)")
        result = validate_report(report)
        self.assertTrue(any("外洩" in i and "函數" in i for i in result["issues"]))

    def test_macro_outlier_detected(self):
        report = _make_report(extra="美債 10Y: 25.00%")
        result = validate_report(report)
        self.assertTrue(result["has_macro_outlier"])

    def test_six_news_tags_required(self):
        """僅有編號列表、無〔新聞 N〕時應提示格式錯誤。"""
        report = _make_report(news_count=0, extra="")
        # 無〔新聞〕，改為 6 條 1. 列表充當新聞（舊 LLM 錯誤模式）
        news_lines = "\n".join(f"{i}. 假新聞標題 {i} 內容" for i in range(1, 7))
        report = report.replace("加密市場核心新聞", "加密市場核心新聞\n" + news_lines)
        result = validate_report(report)
        self.assertTrue(any("〔新聞 N〕" in i for i in result["issues"]))

    def test_yield_spread_mismatch_flagged(self):
        macro = (
            "美債 10Y: 3.55%\n美債 2Y: 4.30%\n"
            "利差: +0.50% （測試用錯誤口徑）\n"
        )
        report = _make_report(extra=macro)
        result = validate_report(report)
        self.assertTrue(any("利差" in i and "10Y" in i for i in result["issues"]))


class TestDailyBriefV2Helpers(unittest.TestCase):
    def test_fix_glued_code_before_word(self):
        raw = "· 24h爆倉 <code>N/A</code>CoinGlass 不可用"
        out = _fix_glued_na_suffix(raw)
        self.assertNotIn("</code>CoinGlass", out)
        self.assertIn("CoinGlass", out)

    def test_conflicting_total_risk_budget_detected(self):
        text = "今日風險預算：總風險預算 40%，單筆 10%\n今日風險預算：總風險預算 20%\n"
        self.assertTrue(_conflicting_total_risk_budget_lines(text))

    def test_conflicting_total_risk_budget_in_validate(self):
        report = _make_report(
            extra="\n今日風險預算：總風險預算 40%，單筆 10%\n今日風險預算：總風險預算 20%\n",
        )
        result = validate_report(report)
        self.assertTrue(any("總風險預算" in i for i in result["issues"]))

    def test_qsrec_opposing_same_asset(self):
        recs = [
            {"asset": "MSFT", "direction": "LONG", "category": "EQUITY"},
            {"asset": "MSFT", "direction": "SHORT", "category": "EQUITY"},
        ]
        issues = _qsrec_opposing_direction_same_asset(recs)
        self.assertTrue(any("互斥" in i for i in issues))

    @patch("report_html_gates._strict_pick_scoring", return_value=False)
    def test_qsrec_opposing_in_consistency_issues_by_default(self, _mock_scoring):
        recs = [
            {
                "asset": "MSFT",
                "direction": "LONG",
                "category": "EQUITY",
                "trigger": "t",
                "invalidation": "i",
                "position_pct": 2.0,
                "timeframe": "swing",
            },
            {
                "asset": "MSFT",
                "direction": "SHORT",
                "category": "EQUITY",
                "trigger": "t2",
                "invalidation": "i2",
                "position_pct": 2.0,
                "timeframe": "swing",
            },
        ]
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QSREC_ALLOW_OPPOSING_DIRECTIONS", None)
            issues = _qsrec_consistency_issues("【今日市場模式】risk_on\n", recs)
        self.assertTrue(any("互斥" in i for i in issues))

    @patch("report_html_gates._strict_pick_scoring", return_value=False)
    def test_qsrec_opposing_skipped_when_env_allow(self, _mock_scoring):
        recs = [
            {
                "asset": "NVDA",
                "direction": "LONG",
                "category": "EQUITY",
                "trigger": "t",
                "invalidation": "i",
                "position_pct": 2.0,
                "timeframe": "swing",
            },
            {
                "asset": "NVDA",
                "direction": "SHORT",
                "category": "EQUITY",
                "trigger": "t2",
                "invalidation": "i2",
                "position_pct": 2.0,
                "timeframe": "swing",
            },
        ]
        with patch.dict(os.environ, {"QSREC_ALLOW_OPPOSING_DIRECTIONS": "1"}, clear=False):
            issues = _qsrec_consistency_issues("【今日市場模式】risk_on\n", recs)
        self.assertFalse(any("互斥" in i for i in issues))


class TestHasCryptoTradeSection(unittest.TestCase):
    """避免 LLM 省略 (Crypto) 括號時誤注入觀望區塊。"""

    def test_detects_header_without_crypto_paren(self):
        text = "【資金流向與精準操作】\n· $BTC (LONG)｜進場：$70000"
        self.assertTrue(_has_crypto_trade_section(text))

    def test_detects_classic_crypto_paren(self):
        text = "區塊④【資金流向與精準操作 (Crypto)】"
        self.assertTrue(_has_crypto_trade_section(text))


class TestAiBoundaryAndWatchMutex(unittest.TestCase):
    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_equity_rotation_accepts_ai_variant_heading(self, mock_y):
        mock_y.return_value = {"NVDA", "MSFT"}
        recs = [
            {"asset": "NVDA", "category": "EQUITY", "selection_score": 82, "alt_candidate_score": 65, "score_gap": 17, "repeat_days": 1},
            {"asset": "MSFT", "category": "EQUITY", "selection_score": 79, "alt_candidate_score": 63, "score_gap": 16, "repeat_days": 2},
        ]
        report = (
            "前言\n────────────\n🤖 AI 與美股市場\n"
            "AI 產業鏈精準操作 (US Equities)\n"
            "本日選擇理由：重複選股理由：維持 NVDA 與 MSFT，因為資金面與宏觀條件延續。\n"
            "訊號衝突摘要：無顯著多空衝突。\n"
            "· $NVDA (SHORT)\n· $MSFT (SHORT)\n"
        )
        self.assertTrue(_pick_rotation_equity_ok(report, recs)[0])

    @patch("report_html_gates._fetch_yesterday_qsrec_canonical_set")
    def test_equity_rotation_prefers_first_ai_section_when_duplicated(self, mock_y):
        mock_y.return_value = {"NVDA", "MSFT"}
        recs = [
            {"asset": "NVDA", "category": "EQUITY", "selection_score": 82, "alt_candidate_score": 65, "score_gap": 17, "repeat_days": 1},
            {"asset": "MSFT", "category": "EQUITY", "selection_score": 79, "alt_candidate_score": 63, "score_gap": 16, "repeat_days": 2},
        ]
        report = (
            "前言\n────────────\n🤖 AI 與美股市場\n"
            "本日選擇理由：重複選用理由：維持昨日兩檔 NVDA 與 MSFT，等待財報前趨勢確認。\n"
            "訊號衝突摘要：無顯著多空衝突。\n"
            "· $NVDA (SHORT)\n· $MSFT (SHORT)\n"
            "────────────\n🤖 AI 市場\n"
            "【核心新聞】N/A\n"
        )
        self.assertTrue(_pick_rotation_equity_ok(report, recs)[0])
        prefix = _crypto_report_prefix(report)
        self.assertNotIn("🤖 AI 與美股市場", prefix)

    def test_watch_mode_and_actionable_prices_conflict(self):
        report = _make_report(
            extra=(
                "\n區塊④【AI 產業鏈精準操作 (US Equities)】\n"
                "· 觀望模式：資料不足觀望，暫不提供股票進出場價格。\n"
                "· $NVDA (SHORT)\n"
                "· 進場：$172.70｜目標：$160.00｜停損：$178.00\n"
            )
        )
        result = validate_report(report)
        self.assertTrue(any("觀望模式契約衝突" in issue for issue in result["issues"]))

    def _report_with_crypto_block_before_ai(self, crypto_block: str) -> str:
        """在 🤖 AI 主段之前插入加密精準操作區塊（extra 若在文末不會進入 crypto_span）。"""
        marker = "────────────\n🤖 AI 市場"
        base = _make_report(include_crypto_trade=False)
        idx = base.find(marker)
        self.assertNotEqual(idx, -1, "template must contain AI section marker")
        return base[:idx] + crypto_block + "\n" + base[idx:]

    def test_crypto_op_span_stock_watch_phrase_alone_no_mutex_conflict(self):
        """加密段誤貼「暫不提供股票…」不應觸發加密觀望／價位互斥（該句僅屬美股觀望）。"""
        crypto_block = (
            "區塊④【資金流向與精準操作】\n"
            "本日選擇理由：測試。\n"
            "今日風險預算：risk_on 模式下總倉位上限 15%。\n"
            "訊號衝突摘要：無顯著多空衝突。\n"
            "· 暫不提供股票進出場價格。（誤貼於加密段）\n"
            "· $BTC (LONG)\n"
            "· 進場：<code>$70000</code>｜目標：<code>$75000</code>｜停損：<code>$68000</code>"
        )
        report = self._report_with_crypto_block_before_ai(crypto_block)
        result = validate_report(report)
        self.assertFalse(
            any("觀望模式契約衝突" in i and "加密" in i for i in result["issues"]),
            result["issues"],
        )

    def test_crypto_watch_mode_and_actionable_still_conflicts(self):
        crypto_block = (
            "區塊④【資金流向與精準操作】\n"
            "本日選擇理由：測試。\n"
            "今日風險預算：risk_on 模式下總倉位上限 15%。\n"
            "訊號衝突摘要：無顯著多空衝突。\n"
            "· <b>觀望模式</b>：資料不足觀望，暫不開新倉。\n"
            "· $BTC (LONG)\n"
            "· 進場：<code>$70000</code>｜目標：<code>$75000</code>｜停損：<code>$68000</code>"
        )
        report = self._report_with_crypto_block_before_ai(crypto_block)
        result = validate_report(report)
        self.assertTrue(
            any("觀望模式契約衝突" in i and "加密" in i for i in result["issues"]),
        )

    def test_negated_feiguanwang_mode_no_mutex_with_prices(self):
        """「非觀望模式」含子字串觀望模式，不應與進場/目標/停損並存時誤判為契約衝突。"""
        crypto_block = (
            "區塊④【資金流向與精準操作】\n"
            "本日選擇理由：測試。\n"
            "今日風險預算：risk_on 模式下總倉位上限 15%。\n"
            "訊號衝突摘要：無顯著多空衝突。\n"
            "· 敘事：本段為非觀望模式，提供可執行參數如下。\n"
            "· $BTC (LONG)\n"
            "· 進場：<code>$70000</code>｜目標：<code>$75000</code>｜停損：<code>$68000</code>"
        )
        report = self._report_with_crypto_block_before_ai(crypto_block)
        result = validate_report(report)
        self.assertFalse(
            any("觀望模式契約衝突" in i and "加密" in i for i in result["issues"]),
            result["issues"],
        )

    def test_negated_watch_does_not_relax_rr_gate(self):
        """否定觀望（非觀望模式）不應觸發 trade_watch_mode 放寬 R:R。"""
        report = _make_report(include_rr=False, extra="\n本段為非觀望模式。\n")
        result = validate_report(report)
        self.assertFalse(result["trade_watch_mode"])
        self.assertTrue(any("R:R" in i and "缺少" in i for i in result["issues"]))


class TestBlockingPrefixesCoverage(unittest.TestCase):
    """Verify every _BLOCKING_PREFIXES entry produces a correctly-classified blocking issue."""

    # ── 1. 核心新聞〔新聞 N〕標籤不足 ──────────────────────────────────────────
    def test_blocking_core_news_tags_insufficient(self):
        report = _make_report(news_count=0)
        news_lines = "\n".join(f"{i}. 假新聞標題 {i} 內容超過十字" for i in range(1, 7))
        report = report.replace("加密市場核心新聞", "加密市場核心新聞\n" + news_lines)
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("核心新聞〔新聞 N〕標籤不足") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 2. 缺少 market_regime ────────────────────────────────────────────────
    def test_blocking_missing_market_regime(self):
        report = _make_report(regime="totally_invalid_mode")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少 market_regime") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 3. 缺少加密市場操作建議 ──────────────────────────────────────────────
    def test_blocking_missing_crypto_trading_advice(self):
        report = _make_report(include_crypto_trade=False)
        # remove any residual "精準操作 Crypto" keyword that might have leaked in
        report = report.replace("精準操作 Crypto", "___")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少加密市場操作建議") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 4. 缺少 AI 美股操作建議 ──────────────────────────────────────────────
    def test_blocking_missing_ai_equity_advice(self):
        report = _make_report(include_ai_trade=False)
        report = report.replace("精準操作 US Equities", "___")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少 AI 美股操作建議") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 5. 缺少 AI 市場段落 ──────────────────────────────────────────────────
    def test_blocking_missing_ai_section(self):
        report = _make_report(include_ai_section=False)
        for kw in ("🤖 AI", "AI 市場", "AI 產業"):
            report = report.replace(kw, "___")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少 AI 市場段落") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 6. 缺少加密市場段落 ──────────────────────────────────────────────────
    def test_blocking_missing_crypto_section(self):
        # HAS_CRYPTO_SECTION_RE = re.compile(r"加密市場|核心新聞|數據儀表板")
        # "AI 數據儀表板" would otherwise keep has_crypto_section=True, so scrub all triggers.
        report = _make_report(include_crypto_section=False)
        for kw in ("加密市場", "核心新聞", "數據儀表板"):
            report = report.replace(kw, "___")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少加密市場段落") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 7. 缺少系統追蹤載荷區塊 ─────────────────────────────────────────────
    def test_blocking_missing_tracking_payload(self):
        report = _make_report(include_qsrec=False)
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("缺少系統追蹤載荷區塊") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 8. QSREC 區塊存在但（JSON 無法解析） ─────────────────────────────────
    def test_blocking_qsrec_invalid_json(self):
        # Build a report without the valid QSREC, then inject a broken one
        report = _make_report(include_qsrec=False)
        report += "\n[QSREC_START]\n{broken_json: [\n[QSREC_END]"
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("QSREC 區塊存在但") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 9. 交易段含 N/A 關鍵價格 ────────────────────────────────────────────
    def test_blocking_trade_na_price(self):
        report = _make_report(extra="· $ETH (LONG)｜現價：N/A｜進場：$3000｜目標：$3500｜停損：$2800")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("交易段含 N/A 關鍵價格") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 10. 關鍵資料來源缺失 ─────────────────────────────────────────────────
    def test_blocking_critical_data_source_missing(self):
        report = _make_report(extra="[DATA_MISSING:newsapi]")
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("關鍵資料來源缺失") for i in result["blocking_issues"]),
            result["blocking_issues"],
        )

    # ── 11–14. 結構化驗證（via validate_structured_report） ─────────────────

    def _make_minimal_structured_report(self, **kwargs):
        return _make_minimal_structured_report_dbr(**kwargs)

    def test_structured_crypto_news_insufficient(self):
        with self.assertRaises(ValidationError) as ctx:
            self._make_minimal_structured_report(crypto_news=1, ai_news=3)
        self.assertIn("結構化加密新聞不足", str(ctx.exception))

    def test_structured_ai_news_insufficient(self):
        with self.assertRaises(ValidationError) as ctx:
            self._make_minimal_structured_report(crypto_news=3, ai_news=1)
        self.assertIn("結構化 AI 新聞不足", str(ctx.exception))

    def test_structured_news_total_insufficient(self):
        with self.assertRaises(ValidationError) as ctx:
            self._make_minimal_structured_report(crypto_news=2, ai_news=2, partial_tier=False)
        self.assertIn("結構化新聞總數", str(ctx.exception))

    def test_structured_qsrec_empty(self):
        with self.assertRaises(ValidationError) as ctx:
            self._make_minimal_structured_report(has_qsrec_recs=False)
        self.assertIn("結構化 qsrec 為空", str(ctx.exception))

    def test_regime_token_surface_variants_pass(self):
        """risk_budget_summary surface variants (space/hyphen/mixed-case) should NOT trigger regime gate."""
        from schemas import validate_structured_report

        variants = [
            "Risk On 模式，總倉位 60%",    # space, title-case
            "risk on 環境，加倉",          # space, lower-case
            "Risk-On，建議增持",           # hyphen, title-case
            "risk-on 模式下",              # hyphen, lower-case
            "RISK_ON 最大曝險 40%",        # underscore, upper-case
        ]
        for summary in variants:
            report = self._make_minimal_structured_report()
            report.crypto.risk_budget_summary = summary
            result = validate_structured_report(report)
            self.assertFalse(
                any("regime token" in i for i in result["issues"]),
                f"Surface variant '{summary}' should pass but got: {result['issues']}",
            )

    def test_regime_token_missing_fails(self):
        """risk_budget_summary with no regime token mention must trigger the gate."""
        from schemas import validate_structured_report

        report = self._make_minimal_structured_report()
        report.crypto.risk_budget_summary = "總倉位維持 20%，謹慎操作"
        result = validate_structured_report(report)
        self.assertTrue(
            any("regime token" in i for i in result["issues"]),
            f"Expected regime token issue, got: {result['issues']}",
        )

    # ── 15. AI 段「本日選擇理由」含基本面用語（第 18 項） ──────────────────
    def test_blocking_ai_pick_reason_fundamental_only(self):
        """AI pick reason using only '基本面' with no specific catalyst hits → blocking (18th prefix)."""
        report = _make_report()
        report = report.replace(
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
            "本日選擇理由：NVDA 基本面穩健，估值相對合理，選擇持有。",
        )
        result = validate_report(report)
        self.assertTrue(
            any(i.startswith("AI 段「本日選擇理由」含基本面用語") for i in result["blocking_issues"]),
            f"Expected 18th blocking issue, got: {result['blocking_issues']}",
        )

    def test_blocking_ai_pick_reason_fundamental_with_catalysts_passes(self):
        """'基本面' in AI reason is allowed when ≥ 2 specific catalyst hits are also present."""
        report = _make_report()
        report = report.replace(
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
            "本日選擇理由：NVDA 基本面強化加財報超預期，GPU 拉貨見於主流新聞，故選 NVDA。",
        )
        result = validate_report(report)
        self.assertFalse(
            any(i.startswith("AI 段「本日選擇理由」含基本面用語") for i in result["blocking_issues"]),
            f"Should not block when catalysts ≥ 2: {result['blocking_issues']}",
        )

    def test_equity_pick_infrastructure_keywords_passes_without_legacy_financial_kw(self):
        """核電／SMR／IPO／供電等擴充詞可單獨滿足 ≥2 線索，不必依賴財報／新聞等舊關鍵字。"""
        report = _make_report()
        report = report.replace(
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
            "本日選擇理由：NVDA 對齊 SMR 與核電基礎設施長線敘事，IPO 窗口與供電／電力／能源配比重置帶動液冷擴產與產能良率追蹤，故點名 NVDA。",
        )
        result = validate_report(report)
        self.assertTrue(
            result["pick_justification_equity_ok"],
            f"Expected equity pick justification OK for infra narrative: {result.get('issues')}",
        )

    def test_equity_pick_exactly_two_infra_keywords_passes(self):
        """Boundary: exactly 2 new infra keywords (SMR + 核電) should satisfy the ≥2 threshold."""
        report = _make_report()
        report = report.replace(
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
            "本日選擇理由：NVDA 對齊 SMR 與核電長線敘事，電力基礎設施配比拉升，點名 NVDA。",
        )
        result = validate_report(report)
        self.assertTrue(
            result["pick_justification_equity_ok"],
            f"Exactly 2 new infra keywords should pass equity pick gate: {result.get('issues')}",
        )

    def test_equity_pick_single_infra_keyword_alone_blocks(self):
        """Negative: only 1 new infra keyword, no fallback, short reason — should block."""
        report = _make_report()
        report = report.replace(
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
            "本日選擇理由：NVDA 符合 SMR 敘事，故選之。",
        )
        result = validate_report(report)
        self.assertFalse(
            result["pick_justification_equity_ok"],
            "Single new infra keyword without fallback or long text should block equity pick gate",
        )


class TestPlanRollingAndScenarioGates(unittest.TestCase):
    def test_pick_rolling_blocks_when_past_days_over_cap(self):
        from report_html_gates import _pick_rolling_frequency_category_ok

        recs = [{"asset": "BTC", "category": "CRYPTO"}]
        with patch.dict(
            os.environ,
            {
                "PICK_ROLLING_FREQ_GATE": "1",
                "PICK_ROLLING_MAX_DISTINCT_DAYS": "2",
                "PICK_ROLLING_WINDOW_DAYS": "5",
            },
            clear=False,
        ):
            with patch(
                "report_html_gates._fetch_distinct_days_per_asset_rolling",
                return_value={"BTC": 2},
            ):
                ok, err = _pick_rolling_frequency_category_ok(recs, "CRYPTO")
        self.assertFalse(ok)
        self.assertIn("滾動頻率", err)

    def test_pick_rolling_skips_when_gate_off(self):
        from report_html_gates import _pick_rolling_frequency_category_ok

        recs = [{"asset": "BTC", "category": "CRYPTO"}]
        with patch.dict(
            os.environ,
            {"PICK_ROLLING_FREQ_GATE": "0", "PICK_ROLLING_MAX_DISTINCT_DAYS": "1"},
            clear=False,
        ):
            with patch(
                "report_html_gates._fetch_distinct_days_per_asset_rolling",
                return_value={"BTC": 99},
            ):
                ok, _ = _pick_rolling_frequency_category_ok(recs, "CRYPTO")
        self.assertTrue(ok)

    def test_qsrec_scenario_strict_missing_bull(self):
        from report_html_gates import _qsrec_consistency_issues

        recs = [
            {
                "trigger": "t",
                "invalidation": "i",
                "position_pct": 1,
                "timeframe": "d",
                "confidence": 4,
                "category": "CRYPTO",
                "asset": "BTC",
                "bull_scenario": "",
                "base_scenario": "基準",
                "bear_scenario": "悲觀",
            }
        ]
        with patch.dict(os.environ, {"STRICT_QSREC_SCENARIO_GATE": "1"}, clear=False):
            issues = _qsrec_consistency_issues("【今日市場模式】risk_on", recs)
        self.assertTrue(any("bull_scenario" in i for i in issues))


class TestStrictInvestmentDashboardNumericGate(unittest.TestCase):
    """STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE：投資解讀數字須出現在同段區塊① <code> 讀值。"""

    def test_strict_off_skips_audit(self):
        text = (
            "<b>區塊①</b>【數據儀表板】\n· <b>RSI</b> <code>55</code>\n"
            "<b>區塊②</b>【核心新聞】\n"
            "<i>投資解讀</i>：亂寫 999。\n<i>💎主編共識</i>：x\n"
        )
        with patch.dict(os.environ, {"STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE": "0"}, clear=False):
            ok, err = _investment_takeaway_dashboard_numeric_ok(text)
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_strict_passes_when_takeaway_matches_code_values(self):
        text = (
            "【今日市場模式】 risk_on\n"
            "<b>區塊①</b>【數據儀表板】\n· <b>RSI</b> <code>55</code>\n"
            "<b>區塊②</b>【核心新聞】\n"
            "<i>投資解讀</i>：結構延續 RSI 55 。\n<i>💎主編共識</i>：BTC\n"
            "\n🤖 AI 市場\n"
            "<b>區塊①</b>【AI 數據儀表板】\n· <b>Score</b> <code>72</code>\n"
            "<b>區塊②</b>【AI 產業新聞】\n"
            "<i>投資解讀</i>：動能分數 72 。\n<i>💎主編共識</i>：NVDA\n"
        )
        with patch.dict(os.environ, {"STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE": "1"}, clear=False):
            ok, err = _investment_takeaway_dashboard_numeric_ok(text)
        self.assertTrue(ok, err)

    def test_strict_fails_when_takeaway_number_not_in_dashboard_codes(self):
        text = (
            "【今日市場模式】 risk_on\n"
            "<b>區塊①</b>【數據儀表板】\n· <b>RSI</b> <code>55</code>\n"
            "<b>區塊②</b>【核心新聞】\n"
            "<i>投資解讀</i>：臆測 SOL 現價 145 。\n<i>💎主編共識</i>：SOL\n"
            "\n🤖 AI 市場\n"
            "<b>區塊①</b>【AI 數據儀表板】\n· <b>X</b> <code>10</code>\n"
            "<b>區塊②</b>【AI 產業新聞】\n"
            "<i>投資解讀</i>：延續 10 。\n<i>💎主編共識</i>：OK\n"
        )
        with patch.dict(os.environ, {"STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE": "1"}, clear=False):
            ok, err = _investment_takeaway_dashboard_numeric_ok(text)
        self.assertFalse(ok)
        self.assertIn("加密", err)
        self.assertIn("145", err)


class TestChatterMsmVerifyGate(unittest.TestCase):
    def test_chatter_msm_skipped_when_strict_off(self):
        with patch.dict(os.environ, {"STRICT_CHATTER_MSM_VERIFY_GATE": "0"}, clear=False):
            ok, err = _chatter_msm_verify_ok("any")
        self.assertTrue(ok)
        self.assertEqual(err, "")

    def test_chatter_msm_fails_when_credibility_without_msm(self):
        body = (
            "══════ 📊 加密市場 ══════\n"
            "<b>區塊③</b>【市場呢喃與傳聞】\n"
            "· 測試（未確認）｜來源：社群｜可信度：B\n"
            "<b>區塊④</b>【資金流向與精準操作 (Crypto)】\n"
            "x\n"
            "🤖 AI 市場\n"
            "<b>區塊③</b>【產業鏈呢喃】\n"
            "· OK（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否\n"
            "<b>區塊④</b>【AI 產業鏈精準操作 (US Equities)】\n"
        )
        with patch.dict(os.environ, {"STRICT_CHATTER_MSM_VERIFY_GATE": "1"}, clear=False):
            ok, err = _chatter_msm_verify_ok(body)
        self.assertFalse(ok)
        self.assertIn("加密", err)
        self.assertIn("主流媒體二次驗證", err)


class TestInvestmentNumericAndUnactionableTrade(unittest.TestCase):
    def test_investment_takeaway_negative_pct_inside_html_passes_numeric_gate(self):
        rep = _make_report()
        rep = rep.replace(
            "投資解讀：BTC 日線 RSI 55，ETF 流入 $120M",
            "投資解讀：<i>資金費率 -0.0008%</i> 與儀表板多空比對照",
        )
        r = validate_report(rep)
        self.assertFalse(any("投資解讀缺少當日量化數據引用" in i for i in r["issues"]))

    def test_investment_takeaway_telegram_i_label_spacing_passes_numeric_gate(self):
        """與 telegram_report.j2 一致：<i>投資解讀</i>：strip 後標籤與冒號間有空格仍應視為有數字錨點。"""
        rep = _make_report()
        rep = rep.replace(
            "投資解讀：BTC 日線 RSI 55，ETF 流入 $120M",
            "<i>投資解讀</i>：BTC 日線 RSI 55 與儀表板對照",
        )
        r = validate_report(rep)
        self.assertFalse(any("投資解讀缺少當日量化數據引用" in i for i in r["issues"]))

    def test_unactionable_trade_detects_code_wrapped_dollar_na(self):
        rep = _make_report()
        rep = rep.replace(
            "· $NVDA (LONG)｜現價：$890",
            "· $NVDA (LONG)｜現價：<code>$N/A</code>",
        )
        r = validate_report(rep)
        self.assertTrue(r["has_unactionable_trade"])
        self.assertTrue(any("交易段含 N/A" in i for i in r["blocking_issues"]))


class TestStrictExecSummaryHtmlGate(unittest.TestCase):
    @patch.dict(os.environ, {"STRICT_EXEC_SUMMARY_HTML_GATE": "1"}, clear=False)
    def test_passes_when_two_bullets_present(self):
        t = _make_report()
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertFalse(any("STRICT_EXEC_SUMMARY_HTML_GATE" in i for i in issues))
        self.assertFalse(any("【執行摘要】要點不足" in i for i in issues))
        self.assertFalse(any("缺少【執行摘要】" in i for i in issues))

    @patch.dict(os.environ, {"STRICT_EXEC_SUMMARY_HTML_GATE": "1"}, clear=False)
    def test_fails_when_section_omitted(self):
        t = _make_report(include_exec_summary=False)
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertTrue(any("【執行摘要】" in i for i in issues))


class TestStrictInstitutionalPhaseBStructuredGate(unittest.TestCase):
    @patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_B_GATE": "1"}, clear=False)
    def test_passes_minimal_structured_with_phase_b_fields(self):
        report = _make_minimal_structured_report_dbr(
            portfolio_framing_summary=(
                "加密與美股在風險預算內雙軸配置；淨曝險偏多；與 SPY 相關性中高；無額外衍生對沖。"
            ),
            scenario_probability_notes=(
                "· 樂觀：延續（機率 30%）\n"
                "· 基準：震盪（機率 45%）\n"
                "· 悲觀：收縮（機率 25%）"
            ),
        )
        res = validate_structured_report(report)
        self.assertTrue(res["valid"], res["issues"])

    def test_fails_when_probabilities_not_100(self):
        report = _make_minimal_structured_report_dbr()
        cr = report.crypto.model_copy(
            update={
                "portfolio_framing_summary": "測試組合敘述足夠長度以通過結構化門檻驗證用。",
                "scenario_probability_notes": (
                    "· 樂觀：x（機率 10%）\n· 基準：y（機率 20%）\n· 悲觀：z（機率 30%）"
                ),
            }
        )
        report = report.model_copy(update={"crypto": cr})
        with patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_B_GATE": "1"}, clear=False):
            res = validate_structured_report(report)
        self.assertFalse(res["valid"])
        self.assertTrue(any("100" in i for i in res["issues"]))


class TestStrictInstitutionalPhaseBHtmlGate(unittest.TestCase):
    @patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_B_GATE": "1"}, clear=False)
    def test_passes_when_phase_b_present(self):
        t = _make_report(include_phase_b_institutional=True)
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertFalse(any("【組合與曝險框架】" in i and "缺少" in i for i in issues), issues)
        self.assertFalse(any("市場定價" in i and "〔新聞" in i for i in issues), issues)

    @patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_B_GATE": "1"}, clear=False)
    def test_fails_when_phase_b_omitted(self):
        t = _make_report(include_phase_b_institutional=False)
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertTrue(any("組合與曝險" in i or "市場定價" in i or "三情境機率" in i for i in issues))


class TestStrictInstitutionalPhaseAHtmlGate(unittest.TestCase):
    @patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_A_GATE": "1"}, clear=False)
    def test_passes_when_phase_a_block_present(self):
        t = _make_report()
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertFalse(any("【投資命題】" in i and "缺少" in i for i in issues))
        self.assertFalse(any("【支持論點】" in i for i in issues))

    @patch.dict(os.environ, {"STRICT_INSTITUTIONAL_PHASE_A_GATE": "1"}, clear=False)
    def test_fails_when_phase_a_omitted(self):
        t = _make_report(include_phase_a_institutional=False)
        r = validate_report(t)
        issues = r.get("issues") or []
        self.assertTrue(any("投資命題" in i or "免責" in i for i in issues))


if __name__ == "__main__":
    unittest.main()

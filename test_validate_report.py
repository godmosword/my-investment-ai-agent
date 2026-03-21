"""Unit tests for validate_report() and its helper functions in main.py."""

import os
import unittest
from unittest.mock import patch

from main import (
    validate_report,
    strip_html,
    _count_effective_news_items,
    _fallback_news_count,
    _normalize_regime_token,
    _has_news_timezone_utc8,
    _has_macro_outlier_values,
    _has_macro_conflicts,
    _risk_off_star_cap_violated,
    _pair_trade_unit_consistent,
    _has_crypto_trade_section,
    _inject_canonical_prev_recs_block,
    _auto_prefix_missing_news_tags,
    _partial_news_ok,
    _pick_rotation_crypto_ok,
    _pick_rotation_equity_ok,
    _pick_rotation_override_min_gap,
    _sanitize_macro_outlier_values,
    _ensure_rumor_grade_marker,
    _has_rumor_grade_marker,
    _postprocess_report_for_resilience,
    _normalize_news_timezone_utc8,
    _fix_glued_na_suffix,
    _conflicting_total_risk_budget_lines,
    _qsrec_opposing_direction_same_asset,
)


# ── Minimal valid report template ──
# Enough sections / keywords to pass most checks; tests override specific parts.
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
    include_signal_conflict: bool = True,
    include_rumor_grade: bool = True,
    include_rr: bool = True,
    include_risk_budget: bool = True,
    include_numeric_investment: bool = True,
    extra: str = "",
) -> str:
    news = ""
    for i in range(1, news_count + 1):
        news += f"〔新聞 {i}〕[03/{i:02d} 10:00 UTC+8] 來源\n測試新聞標題 {i} 內容夠長超過十字元\n\n"

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
        sections.append("────────────\n🤖 AI 市場\nAI 數據儀表板")
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

    body = news + "\n".join(sections) + "\n" + extra
    # Pad to requested length
    if len(body) < length:
        body += "\n" + "x" * (length - len(body))
    return body


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

    @patch("main._fetch_yesterday_qsrec_canonical_set")
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

    @patch("main._fetch_yesterday_qsrec_canonical_set")
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

    @patch("main._fetch_yesterday_qsrec_canonical_set")
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

    @patch("main._fetch_yesterday_qsrec_canonical_set")
    def test_repeat_requires_min_score_gap(self, mock_y):
        mock_y.return_value = {"BTC"}
        recs = [{"asset": "BTC", "category": "CRYPTO", "selection_score": 72, "alt_candidate_score": 66, "score_gap": 6, "repeat_days": 1}]
        body = "區塊④\n本日選擇理由：重複選用理由：新催化延續。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("分差不足", err)
        self.assertGreater(_pick_rotation_override_min_gap(), 0)

    @patch("main._fetch_yesterday_qsrec_canonical_set")
    def test_repeat_requires_quality_anchor(self, mock_y):
        mock_y.return_value = {"BTC"}
        recs = [{"asset": "BTC", "category": "CRYPTO", "selection_score": 74, "alt_candidate_score": 61, "score_gap": 13, "repeat_days": 3}]
        body = "區塊④\n本日選擇理由：重複選用理由：催化延續。\n今日風險預算：x"
        ok, err = _pick_rotation_crypto_ok(body, recs)
        self.assertFalse(ok)
        self.assertIn("repeat_days", err)


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

    def test_missing_source_health(self):
        report = _make_report(include_source_health=False)
        result = validate_report(report)
        self.assertTrue(any("SourceHealth" in i for i in result["issues"]))

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

    def test_code_leak_detected(self):
        report = _make_report(extra="multi_timeframe_tool (arg)")
        result = validate_report(report)
        self.assertTrue(any("外洩" in i and "函數" in i for i in result["issues"]))

    def test_macro_outlier_detected(self):
        report = _make_report(extra="美債 10Y: 25.00%")
        result = validate_report(report)
        self.assertTrue(result["has_macro_outlier"])

    def test_neutral_regime_forbids_risk_off_trade_language(self):
        report = _make_report(
            regime="neutral",
            extra="\n· 倉位建議：4%（高風險環境 risk_off 減倉至極低水位）\n",
        )
        result = validate_report(report)
        self.assertTrue(any("risk_off 敘述" in i or "誤用 risk_off" in i for i in result["issues"]))

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


class TestHasCryptoTradeSection(unittest.TestCase):
    """避免 LLM 省略 (Crypto) 括號時誤注入觀望區塊。"""

    def test_detects_header_without_crypto_paren(self):
        text = "【資金流向與精準操作】\n· $BTC (LONG)｜進場：$70000"
        self.assertTrue(_has_crypto_trade_section(text))

    def test_detects_classic_crypto_paren(self):
        text = "區塊④【資金流向與精準操作 (Crypto)】"
        self.assertTrue(_has_crypto_trade_section(text))


if __name__ == "__main__":
    unittest.main()

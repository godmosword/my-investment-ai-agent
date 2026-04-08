import pytest

from main import sanitize_telegram_html, validate_report
from schemas import assert_sample_output
from tools import _CACHE, _get_cache, _set_cache


def _minimal_valid_report() -> str:
    phase_a = (
        "<blockquote>研究摘要<b>不構成</b>投資建議<b>非</b>個人化勸誘過去績效不預示未來。</blockquote>\n"
        "<b>【投資命題】</b>\n主命題測試涵蓋加密與美股。\n"
        "<b>【支持論點】</b>\n· 甲\n· 乙\n· 丙\n"
        "<b>【反駁論點】</b>\n· 反甲\n· 反乙\n· 反丙\n"
        "<b>【關鍵假設】</b>\n· 假一\n· 假二\n"
        "<b>【敘事失效】</b>\n若宏觀證偽則重估。\n"
    )
    phase_b = (
        "<b>【組合與曝險框架】</b>\n"
        "測試：加密與美股雙軸在風險預算內；淨方向偏多；與 SPY 相關性中高。\n"
        "<b>【三情境機率】</b>\n"
        "· 樂觀：延續（機率 30%）\n"
        "· 基準：震盪（機率 45%）\n"
        "· 悲觀：收縮（機率 25%）\n"
    )
    phase_c = (
        "<b>【加密週期與估值錨】</b>\n"
        "NVT 與儀表板一致；週期測試。\n"
        "<b>【美股估值與修正框架】</b>\n"
        "AI 權值溢價與利率壓力測試敘述足夠長度。\n"
        "<b>【近端事件日曆】</b>\n"
        "· 03/25 NVDA 財報\n"
        "· 03/26 FOMC\n"
        "· 04/01 期權到期\n"
    )
    n1 = "〔新聞 1〕[03/01 10:00 UTC+8] A\n市場定價：未定價／增量資訊\n"
    n2 = "〔新聞 2〕[03/01 11:00 UTC+8] B\n市場定價：大致已定價\n"
    n3 = "〔新聞 3〕[03/01 12:00 UTC+8] C\n市場定價：已高度反應\n"
    n4 = "〔新聞 4〕[03/01 13:00 UTC+8] D\n市場定價：未定價／增量資訊\n"
    n5 = "〔新聞 5〕[03/01 14:00 UTC+8] E\n市場定價：大致已定價\n"
    n6 = "〔新聞 6〕[03/01 15:00 UTC+8] F\n市場定價：已高度反應\n"
    return (
        phase_a
        + phase_b
        + phase_c
        + n1
        + n2
        + n3
        + n4
        + n5
        + n6
        + "【今日市場模式】 risk_on\n"
        + "加密市場核心新聞\n"
        + "DXY 104.5 ｜ BTC OI $18.5B ｜ 資金費率 0.01% ｜ RSI 55 ｜ Fear & Greed 45\n"
        + "區塊④【資金流向與精準操作 (Crypto)】\n"
        + "本日選擇理由：現貨 ETF 連續淨流入、交易所淨流出與永續資金費率同向偏多，且 BTC 在主流新聞中具最強催化，故點名 BTC 為單邊主倉。\n"
        + "· $BTC (LONG)｜現價：$95000｜進場：$94500｜目標：$100000｜停損：$91000\n"
        + "· 流動性／執行：BTC 深度足。\n"
        + "🤖 AI 市場\n"
        + "FinancialDatasets NVDA 年度損益：營收 $61B\n"
        + "AI 產業鏈精準操作 (US Equities)\n"
        + "本日選擇理由：NVDA 在主流新聞中同時具備資料中心 CAPEX 擴張與供應鏈能見度上修催化，並有財報前預期支撐，故點名 NVDA 作為今日美股主倉。\n"
        + "· $NVDA (LONG)｜現價：$890｜進場：$885｜目標：$950｜停損：$860\n"
        + "· 流動性／執行：NVDA ADV 足。\n"
        + "訊號衝突摘要：無顯著多空衝突。\n"
        + "可信度：B\n"
        + "R:R = 1:2.0\n最大回撤風險：<code>-3.0%</code>\n預期勝率：55%\nSignal Score：70/100\n"
        + "今日風險預算：risk_on 模式下總倉位上限 60%\n"
        + "投資解讀：BTC 日線 RSI 55，ETF 流入 $120M\n"
        + "區塊③【呢喃與傳聞】\n"
        + "· 低信噪比，暫無高可信傳聞（未確認）｜可信度：C\n"
        + "[QSREC_START]\n"
        + "["
        + "{\"asset\":\"BTC\",\"direction\":\"LONG\",\"current_price\":95000,\"entry\":94500,"
        + "\"target\":100000,\"stop\":91000,\"confidence\":4,\"category\":\"CRYPTO\","
        + "\"narrative\":\"test\",\"trigger\":\"x\",\"invalidation\":\"y\",\"position_pct\":5,\"timeframe\":\"3d\","
        + "\"selection_score\":78,\"catalyst_score\":80,\"flow_score\":76,\"technical_score\":75,"
        + "\"risk_fit_score\":74,\"execution_score\":79,\"alt_candidate_score\":63,\"score_gap\":15,\"repeat_days\":1,"
        + "\"rr_ratio\":2.0,\"max_drawdown_pct\":-3.0,\"expected_win_rate\":55,\"signal_score\":70,"
        + "\"regime\":\"risk_on\"},"
        + "{\"asset\":\"NVDA\",\"direction\":\"LONG\",\"current_price\":890,\"entry\":885,"
        + "\"target\":950,\"stop\":860,\"confidence\":4,\"category\":\"EQUITY\","
        + "\"narrative\":\"test\",\"trigger\":\"x\",\"invalidation\":\"y\",\"position_pct\":5,\"timeframe\":\"5d\","
        + "\"selection_score\":81,\"catalyst_score\":84,\"flow_score\":78,\"technical_score\":80,"
        + "\"risk_fit_score\":77,\"execution_score\":82,\"alt_candidate_score\":65,\"score_gap\":16,\"repeat_days\":1,"
        + "\"rr_ratio\":2.0,\"max_drawdown_pct\":-3.0,\"expected_win_rate\":55,\"signal_score\":70,"
        + "\"regime\":\"risk_on\"}"
        + "]\n"
        + "[QSREC_END]\n"
        + "x" * 3100
    )


@pytest.mark.smoke
def test_smoke_validate_report_happy_path():
    result = validate_report(_minimal_valid_report())
    non_chatter_issues = [i for i in result["issues"] if "呢喃" not in i and "傳聞" not in i]
    assert result["valid"], f"unexpected issues: {non_chatter_issues}"


@pytest.mark.smoke
def test_smoke_tools_cache_roundtrip():
    _CACHE.clear()
    _set_cache(("smoke", "k"), "v")
    assert _get_cache(("smoke", "k")) == "v"


@pytest.mark.smoke
def test_smoke_output_and_html_sanitize_contract():
    assert_sample_output({"title": "Daily Brief", "code": "<code>BTC: 68000</code>", "news": "clean news"})
    out = sanitize_telegram_html("<pre>blocked</pre><code>ok</code><blockquote>q</blockquote>")
    assert "<pre>" not in out
    assert "<code>ok</code>" in out

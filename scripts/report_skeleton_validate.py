"""Pure-string minimal Telegram report skeleton for Gate dry-run (no main.py import)."""

# Mirrors test_validate_report._make_report() defaults — keep in sync when Gate contract changes.
_PHASE_A_HTML = (
    "<blockquote>"
    "本電報內容僅為研究性質之市場摘要，<b>不構成</b>投資建議；<b>非</b>個人化勸誘；過去績效不預示未來。"
    "</blockquote>\n"
    "<b>【投資命題】</b>\n"
    "測試主命題一句涵蓋加密與美股主軸。\n"
    "<b>【支持論點】</b>\n"
    "· 論點甲\n· 論點乙\n· 論點丙\n"
    "<b>【反駁論點】</b>\n"
    "· 反駁甲\n· 反駁乙\n· 反駁丙\n"
    "<b>【關鍵假設】</b>\n"
    "· 假設一\n· 假設二\n"
    "<b>【敘事失效】</b>\n"
    "若關鍵宏觀假設被證偽則重估主命題。\n"
)


def minimal_valid_report_text(*, length: int = 5000) -> str:
    news = ""
    for i in range(1, 9):
        news += f"〔新聞 {i}〕[03/{i:02d} 10:00 UTC+8] 來源\n測試新聞標題 {i} 內容夠長超過十字元\n\n"

    regime = "risk_on"
    sections = [
        f"【今日市場模式】 {regime}",
        "DXY 104.5 ｜ BTC OI $18.5B ｜ 資金費率 0.01% ｜ RSI 55 ｜ Fear & Greed 45",
        "區塊④ 資金流向與精準操作 (Crypto)\n"
        "本日選擇理由：現貨 ETF 淨流入與監管新聞構成催化，鏈上資金費率與多空比同步支持偏多結構，選 BTC 作為單邊主倉。\n"
        "· $BTC (LONG)｜現價：$95000｜進場：$94500｜目標：$100000｜停損：$91000",
        "────────────\n🤖 AI 市場\nAI 數據儀表板\n· FinancialDatasets NVDA 年度損益：營收 $61B",
        "AI 產業鏈精準操作 (US Equities)\n"
        "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。\n"
        "· $NVDA (LONG)｜現價：$890",
        "加密市場核心新聞",
        "呢喃與傳聞掃描",
        "訊號衝突摘要：短期動能與中期結構分歧",
        "可信度：B",
        "R:R = 1:2.5\n最大回撤風險：<code>-3.7%</code>\n預期勝率：55%\nSignal Score：72/100",
        f"今日風險預算：{regime} 模式下總倉位上限 15%",
        "投資解讀：BTC 日線 RSI 55，ETF 流入 $120M",
        "【SourceHealth】 5/5 正常\n【SourceErrors】 0 次\n【SourceQuota】 NewsAPI 82%",
        "[QSREC_START]\n["
        '{"asset":"BTC","direction":"LONG","current_price":95000,"entry":94500,'
        '"target":100000,"stop":91000,"confidence":4,"category":"CRYPTO",'
        f'"narrative":"test","trigger":"x","invalidation":"y","position_pct":5,"timeframe":"3d","regime":"{regime}",'
        '"selection_score":78,"catalyst_score":80,"flow_score":76,"technical_score":75,"risk_fit_score":74,'
        '"execution_score":79,"alt_candidate_score":63,"score_gap":15,"repeat_days":1'
        "},"
        '{"asset":"NVDA","direction":"LONG","current_price":890,"entry":885,'
        '"target":950,"stop":860,"confidence":4,"category":"EQUITY",'
        f'"narrative":"test","trigger":"x","invalidation":"y","position_pct":5,"timeframe":"5d","regime":"{regime}",'
        '"selection_score":81,"catalyst_score":84,"flow_score":78,"technical_score":80,"risk_fit_score":77,'
        '"execution_score":82,"alt_candidate_score":65,"score_gap":16,"repeat_days":1'
        "}]\n[QSREC_END]",
    ]
    exec_hdr = (
        "【執行摘要】\n"
        "· 測試摘要甲：風險可控延續觀察 BTC 偏多結構\n"
        "→ 測試摘要乙：美股以 NVDA 財報催化為主軸\n\n"
    )
    body = news + exec_hdr + _PHASE_A_HTML + "\n".join(sections) + "\n"
    if len(body) < length:
        body += "\n" + "x" * (length - len(body))
    return body

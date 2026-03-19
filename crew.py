import os
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from tools import (
    ai_momentum_tool,
    coinglass_data_tool,
    cryptopanic_tool,
    econ_calendar_tool,
    etf_flow_tool,
    fear_greed_tool,
    gnews_tool,
    macro_context_tool,
    market_search_tool,
    ml_quant_tool,
    multi_timeframe_tool,
    newsapi_tool,
    onchain_metrics_tool,
    regime_scorecard_tool,
    rss_feed_tool,
    rumor_scanner_tool,
    sentiment_score_tool,
    x_search_tool,
)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

MODEL_GROK = "xai/grok-4-1-fast-reasoning"
# 預設改為 gpt-4o-mini 以壓低單次日報成本（約 $0.03～0.05）；可設 OPENAI_MODEL 覆寫，例如 openai/gpt-4o
MODEL_GPT = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

_TELEGRAM_FMT = dedent("""\
    Telegram HTML：只允許 <b> <i> <u> <s> <code> <blockquote> <a href>
    禁止 Markdown 與其他 HTML；大區塊前加分隔線 ────────────
    儀表板每項獨立一行且數值包 <code>；摘要用 <blockquote>；缺資料寫 <code>N/A</code>""")

_FINAL_TEMPLATE_CRYPTO = dedent("""\
    === 極簡範例（嚴禁輸出除錯字樣） ===
    <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief</i>
    【今日市場模式】neutral
    ══════ <b>📊 加密市場</b> ══════
    區塊①【數據儀表板】（每行獨立，數值用 <code>）
    區塊②【核心新聞】（3 則，每則含投資解讀 + 💎主編共識）
    區塊③【市場呢喃與傳聞】（2~3 條）
    區塊④【資金流向與精準操作 (Crypto)】（含 R:R/回撤/勝率/Signal Score）
    [QSREC_START]
    [{"asset":"BTC","direction":"LONG","current_price":70578,"entry":69800,"target":72800,"stop":67800,"confidence":3,"category":"CRYPTO","trigger":"...","invalidation":"...","position_pct":8,"timeframe":"3-5天"}]
    [QSREC_END]
    """)

_FINAL_TEMPLATE_AI = dedent("""\
    === 極簡範例（嚴禁輸出除錯字樣） ===
    ══════ <b>🤖 AI 市場</b> ══════
    區塊①【AI 數據儀表板】（每行獨立，數值用 <code>）
    區塊②【AI 產業新聞】（3 則，每則含投資解讀 + 💎主編共識）
    區塊③【產業鏈呢喃】（2~3 條）
    區塊④【AI 產業鏈精準操作 (US Equities)】（2 檔，由今日新聞動態選出，含完整風控欄位）
    [QSREC_START]
    [{"asset":"TODAY_PICK_1","direction":"LONG/SHORT","current_price":0,"entry":0,"target":0,"stop":0,"confidence":3,"category":"EQUITY","trigger":"...","invalidation":"...","position_pct":6,"timeframe":"5-10天"}]
    [QSREC_END]
    """)

_EDITOR_RULE = dedent("""\
    【主編共識與排版紅線】
    1. 【極致洗鍊】投資解讀必須精簡，展現華爾街頂級投行主編的俐落。
    2. 【黑名單封殺】你的輸出【絕對禁止】包含以下字眼或結構：
       - 禁止印出「(嚴格要求...)」或「[IMPACT...]」等標籤。
       - 禁止印出任何 Python 函數名稱（如 multi_timeframe_tool）。
    3. 【專業交易欄位必備】每筆建議必須包含：進場、目標、停損、觸發模式、失效條件、倉位建議、敘事邏輯。
    4. 【量化風控必備】每筆建議必須包含：R:R、最大回撤風險、預期勝率（%）、Signal Score（0-100）。
    5. 【缺值處理】若關鍵欄位 N/A 超過 3 項，必須加註「低置信度」並說明資料缺失原因與替代指標。
    6. 【資料載荷】結尾 QSREC JSON 不得遺漏，且欄位需與交易內容一致。
    """)
_REGIME_POSITION_POLICY = dedent("""\
    【Regime 風險預算（硬規則）】
    - risk_off：單筆建議倉位上限 5%，總風險預算 20%，信心上限 ⭐️⭐️⭐️
    - neutral：單筆建議倉位上限 10%，總風險預算 40%
    - risk_on：單筆建議倉位上限 15%，總風險預算 60%
    必須在交易段落前輸出「今日風險預算」摘要，並讓每筆 position_pct 與 regime 一致。""")
_DATA_RULES = dedent("""\
    【新鮮度】新聞必須在 48h 內；超時跳過重搜。
    【嚴禁播報系統錯誤】若任何 Tool 回傳 `[DATA_MISSING...]`、`失敗` 或 `API 未設定`，絕對禁止將這些錯誤訊息寫成新聞！請直接忽略該工具的輸出。若無足夠真實新聞，寧可減少新聞數量，也絕不允許播報系統日誌！""")

_NEWS_FMT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM UTC+8] <b>新聞標題</b>（來源：xxx｜性質：confirmed / likely / unverified rumor）
    <blockquote>摘要：（1 句核心事實，禁止加入主觀評論）</blockquote>
    投資解讀：（將受影響資產、做多做空風險等情報，融合成 1~2 句通順段落；且必須至少引用 1 個當日數據，如資金費率/成交量/基差/RSI/MA/ETF 流向）
    💎主編共識：[1 句最終操作判斷，必須點名具體標的]
    【格式紅線】嚴禁在最終戰報中印出「📍 受影響資產」、「📈 做多機會」、「📉 做空風險」、「⏱️ 時效」、「🎯 IMPACT」等原始標籤符號，必須轉化為自然語言！""")

_DASHBOARD_FMT = dedent("""\
    儀表板格式：每項獨立一行，數值部分【必須】用 <code> 標籤包覆。
    · <b>指標名</b> <code>數值 ▲/▼幅度%</code>
    缺資料寫 <code>N/A</code>，禁止同一行塞多個指標。
    儀表板尾端固定輸出兩行（不可省略）：
    · <b>SourceHealth</b> <code>newsapi:x.xx | gnews:x.xx | apify:x.xx</code>
    · <b>SourceErrors</b> <code>newsapi:429=n,400=n,timeout=n,5xx=n,other=n | gnews:... | apify:...</code>
    · <b>SourceQuota</b> <code>newsapi:used/max | gnews:used/max | apify:used/max</code>
    若關鍵欄位 N/A 超過 3 項，必須在該區塊加註：<b>低置信度</b>，
    並補 1 行「資料缺失原因 + 替代指標」（例如：OI 缺失改看 funding/多空比/現貨成交額）。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質與可信度分級（A/B/C 或 0~100）、
    並標註是否已被主流媒體二次驗證（是/否），輸出 2~3 條""")


_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL 及當日選定美股標的等數值，
    以及 RSI(14)、MA20/MA50、VIX 期限結構等技術指標，
    必須直接使用上方【系統強制即時報價】+【技術指標與結構】Context；不得自行捏造或改寫。""")

_NARRATIVE_CONSISTENCY_RULE = dedent("""\
    【敘事與數據一致】引用 BTC/指數/均線時，須與【技術指標與結構】的趨勢描述一致：
    若 Context 為「多頭排列（價>MA20>MA50）」或現價高於 MA50，不得寫「跌破 MA50」或「跌破均線」；
    若為「空頭排列（價<MA20<MA50）」或現價低於 MA50，不得寫「站上 MA50」。不確定時改寫為「若跌破/若站上」等條件句。""")

_TRADE_RULE = dedent("""\
    · <b>$代幣/股票 (操作方向)</b>｜現價：$真實最新報價｜信心水準：⭐️⭐️⭐️⭐️
    · 進場：<code>$數值</code>｜目標：<code>$數值</code> (+Y%)｜停損：<code>$數值</code> (-Z%)
    · 風控：<code>R:R = 1:X</code>｜最大回撤風險：<code>-Z%</code>｜預期勝率：<code>W%</code>｜Signal Score：<code>S/100</code>
    · 觸發模式：具體進場條件（例：「4H 收盤突破 $70.5k 確認」）
    · 建倉邏輯：多時間框架分批建倉（例：「日線確認方向 → 4H 拉回 MA20 → 1H 收針進場 50%，目標位再加 50%」）
    · 失效條件：清倉觸發（例：「日線收盤 < $67k 或 funding rate > 0.08%」）
    · 倉位建議：佔總資金比例（例：「8%，高風險環境減半至 4%」）
    · 敘事邏輯：1 句，引用本日新聞
    請確保每個數值都用 <code> 標籤包覆，勿轉換為 Markdown 格式。""")

_RISK_MODE_RULE = dedent("""\
    【市場模式聯動風控】
    - 全文只能有一個 market_regime（risk_on / neutral / risk_off）；嚴禁在不同段落切換 regime。
    - 若今日市場模式為 risk_off：所有交易建議信心水準上限降一級（最高只能 ⭐️⭐️⭐️），並在敘事中明確標註「減倉/輕倉」。
    - 若訊號互相衝突（例如 RSI 中性 + VIX 倒掛 + 資金費率回穩），必須新增 1 行「訊號衝突摘要：...」。
    - 交易段落前必須新增 1 行「今日風險預算：...」（依 Regime 風險預算硬規則）。""")

_PAIR_TRADE_RULE = dedent("""\
    【配對交易單位一致性】
    - 若輸出配對交易（如 $BTC / $SOL），必須明確標註「單位：BTC/SOL 比值」或「單位：價差」。
    - 現價/進場/目標/停損必須使用同一單位，禁止混用單幣現價與比值。""")

# tracker.py 解析用的機器可讀區塊格式（Telegram 不渲染，純文字標記）
# 欄位：asset=代號大寫不含$, entry/target/stop=純數字, target_pct/stop_pct=百分比數字,
#        confidence=1~4, category=CRYPTO|EQUITY, current_price=現價數字
_TRADE_JSON_RULE = dedent("""\
    === 系統強制驗證區塊 ===
    在報告最後輸出 `[QSREC_START]` 與 `[QSREC_END]` 包住的 JSON 陣列：
    [QSREC_START]
    [
      {"asset": "代號", "direction": "LONG/SHORT", "current_price": 數字, "entry": 數字, "target": 數字, "stop": 數字, "confidence": 數字, "category": "CRYPTO/EQUITY", "narrative": "敘事...", "trigger": "觸發條件", "invalidation": "失效條件", "position_pct": 數字, "timeframe": "持倉週期"}
    ]
    [QSREC_END]
    規則：數字欄位不可加引號、asset 不含 $、必須是合法 JSON、所有建議放在同一陣列。
    可附加欄位：rr_ratio、max_drawdown_pct、expected_win_rate、signal_score、regime。""")

_MTF_CONF_RULE = dedent("""\
    === 交易建議（通用）===
    每筆必須呼叫 multi_timeframe_tool('標的')，僅輸出自然語言（禁止函數名）：
    - 三時框同向 → ⭐️⭐️⭐️⭐️
    - 兩同向一中性 → ⭐️⭐️⭐️
    - 分歧 → ⭐️⭐️ 或 ⭐️""")

_CRYPTO_LAYOUT_RULE = dedent("""\
    === 排版順序（Crypto）===
    1) <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
    2) 若有【上期建議追蹤】則原文貼上（標題後）
    3) 【今日市場模式】與評分卡明細（取自 review_task）
    4) 🏛️ 宏觀框架（取自 macro_context_tool）
    5) 📊 加密市場：
       - 區塊① 儀表板（宏觀/技術/籌碼；嚴格套用儀表板格式）
       - 區塊② 核心新聞 3 則（套用新聞格式）
       - 區塊②b X 推文精選（無資料可跳過）
       - 區塊③ 市場呢喃與傳聞 2~3 條
       - 區塊④ 資金流向與精準操作：1 單邊 + 1 配對
    6) 最後必須輸出 QSREC JSON 區塊""")

_AI_LAYOUT_RULE = dedent("""\
    === 排版順序（AI）===
    1) 🏛️ 宏觀框架：本戰報將接在加密戰報之後，前段已含完整宏觀數據；本節僅輸出「承上宏觀」+ 一句主編共識（如 10Y/VIX 對美股影響），勿重複貼上美債/SOFR/利差整段。
    2) 🤖 AI 市場：
       - 區塊① AI 儀表板（HuggingFace / OpenRouter 模型熱度 Top5；缺值 <code>N/A</code>）
       - 區塊② AI 產業新聞 3 則（基建/投資案/模型各 1）
       - 區塊②b X 推文精選（無資料可跳過）
       - 區塊③ 產業鏈呢喃 2~3 條
       - 區塊④ AI 精準操作 2 檔：
         【動態選股規則】禁止固定使用特定股票。必須根據以下優先順序動態選出本日 2 檔：
         (a) 優先選今日 AI 新聞中直接點名且有具體財務/產品事件的美股（如財報、拉貨、合約）
         (b) 次選 ai_momentum_tool 回傳模型排名中，對應的上市公司股票（如 Meta, Google, Microsoft, AMD 等）
         (c) 最後才考慮 AI 基建通殺標的（如 ETF BOTZ/ARKQ）
         每次必須說明「本日選擇理由：XXX 因 [具體事件] 入選」
    3) 最後必須輸出 QSREC JSON 區塊""")


def _make_llms(*names: str):
    """建立並回傳指定的 LLM 實例。"""
    factories = {
        "grok": lambda: LLM(model=MODEL_GROK, api_key=os.getenv("XAI_API_KEY"), max_retries=3, timeout=120),
        "gpt": lambda: LLM(model=MODEL_GPT, api_key=os.getenv("OPENAI_API_KEY"), max_retries=3, timeout=120),
        "gemini": lambda: LLM(model=MODEL_GEMINI, api_key=os.getenv("GEMINI_API_KEY"), max_retries=5, timeout=180),
    }
    return tuple(factories[n]() for n in names)


class CryptoResearchCrew:
    def __init__(self):
        grok, gpt, gemini = _make_llms("grok", "gpt", "gemini")

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，產出 3 則高衝擊幣圈新聞。",
            backstory="冷靜量化研究員，專注流動性、槓桿與聰明錢行為。",
            llm=grok,
            tools=[market_search_tool, newsapi_tool, rss_feed_tool, gnews_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, fear_greed_tool, etf_flow_tool, econ_calendar_tool, x_search_tool, onchain_metrics_tool, sentiment_score_tool],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席幣圈風險審計員",
            goal="對幣圈新聞做反向辯論，以評分卡判定 market_regime。",
            backstory="反身性風險審計者，負責挑錯、驗證與量化機制判斷。",
            llm=gpt,
            allow_delegation=False,
            tools=[regime_scorecard_tool, macro_context_tool],
            verbose=_VERBOSE,
        )

        self.quant_strategist = Agent(
            role="機構策略主編（加密市場）",
            goal="整合研究成果，輸出戰報上半部。",
            backstory="最終排版與風控守門員。",
            llm=gemini,
            tools=[coinglass_data_tool, ml_quant_tool, multi_timeframe_tool],
            verbose=_VERBOSE,
        )

    def run(self, exclude_context: str | None = None, price_context: str = "",
            prev_recs_block: str = ""):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        excl = (
            f"\n【避免重複】昨日已涵蓋：\n{exclude_context}\n"
            if exclude_context else ""
        )
        ctx = f"\n【系統強制即時報價】\n{price_context}\n"
        prev_recs_ctx = (
            f"\n【上期建議追蹤（必須原文輸出於報告最頂端，排在標題之後）】\n{prev_recs_block}\n"
            if prev_recs_block else ""
        )

        crypto_task = Task(
            description=dedent(f"""
                【加密市場情報收集 — Grok】
                {ctx}

                {_DATA_RULES}
                {_QUOTE_RULE}
                {excl}
                === 數據來源（必須全部呼叫）===
                · coinglass_data_tool：funding_rate / liquidations / long_short_ratio / options_info
                · fear_greed_tool()（恐懼與貪婪指數）
                · etf_flow_tool()（BTC Spot ETF 每日資金流，禁止自行猜測 ETF 數據）
                · econ_calendar_tool()（本週宏觀經濟日曆，禁止自行猜測 FOMC/CPI 日期）
                · cryptopanic_tool('bitcoin')
                · rss_feed_tool('crypto')（CoinDesk / TheBlock / Cointelegraph 免費 RSS，優先取用）
                · newsapi_tool('Bitcoin crypto ETF market')（Bloomberg / Reuters 主流財經新聞）
                · gnews_tool('Bitcoin crypto market')（多語言補充）
                · rumor_scanner_tool('BTC ETF flow OR crypto manipulation OR whale alert')
                · market_search_tool('Bitcoin market liquidity derivatives risk')
                · x_search_tool('bitcoin BTC crypto market ETF liquidation')（取得 X/Twitter 即時情緒推文，供 X 推文精選區塊使用）
                · onchain_metrics_tool()（P2 鏈上深度：SOPR / 交易所淨流向 / 活躍地址數 / NUPL）
                · sentiment_score_tool(news_and_tweets=<將上方新聞標題 + X 推文拼接後傳入>)（P2 社群情緒量化：-1 到 +1）

                === 幣圈新聞（3 則）===
                {_NEWS_FMT}
                研判：2~3 句，必須明確說明哪個標的受影響
                禁止捏造來源。
            """),
            expected_output="3 則幣圈新聞結構化初稿。",
            agent=self.crypto_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — GPT】
                {ctx}

                {_QUOTE_RULE}

                === Fact-Check ===
                以【系統強制即時報價】核對 DXY/VIX/IBIT/BTC。
                {_NARRATIVE_CONSISTENCY_RULE}

                === 宏觀框架 ===
                必須呼叫 macro_context_tool()，將美債殖利率、利率曲線、Fed 預期、本週財報輸出於此區塊。

                === market_regime（可審計評分卡）===
                必須呼叫 regime_scorecard_tool()，將完整評分卡（6 項指標各自評分 + 總分 + 最終 regime）原文輸出。
                格式範例：
                【今日市場模式】risk_on（+4/6）
                ✅ VIX <code>18.5(< 20)</code>→+1 | ✅ ETF流 <code>320.0(>200)</code>→+1 | ✅ 資金費率 <code>0.012(< 0.03)</code>→+1
                ❌ 24h爆倉 <code>420.5(> 300)</code>→-1 | ✅ 恐懼貪婪 <code>62.0(> 55)</code>→+1 | ✅ BTC RSI <code>55.2(45–65)</code>→+1

                === 新聞辯論（3 則）===
                每則 2~3 句反向觀點。
            """),
            expected_output="宏觀框架、風險審計與可審計 regime 評分卡。",
            agent=self.risk_critic,
            context=[crypto_task],
        )

        final_report_task = Task(
            description=dedent(f"""
                【加密市場戰報排版 — GPT 主編】
                {_QUOTE_RULE}
                {_NARRATIVE_CONSISTENCY_RULE}
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_RISK_MODE_RULE}
                {_REGIME_POSITION_POLICY}
                {_PAIR_TRADE_RULE}
                {ctx}
                {prev_recs_ctx}

                {_MTF_CONF_RULE}
                {_TRADE_RULE}

                {_CRYPTO_LAYOUT_RULE.format(today_str=today_str)}

                {_TRADE_JSON_RULE}

                {_FINAL_TEMPLATE_CRYPTO}
            """),
            expected_output="一份純淨的 HTML 戰報。報告的最末端必須、絕對要包含 [QSREC_START] 到 [QSREC_END] 的 JSON 陣列。若遺漏 JSON，你的任務將被判定為徹底失敗！",
            agent=self.quant_strategist,
            context=[crypto_task, review_task],
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, review_task, final_report_task],
            process=Process.sequential,
        )
        return crew.kickoff()


class AIResearchCrew:
    def __init__(self):
        gpt, grok, gemini = _make_llms("gpt", "grok", "gemini")

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="收集 AI 市場核心資訊並輸出 3 則可交易新聞。",
            backstory="科技產業鏈研究員，聚焦可驗證催化。",
            llm=gpt,
            tools=[market_search_tool, newsapi_tool, rss_feed_tool, gnews_tool, ai_momentum_tool, rumor_scanner_tool, x_search_tool],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席 AI 市場辯論員",
            goal="對 AI 新聞做反向辯論，引用宏觀框架強化論點。",
            backstory="對估值泡沫與敘事偏差高度敏感，善用利率與財報催化分析 AI 板塊。",
            llm=grok,
            allow_delegation=False,
            tools=[macro_context_tool],
            verbose=_VERBOSE,
        )

        self.quant_strategist = Agent(
            role="機構策略主編（AI 市場）",
            goal="整合 AI 研究成果輸出戰報下半部。",
            backstory="最終格式與可操作性守門。",
            llm=gemini,
            tools=[multi_timeframe_tool],
            verbose=_VERBOSE,
        )

    def run(self, exclude_context: str | None = None, price_context: str = ""):
        excl = (
            f"\n【避免重複】昨日已涵蓋：\n{exclude_context}\n"
            if exclude_context else ""
        )
        year = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m")
        ctx = f"\n【系統強制即時報價】\n{price_context}\n"

        ai_task = Task(
            description=dedent(f"""
                【AI 市場情報收集 — GPT】
                {ctx}

                {_DATA_RULES}
                {_QUOTE_RULE}
                {excl}
                呼叫 ai_momentum_tool('openrouter_rankings')。
                搜尋：
                · rss_feed_tool('ai')（TechCrunch / VentureBeat AI RSS，優先取用）
                · newsapi_tool('AI data center GPU cloud computing semiconductor')（Bloomberg / Reuters AI 報導）
                · gnews_tool('artificial intelligence GPU infrastructure semiconductor')（多語言補充）
                · market_search_tool('AI data center GPU semiconductor infrastructure {year}')
                · market_search_tool('data center power supply nuclear energy AI {year}')
                · rumor_scanner_tool('AI infrastructure supply chain risk')
                · x_search_tool('NVIDIA AI GPU data center OpenAI Anthropic Microsoft')（取得 AI 板塊 X/Twitter 即時推文）

                產出 AI 新聞 3 則，每則格式：
                {_NEWS_FMT}
                🤖 GPT 研判：2~3 句，必須點名受影響美股或 ETF
            """),
            expected_output="3 則 AI 新聞結構化初稿。",
            agent=self.ai_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Grok】
                {_QUOTE_RULE}
                {_NARRATIVE_CONSISTENCY_RULE}
                {ctx}

                === 宏觀框架（美股利率敏感性）===
                必須呼叫 macro_context_tool()，輸出美債利率、殖利率曲線、Fed 預期、本週財報，
                分析這些宏觀變數對本日 AI 新聞點名之美股標的的下一步影響。

                === 新聞辯論 ===
                對 3 則 AI 新聞逐條提出反向觀點（每則 2~3 句）；引用 BTC/均線時須與上方【技術指標與結構】一致。
            """),
            expected_output="宏觀框架分析與 3 則 AI 新聞辯論觀點。",
            agent=self.risk_critic,
            context=[ai_task],
        )

        final_report_task = Task(
            description=dedent(f"""
                【AI 市場戰報排版 — GPT 主編】
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_QUOTE_RULE}
                {_NARRATIVE_CONSISTENCY_RULE}
                {_RISK_MODE_RULE}
                {_REGIME_POSITION_POLICY}
                {_PAIR_TRADE_RULE}
                {ctx}

                {_MTF_CONF_RULE}
                {_TRADE_RULE}

                {_AI_LAYOUT_RULE}

                {_TRADE_JSON_RULE}

                {_FINAL_TEMPLATE_AI}
            """),
            expected_output="一份純淨的 HTML 戰報。報告的最末端必須、絕對要包含 [QSREC_START] 到 [QSREC_END] 的 JSON 陣列。若遺漏 JSON，你的任務將被判定為徹底失敗！",
            agent=self.quant_strategist,
            context=[ai_task, review_task],
        )

        crew = Crew(
            agents=[self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[ai_task, review_task, final_report_task],
            process=Process.sequential,
        )
        return crew.kickoff()


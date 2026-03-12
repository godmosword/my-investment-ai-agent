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
    market_search_tool,
    ml_quant_tool,
    multi_timeframe_tool,
    newsapi_tool,
    onchain_metrics_tool,
    rss_feed_tool,
    rumor_scanner_tool,
    sentiment_score_tool,
    x_search_tool,
)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

MODEL_GROK = "xai/grok-4-1-fast-reasoning"
MODEL_GPT = "openai/gpt-5.2-2025-12-11"
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

_TELEGRAM_FMT = dedent("""\
    Telegram HTML：只允許 <b> <i> <u> <s> <code> <blockquote> <a href>
    禁止 Markdown 與其他 HTML；大區塊前加分隔線 ────────────
    儀表板每項獨立一行且數值包 <code>；摘要用 <blockquote>；缺資料寫 <code>N/A</code>""")

_FINAL_TEMPLATE = dedent("""\
    === 【排版參考】輸出結構參照以下範例，嚴禁添加任何自創欄位，嚴禁印出除錯文字！ ===
    <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief</i>
    ────────────
    【今日市場模式】neutral
    ══════ <b>📊 加密市場</b> ══════
    區塊①【數據儀表板】：
    · <b>DXY</b> <code>104.5</code>
    · <b>VIX</b> <code>24.44</code>
    · <b>IBIT</b> <code>$40.12</code>
    （依序輸出所有儀表板指標，每項獨立一行）
    區塊④【精準操作】：
    · <b>$BTC (LONG)</b>｜現價：$70578｜信心水準：⭐️⭐️
    · 進場：<code>$69800</code>｜目標：<code>$72800 (+4.3%)</code>｜停損：<code>$67800 (-2.8%)</code>
    · 敘事邏輯：多時框狀態 D(中性)/4H(中性)/1H(多)，資金費率轉負支持反彈...
    [QSREC_START]
    [
      {"asset": "BTC", "direction": "LONG", "current_price": 70578, "entry": 69800, "target": 72800, "stop": 67800, "confidence": 2, "category": "CRYPTO", "narrative": "多時框狀態 D(中性)/4H(中性)/1H(多)..."}
    ]
    [QSREC_END]
    """)

_EDITOR_RULE = dedent("""\
    【主編共識與排版紅線】
    1. 【極致洗鍊】投資解讀必須精簡，展現華爾街頂級投行主編的俐落。
    2. 【黑名單封殺】你的輸出【絕對禁止】包含以下字眼或結構：
       - 禁止印出「低置信度」、「資料缺失原因」、「替代指標」等系統除錯文字。若無資料直接寫 N/A。
       - 禁止印出「(嚴格要求...)」或「[IMPACT...]」等標籤。
       - 禁止自創「風控：R:R」或「最大回撤風險」等欄位，交易操作只需列出進場、目標、停損與敘事邏輯。
    """)
_DATA_RULES = dedent("""\
    【新鮮度】新聞必須在 48h 內；超時跳過重搜。
    【嚴禁播報系統錯誤】若任何 Tool 回傳 `[DATA_MISSING...]`、`失敗` 或 `API 未設定`，絕對禁止將這些錯誤訊息寫成新聞！請直接忽略該工具的輸出。若無足夠真實新聞，寧可減少新聞數量，也絕不允許播報系統日誌！""")

_NEWS_FMT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] <b>新聞標題</b>（來源：xxx｜性質：confirmed / likely / unverified rumor）
    <blockquote>摘要：（1 句核心事實，禁止加入主觀評論）</blockquote>
    投資解讀：（將受影響資產、做多做空風險等情報，融合成 1~2 句通順的段落）
    💎主編共識：[1 句最終操作判斷，必須點名具體標的]
    【格式紅線】嚴禁在最終戰報中印出「📍 受影響資產」、「📈 做多機會」、「📉 做空風險」、「⏱️ 時效」、「🎯 IMPACT」等原始標籤符號，必須轉化為自然語言！""")

_DASHBOARD_FMT = dedent("""\
    儀表板格式：每項獨立一行，數值部分【必須】用 <code> 標籤包覆。
    · <b>指標名</b> <code>數值 ▲/▼幅度%</code>
    缺資料寫 <code>N/A</code>，禁止同一行塞多個指標。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質，輸出 2~3 條""")

_TWEET_FMT = dedent("""\
    X 推文精選：僅摘錄 x_search_tool 回傳的真實推文，嚴禁捏造任何用戶名或推文內容
    每條格式：· 🐦 @用戶名 [時間] 推文核心內容（❤️互動數）
    若 x_search_tool 回傳 [DATA_MISSING:x_search]，直接跳過此區塊，不輸出任何佔位文字""")

_IMPACT_TAG = dedent("""\
    📍 受影響資產：[Ticker]
    📈 做多機會：[標的]—[原因]
    📉 做空風險：[標的]—[原因]
    ⏱️ 時效：短期/中期/長期
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多""")

_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL、NVDA、MSFT 等數值，
    以及 RSI(14)、MA20/MA50、VIX 期限結構等技術指標，
    必須直接使用上方【系統強制即時報價】+【技術指標與結構】Context；不得自行捏造或改寫。""")

_TRADE_RULE = dedent("""\
    · <b>$代幣/股票 (操作方向)</b>｜現價：$真實最新報價｜信心水準：⭐️⭐️⭐️⭐️
    · 進場：<code>$數值</code>｜目標：<code>$數值</code> (+Y%)｜停損：<code>$數值</code> (-Z%)
    · 敘事邏輯：1 句，引用本日新聞
    請確保每個數值都用 <code> 標籤包覆，勿轉換為 Markdown 格式。""")

# tracker.py 解析用的機器可讀區塊格式（Telegram 不渲染，純文字標記）
# 欄位：asset=代號大寫不含$, entry/target/stop=純數字, target_pct/stop_pct=百分比數字,
#        confidence=1~4, category=CRYPTO|EQUITY, current_price=現價數字
_TRADE_JSON_RULE = dedent("""\
    === 系統強制驗證區塊（不可見的資料庫載荷）===
    【最高警告】你是一個 API 端點，在輸出完上述所有 HTML 戰報後，你的最後輸出【必須】是以下結構，一字不漏地印出 `[QSREC_START]` 與 `[QSREC_END]`：

    [QSREC_START]
    [
      {"asset": "代號", "direction": "LONG/SHORT", "current_price": 數字, "entry": 數字, "target": 數字, "stop": 數字, "confidence": 數字, "category": "CRYPTO/EQUITY", "narrative": "敘事..."}
    ]
    [QSREC_END]
    JSON 規則：數字欄位禁止加引號、asset 不含 $、禁止多行縮排、所有建議合併進同一個陣列。""")


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
            goal="對幣圈新聞做反向辯論，判定 market_regime。",
            backstory="反身性風險審計者，負責挑錯與驗證。",
            llm=gpt,
            allow_delegation=False,
            tools=[],
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

    def run(self, exclude_context: str | None = None, price_context: str = ""):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        excl = (
            f"\n【避免重複】昨日已涵蓋：\n{exclude_context}\n"
            if exclude_context else ""
        )
        ctx = f"\n【系統強制即時報價】\n{price_context}\n"

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
                {_IMPACT_TAG}
                （以上 IMPACT 標籤為主編整合用的內部格式，不得原文印入最終戰報，主編須轉化為自然語言）
                禁止捏造來源。
            """),
            expected_output="3 則幣圈新聞結構化初稿。",
            agent=self.crypto_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — GPT】
                {ctx}

                {_DATA_RULES}
                {_QUOTE_RULE}

                === Fact-Check ===
                以【系統強制即時報價】核對 DXY/VIX/IBIT/BTC。

                === market_regime（risk_on/risk_off/neutral）===
                列出 6 項信號：VIX（含期限結構）、IBIT、資金費率、爆倉、Fear & Greed、BTC RSI(14)，並給最終判定。

                === 新聞辯論（3 則）===
                每則 2~3 句反向觀點。
            """),
            expected_output="風險審計與 regime 判定。",
            agent=self.risk_critic,
            context=[crypto_task],
        )

        final_report_task = Task(
            description=dedent(f"""
                【加密市場戰報排版 — Gemini 主編】
                {_QUOTE_RULE}
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {ctx}

                === 交易建議（Crypto）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                對每筆交易建議必須呼叫 multi_timeframe_tool('標的')，輸出 D/4H/1H：
                - 三時框同向 → 信心 ⭐️⭐️⭐️⭐️
                - 兩時框同向且一個中性 → 信心 ⭐️⭐️⭐️
                - 方向分歧 → 信心降為 ⭐️⭐️ 或 ⭐️
                {_TRADE_RULE}

                {_FINAL_TEMPLATE}
                === 排版結構（嚴格依序，禁止調換區塊順序）===
                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on / risk_off / neutral
                ══════ <b>📊 加密市場</b> ══════
                區塊①【數據儀表板】：
                - 三組：宏觀（DXY/VIX/VIX期限結構/IBIT/近期宏觀事件）、技術（BTC RSI/MA20MA50/Fear&Greed）、籌碼（資金費率/多空比/OI/爆倉/P-C/MaxPain/ETF流向）
                - 嚴格套用【上方儀表板格式】
                區塊②【核心新聞】：3 則，套用【上方新聞格式】，將 IMPACT 資訊融入投資解讀（禁止原文印出標籤），每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用【上方推文格式】；若無推文數據則跳過此區塊
                ────────────
                區塊③【市場呢喃與傳聞】：2~3 條，套用【上方呢喃格式】，不可重複新聞事件
                區塊④【資金流向與精準操作 (Crypto)】：1 單邊 + 1 配對，套用【上方交易格式】

                {_TRADE_JSON_RULE}
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
            goal="對 AI 新聞做反向辯論與風險審計。",
            backstory="對估值泡沫與敘事偏差高度敏感。",
            llm=grok,
            allow_delegation=False,
            tools=[],
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
                · newsapi_tool('AI NVIDIA data center GPU Microsoft')（Bloomberg / Reuters AI 報導）
                · gnews_tool('artificial intelligence GPU infrastructure')（多語言補充）
                · market_search_tool('AI data center GPU NVIDIA infrastructure {year}')
                · market_search_tool('data center power supply nuclear energy AI {year}')
                · market_search_tool('AI model releases enterprise adoption {year}')
                · rumor_scanner_tool('AI infrastructure supply chain risk')
                · x_search_tool('NVIDIA AI GPU data center OpenAI Anthropic Microsoft')（取得 AI 板塊 X/Twitter 即時推文）

                產出 AI 新聞 3 則，每則格式：
                {_NEWS_FMT}
                🤖 GPT 研判：2~3 句，必須點名受影響美股或 ETF
                {_IMPACT_TAG}
                （以上 IMPACT 標籤為主編整合用的內部格式，不得原文印入最終戰報，主編須轉化為自然語言）
            """),
            expected_output="3 則 AI 新聞結構化初稿。",
            agent=self.ai_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Grok】
                {_QUOTE_RULE}
                {ctx}
                對 3 則新聞逐條提出反向觀點（每則 2~3 句）。
            """),
            expected_output="3 則 AI 新聞辯論觀點。",
            agent=self.risk_critic,
            context=[ai_task],
        )

        final_report_task = Task(
            description=dedent(f"""
                【AI 市場戰報排版 — Gemini 主編】
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_QUOTE_RULE}
                {ctx}

                === 交易建議（US Equities）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                對每筆交易建議必須呼叫 multi_timeframe_tool('標的')，輸出 D/4H/1H：
                - 三時框同向 → 信心 ⭐️⭐️⭐️⭐️
                - 兩時框同向且一個中性 → 信心 ⭐️⭐️⭐️
                - 方向分歧 → 信心降為 ⭐️⭐️ 或 ⭐️
                {_TRADE_RULE}

                {_FINAL_TEMPLATE}
                === 排版結構（嚴格依序，禁止調換區塊順序）===

                ══════ <b>🤖 AI 市場</b> ══════
                區塊①【AI 數據儀表板】：列 OpenRouter Top5 熱度（缺資料寫 <code>N/A</code>），嚴格套用【上方儀表板格式】
                區塊②【AI 產業新聞】：3 則（基建/投資案/最新模型各1），套用【上方新聞格式】，將 IMPACT 資訊融入投資解讀（禁止原文印出標籤），每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用【上方推文格式】；若無推文數據則跳過此區塊
                ────────────
                區塊③【產業鏈呢喃】：2~3 條，套用【上方呢喃格式】，不可重複新聞事件
                區塊④【AI 產業鏈精準操作 (US Equities)】：2 支，套用【上方交易格式】

                {_TRADE_JSON_RULE}
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


# 向後相容別名（保留給直接使用舊名稱的程式碼參考）
class QSiliconResearchCrew:
    """向後相容別名：保留舊入口。"""

    def run(self, exclude_context: str | None = None, price_context: str = ""):
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(
                lambda: str(CryptoResearchCrew().run(exclude_context=exclude_context, price_context=price_context))
            )
            future_ai = executor.submit(
                lambda: str(AIResearchCrew().run(exclude_context=exclude_context, price_context=price_context))
            )
            crypto_report = future_crypto.result()
            ai_report = future_ai.result()
        return f"{crypto_report}\n\n{ai_report}"

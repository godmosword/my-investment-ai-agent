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
    market_search_tool,
    ml_quant_tool,
    multi_timeframe_tool,
    onchain_metrics_tool,
    rumor_scanner_tool,
    sentiment_score_tool,
    x_search_tool,
)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

MODEL_GROK = "xai/grok-4-1-fast-reasoning"
MODEL_GPT = "openai/gpt-5.3-chat-latest"
MODEL_CLAUDE = "openrouter/anthropic/claude-sonnet-4.6"
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

_TELEGRAM_FMT = dedent("""\
    Telegram HTML：只允許 <b> <i> <u> <s> <code> <blockquote> <a href>
    禁止 Markdown 與其他 HTML；大區塊前加分隔線 ────────────
    儀表板每項獨立一行且數值包 <code>；摘要用 <blockquote>；缺資料寫 <code>N/A</code>""")

_EDITOR_RULE = "【主編共識】每則新聞給 1 句最終操作判斷，必須點名具體標的。"
_DATA_RULES = "【新鮮度】新聞必須在 48h 內；超時跳過重搜。"

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
    · 進場：<code>$XXX.XX</code>｜目標：<code>$XXX.XX (+Y%)</code>｜停損：<code>$XXX.XX (-Z%)</code>
    · 敘事邏輯：1 句，引用本日新聞
    【致命警告】「進場」、「目標」、「停損」的數值【必須、絕對要】被 <code> 標籤包覆！否則系統後端資料庫將全面崩潰！嚴禁輸出純文字！""")

# tracker.py 解析用的機器可讀區塊格式（Telegram 不渲染，純文字標記）
# 欄位：asset=代號大寫不含$, entry/target/stop=純數字, target_pct/stop_pct=百分比數字,
#        confidence=1~4, category=CRYPTO|EQUITY, current_price=現價數字
_TRADE_JSON_RULE = dedent("""\
    === 機器可讀建議（Telegram 不顯示，tracker.py 解析用）===
    在報告最後一行之後，另起一行輸出以下格式（禁止省略、禁止破壞 JSON 結構）：
    [QSREC_START]
    [{"asset":"代號大寫","direction":"LONG或SHORT","current_price":現價數字,"entry":進場數字,"target":目標數字,"stop":停損數字,"target_pct":目標漲幅數字,"stop_pct":停損幅度數字,"confidence":信心1到4,"category":"CRYPTO或EQUITY","narrative":"敘事邏輯原文"}]
    [QSREC_END]
    JSON 規則：數字欄位禁止加引號、asset 不含 $、禁止多行縮排、所有建議合併進同一個陣列。""")


def _make_llms(*names: str):
    """建立並回傳指定的 LLM 實例。"""
    factories = {
        "grok": lambda: LLM(model=MODEL_GROK, api_key=os.getenv("XAI_API_KEY"), max_retries=3, timeout=120),
        "gpt": lambda: LLM(model=MODEL_GPT, api_key=os.getenv("OPENAI_API_KEY"), max_retries=3, timeout=120),
        "claude": lambda: LLM(model=MODEL_CLAUDE, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3, timeout=120),
        "gemini": lambda: LLM(model=MODEL_GEMINI, api_key=os.getenv("GEMINI_API_KEY"), max_retries=5, timeout=180),
    }
    return tuple(factories[n]() for n in names)


class CryptoResearchCrew:
    def __init__(self):
        grok, claude, gemini = _make_llms("grok", "claude", "gemini")

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，產出 3 則高衝擊幣圈新聞。",
            backstory="冷靜量化研究員，專注流動性、槓桿與聰明錢行為。",
            llm=grok,
            tools=[market_search_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, fear_greed_tool, etf_flow_tool, econ_calendar_tool, x_search_tool, onchain_metrics_tool, sentiment_score_tool],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席幣圈風險審計員",
            goal="對幣圈新聞做反向辯論，判定 market_regime。",
            backstory="反身性風險審計者，負責挑錯與驗證。",
            llm=claude,
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
                · rumor_scanner_tool('BTC ETF flow OR crypto manipulation OR whale alert')
                · market_search_tool('Bitcoin market liquidity derivatives risk')
                · x_search_tool('bitcoin BTC crypto market ETF liquidation')（取得 X/Twitter 即時情緒推文，供 X 推文精選區塊使用）
                · onchain_metrics_tool()（P2 鏈上深度：SOPR / 交易所淨流向 / 活躍地址數 / NUPL）
                · sentiment_score_tool(news_and_tweets=<將上方新聞標題 + X 推文拼接後傳入>)（P2 社群情緒量化：-1 到 +1）

                === 幣圈新聞（3 則）===
                {_NEWS_FMT}
                研判：2~3 句，必須明確說明哪個標的受影響
                {_IMPACT_TAG}
                禁止捏造來源。
            """),
            expected_output="3 則幣圈新聞結構化初稿。",
            agent=self.crypto_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — Claude】
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

                === 排版結構（嚴格依序，禁止調換區塊順序）===
                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on / risk_off / neutral
                ══════ <b>📊 加密市場</b> ══════
                區塊①【數據儀表板】：
                - 三組：宏觀（DXY/VIX/VIX期限結構/IBIT/近期宏觀事件）、技術（BTC RSI/MA20MA50/Fear&Greed）、籌碼（資金費率/多空比/OI/爆倉/P-C/MaxPain/ETF流向）
                - 嚴格套用 {_DASHBOARD_FMT}
                區塊②【核心新聞】：3 則，套用 {_NEWS_FMT} + {_IMPACT_TAG}，每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用 {_TWEET_FMT}；若無推文數據則跳過此區塊
                ────────────
                區塊③【市場呢喃與傳聞】：2~3 條，套用 {_CHATTER_FMT}，不可重複新聞事件
                區塊④【資金流向與精準操作 (Crypto)】：1 單邊 + 1 配對，套用 {_TRADE_RULE}

                {_TRADE_JSON_RULE}
            """),
            expected_output="戰報上半部 Telegram HTML，依序包含：①數據儀表板 ②核心新聞×3 ②b X推文精選（有則列出） ③市場呢喃×2~3 ④精準操作×2，末尾附 [QSREC_START]…[QSREC_END] JSON。",
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
        gpt, claude, gemini = _make_llms("gpt", "claude", "gemini")

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="收集 AI 市場核心資訊並輸出 3 則可交易新聞。",
            backstory="科技產業鏈研究員，聚焦可驗證催化。",
            llm=gpt,
            tools=[market_search_tool, ai_momentum_tool, rumor_scanner_tool, x_search_tool],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席 AI 市場辯論員",
            goal="對 AI 新聞做反向辯論與風險審計。",
            backstory="對估值泡沫與敘事偏差高度敏感。",
            llm=claude,
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
                · market_search_tool('AI data center GPU NVIDIA infrastructure {year}')
                · market_search_tool('data center power supply nuclear energy AI {year}')
                · market_search_tool('AI model releases enterprise adoption {year}')
                · rumor_scanner_tool('AI infrastructure supply chain risk')
                · x_search_tool('NVIDIA AI GPU data center OpenAI Anthropic Microsoft')（取得 AI 板塊 X/Twitter 即時推文）

                產出 AI 新聞 3 則，每則格式：
                {_NEWS_FMT}
                🤖 GPT 研判：2~3 句，必須點名受影響美股或 ETF
                {_IMPACT_TAG}
            """),
            expected_output="3 則 AI 新聞結構化初稿。",
            agent=self.ai_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Claude】
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

                === 排版結構（嚴格依序，禁止調換區塊順序）===

                ══════ <b>🤖 AI 市場</b> ══════
                區塊①【AI 數據儀表板】：列 OpenRouter Top5 熱度（缺資料寫 <code>N/A</code>），嚴格套用 {_DASHBOARD_FMT}
                區塊②【AI 產業新聞】：3 則（基建/投資案/最新模型各1），套用 {_NEWS_FMT} + {_IMPACT_TAG}，每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用 {_TWEET_FMT}；若無推文數據則跳過此區塊
                ────────────
                區塊③【產業鏈呢喃】：2~3 條，套用 {_CHATTER_FMT}，不可重複新聞事件
                區塊④【AI 產業鏈精準操作 (US Equities)】：2 支，套用 {_TRADE_RULE}

                {_TRADE_JSON_RULE}
            """),
            expected_output="戰報下半部 Telegram HTML，依序包含：①AI 數據儀表板 ②AI 產業新聞×3 ②b X推文精選（有則列出） ③產業鏈呢喃×2~3 ④精準操作×2，末尾附 [QSREC_START]…[QSREC_END] JSON。",
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

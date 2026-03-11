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

_EDITOR_RULE = dedent("""\
    【主編共識與排版紅線】
    1. 每則新聞給 1 句最終操作判斷，必須點名具體標的。
    2. 【嚴禁外洩程式碼】絕對不可在戰報中印出 `multi_timeframe_tool` 等任何 Python 函數名稱，請轉化為自然語言（例：多時框狀態：D(多)/4H(空)/1H(空)）。
    3. 【嚴禁外洩內部標籤】徹底消除「[IMPACT: 負面]」、「🎯 IMPACT」、「📍 受影響資產」、「📈 做多機會」、「📉 做空風險」、「⏱️ 時效」等原始標籤，必須融入「投資解讀」自然段落。
    4. 【結尾資料載荷不可省略】輸出末尾必須保留 [QSREC_START] ... [QSREC_END] 區塊，且內含合法 JSON 陣列。""")
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
    若關鍵欄位 N/A 超過 3 項，必須在該區塊加註：<b>低置信度</b>，
    並補 1 行「資料缺失原因 + 替代指標」（例如：OI 缺失改看 funding/多空比/現貨成交額）。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質與可信度分級（A/B/C 或 0~100）、
    並標註是否已被主流媒體二次驗證（是/否），輸出 2~3 條""")

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
    · 風控：<code>R:R = 1:X</code>｜最大回撤風險：<code>-Z%</code>
    · 敘事邏輯：1 句，引用本日新聞與至少 1 個當日量化數據
    【系統強制覆寫】你輸出的文字【必須完全包含】 `<`、`c`、`o`、`d`、`e`、`>` 這些字元，絕對不允許轉換成 Markdown 格式，否則資料庫將立刻崩潰！""")

_RISK_MODE_RULE = dedent("""\
    【市場模式聯動風控】
    - 若今日市場模式為 risk_off：所有交易建議信心水準上限降一級（最高只能 ⭐️⭐️⭐️），並在敘事中明確標註「減倉/輕倉」。
    - 若訊號互相衝突（例如 RSI 中性 + VIX 倒掛 + 資金費率回穩），必須新增 1 行「訊號衝突摘要：...」。""")

_PAIR_TRADE_RULE = dedent("""\
    【配對交易單位一致性】
    - 若輸出配對交易（如 $BTC / $SOL），必須明確標註「單位：BTC/SOL 比值」或「單位：價差」。
    - 現價/進場/目標/停損必須使用同一單位，禁止混用單幣現價與比值。""")

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
    JSON 規則：數字欄位禁止加引號、asset 不含 $、允許多行縮排（但必須為合法 JSON）、所有建議合併進同一個陣列。""")

_FINAL_TEMPLATE_CRYPTO = dedent("""\
    === 【最高排版指令】你最終輸出的戰報必須 100% 模仿以下範例結構（包含獨立換行、<code>標籤與結尾 JSON），不准改變排版樣式！===

    <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · YYYY-MM-DD</i>
    ────────────
    【今日市場模式】neutral
    訊號衝突摘要：RSI 中性 + VIX 倒掛 + 資金費率回穩，短線方向不明，採輕倉。

    ══════ <b>📊 加密市場</b> ══════
    區塊①【數據儀表板】：(嚴格要求：每項指標必須獨立換行！)
    · <b>DXY</b> <code><示例值></code>
    · <b>VIX</b> <code><示例值></code>
    · <b>VIX期限結構</b> <code><示例值></code>
    · <b>IBIT</b> <code><示例值></code>
    · <b>BTC RSI(14)</b> <code><示例值></code>
    · <b>BTC MA20</b> <code><示例值></code>
    · <b>BTC MA50</b> <code><示例值></code>
    · <b>ETF流向</b> <code>N/A</code>
    · <b>OI</b> <code>N/A</code>
    · <b>爆倉</b> <code>N/A</code>
    · <b>P-C</b> <code>N/A</code>
    <b>低置信度</b>：資料缺失原因：部分衍生品 API 回傳延遲；替代指標：funding、多空比、現貨成交額。

    ...(中間的新聞與呢喃區塊省略，請照常輸出，新聞時間固定 [MM/DD HH:MM UTC+8]，投資解讀至少含一個當日數據)...

    區塊④【資金流向與精準操作 (Crypto)】：
    · <b>$BTC (LONG)</b>｜現價：$<示例值>｜信心水準：⭐️⭐️
    · 進場：<code>$<示例值></code>｜目標：<code>$<示例值> (+X.X%)</code>｜停損：<code>$<示例值> (-X.X%)</code>
    · 風控：<code>R:R = 1:X.X</code>｜最大回撤風險：<code>-X.X%</code>
    · 敘事邏輯：多時框狀態 D(中性)/4H(中性)/1H(多)，引用當日數據（例如 funding/RSI/MA）。

    · <b>$BTC / $SOL (配對交易)</b>｜現價：$<示例值> / $<示例值>｜信心水準：⭐️⭐️
    · 單位：BTC/SOL 比值
    · 進場：<code><比值示例值></code>｜目標：<code><比值示例值> (+X.X%)</code>｜停損：<code><比值示例值> (-X.X%)</code>
    · 風控：<code>R:R = 1:X.X</code>｜最大回撤風險：<code>-X.X%</code>
    · 敘事邏輯：必須與比值單位一致，禁止混用單幣價格與比值。

    [QSREC_START]
    [
      {"asset": "BTC", "direction": "LONG", "current_price": 70578, "entry": 69800, "target": 72800, "stop": 67800, "confidence": 2, "category": "CRYPTO", "narrative": "多時框狀態 D(中性)/4H(中性)/1H(多)，funding 轉負支持反彈。"},
      {"asset": "BTC", "direction": "LONG", "current_price": 70578, "entry": 0.000121, "target": 0.000129, "stop": 0.000117, "confidence": 2, "category": "CRYPTO", "narrative": "配對單以 BTC/SOL 比值表示，單位一致。"}
    ]
    [QSREC_END]
    """)

_FINAL_TEMPLATE_AI = dedent("""\
    === 【最高排版指令】你最終輸出的 AI 戰報必須 100% 模仿以下範例結構（包含獨立換行、<code>標籤與結尾 JSON），不准改變排版樣式！===

    ══════ <b>🤖 AI 市場</b> ══════
    區塊①【AI 數據儀表板】：(嚴格要求：每項指標必須獨立換行！)
    · <b>OpenRouter Top1 熱度</b> <code><示例值></code>
    · <b>OpenRouter Top2 熱度</b> <code><示例值></code>
    · <b>OpenRouter Top3 熱度</b> <code><示例值></code>
    · <b>OpenRouter Top4 熱度</b> <code><示例值></code>
    · <b>OpenRouter Top5 熱度</b> <code><示例值></code>

    區塊②【AI 產業新聞】：
    〔新聞 1〕[MM/DD HH:MM UTC+8] <b>示例標題</b>（來源：TechCrunch｜性質：confirmed）
    <blockquote>摘要：1 句核心事實。</blockquote>
    投資解讀：至少含 1 個當日數據（例如 NVDA 現價、量能、估值或資金流變化）。
    💎主編共識：點名具體標的，並註明倉位控制。

    區塊③【產業鏈呢喃】：
    · 傳聞內容...（未確認｜來源：供應鏈訪談｜可信度：B｜主流媒體二次驗證：否）

    區塊④【AI 產業鏈精準操作 (US Equities)】：
    · <b>NVDA (LONG)</b>｜現價：$<示例值>｜信心水準：⭐️⭐️⭐️
    · 進場：<code>$<示例值></code>｜目標：<code>$<示例值> (+X.X%)</code>｜停損：<code>$<示例值> (-X.X%)</code>
    · 風控：<code>R:R = 1:X.X</code>｜最大回撤風險：<code>-X.X%</code>
    · 敘事邏輯：多時框狀態 D(多)/4H(多)/1H(中性)，並引用當日數據。

    [QSREC_START]
    [
      {"asset": "NVDA", "direction": "LONG", "current_price": 184.7, "entry": 184.0, "target": 198.0, "stop": 174.0, "confidence": 3, "category": "EQUITY", "narrative": "多時框共振偏多，且有當日量化數據支持。"}
    ]
    [QSREC_END]
    """)


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
        grok, gpt = _make_llms("grok", "gpt")

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
            llm=gpt,
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
                【加密市場戰報排版 — GPT 主編】
                {_QUOTE_RULE}
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_RISK_MODE_RULE}
                {_PAIR_TRADE_RULE}
                {ctx}

                === 交易建議（Crypto）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                對每筆交易建議必須呼叫 multi_timeframe_tool('標的')，並以自然語言輸出多時框狀態 D/4H/1H（禁止印出函數名稱）：
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
                - 嚴格套用【上方儀表板格式】
                區塊②【核心新聞】：3 則，套用【上方新聞格式（內部標籤改為自然語言）】，每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用【上方推文格式】；若無推文數據則跳過此區塊
                ────────────
                區塊③【市場呢喃與傳聞】：2~3 條，套用【上方呢喃格式】，不可重複新聞事件
                區塊④【資金流向與精準操作 (Crypto)】：1 單邊 + 1 配對，套用【上方交易格式】

                {_TRADE_JSON_RULE}

                {_FINAL_TEMPLATE_CRYPTO}
            """),
            expected_output="包含 HTML 戰報與結尾 JSON 陣列的完整字串。結尾必定包含 [QSREC_START] 與 [QSREC_END]。",
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
        gpt, grok = _make_llms("gpt", "grok")

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
            llm=gpt,
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
                【AI 市場戰報排版 — GPT 主編】
                {_EDITOR_RULE}
                {_TELEGRAM_FMT}
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_QUOTE_RULE}
                {_RISK_MODE_RULE}
                {_PAIR_TRADE_RULE}
                {ctx}

                === 交易建議（US Equities）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                對每筆交易建議必須呼叫 multi_timeframe_tool('標的')，並以自然語言輸出多時框狀態 D/4H/1H（禁止印出函數名稱）：
                - 三時框同向 → 信心 ⭐️⭐️⭐️⭐️
                - 兩時框同向且一個中性 → 信心 ⭐️⭐️⭐️
                - 方向分歧 → 信心降為 ⭐️⭐️ 或 ⭐️
                {_TRADE_RULE}

                === 排版結構（嚴格依序，禁止調換區塊順序）===

                ══════ <b>🤖 AI 市場</b> ══════
                區塊①【AI 數據儀表板】：列 OpenRouter Top5 熱度（缺資料寫 <code>N/A</code>），嚴格套用【上方儀表板格式】
                區塊②【AI 產業新聞】：3 則（基建/投資案/最新模型各1），套用【上方新聞格式（內部標籤改為自然語言）】，每則附 1 句💎主編共識
                ════ 🐦 X 即時情緒推文 ════
                區塊②b【X 推文精選】：套用【上方推文格式】；若無推文數據則跳過此區塊
                ────────────
                區塊③【產業鏈呢喃】：2~3 條，套用【上方呢喃格式】，不可重複新聞事件
                區塊④【AI 產業鏈精準操作 (US Equities)】：2 支，套用【上方交易格式】

                {_TRADE_JSON_RULE}

                {_FINAL_TEMPLATE_AI}
            """),
            expected_output="包含 HTML 戰報與結尾 JSON 陣列的完整字串。結尾必定包含 [QSREC_START] 與 [QSREC_END]。",
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

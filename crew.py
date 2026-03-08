import os
from datetime import datetime, timezone, timedelta
from textwrap import dedent
from crewai import Agent, Task, Crew, Process, LLM

# 除錯：CREW_VERBOSE=1 時 Agent 會輸出 tool 呼叫與步驟，方便排查
_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

# LLM 模型常數（便於統一升級版本）
MODEL_GROK   = "xai/grok-4-1-fast-reasoning"
MODEL_GPT    = "openai/gpt-5.3-chat-latest"
MODEL_CLAUDE = "openrouter/anthropic/claude-sonnet-4.6"
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

from tools import (
    ai_momentum_tool,
    macro_liquidity_tool,
    market_search_tool,
    mvrv_tool,
    x_search_tool,
    coinglass_data_tool,
    cryptoquant_tool,
    ml_quant_tool,
    rumor_scanner_tool,
    cryptopanic_tool,
    yfinance_macro_tool,
    yfinance_tool,
    yfinance_multi_tool,
)

# ── Shared prompt fragments ────────────────────────────────
_TELEGRAM_FMT = dedent("""\
    ════ Telegram HTML ════
    允許：<b> <i> <u> <s> <code> <blockquote> <a href>｜禁止：Markdown、<h1~h2> <div> <p> <br> <hr> <span> <table>
    分隔線 ────────────（每大區塊前加）｜標題 <b>【】</b>｜數值 <code>｜推文 <blockquote>
    每則新聞完整輸出（標題/來源/摘要/投資解讀/💎 在一起），禁止中間插分隔線""")

_EDITOR_RULE = dedent("""\
    【主編共識】Grok/GPT 與 Claude 辯論濃縮為 💎 <b>主編共識</b>（1句操作判斷，必須點名具體標的）。
    正文僅保留 💎 主編共識，禁止呈現個別 Agent 觀點。""")

_NEWS_FMT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM UTC+8] 新聞標題（時間不明確標 [近24h] 或 [近48h]）
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1 句，聚焦事件本身）""")

_IMPACT_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker，如 BTC/ETH/AMD/NVDA/IBIT，可多個]
    📈 做多機會：[標的] — [1句受益原因與觸發條件]
    📉 做空風險：[標的] — [1句受害原因與風險情境]
    ⏱️ 時效：短期(1-7天) / 中期(2-4週) / 長期(1季+)
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）""")

_TWEET_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker]
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多
    ⏱️ 時效：短期 / 中期 / 長期""")

_DATA_RULES = dedent("""\
    ⚠️ [DATA_MISSING:xxx] → 報告寫「⚠️ [xxx] 數據暫缺」，禁止 N/A 或省略。
    【新鮮度】新聞限 48h 內，超時跳過重搜，禁用 3 天前舊聞。""")

_DASH_FALLBACK = dedent("""\
    【儀表板缺失處理】
    · "Tool Failed"/"失效" → 寫「[指標] 暫缺」，禁複製錯誤訊息
    · VIX/IBIT 失效 → yfinance_tool('^VIX')/yfinance_tool('IBIT') 重試
    · "[Tavily備援-MVRV]" → 從文字解讀 Z-Score 數值
    · ML "建置中" → 寫 ML 建置中（XX/30天）｜部位建議 暫不適用
    · 禁止出現 "無數據"/"N/A"/"Failed" 字樣""")

_TRADE_PRICE_RULE = dedent("""\
    【交易價格規則（嚴格執行）】
    ① 使用任務開頭【Python 強制市場快照】中已提供的現價，Python 預先抓取，絕對準確
    ② 禁止自行推測、估算或捏造任何價格數字；禁止 "N/A"/"API 取價異常"/"當前價位"/"市場價" 等模糊字樣
    ③ 若快照中無需要的標的，才可呼叫 yfinance_tool('SYMBOL') 作為最後手段，並在報告中標注「即時補查」
    ④ 進場 = 現價 ± ≤0.5% 滑點，目標 = 現價×(1+Y%)，停損 = 現價×(1-Z%)
    ⑤ 格式：現價 <code>$XXX.XX</code>，進場 <code>$XXX.XX</code>，目標 <code>$XXX.XX (+Y%)</code>，停損 <code>$XXX.XX (-Z%)</code>""")


def _make_llms(*names: str):
    """建立並回傳指定的 LLM 實例。names: 'grok','gpt','claude','gemini'"""
    factories = {
        "grok": lambda: LLM(model=MODEL_GROK, api_key=os.getenv("XAI_API_KEY"), max_retries=3, timeout=120),
        "gpt": lambda: LLM(model=MODEL_GPT, api_key=os.getenv("OPENAI_API_KEY"), max_retries=3, timeout=120),
        "claude": lambda: LLM(model=MODEL_CLAUDE, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3, timeout=120),
        "gemini": lambda: LLM(model=MODEL_GEMINI, api_key=os.getenv("GEMINI_API_KEY"), max_retries=5, timeout=180),
    }
    return tuple(factories[n]() for n in names)


class CryptoResearchCrew:
    """加密市場專屬雙引擎：Grok 情報 → Claude 幣圈審計/Market Regime → Gemini 上半部戰報。"""

    def __init__(self):
        grok_latest, claude_latest, gemini_latest = _make_llms("grok", "claude", "gemini")

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，挑選 3 則最具市場衝擊力的幣圈新聞與 5 則 X 推文，提供 Grok 視角的利多與利空分析。",
            backstory="極度冷血的量化追蹤者，專注聰明錢與散戶情緒背離分析。在散戶最狂熱時尋找巨鯨倒貨的蛛絲馬跡，在市場最恐慌時尋找強者積累的痕跡。",
            llm=grok_latest,
            tools=[market_search_tool, x_search_tool, macro_liquidity_tool, mvrv_tool,
                   coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, yfinance_macro_tool],
            verbose=_VERBOSE
        )

        self.risk_critic = Agent(
            role="首席幣圈風險審計員",
            goal="針對幣圈新聞與推文提供 Claude 的反向辯論觀點，完成 VIX/IBIT 宏觀 Risk Off 訊號審計，並判定今日 market_regime。",
            backstory="索羅斯反射性理論信徒。深知假新聞能創造真實踩踏，真正轉折在共識反面。",
            llm=claude_latest,
            allow_delegation=False,
            tools=[yfinance_multi_tool],
            verbose=_VERBOSE
        )

        self.quant_strategist = Agent(
            role="機構策略主編（加密市場）",
            goal="整合加密市場研究成果，為每則幣圈新聞與推文下達 Gemini 共識結論，排版輸出戰報上半部。",
            backstory="負責最終整合與排版的機構主編，確保每一個判斷都有依據，每一個觀點都有對立面的檢驗。",
            llm=gemini_latest,
            tools=[coinglass_data_tool, cryptoquant_tool, ml_quant_tool, yfinance_tool],
            verbose=_VERBOSE
        )

    def run(self, exclude_context: str | None = None, market_snapshot: str | None = None):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )
        _snapshot = market_snapshot or "（市場快照未提供 — 請呼叫 yfinance_tool 取得報價）"

        # ══════════════════════════════════════════════════════════════
        # Task 1：加密市場情報（Grok）
        # ══════════════════════════════════════════════════════════════
        crypto_task = Task(
            description=dedent(f"""
                【加密市場情報收集 — Grok】
                {_snapshot}

                {_DATA_RULES}
                {_excl}
                === 數據收集（全部必須執行）===
                ① macro_liquidity_tool×2：DXY 與 M2
                ② mvrv_tool('latest')：BTC MVRV Z-Score
                ③ coinglass_data_tool×3：funding_rate / liquidations / long_short_ratio
                ④ yfinance_macro_tool('vix')：VIX 指數
                ⑤ yfinance_macro_tool('etf_flow')：SPY/QQQ 成交額 proxy
                ⑥ cryptopanic_tool('bitcoin')：幣圈原生快訊
                ⑦ rumor_scanner_tool：'BTC ETF flow OR crypto manipulation OR whale alert'
                ⑧ x_search_tool：'BTC whale OR bitcoin ETF OR crypto rumor'

                === 幣圈新聞（3 則）===
                優先：ETF 資金流、槓桿清算、鏈上流向、做市商操作。至少一則來自 CryptoPanic。
                每則格式：
                {_NEWS_FMT}
                🛸 Grok 研判：2~3 句，必須明確說明「哪個標的」受影響及「為何」
                {_IMPACT_TAG}

                === 背離與衍生品 ===
                · FOMO + MVRV>7 + 巨鯨轉帳 →「聰明錢出貨警告」
                · 全網悲觀 + MVRV<0 + 巨鯨平靜 →「散戶盲目恐慌」
                · 資金費率極正 + 多頭過熱 →「多頭清算風險」
                · 巨額多頭爆倉 →「流動性洗盤，左側建倉條件」

                === 幣圈推文（5 則）===
                每則：
                〔推文 N〕[MM/DD] <blockquote>推文原文</blockquote>
                簡述：（1句）
                🛸 Grok 研判：指出具體受益/受害幣種 + 1句理由
                {_TWEET_TAG}

                禁止捏造來源或未出現於搜尋結果中的事實。
            """),
            expected_output="加密市場數據 + 3 則幣圈新聞 + 5 則推文的結構化初稿。",
            agent=self.crypto_researcher
        )

        # ══════════════════════════════════════════════════════════════
        # Task 2：幣圈辯論與宏觀 Risk Off 審計（Claude）
        # ══════════════════════════════════════════════════════════════
        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — Claude】
                {_snapshot}

                {_DATA_RULES}

                === Fact-Check ===
                檢視所有數據（DXY/M2/MVRV/資金費率/爆倉/多空比/VIX/IBIT/ETF flow）。
                數據滯後 >12h 或極端異常 → 標記「數據失真警告：[指標]」。

                === Risk Off 訊號 ===
                直接使用上方【Python 強制市場快照】中的 VIX 與 IBIT 數值，無須再呼叫 yfinance_multi_tool。
                VIX 暴漲 + IBIT 下跌 → 「Risk Off 信號」；反之 → 風險偏好未退潮。

                === 幣圈新聞辯論（3 則）===
                每則：🛡️ Claude（幣圈新聞 N）：2~3 句辯論觀點。

                === 幣圈推文辯論（5 則）===
                每則：🛡️ Claude（幣圈推文 N）：1 句反向/補充觀點。

                === market_regime（risk_on / risk_off / neutral 三選一）===
                必須量化判定：列出 VIX 數值、IBIT 日漲跌、BTC 資金費率、MVRV Z-Score 各自的信號方向。
                綜合 4 項信號給出最終判定，並說明主要驅動因子（各一句話）：
                · 因子 1：[VIX 信號]
                · 因子 2：[IBIT/ETF 信號]
                · 因子 3：[鏈上/衍生品信號（MVRV/資金費率/爆倉）]
                判定規則：3/4 信號 risk_off → risk_off；3/4 risk_on → risk_on；其餘 → neutral
                · FUD + ETF 巨大淨流出 → 「情緒感染流動性」高風險
                · 全網恐慌 + 巨鯨平靜 + MVRV<3 → 「黃金坑/洗盤」
                · 散戶過度槓桿做多 → 即使無 FUD 也判定 risk_off
            """),
            expected_output="Fact-Check 備忘 + VIX/IBIT 判定 + 3 新聞 5 推文辯論 + market_regime。",
            agent=self.risk_critic,
            context=[crypto_task]
        )

        # ══════════════════════════════════════════════════════════════
        # Task 3：加密市場戰報上半部（Gemini 主編）
        # ══════════════════════════════════════════════════════════════
        final_report_task = Task(
            description=dedent(f"""
                【加密市場戰報排版 — Gemini 主編】
                {_snapshot}

                {_DATA_RULES}
                {_DASH_FALLBACK}

                排版前數據獲取：coinglass_data_tool('open_interest')、cryptoquant_tool('inflow'/'outflow')、ml_quant_tool。
                VIX 與 IBIT 現價請直接使用上方【Python 強制市場快照】，無需重新呼叫 yfinance_tool。
                含 [Tavily 備援] 直接萃取數值。

                {_EDITOR_RULE}
                {_TELEGRAM_FMT}

                === 投資標的 ===
                在【資金流向與精準操作 (Crypto)】提供 1 單邊標的（非 BTC）+ 1 配對交易。
                {_TRADE_PRICE_RULE}
                加密貨幣 symbol 必須加 '-USD'（如 SOL-USD, ETH-USD）。

                === 排版結構（嚴格依序）===
                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on/risk_off/neutral + 3 驅動因子
                ══════ <b>📊 加密市場</b> ══════
                【加密市場數據儀表板】宏觀(M2/DXY/VIX) + 量化模型(ML權重/部位建議) + 幣圈指標(MVRV/OI/IBIT/資金費率/爆倉/多空比/交易所淨流入)
                【幣圈新聞】3 則，每則嚴格按格式：
                  標題/來源/摘要
                  📍 受影響資產：[具體幣種 Ticker]
                  📈 做多機會：[幣種] — [原因]
                  📉 做空風險：[幣種] — [原因]
                  ⏱️ 時效：短期/中期/長期
                  🎯 IMPACT：[五選一]
                  💎 <b>主編共識</b>：[1句最終操作判斷，必須點名具體標的]
                【幣圈推文討論】5 則，每則：
                  <blockquote>原文</blockquote>
                  簡述（1句）｜📍 受影響資產：[Ticker]｜⏱️ 時效｜🎯 IMPACT
                  💎 <b>主編共識</b>：[1句操作判斷]
                【資金流向與精準操作 (Crypto)】1 單邊 + 1 配對（現價/信心/資金佔比/進場/目標/停損 %/敘事）

                禁止 Markdown 與 HORIZON 標籤。
            """),
            expected_output="戰報上半部 Telegram HTML 格式完整輸出。",
            agent=self.quant_strategist,
            context=[crypto_task, review_task]
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, review_task, final_report_task],
            process=Process.sequential
        )
        return crew.kickoff()


class AIResearchCrew:
    """AI 市場專屬雙引擎：GPT 情報 → Claude AI 毒舌審計 → Gemini 下半部戰報。"""

    def __init__(self):
        gpt_latest, claude_latest, gemini_latest = _make_llms("gpt", "claude", "gemini")

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="分三個部分（AI 基建現況、AI 投資案、最新 AI 模型）各找 3 則新聞，另搜尋 5 則聚焦 AI 新應用與 MCP 發展的推文，提供 GPT 視角的利多與利空分析。",
            backstory="華爾街科技股做空機構分析師，緊盯 AI 基礎設施的經濟效益與資本支出疲勞的早期信號。對每一波技術熱潮都保持健康的懷疑，但不放過真正的突破性進展。",
            llm=gpt_latest,
            tools=[market_search_tool, x_search_tool, ai_momentum_tool, rumor_scanner_tool],
            verbose=_VERBOSE
        )

        self.risk_critic = Agent(
            role="首席 AI 市場辯論員",
            goal="針對 AI 的 9 則新聞與 5 則推文提供 Claude 的毒舌反向辯論觀點，完成 AI 市場的風險審計。",
            backstory="索羅斯反射性理論信徒。深知 AI 炒作週期本質，善於在共識反面尋找機會或風險。",
            llm=claude_latest,
            allow_delegation=False,
            tools=[],
            verbose=_VERBOSE
        )

        self.quant_strategist = Agent(
            role="機構策略主編（AI 市場）",
            goal="整合 AI 市場研究成果，為每則 AI 新聞與推文下達 Gemini 共識結論，排版輸出戰報下半部。",
            backstory="負責最終整合與排版的機構主編，確保每一個判斷都有依據，每一個觀點都有對立面的檢驗。",
            llm=gemini_latest,
            tools=[yfinance_tool],
            verbose=_VERBOSE
        )

    def run(self, exclude_context: str | None = None, market_snapshot: str | None = None):
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )
        _snapshot = market_snapshot or "（市場快照未提供 — 請呼叫 yfinance_tool 取得報價）"
        _YEAR_ = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m")

        # ══════════════════════════════════════════════════════════════
        # Task 1：AI 市場情報（GPT）
        # ══════════════════════════════════════════════════════════════
        ai_task = Task(
            description=dedent(f"""
                【AI 市場情報收集 — GPT】
                {_snapshot}

                {_DATA_RULES}
                {_excl}
                === 數據 ===
                呼叫 ai_momentum_tool('openrouter_rankings') 取得模型熱度排名。

                === 第一部分：AI 基建現況（3 則）===
                聚焦：資料中心/GPU/TPU/算力/電力/散熱/能源基建。
                搜尋（各至少一次）：
                · market_search_tool: 'AI data center GPU NVIDIA infrastructure {_YEAR_}'
                · market_search_tool: 'data center power supply nuclear energy AI {_YEAR_}'
                · market_search_tool: 'AI data center cooling thermal technology {_YEAR_}'
                · rumor_scanner_tool: 'data center materials semiconductor supply chain'
                3 則中至少一則涵蓋電力/散熱/材料/能源基建。
                每則格式：
                {_NEWS_FMT}
                🤖 GPT 研判：2~3 句，必須明確說明「哪個美股標的或 ETF」受影響及投資含義
                {_IMPACT_TAG}

                === 第二部分：AI 投資案（3 則）===
                聚焦：AI 新創融資、科技收購、風投、IPO。格式同上。

                === 第三部分：最新 AI 模型（3 則）===
                聚焦：LLM/多模態/Agent 框架新發布，摘要含模型特色。格式同上。

                === AI 推文（5 則）===
                x_search_tool: 'MCP Model Context Protocol OR AI agent app {_YEAR_}'
                聚焦：AI 應用落地、MCP 發展、Agent 框架。
                每則：
                〔推文 N〕[MM/DD] <blockquote>推文原文</blockquote>
                簡述：（1句）
                🤖 GPT 研判：指出具體受益美股（如 MSFT/PLTR/AI/SMCI）+ 1句理由
                {_TWEET_TAG}

                · 訓練成本攀升但 Big Tech capex 增速放緩 → 標示「算力通縮研發通膨矛盾」
                禁止捏造事實。
            """),
            expected_output="OpenRouter 排名 + 三部分各 3 則 AI 新聞 + 5 則推文結構化初稿。",
            agent=self.ai_researcher
        )

        # ══════════════════════════════════════════════════════════════
        # Task 2：AI 市場辯論審計（Claude）
        # ══════════════════════════════════════════════════════════════
        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Claude】
                {_DATA_RULES}

                === AI 基建辯論（3 則）===
                每則：🛡️ Claude（AI基建 N）：2~3 句辯論。

                === AI 投資案辯論（3 則）===
                每則：🛡️ Claude（AI投資 N）：2~3 句辯論。

                === 最新 AI 模型辯論（3 則）===
                每則：🛡️ Claude（AI模型 N）：2~3 句辯論。

                === AI 推文辯論（5 則）===
                每則：🛡️ Claude（AI推文 N）：1 句反向/補充觀點。
            """),
            expected_output="9 新聞 + 5 推文 Claude 辯論觀點。",
            agent=self.risk_critic,
            context=[ai_task]
        )

        # ══════════════════════════════════════════════════════════════
        # Task 3：AI 市場戰報下半部（Gemini 主編）
        # ══════════════════════════════════════════════════════════════
        final_report_task = Task(
            description=dedent(f"""
                【AI 市場戰報排版 — Gemini 主編】
                {_snapshot}

                {_DATA_RULES}

                {_EDITOR_RULE}
                {_TELEGRAM_FMT}

                === 投資標的 ===
                在【AI 產業鏈精準操作 (US Equities)】提供 2 個美股標的。
                {_TRADE_PRICE_RULE}

                === 排版結構 ===
                ══════ <b>🤖 AI 市場</b> ══════
                【AI 數據參考】OpenRouter 模型熱度排名
                【AI 基建現況】3 則，每則嚴格按格式：
                  標題/來源/摘要
                  📍 受影響資產：[具體美股如 NVDA/AMD/VST/CEG/GEV]
                  📈 做多機會：[標的] — [原因]
                  📉 做空風險：[標的] — [原因]
                  ⏱️ 時效：短期/中期/長期
                  🎯 IMPACT：[五選一]
                  💎 <b>主編共識</b>：[1句最終判斷，點名可操作標的]
                【AI 投資案】3 則（同上格式）
                【最新 AI 模型】3 則（同上格式，摘要含模型特色與對算力/應用的影響）
                【AI 推文討論】5 則，每則：
                  <blockquote>原文</blockquote>
                  簡述（1句）｜📍 受影響資產：[Ticker]｜⏱️ 時效｜🎯 IMPACT
                  💎 <b>主編共識</b>：[1句操作判斷]
                【AI 產業鏈精準操作 (US Equities)】2 支（現價/信心/資金佔比/進場/目標/停損 %/敘事）

                禁止 Markdown 與 HORIZON 標籤。
            """),
            expected_output="戰報下半部 Telegram HTML 格式完整輸出。",
            agent=self.quant_strategist,
            context=[ai_task, review_task]
        )

        crew = Crew(
            agents=[self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[ai_task, review_task, final_report_task],
            process=Process.sequential
        )
        return crew.kickoff()


# 向後相容別名（保留給直接使用舊名稱的程式碼參考）
class QSiliconResearchCrew:
    """已棄用：請改用 CryptoResearchCrew + AIResearchCrew 雙引擎架構。"""
    def run(self, exclude_context: str | None = None):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(lambda: str(CryptoResearchCrew().run(exclude_context=exclude_context)))
            future_ai = executor.submit(lambda: str(AIResearchCrew().run(exclude_context=exclude_context)))
            crypto_report = future_crypto.result()
            ai_report = future_ai.result()
        return f"{crypto_report}\n\n{ai_report}"

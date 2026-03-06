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

_IMPACT_TAG = "IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）｜NARRATIVE：FOMO/FUD/Infra/Regulation/Other"

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

# ── Shared prompt fragments（減少 token 重複）────────────────────────────────
_TELEGRAM_FORMAT_RULES = dedent("""\
    ════ Telegram HTML 格式 ════
    僅允許：<b>、<i>、<u>、<s>、<code>、<blockquote>
    禁止：Markdown（#、**、*、_、`）、<h1~h2>、<div>、<p>、<br>、<hr>、<span>、<table>
    分隔線用 ────────────，標題用 <b>【標題】</b>，條列用「· 」，數值用 <code>，推文用 <blockquote>""")

_EDITOR_CONSENSUS_RULE = dedent("""\
    【主編共識原則】
    將 Grok/GPT 與 Claude 的辯論濃縮為一句話共識填入 💎 <b>主編共識</b>。
    戰報正文中每則新聞/推文僅保留 💎 主編共識一行，禁止呈現個別 Agent 觀點。""")

_NEWS_FORMAT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] 新聞標題
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1~2 句）""")

_PRICE_CHECK_RULE = "進場/目標/停損前必須呼叫 yfinance_tool 查詢最新報價，禁止憑空捏造價格。"


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

    def run(self, exclude_context: str | None = None):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )

        # ══════════════════════════════════════════════════════════════
        # Task 1：加密市場情報（Grok）
        # ══════════════════════════════════════════════════════════════
        crypto_task = Task(
            description=dedent(f"""
                【加密市場情報收集 — Grok】
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
                每則格式（標註發布時間，無精確時間則 [近24h]/[近72h]）：
                {_NEWS_FORMAT}
                🛸 Grok 利多 / 🛸 Grok 利空（各 1~2 句）
                {_IMPACT_TAG}

                === 背離與衍生品 ===
                · FOMO + MVRV>7 + 巨鯨轉帳 → 標示「聰明錢出貨警告」
                · 全網悲觀 + MVRV<0 + 巨鯨平靜 → 標示「散戶盲目恐慌」
                · 資金費率極正 + 多頭過熱 → 標示「多頭清算風險」
                · 剛發生巨額多頭爆倉 → 標示「流動性洗盤，左側建倉條件」

                === 幣圈推文（5 則）===
                每則：〔推文 N〕推文原文 / 簡述 / 🛸 Grok 利多+利空 / {_IMPACT_TAG}

                禁止捏造來源或未出現於搜尋結果中的事實。
            """),
            expected_output="加密市場數據 + 3 則幣圈新聞 + 5 則推文的結構化初稿。",
            agent=self.crypto_researcher
        )

        # ══════════════════════════════════════════════════════════════
        # Task 2：幣圈辯論與宏觀 Risk Off 審計（Claude）
        # ══════════════════════════════════════════════════════════════
        review_task = Task(
            description=dedent("""
                【幣圈辯論與風險審計 — Claude】

                === Fact-Check ===
                檢視所有數據（DXY/M2/MVRV/資金費率/爆倉/多空比/VIX/IBIT/ETF flow）。
                數據滯後 >12h 或極端異常 → 標記「數據失真警告：[指標]」。

                === Risk Off 訊號 ===
                呼叫 yfinance_multi_tool('^VIX,IBIT') 一次取得 VIX 與 IBIT。
                VIX 暴漲 + IBIT 下跌 → 「Risk Off 信號」；反之 → 風險偏好未退潮。

                === 幣圈新聞辯論（3 則）===
                每則：🛡️ Claude（幣圈新聞 N）：2~3 句辯論觀點。

                === 幣圈推文辯論（5 則）===
                每則：🛡️ Claude（幣圈推文 N）：1 句反向/補充觀點。

                === market_regime（risk_on / risk_off / neutral 三選一）===
                提供 3 個驅動因子（各一句話）。
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

                排版前數據獲取：coinglass_data_tool('open_interest')（Task 1 已含 funding_rate/liquidations/long_short_ratio，請沿用）、cryptoquant_tool('inflow' 或 'outflow')、ml_quant_tool。若回傳含 [Tavily 備援] 直接萃取數值，嚴禁 N/A。

                {_EDITOR_CONSENSUS_RULE}

                {_TELEGRAM_FORMAT_RULES}

                === 投資標的 ===
                在【資金流向與精準操作 (Crypto)】提供 1 單邊標的（非 BTC）+ 1 配對交易。
                {_PRICE_CHECK_RULE}
                加密貨幣請用 yfinance_tool 查詢時加 '-USD'（如 SOL-USD）。每標的含：信心水準⭐️1~5、資金佔比、進場/目標/停損、敘事邏輯。

                === 排版結構（嚴格依序）===
                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on/risk_off/neutral + 3 驅動因子
                ══════ <b>📊 加密市場</b> ══════
                【加密市場數據儀表板】宏觀(M2/DXY/VIX) + 量化模型(ML權重/部位建議) + 幣圈指標(MVRV/OI/IBIT/資金費率/爆倉/多空比/交易所淨流入)
                【幣圈新聞】3 則：標題/來源/摘要/IMPACT/💎主編共識
                【幣圈推文討論】5 則：<blockquote>原文</blockquote>/簡述/IMPACT/💎主編共識
                【資金流向與精準操作 (Crypto)】1 單邊 + 1 配對（格式：現價/信心/資金佔比/進場/目標/停損 %/敘事）

                所有標題用 <b>，數值用 <code>，推文用 <blockquote>。禁止 Markdown 與 HORIZON 標籤。
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

    def run(self, exclude_context: str | None = None):
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )

        # ══════════════════════════════════════════════════════════════
        # Task 1：AI 市場情報（GPT）
        # ══════════════════════════════════════════════════════════════
        ai_task = Task(
            description=dedent(f"""
                【AI 市場情報收集 — GPT】
                {_excl}
                === 數據 ===
                呼叫 ai_momentum_tool('openrouter_rankings') 取得模型熱度排名。

                === 第一部分：AI 基建現況（3 則）===
                聚焦：資料中心/GPU/TPU/算力/電力/散熱/能源基建。
                必須搜尋（各至少一次）：
                · market_search_tool: 'AI data center GPU NVIDIA infrastructure 2025'
                · market_search_tool: 'data center power supply nuclear energy AI 2025'
                · market_search_tool: 'AI data center cooling thermal technology 2025'
                · rumor_scanner_tool: 'data center materials semiconductor supply chain'
                3 則中至少一則涵蓋電力/散熱/材料/能源基建。
                每則：{_NEWS_FORMAT} + 🤖 GPT 利多/利空 + {_IMPACT_TAG}

                === 第二部分：AI 投資案（3 則）===
                聚焦：AI 新創融資、科技收購、風投、IPO。
                搜尋：market_search_tool + rumor_scanner_tool。格式同上。

                === 第三部分：最新 AI 模型（3 則）===
                聚焦：LLM/多模態/Agent 框架新發布，摘要含模型特色。格式同上。

                === AI 推文（5 則）===
                x_search_tool: 'MCP Model Context Protocol OR AI agent app 2025'
                聚焦：AI 應用落地、MCP 發展、Agent 框架。
                每則：〔推文 N〕原文/簡述/🤖 GPT 利多+利空/{_IMPACT_TAG}

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
            description=dedent("""
                【AI 市場辯論審計 — Claude】

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

                {_EDITOR_CONSENSUS_RULE}
                {_TELEGRAM_FORMAT_RULES}

                === 投資標的 ===
                在【AI 產業鏈精準操作 (US Equities)】提供 2 個美股標的。
                {_PRICE_CHECK_RULE}
                每標的含：信心水準⭐️1~5、資金佔比、進場/目標/停損、敘事邏輯。

                === 排版結構 ===
                ══════ <b>🤖 AI 市場</b> ══════
                【AI 數據參考】OpenRouter 模型熱度排名
                【AI 基建現況】3 則：標題/來源/摘要/IMPACT/💎主編共識
                【AI 投資案】3 則（同上格式）
                【最新 AI 模型】3 則（摘要含模型特色）
                【AI 推文討論】5 則：<blockquote>原文</blockquote>/簡述/IMPACT/💎主編共識
                【AI 產業鏈精準操作 (US Equities)】2 支（格式：現價/信心/資金佔比/進場/目標/停損 %/敘事）

                所有標題用 <b>，數值用 <code>，推文用 <blockquote>。禁止 Markdown 與 HORIZON 標籤。
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

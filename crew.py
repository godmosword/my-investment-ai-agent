import os
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from tools import (
    ai_momentum_tool,
    coinglass_data_tool,
    cryptopanic_tool,
    market_search_tool,
    ml_quant_tool,
    rumor_scanner_tool,
)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

MODEL_GROK = "xai/grok-4-1-fast-reasoning"
MODEL_GPT = "openai/gpt-5.3-chat-latest"
MODEL_CLAUDE = "openrouter/anthropic/claude-sonnet-4.6"
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

_TELEGRAM_FMT = dedent("""\
    ════ Telegram HTML ════
    允許：<b> <i> <u> <s> <code> <blockquote> <a href>
    禁止：Markdown、<h1~h2> <div> <p> <br> <hr> <span> <table>
    分隔線 ────────────（每大區塊前加）""")

_EDITOR_RULE = "【主編共識】每則新聞給 1 句最終操作判斷，必須點名具體標的。"
_DATA_RULES = "【新鮮度】新聞必須在 48h 內；超時跳過重搜。"

_NEWS_FMT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] 新聞標題
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1 句，聚焦事件本身）""")

_IMPACT_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker]
    📈 做多機會：[標的] — [原因]
    📉 做空風險：[標的] — [原因]
    ⏱️ 時效：短期(1-7天) / 中期(2-4週) / 長期(1季+)
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多""")

_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL、NVDA、MSFT 等數值，
    必須直接使用上方【系統強制即時報價】Context；不得自行捏造或改寫。""")

_TRADE_RULE = dedent("""\
    · <b>$代幣/股票 (操作方向)</b>｜現價：$真實最新報價｜信心水準：⭐️⭐️⭐️⭐️
    · 進場：<code>$XXX.XX</code>｜目標：<code>$XXX.XX (+Y%)</code>｜停損：<code>$XXX.XX (-Z%)</code>
    · 敘事邏輯：1 句，引用本日新聞""")


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
            tools=[market_search_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool],
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
            tools=[coinglass_data_tool, ml_quant_tool],
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
                {ctx}
                {excl}
                === 數據來源 ===
                · coinglass_data_tool：funding_rate / liquidations / long_short_ratio
                · cryptopanic_tool('bitcoin')
                · rumor_scanner_tool('BTC ETF flow OR crypto manipulation OR whale alert')
                · market_search_tool('Bitcoin market liquidity derivatives risk')

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
                {ctx}

                === Fact-Check ===
                以【系統強制即時報價】核對 DXY/VIX/IBIT/BTC。

                === market_regime（risk_on/risk_off/neutral）===
                列出 4 項信號：VIX、IBIT、資金費率、爆倉，並給最終判定。

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
                {ctx}

                === 交易建議（Crypto）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                {_TRADE_RULE}

                === 排版結構（嚴格依序）===
                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on/risk_off/neutral
                ══════ <b>📊 加密市場</b> ══════
                【加密市場數據儀表板】宏觀(DXY/VIX/IBIT) + 量化模型(ML權重/部位建議) + 幣圈指標(OI/資金費率/爆倉/多空比)
                【幣圈新聞】3 則（標題/來源/摘要/投資解讀/💎主編共識）
                【資金流向與精準操作 (Crypto)】1 單邊 + 1 配對
            """),
            expected_output="戰報上半部 Telegram HTML。",
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
            tools=[market_search_tool, ai_momentum_tool, rumor_scanner_tool],
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
            tools=[],
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
                {ctx}
                {excl}
                呼叫 ai_momentum_tool('openrouter_rankings')。
                搜尋：
                · market_search_tool('AI data center GPU NVIDIA infrastructure {year}')
                · market_search_tool('data center power supply nuclear energy AI {year}')
                · market_search_tool('AI model releases enterprise adoption {year}')
                · rumor_scanner_tool('AI infrastructure supply chain risk')

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
                {_QUOTE_RULE}
                {ctx}

                === 交易建議（US Equities）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                {_TRADE_RULE}

                === 排版結構 ===
                ══════ <b>🤖 AI 市場</b> ══════
                【AI 數據參考】OpenRouter 模型熱度排名
                【AI 基建現況】1 則
                【AI 投資案】1 則
                【最新 AI 模型】1 則
                （每則皆需：標題/來源/摘要/投資解讀/💎主編共識）
                【AI 產業鏈精準操作 (US Equities)】2 支
            """),
            expected_output="戰報下半部 Telegram HTML。",
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

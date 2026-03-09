import os
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from tools import (
    ai_momentum_tool,
    coinglass_data_tool,
    cryptopanic_tool,
    fear_greed_tool,
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
    分隔線 ────────────（每大區塊前加）
    ── 排版強制規則 ──
    · 儀表板數值：用 <code> 標籤包覆（等寬對齊），每項獨立一行，禁止同行塞多個數值
    · 新聞摘要：用 <blockquote> 包覆，限 1 句核心事實
    · 重點標的 / Ticker：用 <b> 標示
    · 資料缺失時寫 <code>N/A</code>，禁止自行估算或留空""")

_EDITOR_RULE = "【主編共識】每則新聞給 1 句最終操作判斷，必須點名具體標的。"
_DATA_RULES = "【新鮮度】新聞必須在 48h 內；超時跳過重搜。"

_NEWS_FMT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] <b>新聞標題</b>（來源：xxx｜性質：confirmed / likely / unverified rumor）
    <blockquote>摘要：（1 句核心事實，禁止加入主觀評論）</blockquote>""")

_DASHBOARD_FMT = dedent("""\
    ── 儀表板格式規則 ──
    每項數值獨立一行，格式：· <b>指標名</b> <code>數值 ▲/▼幅度%</code>
    資料缺失時寫 <code>N/A</code>；禁止同行塞多個指標（避免手機折行）""")

_CHATTER_FMT = dedent("""\
    ── 呢喃 / 傳聞格式規則 ──
    · 僅收錄社群推測或未確認消息，排除任何有官方聲明的事件（那屬於新聞板塊）
    · 每條限 1 句話，結尾必須標注（未確認）
    · 需標明來源性質，例：（來源：CT / Telegram 群 / 鏈上數據推測）
    · 輸出 2~3 條，條列式""")

_IMPACT_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker]
    📈 做多機會：[標的] — [原因]
    📉 做空風險：[標的] — [原因]
    ⏱️ 時效：短期(1-7天) / 中期(2-4週) / 長期(1季+)
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多""")

_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL、NVDA、MSFT 等數值，
    以及 RSI(14)、MA20/MA50、VIX 期限結構等技術指標，
    必須直接使用上方【系統強制即時報價】+【技術指標與結構】Context；不得自行捏造或改寫。""")

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
            tools=[market_search_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, fear_greed_tool],
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
                {excl}
                === 數據來源 ===
                · coinglass_data_tool：funding_rate / liquidations / long_short_ratio / options_info
                · fear_greed_tool()（恐懼與貪婪指數）
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
                {_TRADE_RULE}

                === 排版結構（嚴格依序，禁止調換區塊順序）===

                <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
                ────────────
                【今日市場模式】risk_on / risk_off / neutral
                ══════ <b>📊 加密市場</b> ══════

                ── 區塊①【數據儀表板】──
                嚴格套用 _DASHBOARD_FMT，每項獨立一行，分三組輸出：
                宏觀數據（來自【系統強制即時報價】）：
                  · <b>DXY</b> <code>...數值 ▲/▼...%</code>
                  · <b>VIX</b> <code>...數值 ▲/▼...%</code>
                  · <b>VIX 期限結構</b> <code>Contango / Backwardation</code>
                  · <b>IBIT</b> <code>...數值 ▲/▼...%</code>
                技術面（來自【技術指標與結構】）：
                  · <b>BTC RSI(14)</b> <code>...數值（超買/中性/超賣）</code>
                  · <b>BTC MA20/MA50</b> <code>多頭排列 / 空頭排列 / 盤整</code>
                  · <b>Fear & Greed</b> <code>...數值/100（情緒標籤）</code>
                籌碼數據（來自 coinglass_data_tool）：
                  · <b>資金費率(BTC)</b> <code>...數值</code>
                  · <b>大戶多空比</b> <code>...數值</code>
                  · <b>未平倉量(OI)</b> <code>...數值 ▲/▼...%</code>
                  · <b>24h 爆倉</b> <code>...金額</code>
                  · <b>BTC 選擇權 P/C Ratio</b> <code>...數值</code>
                  · <b>BTC Max Pain</b> <code>$...價位</code>
                ────────────

                ── 區塊②【核心新聞】──
                共 3 則，嚴格套用更新後的 _NEWS_FMT + _IMPACT_TAG，每則結尾加 💎 主編共識（1 句操作判斷，必須點名具體標的）。
                ────────────

                ── 區塊③【市場呢喃與傳聞】──
                嚴格套用 _CHATTER_FMT，輸出 2~3 條；本區塊禁止重複新聞板塊已報導的事件。
                ────────────

                ── 區塊④【資金流向與精準操作 (Crypto)】──
                套用 _TRADE_RULE，輸出 1 單邊 + 1 配對交易建議。
            """),
            expected_output="戰報上半部 Telegram HTML，依序包含：①數據儀表板 ②核心新聞×3 ③市場呢喃×2~3 ④精準操作×2。",
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
                {_DASHBOARD_FMT}
                {_CHATTER_FMT}
                {_QUOTE_RULE}
                {ctx}

                === 交易建議（US Equities）===
                【實盤價格強制查核】：必須使用 Context 中的【系統強制即時報價】來設定現價與進場點位，嚴禁自行捏造！
                {_TRADE_RULE}

                === 排版結構（嚴格依序，禁止調換區塊順序）===

                ══════ <b>🤖 AI 市場</b> ══════

                ── 區塊①【AI 數據儀表板】──
                嚴格套用 _DASHBOARD_FMT，每項獨立一行；
                從 ai_momentum_tool 取得的 OpenRouter 模型熱度，列出 Top 5：
                  · <b>#1 [模型名]</b> <code>[熱度指標 / 週排名變化]</code>
                  · <b>#2 [模型名]</b> <code>[熱度指標 / 週排名變化]</code>
                  · ...（最多 5 條）
                資料缺失時寫 <code>N/A</code>，禁止自行捏造排名。
                ────────────

                ── 區塊②【AI 產業新聞】──
                共 3 則（AI 基建 / AI 投資案 / 最新模型各 1），嚴格套用更新後的 _NEWS_FMT + _IMPACT_TAG，每則結尾加 💎 主編共識（1 句，必須點名受影響美股或 ETF）。
                ────────────

                ── 區塊③【產業鏈呢喃】──
                嚴格套用 _CHATTER_FMT，輸出 2~3 條供應鏈傳聞或非官方消息（GPU 缺貨、代工廠產能、未公開合約等）；本區塊禁止重複新聞板塊已報導的事件。
                ────────────

                ── 區塊④【AI 產業鏈精準操作 (US Equities)】──
                套用 _TRADE_RULE，輸出 2 支美股操作建議。
            """),
            expected_output="戰報下半部 Telegram HTML，依序包含：①AI 數據儀表板 ②AI 產業新聞×3 ③產業鏈呢喃×2~3 ④精準操作×2。",
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

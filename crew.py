import os
from datetime import datetime, timezone, timedelta
from textwrap import dedent
from crewai import Agent, Task, Crew, Process, LLM

# LLM 模型常數（便於統一升級版本）
MODEL_GROK   = "xai/grok-4-1-fast-reasoning"
MODEL_GPT    = "openai/gpt-5.2-chat-latest"
MODEL_CLAUDE = "openrouter/anthropic/claude-sonnet-4.6"
MODEL_GEMINI = "gemini/gemini-3.1-pro-preview"

# 標籤規範（移除 HORIZON，保留 IMPACT + NARRATIVE）
_IMPACT_TAG = "【IMPACT】強利空/弱利空/中性/弱利多/強利多（五選一）｜【NARRATIVE】FOMO/FUD/Infra/Regulation/Other"

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
)


class QSiliconResearchCrew:
    def __init__(self):
        # 🛸 Grok — 加密市場
        grok_latest = LLM(
            model=MODEL_GROK,
            api_key=os.getenv("XAI_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 🤖 GPT — AI 市場
        gpt_latest = LLM(
            model=MODEL_GPT,
            api_key=os.getenv("OPENAI_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 🛡️ Claude — 辯論與風險審計
        claude_latest = LLM(
            model=MODEL_CLAUDE,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 💎 Gemini — 主編與共識整合
        gemini_latest = LLM(
            model=MODEL_GEMINI,
            api_key=os.getenv("GEMINI_API_KEY"),
            max_retries=5,
            timeout=180,
        )

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，挑選 3 則最具市場衝擊力的幣圈新聞與 5 則 X 推文，提供 Grok 視角的利多與利空分析。",
            backstory="極度冷血的量化追蹤者，專注聰明錢與散戶情緒背離分析。在散戶最狂熱時尋找巨鯨倒貨的蛛絲馬跡，在市場最恐慌時尋找強者積累的痕跡。",
            llm=grok_latest,
            tools=[market_search_tool, x_search_tool, macro_liquidity_tool, mvrv_tool,
                   coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, yfinance_macro_tool],
            verbose=False
        )

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="分三個部分（AI 基建現況、AI 投資案、最新 AI 模型）各找 3 則新聞，另搜尋 5 則聚焦 AI 新應用與 MCP 發展的推文，提供 GPT 視角的利多與利空分析。",
            backstory="華爾街科技股做空機構分析師，緊盯 AI 基礎設施的經濟效益與資本支出疲勞的早期信號。對每一波技術熱潮都保持健康的懷疑，但不放過真正的突破性進展。",
            llm=gpt_latest,
            tools=[market_search_tool, x_search_tool, ai_momentum_tool, rumor_scanner_tool],
            verbose=False
        )

        self.risk_critic = Agent(
            role="首席跨域辯論員",
            goal="針對幣圈與 AI 兩大市場的所有新聞與推文提供 Claude 的反向辯論觀點，完成 VIX/IBIT 傳統金融風險審計，並判定今日 market_regime。",
            backstory="信奉索羅斯反射性理論的獨立分析師。職責是讓每個論點都受到嚴格審視，深知假新聞本身也能創造真實的市場踩踏，也深知真正的轉折往往發生在市場共識的反面。",
            llm=claude_latest,
            allow_delegation=False,
            tools=[yfinance_tool],
            verbose=False
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="整合所有 Agent 的研究成果，為每則新聞與推文下達 Gemini 共識結論，排版輸出完整的雙市場戰報。",
            backstory="負責最終整合與排版的機構主編，確保每一個判斷都有依據，每一個觀點都有對立面的檢驗。",
            llm=gemini_latest,
            tools=[coinglass_data_tool, cryptoquant_tool, ml_quant_tool],
            verbose=False
        )

    def run(self, exclude_context: str | None = None):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )

        # ══════════════════════════════════════════════════════════════
        # Task 1：加密市場情報（Grok，與 ai_task 並行執行）
        # ══════════════════════════════════════════════════════════════
        crypto_task = Task(
            async_execution=True,
            description=dedent(f"""
                【加密市場情報收集任務 — Grok 執行】
                {_excl}
                === 數據收集（強制，不得跳過）===
                1. 呼叫 macro_liquidity_tool 兩次：分別取得 DXY（ICE 美元指數）與 M2 最新數值及變動方向。
                2. 呼叫 mvrv_tool（'latest'）取得 BTC MVRV Z-Score，說明估值區間（>7 高估 / <0 低估）。
                3. 呼叫 coinglass_data_tool 三次，分別取得 'funding_rate'、'liquidations'、'long_short_ratio'。
                4. 呼叫 yfinance_macro_tool（metric='vix'）取得 VIX 指數與日變化。
                5. 呼叫 yfinance_macro_tool（metric='etf_flow'）取得 SPY/QQQ 成交額 vs 5 日均值 proxy。
                6. 呼叫 cryptopanic_tool（topic='bitcoin'）取得幣圈原生熱點新聞。
                7. 呼叫 rumor_scanner_tool 搜尋：'BTC ETF flow OR crypto market manipulation OR whale alert'。
                8. 呼叫 x_search_tool 搜尋：'BTC whale OR bitcoin ETF OR crypto rumor'。

                === 幣圈新聞（強制輸出 3 則）===
                優先選取：ETF 資金流、槓桿清算風險、鏈上流向、做市商操作相關題材。
                至少一則來源必須標示為 CryptoPanic 原生快訊。
                每則新聞輸出格式：
                〔新聞 N〕標題
                來源：xxx｜性質：confirmed / likely / unverified rumor
                摘要：（1~2 句）
                🛸 Grok 利多：（從看多角度解讀，1~2 句）
                🛸 Grok 利空：（從看空角度解讀，1~2 句）
                {_IMPACT_TAG}

                【背離對撞測試】
                (a) FOMO 情緒高漲但 MVRV > 7 且有巨鯨轉帳 → 必須標示「聰明錢出貨警告」。
                (b) 全網悲觀但 MVRV < 0 且巨鯨平靜 → 必須標示「散戶盲目恐慌，強者積累籌碼」。
                【衍生品獵殺分析】
                (a) 資金費率極正且多頭過熱 → 標示「多頭清算風險」。
                (b) 剛發生巨額多頭爆倉 → 標示「流動性洗盤，具備左側建倉條件」。

                === 幣圈推文（強制輸出 5 則）===
                列出 5 則來自 x_search_tool 的原始推文，每則格式：
                〔推文 N〕推文原文
                簡述：（一句話說明推文主張）
                🛸 Grok 利多：（1 句）
                🛸 Grok 利空：（1 句）
                {_IMPACT_TAG}

                嚴禁捏造來源或未出現於搜尋結果中的事實。
            """),
            expected_output="包含完整加密市場數據（DXY/M2/MVRV/衍生品/VIX/ETF flow）、3 則幣圈新聞（含 Grok 利多/利空分析）、5 則推文（含簡述與 Grok 利多/利空觀點）的結構化初稿。",
            agent=self.crypto_researcher
        )

        # ══════════════════════════════════════════════════════════════
        # Task 2：AI 市場情報（GPT，與 crypto_task 並行執行）
        # ══════════════════════════════════════════════════════════════
        ai_task = Task(
            async_execution=True,
            description=dedent(f"""
                【AI 市場情報收集任務 — GPT 執行】
                {_excl}
                === 數據參考 ===
                1. 呼叫 ai_momentum_tool（'model_benchmarks'）取得最新 LMSYS 模型排名前三名。
                2. 呼叫 ai_momentum_tool（'big_tech_capex'）取得 Amazon / Microsoft / Alphabet / Meta AI 資本支出規模。

                === 第一部分：AI 基建現況（強制 3 則新聞）===
                聚焦：資料中心、GPU/TPU 晶片、算力基礎設施、電力與散熱技術。
                呼叫 market_search_tool 搜尋：'AI data center GPU NVIDIA infrastructure investment 2025'。
                每則新聞輸出格式：
                〔新聞 N〕標題
                來源：xxx｜性質：confirmed / likely / unverified rumor
                摘要：（1~2 句）
                🤖 GPT 利多：（1~2 句）
                🤖 GPT 利空：（1~2 句）
                {_IMPACT_TAG}

                === 第二部分：AI 投資案（強制 3 則新聞）===
                聚焦：AI 新創融資輪、科技巨頭收購、風投動向、AI 公司 IPO 或估值事件。
                呼叫 market_search_tool 搜尋：'AI startup funding round investment acquisition 2025'。
                呼叫 rumor_scanner_tool 搜尋：'AI unicorn OR OpenAI funding OR Anthropic deal OR AI IPO'。
                格式同上（3 則，各含 GPT 利多/利空）。

                === 第三部分：最新 AI 模型（強制 3 則新聞）===
                聚焦：最新發布的 LLM / 多模態 / Agent 框架，必須說明模型核心特色與技術突破點。
                呼叫 market_search_tool 搜尋：'new AI model release LLM multimodal agent 2025'。
                格式同上，摘要需含模型特色說明（3 則，各含 GPT 利多/利空）。

                === AI 推文（強制 5 則）===
                呼叫 x_search_tool 搜尋：'MCP Model Context Protocol OR AI agent app OR AI application 2025'。
                聚焦：新 AI 應用落地案例、MCP（Model Context Protocol）發展、Agent 框架進展。
                每則格式：
                〔推文 N〕推文原文
                簡述：（一句話說明推文主張）
                🤖 GPT 利多：（1 句）
                🤖 GPT 利空：（1 句）
                {_IMPACT_TAG}

                【算力經濟學審查】
                (a) 訓練成本持續攀升但 Big Tech 資本支出增速放緩 → 必須標示「算力通縮研發通膨矛盾」。
                (b) 評估市場是否出現對 AI 基建股的敘事疲勞風險。

                嚴禁捏造未出現於來源中的事實。
            """),
            expected_output="包含 LMSYS 排名與 Big Tech CapEx 數據、三個部分各 3 則 AI 新聞（含 GPT 利多/利空分析）、5 則 AI 推文（含簡述與 GPT 利多/利空觀點）的結構化初稿。",
            agent=self.ai_researcher
        )

        # ══════════════════════════════════════════════════════════════
        # Task 3：跨域辯論與風險審計（Claude）
        # ══════════════════════════════════════════════════════════════
        review_task = Task(
            description=dedent("""
                【跨域辯論與風險審計任務 — Claude 執行】
                你已收到 Grok 的加密市場分析與 GPT 的 AI 市場分析。

                === 傳統金融 Risk Off 訊號（強制執行）===
                呼叫 yfinance_tool（symbol='^VIX'）取得 VIX 最新指數與日漲跌幅。
                呼叫 yfinance_tool（symbol='IBIT'）取得比特幣現貨 ETF IBIT 最新價格與漲跌幅。
                (a) VIX 明顯暴漲且 IBIT 下跌 → 判定為「傳統金融資金撤退的 Risk Off 信號」。
                (b) VIX 平穩或下跌且 IBIT 上漲 → 說明傳統金融風險偏好尚未退潮。

                === 幣圈新聞辯論（對應 Grok 的 3 則新聞）===
                對每則新聞提供 🛡️ Claude 的辯論觀點（2~3 句）：
                - 若 Grok 分析可信，補充支持論據或 Grok 未提及的潛在風險。
                - 若 Grok 過於樂觀或悲觀，提出反向論點。
                格式：🛡️ Claude（幣圈新聞 N）：（2~3 句）

                === 幣圈推文辯論（對應 Grok 的 5 則推文）===
                每則推文提供 🛡️ Claude 的一句反向或補充觀點。
                格式：🛡️ Claude（幣圈推文 N）：（1 句）

                === AI 基建現況辯論（對應 GPT 的 3 則新聞）===
                格式同幣圈新聞辯論。
                格式：🛡️ Claude（AI基建 N）：（2~3 句）

                === AI 投資案辯論（對應 GPT 的 3 則新聞）===
                格式：🛡️ Claude（AI投資 N）：（2~3 句）

                === 最新 AI 模型辯論（對應 GPT 的 3 則新聞）===
                格式：🛡️ Claude（AI模型 N）：（2~3 句）

                === AI 推文辯論（對應 GPT 的 5 則推文）===
                格式：🛡️ Claude（AI推文 N）：（1 句）

                === 市場模式判定 ===
                綜合以上所有資訊（含 VIX/IBIT 訊號、幣圈與 AI 新聞/推文辯論結果），判定 market_regime：
                只能從 risk_on / risk_off / neutral 三選一。
                提供 3 個關鍵驅動因子（各一句話）。

                【反射性判斷】
                (a) FUD 傳聞 + 當日 ETF 巨大淨流出 → 判定「情緒已感染流動性」，高風險警告。
                (b) 全網極度恐慌但巨鯨平靜且 MVRV < 3 → 標示「黃金坑 / 洗盤」。
                【衍生品槓桿共振】
                散戶過度槓桿做多（高資金費率 + 高 OI）→ 即使無 FUD 也判定 risk_off。
            """),
            expected_output="包含 VIX/IBIT 數據判定、幣圈 3 新聞與 5 推文的 Claude 辯論觀點、AI 三部分 9 新聞與 5 推文的 Claude 辯論觀點，以及 market_regime 與 3 個驅動因子的完整審計報告。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        # ══════════════════════════════════════════════════════════════
        # Task 4：最終戰報整合（Gemini 主編）
        # ══════════════════════════════════════════════════════════════
        final_report_task = Task(
            description=dedent(f"""
                【最終戰報整合任務 — Gemini 主編執行】

                【排版前強制數據獲取】
                - 呼叫 coinglass_data_tool（'open_interest'）取得 BTC OI。
                - 呼叫 coinglass_data_tool（'funding_rate'）、（'liquidations'）、（'long_short_ratio'）。
                - 呼叫 cryptoquant_tool（'inflow' 或 'outflow'）取得 BTC 交易所淨流入/流出。
                - 呼叫 ml_quant_tool 取得 ML 最佳化權重與量化訊號。
                若工具回傳含 [Tavily 備援]，直接萃取可用數值。嚴禁輸出 N/A。

                你已收到：
                ① Grok 的加密市場分析（數據 + 3 幣圈新聞 + 5 推文，含 Grok 利多/利空）
                ② GPT 的 AI 市場分析（三部分各 3 新聞 + 5 推文，含 GPT 利多/利空）
                ③ Claude 的辯論審計（每則新聞/推文的 Claude 觀點 + VIX/IBIT + market_regime）

                對每則新聞與推文，你必須：
                1. 呈現各 Agent 的多方討論（Grok/GPT 提供利多利空，Claude 提供辯論觀點）
                2. 加上 💎 Gemini 共識結論（綜合各方，給出明確判斷）

                ════ Telegram HTML 格式規範（最高優先級）════
                僅允許：<b>、<i>、<u>、<s>、<code>、<blockquote>
                禁止：Markdown 符號（#、**、*、_、`）、<h1~h2>、<div>、<p>、<br>、<hr>、<span>、<table>
                <、>、& 三個符號以外禁止 HTML encoding。
                分隔線：────────────
                區塊標題：<b>【標題名稱】</b>
                條列：「· 」開頭；數值變動用「→」與「↑ / ↓」；推文原文用 <blockquote>；數值用 <code>。

                ════【終極排版警告】════
                ① 所有【區塊標題】與 Agent 署名，一律用 <b>...</b> 包覆。
                ② 所有數值數據與 IMPACT 標籤行，一律用 <code>...</code> 包覆。
                ③ 所有推文原文，一律用 <blockquote>...</blockquote> 包覆。
                ④ 嚴禁使用 HORIZON 標籤！
                如漏掉任何 HTML 標籤，報告視為失敗，必須重新生成！

                ════ 戰報結構（嚴格依序輸出）════

                <b>🛡️ Q-Silicon Institutional Research</b>
                <i>Daily Brief · {today_str}</i>
                ────────────

                <b>【今日市場模式】</b>
                今日模式：<b>risk_on / risk_off / neutral</b>（填入 Claude 判定結果，粗體）
                · 驅動因子 1：（一句話）
                · 驅動因子 2：（一句話）
                · 驅動因子 3：（一句話）
                ────────────

                ══════ <b>📊 加密市場</b> ══════
                ────────────

                <b>【加密市場數據儀表板】</b>
                <b>【宏觀】</b>
                · M2 → <code>xxx</code>（↑/↓ x%）
                · ICE DXY → <code>xx.xx</code>（↑/↓ x%）
                · VIX 恐慌指數 → <code>xx.xx（↑/↓ x%）</code>
                <b>【量化模型】</b>
                · ML 最佳權重 → <code>DXY: xx%, ETF: xx%, RISK: xx%, MVRV: xx%</code>
                · 系統建議部位 → <code>做多 / 避險（動能分數: x.xx）</code>
                <b>【幣圈指標】</b>
                · MVRV Z-Score → <code>x.xx</code>（高估/低估/健康）
                · BTC OI → <code>$xxB</code>（↑/↓ x%）
                · IBIT 現貨 ETF → <code>$xx.xx（↑/↓ x%）</code>
                · BTC 資金費率 → <code>xxx%</code>
                · 24h 爆倉 → <code>$xxxM（多頭 $xxM / 空頭 $xxM）</code>
                · 大戶多空比 → <code>x.xx</code>
                · BTC 交易所淨流入 → <code>xxx BTC</code>
                ────────────

                <b>【幣圈新聞】</b>
                依序列出 3 則幣圈新聞，每則格式：

                〔新聞 N〕<b>新聞標題</b>
                來源：xxx｜性質：<i>confirmed / likely / unverified rumor</i>
                摘要：（1~2 句）
                🛸 <b>Grok 利多</b>：（1 句）
                🛸 <b>Grok 利空</b>：（1 句）
                🛡️ <b>Claude</b>：（辯論觀點 1~2 句）
                <code>IMPACT: xxx | NARRATIVE: xxx</code>
                💎 <b>Gemini 結論</b>：（綜合各方觀點，給出共識判斷 1 句）

                ────────────

                <b>【幣圈推文討論】</b>
                依序列出 5 則推文，每則格式：

                〔推文 N〕<blockquote>推文原文</blockquote>
                簡述：（一句話說明推文主張）
                🛸 <b>Grok 利多</b>：（1 句）｜🛸 <b>Grok 利空</b>：（1 句）
                🛡️ <b>Claude</b>：（1 句）
                <code>IMPACT: xxx | NARRATIVE: xxx</code>
                💎 <b>Gemini 結論</b>：（1 句共識）

                ────────────

                ══════ <b>🤖 AI 市場</b> ══════
                ────────────

                <b>【AI 數據參考】</b>
                · LMSYS 模型排名 → （前三名）
                · Big Tech AI 資本支出 → （Amazon / Microsoft / Alphabet / Meta 近期趨勢）
                ────────────

                <b>【AI 基建現況】</b>
                依序列出 3 則新聞，每則格式：

                〔新聞 N〕<b>新聞標題</b>
                來源：xxx｜性質：<i>confirmed / likely / unverified rumor</i>
                摘要：（1~2 句）
                🤖 <b>GPT 利多</b>：（1 句）
                🤖 <b>GPT 利空</b>：（1 句）
                🛡️ <b>Claude</b>：（辯論觀點 1~2 句）
                <code>IMPACT: xxx | NARRATIVE: xxx</code>
                💎 <b>Gemini 結論</b>：（1 句共識）

                ────────────

                <b>【AI 投資案】</b>
                （格式與 AI 基建現況相同，列出 3 則新聞）
                ────────────

                <b>【最新 AI 模型】</b>
                （格式與 AI 基建現況相同，列出 3 則新聞；摘要必須包含模型核心特色與技術突破點）
                ────────────

                <b>【AI 推文討論】</b>
                （聚焦：新 AI 應用落地、MCP 發展、Agent 框架進展；格式與幣圈推文相同，5 則）

                ────────────
                ════ 嚴禁刪減！加密市場 3 則新聞 + 5 則推文、AI 市場各部分 3 則新聞 + 5 則推文，必須完整保留！════
                ════ 嚴禁使用 HORIZON 標籤！嚴禁使用任何 Markdown 符號！════
            """),
            expected_output="一份完整的 Q-Silicon 戰報：加密市場區塊（數據儀表板 + 3 幣圈新聞 + 5 推文，每則含多 Agent 討論與 Gemini 共識）+ AI 市場區塊（基建/投資/模型各 3 新聞 + 5 推文，每則含多 Agent 討論與 Gemini 共識），符合 Telegram HTML 格式。",
            agent=self.quant_strategist,
            context=[crypto_task, ai_task, review_task]
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, ai_task, review_task, final_report_task],
            process=Process.sequential
        )
        return crew.kickoff()

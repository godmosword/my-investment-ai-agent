import os
from datetime import datetime, timezone, timedelta
from textwrap import dedent
from crewai import Agent, Task, Crew, Process, LLM

# LLM 模型常數（便於統一升級版本）
MODEL_GROK   = "xai/grok-4-1-fast-reasoning"
MODEL_GPT    = "openai/gpt-5.2-chat-latest"
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
    rumor_scanner_tool,
)


class QSiliconResearchCrew:
    def __init__(self):
        # 🛸 Grok
        grok_latest = LLM(
            model=MODEL_GROK,
            api_key=os.getenv("XAI_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 🤖 GPT
        gpt_latest = LLM(
            model=MODEL_GPT,
            api_key=os.getenv("OPENAI_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 🛡️ Claude
        claude_latest = LLM(
            model=MODEL_CLAUDE,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_retries=3,
            timeout=120,
        )
        # 💎 Gemini — 加大 timeout 防止長任務期間 TCP connection reset
        gemini_latest = LLM(
            model=MODEL_GEMINI,
            api_key=os.getenv("GEMINI_API_KEY"),
            max_retries=5,
            timeout=180,
        )

        self.crypto_researcher = Agent(
            role="幣圈與宏觀市場研究員",
            goal="挑選 3 則幣圈新聞並分析宏觀 M2/DXY 指標，同時標記潛在『未證實市場傳聞』與操盤爭議。",
            backstory="您擅長交叉比對鏈上流向、全球流動性與市場敘事，特別留意具殺傷力的負面訊號，但嚴格區分事實與傳聞。你是一名極度冷血的量化追蹤者，專注於『聰明錢與散戶情緒的背離分析 (Divergence Analysis)』。你喜歡在散戶最狂熱時尋找巨鯨倒貨的蛛絲馬跡。",
            llm=grok_latest,
            tools=[market_search_tool, x_search_tool, macro_liquidity_tool, mvrv_tool, rumor_scanner_tool],
            verbose=True
        )

        self.ai_researcher = Agent(
            role="前沿 AI 科技研究員",
            goal="挑選 3 則最新 AI 動態並分析 LMSYS 模型排名，特別追蹤模型洩漏、數據濫用與安全爭議。",
            backstory="您關注矽谷與全球 AI 生態的黑暗面，包含模型洩漏、算力壟斷與安全事故，同時會標明可信度與風險等級。比起盲目崇拜技術突破，你更像是一名華爾街科技股做空機構的分析師。你緊盯 AI 基礎設施的經濟效益與『資本支出疲勞 (CapEx Fatigue)』的早期信號。",
            llm=gpt_latest,
            tools=[market_search_tool, x_search_tool, ai_momentum_tool, rumor_scanner_tool],
            verbose=True
        )

        self.risk_critic = Agent(
            role="首席風險與邏輯評論員",
            goal="針對數據與『八卦 / 傳聞』進行毒舌審計，區分可驗證事實與純敘事炒作，並標註風險等級。",
            backstory="您負責潑冷水，揭露虛假的指標背離與敘事操縱，特別審視所謂內線或八卦是否有足夠證據支撐。你信奉索羅斯的『反射性理論 (Reflexivity)』。你深知假新聞本身也能創造真實的市場踩踏。你的職責不只是打假，更要判斷『錯誤的敘事是否已經實質感染了流動性』。",
            llm=claude_latest,
            allow_delegation=False,
            verbose=True
        )

        self.quant_strategist = Agent(
            role="機構策略主編",
            goal="整合『精準數據儀表板』與 Agent 短評。Gemini 是您的靈魂。",
            backstory="您負責最後排版，嚴禁廢話。僅列出有實際參與評述的 Agent。",
            llm=gemini_latest,
            tools=[coinglass_data_tool, cryptoquant_tool],
            verbose=True
        )

    def run(self, exclude_context: str | None = None):
        today_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選用過去 24 小時內的新聞：\n{exclude_context}\n\n"
            if exclude_context else ""
        )
        crypto_task = Task(
            async_execution=True,  # ai_task 與本 task 同步並行，節省 40-50% 執行時間
            description=dedent(f"""
                【幣圈「八卦與內線」情報網任務——請嚴格依照以下指示行動】
                {_excl}
                1. 必須呼叫 macro_liquidity_tool 兩次，分別獲取「最新 DXY 指標」與「M2 貨幣供應」，並說明其變動方向，僅使用公開數據。
                2. 必須呼叫 mvrv_tool（參數: 'latest'）取得 BTC MVRV Z-Score，並根據數值解讀市場估值狀態（>7 高估 / <0 低估），嚴禁輸出 N/A。
                3. 必須呼叫 rumor_scanner_tool 與 market_search_tool，搜尋以下關鍵字（僅限公開新聞 / 報導來源）：
                   'crypto market maker manipulation OR Jane Street rumor OR BTC ETF flow leak'
                4. 必須呼叫 x_search_tool，搜尋 X 上的關鍵字：
                   'crypto rumor OR BTC leak'

                【強制輸出規範（極為嚴格，請逐條遵守）】：
                - 僅使用可公開取得的新聞與社群內容，不得捏造任何「未出現於來源中的」具體事實或人物指控。
                - 必須明確列出「3 則具爭議性或前瞻性」的市場新聞，內容需與：
                  做市商行為、槓桿清算風險、ETF 資金流或 Jane Street 類型機構操作「傳聞」相關。
                - 對每一則新聞，需標註：
                  (a) 資訊來源（例如：媒體 / 報告 / 研究機構）
                  (b) 性質：confirmed / likely / unverified rumor（三選一）
                  (c) 您的風險與可信度評論。

                【背離對撞測試】：在撰寫評論時，你必須將 X 上的社群情緒與 MVRV Z-Score 及巨鯨數據對比。
                (a) 若 X 上極度 FOMO，但 MVRV Z-Score > 7 且有巨鯨大額轉帳，必須發出最高級別的『聰明錢出貨警告 (Smart Money Distribution)』。
                (b) 若 X 上極度悲觀，但 MVRV < 0 且巨鯨無動作，必須點出『散戶盲目恐慌，籌碼正落入強者手中』。

                - 必須原汁原味列出「5 則最具殺傷力的 X 原始推文內容」，並對每則推文加上：
                  (a) 該推文的具體主張
                  (b) 您對其可信度的評估
                  (c) 若為純情緒帶風向，請明確指出。
                - 對於每一則新聞與推文，請額外給出統一格式的標籤行：
                  【IMPACT】強利空/弱利空/中性/弱利多/強利多（五選一，直觀表達對投資的影響方向與強度）｜【NARRATIVE】FOMO/FUD/Infra/Regulation/Other｜【HORIZON】intraday/swing/cycle

                嚴禁輸出任何法律建議或保證某傳聞為真。所有內容必須標註為「市場敘事 / 傳聞」，僅供風險研究與情緒監控使用。
            """),
            expected_output="一份包含：最新 DXY 指標解讀、MVRV Z-Score 估值解讀、3 則具爭議性的幣圈新聞（附來源與可信度標註），以及 5 則最具殺傷力 X 推文與 Grok 的辛辣評論與風險評分的完整初稿。",
            agent=self.crypto_researcher
        )

        ai_task = Task(
            async_execution=True,  # 與 crypto_task 同步並行
            description=dedent(f"""
                【AI 圈「黑暗傳聞」情資任務——請嚴格依照以下指示行動】
                {_excl}
                1. 必須呼叫 ai_momentum_tool 兩次：(a) 參數 'model_benchmarks' 取得最新 LMSYS 模型排名；(b) 參數 'big_tech_capex' 取得 Amazon、Microsoft、Alphabet、Meta 等 Big Tech 的 AI 資本支出與資料中心投資數據。不得遺漏或捏造數值。
                2. 必須呼叫 rumor_scanner_tool 與 market_search_tool，搜尋以下關鍵字（僅限公開新聞 / 報導來源）：
                   'AI model leak OR OpenAI internal drama OR NVIDIA secret project'
                3. 必須呼叫 x_search_tool，搜尋 X 上的關鍵字：
                   '#OpenSourceAI breakthrough OR AI rumor OR Sam Altman drama'

                【強制輸出規範（極為嚴格，請逐條遵守）】：
                - 僅使用可公開取得的新聞、部落格與開發者社群內容，不得捏造「從未出現在來源中的」內線或機密資訊。
                - 必須明確列出「3 則矽谷暗盤或未正式對外公關包裝的 AI 產業動態」，例如：
                  模型洩漏事件、內部文化與管理爭議、GPU 供應與算力壟斷爭議、開源社群爆料等。
                - 對每一則動態，需標註：
                  (a) 資訊來源（開發者論壇、技術部落格、主流媒體等）
                  (b) 性質：confirmed / likely / unverified rumor
                  (c) 您對其對產業格局與投資情緒之潛在影響。

                【算力經濟學審查】：在評論 AI 產業動態時，必須結合你抓取到的 Big Tech AI 資本支出、LMSYS 模型數據，以及可得的 GPU 租賃價格資訊。
                (a) 若發現模型訓練成本/規模持續上升，但 GPU 租賃價格或 Big Tech 資本支出增速出現疲軟或放緩，你必須在評論中強烈警告『算力通縮但研發通膨的矛盾』。
                (b) 評估市場是否對 AI 基建股 (Infra) 產生了敘事轉換與資本支出疲勞的風險。

                - 必須原汁原味列出「5 則來自開發者社群的 X 原始推文內容」，並對每則推文加上：
                  (a) 具體技術或內部狀況主張
                  (b) 您對其專業度與可信度的評估
                  (c) 是否可能被誇大、帶有個人情緒或商業動機。
                - 對於每一則新聞與推文，請額外給出統一格式的標籤行：
                  【IMPACT】強利空/弱利空/中性/弱利多/強利多（五選一，直觀表達對投資的影響方向與強度）｜【NARRATIVE】FOMO/FUD/Infra/Regulation/Other｜【HORIZON】intraday/swing/cycle

                嚴禁聲稱掌握真實內線或未公開機密；所有內容均須標註為「產業傳聞與社群敘事」，僅供風險研究與前瞻情緒分析使用。
            """),
            expected_output="一份包含：最新 LMSYS 模型排名摘要、Big Tech AI 資本支出摘要、3 則具爭議性的 AI 產業傳聞與動態（附來源與可信度標註），以及 5 則來自開發者社群的代表性 X 推文與 GPT 的辛辣評論與產業風險評估的完整初稿。",
            agent=self.ai_researcher
        )

        review_task = Task(
            description=dedent("""
                綜合幣圈與 AI 區塊的所有數據與傳聞，執行以下任務：
                1. 審查各指標與新聞、推文的一致性與可信度，指出明顯誇大或自相矛盾之處。
                2. 對每一類主要敘事（例如：ETF 資金流、模型洩漏、算力壟斷）給出「風險說明」與「可能被市場過度/不足定價」的簡短評語。

                【反射性判斷要求】：
                (a) 若發現 FUD (恐慌) 傳聞，且當日 ETF 出現巨大淨流出，必須判定為『情緒已感染流動性』，強制給予高風險警告。
                (b) 若全網極度恐慌 (FUD 滿天飛)，但巨鯨轉帳平靜且 MVRV Z-Score 處於健康/低估區間 (<3)，你必須大膽在備忘錄中標註此為『黃金坑 (Bear Trap) / 洗盤』。

                3. 給出當前市場的整體模式標籤 (market_regime)，只能從下列三者中擇一：
                   - risk_on
                   - risk_off
                   - neutral
                   並用不超過 3 個關鍵驅動因子說明理由（例如：DXY 走強 + OI 降溫 + FUD 類傳聞升溫）。
            """),
            expected_output="一份包含：各主要敘事的可信度與風險批註、以及最終 market_regime（risk_on / risk_off / neutral）與 3 個關鍵驅動因子的審計備忘錄。",
            agent=self.risk_critic,
            context=[crypto_task, ai_task]
        )

        final_report_task = Task(
            description=dedent(f"""
                【強制數據獲取指令】在開始排版前，你必須親自執行以下動作：
                - 呼叫 `coinglass_data_tool` (參數: 'open_interest') 取得 BTC OI；若回傳含 [Tavily 備援]，請從中萃取可用數值或趨勢。
                - 呼叫 `cryptoquant_tool` (參數: 'inflow' 或 'outflow') 取得 BTC 交易所淨流入/流出；若回傳含 [Tavily 備援]，請從中萃取可用數值或趨勢。
                嚴禁在數據儀表板輸出 N/A，若工具與備援均失敗，始可寫「API 暫時無回應」。

                撰寫 [Q-Silicon Institutional Research] Daily Brief。
                輸出格式為 Telegram HTML，Telegram 只支援以下標籤，嚴禁使用其他任何 HTML 標籤：
                <b>粗體</b>、<i>斜體</i>、<u>底線</u>、<s>刪除線</s>、<code>等寬</code>、<blockquote>引用</blockquote>

                ════ 排版格式規範（最高優先級，必須嚴格遵守）════
                禁止使用 Markdown 符號：#、##、**、*、_、`、---。
                禁止使用 <h1>、<h2>、<div>、<p>、<br>、<hr>、<span>、<table> 等不支援的 HTML 標籤。
                禁止對 <、>、& 以外的字元做 HTML encoding。
                正文中若有 <、>、& 符號，必須轉義為 &lt;、&gt;、&amp;。
                分隔線用「────────────」。
                區塊標題格式：<b>【標題名稱】</b>
                條列項目用「· 」開頭。
                數值變動用「→」與「↑ / ↓」標示。
                評論署名格式：🛸 <b>Grok</b>｜🛡️ <b>Claude</b>｜💎 <b>主編</b>｜🤖 <b>GPT</b>
                每則新聞末尾附標籤行（用 <code> 包住）：
                <code>IMPACT: 強利空/弱利空/中性/弱利多/強利多 | NARRATIVE: xxx | HORIZON: xxx</code>

                ════【終極排版警告】════
                你必須，且絕對必須：
                ① 所有【區塊標題】與 Agent 署名，一律用 <b>...</b> 包覆。
                ② 所有數值數據、IMPACT 標籤行，一律用 <code>...</code> 包覆。
                ③ 所有推文原文，一律用 <blockquote>...</blockquote> 包覆。
                如果漏掉任何一個 HTML 標籤，這份報告將被視為失敗，必須重新生成！

                ════ 報告結構（依序輸出）════

                <b>🛡️ Q-Silicon Institutional Research</b>
                <i>Daily Brief · {today_str}</i>
                ────────────

                <b>【今日市場模式】</b>
                今日模式：<b>risk_on / risk_off / neutral</b>（三選一，粗體標示）
                · 驅動因子 1：（一句話）
                · 驅動因子 2：（一句話）
                · 驅動因子 3：（一句話）

                ────────────

                <b>【數據儀表板】</b>
                【宏觀】
                · M2 → <code>xxx</code>（↑/↓ x%）
                · ICE DXY → <code>xx.xx</code>（↑/↓ x%）
                【幣圈】
                · MVRV Z-Score → <code>x.xx</code>（附估值信號：高估/低估/健康）
                · BTC OI → <code>$xxB</code>（↑/↓ x%）
                · BTC 交易所淨流入 → <code>xxx BTC</code>
                【AI】
                · LMSYS 模型排名 → （前三名）
                · Big Tech AI 資本支出 → （Amazon / Microsoft / Alphabet / Meta 近期投資規模或趨勢，可用億美元計）

                ────────────

                <b>【幣圈情報】</b>
                依序列出 Grok 找到的 3 則爭議新聞，每則格式：

                〔新聞 1〕<b>新聞標題</b>
                來源：xxx｜性質：<i>confirmed / likely / unverified rumor</i>
                摘要：（一至兩句）
                <code>IMPACT: 強利空/弱利空/中性/弱利多/強利多 | NARRATIVE: FUD/FOMO/Infra/Regulation | HORIZON: intraday/swing/cycle</code>
                🛸 <b>Grok</b>：（評論一句）
                🛡️ <b>Claude</b>：（評論一句）
                💎 <b>主編</b>：（評論一句）

                接著列出 5 則 X 推文，每則格式：
                〔推文 1〕<blockquote>推文原文</blockquote>
                可信度：（一句話）
                <code>IMPACT: 強利空/弱利空/中性/弱利多/強利多 | NARRATIVE: xxx | HORIZON: xxx</code>

                ────────────

                <b>【AI 產業情報】</b>
                依序列出 GPT 找到的 3 則暗盤動態，每則格式同幣圈（署名改為 🤖 GPT）。
                接著列出 5 則 X 推文，格式同上。

                ════ 嚴禁主編私自刪減新聞標題與推文原文！每區塊各 3 則新聞、5 則推文，保留原始內容！════
            """),
            expected_output="一份符合 Telegram HTML 格式、使用 <b>/<i>/<code>/<blockquote> 標籤排版的專業戰報，完整保留 3 則新聞與 5 則推文原文，並附各 Agent 評論與風險標籤。",
            agent=self.quant_strategist,
            context=[crypto_task, ai_task, review_task]
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, ai_task, review_task, final_report_task],
            process=Process.sequential
        )
        return crew.kickoff()

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from config import MODEL_CLAUDE, MODEL_GEMINI, MODEL_GROK, MODEL_GPT, MODEL_GPT_NANO
import scratchpad
from crew_output_parse import kickoff_to_pydantic
from schemas import AISection, CryptoSection
from tools import (
    ai_momentum_tool,
    ai_sector_market_tool,
    coinglass_data_tool,
    correlation_matrix_tool,
    cot_positioning_tool,
    cryptopanic_tool,
    grayscale_premium_tool,
    historical_analog_tool,
    econ_calendar_tool,
    etf_flow_tool,
    fear_greed_tool,
    financial_datasets_tool,
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
    valuation_anchor_tool,
)

logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")
# 1=加密研究員不掛載 sentiment_score_tool（少一輪 LLM 呼叫；BigQuery sentiment_score 可能為空）
_PIPELINE_SKIP_SENTIMENT_SCORE = os.getenv("PIPELINE_SKIP_SENTIMENT_SCORE", "").lower() in (
    "1",
    "true",
    "yes",
)


def _crew_parallel_research_enabled() -> bool:
    """啟用研究員 Task 拆分 + CrewAI async_execution 並行；CREW_DISABLE_ASYNC_RESEARCH=1 回退單一任務。"""
    return os.getenv("CREW_DISABLE_ASYNC_RESEARCH", "").lower() not in ("1", "true", "yes")


def _crypto_researcher_tools():
    core = [
        market_search_tool,
        newsapi_tool,
        rss_feed_tool,
        gnews_tool,
        coinglass_data_tool,
        rumor_scanner_tool,
        cryptopanic_tool,
        fear_greed_tool,
        etf_flow_tool,
        econ_calendar_tool,
        onchain_metrics_tool,
    ]
    tail = [
        correlation_matrix_tool,
        valuation_anchor_tool,
        cot_positioning_tool,
        grayscale_premium_tool,
        historical_analog_tool,
    ]
    if _PIPELINE_SKIP_SENTIMENT_SCORE:
        return core + tail
    return core + [sentiment_score_tool] + tail

# 每個角色的 LLM fallback chain：主 LLM 失敗時依序嘗試下一個
_FALLBACK_CHAINS: dict[str, list[str]] = {
    "grok":     [MODEL_GROK, MODEL_CLAUDE, MODEL_GPT],
    "gpt":      [MODEL_GPT, MODEL_CLAUDE, MODEL_GROK],
    "gemini":   [MODEL_GEMINI, MODEL_GPT, MODEL_CLAUDE],
    # 文稿潤稿主編：nano → 標準 GPT → Claude 降級
    "gpt_nano": [MODEL_GPT_NANO, MODEL_GPT, MODEL_CLAUDE],
}

_API_KEY_MAP: dict[str, str] = {
    MODEL_GROK:     "XAI_API_KEY",
    MODEL_GPT:      "OPENAI_API_KEY",
    MODEL_GEMINI:   "GEMINI_API_KEY",
    MODEL_CLAUDE:   "ANTHROPIC_API_KEY",
    MODEL_GPT_NANO: "OPENAI_API_KEY",
}

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
    區塊④【資金流向與精準操作 (Crypto)】（1 單邊 + 1 配對，由今日新聞動態選出）
    [QSREC_START]
    [{"asset":"TODAY_PICK_CRYPTO","direction":"LONG/SHORT","current_price":0,"entry":0,"target":0,"stop":0,"confidence":3,"category":"CRYPTO","trigger":"...","invalidation":"...","position_pct":8,"timeframe":"3-5天"}]
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


def build_crypto_final_prompt(*, ctx: str, prev_recs_ctx: str, today_str: str) -> str:
    """組裝加密最終戰報 prompt（集中管理，降低重複與漏改風險）。"""
    return dedent(f"""
        【加密市場戰報排版 — GPT 主編】
        {_QUOTE_RULE}
        {_NARRATIVE_CONSISTENCY_RULE}
        {_EDITOR_RULE}
        {_TELEGRAM_FMT}
        {_DASHBOARD_FMT}
        {_TOOL_TRUTH_RULE}
        {_CHATTER_FMT}
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_CRYPTO_TRADE_MUTEX_RULE}
        {_BRIEF_V2_RULE}
        {_HEDGE_FUND_BRIEF_RULE}
        {_READER_QUALITY_RULE}
        {_EXEC_SUMMARY_RULE}
        {_X_HIGHLIGHTS_SECTION_LABEL_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {ctx}
        {prev_recs_ctx}

        {_MTF_CONF_RULE}
        {_TRADE_RULE}

        {_CRYPTO_LAYOUT_RULE.format(today_str=today_str)}

        {_TRADE_JSON_RULE}

        {_FINAL_TEMPLATE_CRYPTO}
    """)


def build_ai_final_prompt(*, ctx: str) -> str:
    """組裝 AI 最終戰報 prompt（集中管理，降低重複與漏改風險）。"""
    return dedent(f"""
        【AI 市場戰報排版 — GPT 主編】
        {_EDITOR_RULE}
        {_TELEGRAM_FMT}
        {_DASHBOARD_FMT}
        {_TOOL_TRUTH_RULE}
        {_CHATTER_FMT}
        {_QUOTE_RULE}
        {_NARRATIVE_CONSISTENCY_RULE}
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_BRIEF_V2_RULE}
        {_HEDGE_FUND_BRIEF_RULE}
        {_READER_QUALITY_RULE}
        {_X_HIGHLIGHTS_SECTION_LABEL_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {_AI_RISK_BRIDGE_RULE}
        {ctx}

        {_MTF_CONF_RULE}
        {_TRADE_RULE}

        {_AI_LAYOUT_RULE}

        {_TRADE_JSON_RULE}

        {_FINAL_TEMPLATE_AI}
    """)


_STRUCTURED_IO_HEADER = dedent("""\
    【結構化輸出 — 資料引擎模式】
    你必須嚴格輸出符合指定 Pydantic schema 的 JSON 物件（系統以 output_pydantic 驗證）。
    禁止 Markdown、禁止 HTML 標籤、禁止 ``` 程式碼區塊包裝。
    所有字串為純文字；缺資料用 "N/A" 或 null／空陣列，勿捏造工具未回傳的價格或指標。
    """)

# Quant Strategist 最終任務追加；{recent_lessons} 由 crew.kickoff(inputs=...) 代入（勿改為 f-string）。
_REFLECTION_DYNAMIC_RISK_RULE = dedent("""\
    【Reflection Loop｜停損記憶與動態風控】
    以下為系統自 BigQuery 聚合之資料（可能為單行 JSON，或中性「無紀錄」句）：
    {recent_lessons}

    You are equipped with a **Reflection Loop**. When the payload is JSON, treat `by_sector` / `by_ticker` as **recent stopped-out clusters** (status HIT_STOP only).
    You **MUST** dynamically **reduce** risk budget and exposure (lower `position_pct`, fewer legs, or explicit neutral/watch) for any sector or ticker where `suggestion` is **reduce_exposure** or `stop_loss_count` is clearly elevated—**unless** a **strong, tool-backed** macro or idiosyncratic catalyst in your narrative **clearly** overrides it; if you override, state that override **explicitly** in `pick_reason` or `signal_conflict_summary` in one short sentence.
    **Differentiate** thesis invalidation vs. short-term market noise / whipsaw: prefer `monitor` buckets for single-stop names unless the JSON already flags `reduce_exposure`.
    若上列為中性繁中句（無 JSON）：維持一般風控，並可在 `signal_conflict_summary` 註明「無近期 HIT_STOP 聚合需調降」。
    """)


def build_crypto_structured_final_prompt(
    *, ctx: str, prev_recs_ctx: str, today_str: str, agreed_regime: str | None = None
) -> str:
    """最終任務：結構化 CryptoSection（無排版指令）。"""
    regime_lock = (
        f"\n【⚠️ Pipeline 鎖定 market_regime = {agreed_regime}】"
        f" market.regime 欄位與全文所有 regime= token 必須一律使用 {agreed_regime}，"
        f"嚴禁混用其他 regime 值。\n"
        if agreed_regime else ""
    )
    return dedent(f"""
        {_STRUCTURED_IO_HEADER}
        【加密 — 最終整合主編】
        {regime_lock}
        {_QUOTE_RULE}
        {_NARRATIVE_CONSISTENCY_RULE}
        {_TOOL_TRUTH_RULE}
        {_EARNINGS_ANALYSIS_WALL_STREET_RULE}
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_CRYPTO_TRADE_MUTEX_RULE}
        {_BRIEF_V2_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {_X_HIGHLIGHTS_SECTION_LABEL_RULE}
        {ctx}
        {prev_recs_ctx}

        {_MTF_CONF_RULE}
        {_SCENARIO_RULE}
        {_HIT_STOP_STRATEGIST_RULE}
        {_THINK_SHOW_ZONE_RULE}
        {_INSTITUTIONAL_VOICE_RULE}
        {_INSTITUTIONAL_PHASE_A_RULE}
        {_INSTITUTIONAL_PHASE_B_RULE}
        {_INSTITUTIONAL_PHASE_C_RULE}

        === 填入 CryptoSection 欄位 ===
        - report_title_date: 使用 {today_str}
        - exec_summary：3–5 則 bullet（見【Executive Summary】）；加密與美股主倉若方向明顯相反，其一則須框定跨資產組合邏輯。
        - market.regime / score_suffix / scorecard_lines：承接上一任務評分卡，regime 僅 risk_on|risk_off|neutral。
        - narrative_of_day：今日主敘事一句 ≤45 字。
        - investment_thesis_one_liner / thesis_supporting_points（3）/ thesis_contrary_points（3）/ key_assumptions_lines（2–4）/ narrative_invalidation_summary：見【華爾街級 Phase A】。
        - portfolio_framing_summary / scenario_probability_notes：見【華爾街級 Phase B】。
        - crypto_cycle_valuation_notes / equity_valuation_framing / event_calendar_lines：見【華爾街級 Phase C】。
        - macro_framework_lines：≤4 行宏觀 bullet。
        - dashboard：幣圈儀表板，每列 MetricLine；缺值 value="N/A"。
        - news：3 則 index 1–3；timestamp_line 必含 UTC+8；investment_takeaway 至少一個數字化數據，且勿重複儀表板已列之同一讀數；**每則** `pricing_note` 見【華爾街級 Phase B】。
        - x_highlights：選填；主題式摘要句，非 X 即時推文（見【區塊②b｜x_highlights】）。
        - chatter：2–3 則呢喃，含可信度與（未確認）。
        - pick_reason / risk_budget_summary / signal_conflict_summary：供區塊④，順序與 Gate 一致。
        - trade_legs：若可執行則填 ExecutableTradeLeg（含 internal_reasoning + narrative + **liquidity_execution_note**）；asset 勿含 $；R:R 等放於 rr 等字串欄位。
          star_rating 1–4。若無法給價則 trade_legs 留空（由管線渲染觀望模式）。
        - qsrec：與 trade_legs 方向一致；每筆含 internal_reasoning + narrative；category 僅 CRYPTO；數字欄位為 JSON number；填滿選分與 repeat_days 等 Gate 欄位；**`regime` 欄請省略**（管線會以 market.regime 對齊）。

        嚴禁在字串中出現字面 DATA_MISSING 方括號標記（改 N/A 或自然語）；嚴禁函數名 multi_timeframe_tool。
    """)


def build_ai_structured_final_prompt(*, ctx: str, agreed_regime: str | None = None) -> str:
    """最終任務：結構化 AISection（無排版指令）。"""
    regime_lock = (
        f"\n【⚠️ Pipeline 鎖定 market_regime = {agreed_regime}】"
        f" QSREC JSON 內 **請省略每筆 `regime` 欄**（管線會自動對齊 {agreed_regime}）；若誤填與主判定不一致將被覆寫。\n"
        if agreed_regime else ""
    )
    return dedent(f"""
        {_STRUCTURED_IO_HEADER}
        【AI 美股 — 最終整合主編】
        {regime_lock}
        {_QUOTE_RULE}
        {_NARRATIVE_CONSISTENCY_RULE}
        {_TOOL_TRUTH_RULE}
        {_EARNINGS_ANALYSIS_WALL_STREET_RULE}
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_BRIEF_V2_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {_X_HIGHLIGHTS_SECTION_LABEL_RULE}
        {_AI_RISK_BRIDGE_RULE}
        {ctx}

        {_MTF_CONF_RULE}
        {_SCENARIO_RULE}
        {_HIT_STOP_STRATEGIST_RULE}
        {_THINK_SHOW_ZONE_RULE}
        {_INSTITUTIONAL_VOICE_RULE}
        {_INSTITUTIONAL_PHASE_B_RULE}
        {_INSTITUTIONAL_PHASE_C_RULE}

        === 填入 AISection 欄位 ===
        - macro_bridge_lines：承上宏觀，勿重貼完整美債段；勿再逐字複誦加密儀表板已給之 VIX/BTC 讀數，必要時指稱「見上方儀表板」。
        - dashboard：AI 儀表板 MetricLine；**順序建議**：yfinance 族群（ai_sector_market_tool）→ FinancialDatasets（**NVDA+MSFT 各≥2 行**；其餘 watchlist 每檔≤3 行）→ ai_momentum（**≤2 行**）。yfinance 列 label 須含 ticker 與「yfinance」。
        - news：3 則 index 4–6，格式同加密新聞；investment_takeaway 勿重複儀表板已列之同一讀數；**每則** `pricing_note` 見【華爾街級 Phase B】。
        - x_highlights：選填；主題式摘要（見【區塊②b｜x_highlights】）。
        - chatter：2–3 產業鏈呢喃含可信度。
        - pick_reason / signal_conflict_summary / us_equity_allocation_note：遵守 AI 段 Gate（不重複今日風險預算整行）。
        - trade_legs：兩檔美股為主；每筆 internal_reasoning + narrative + **liquidity_execution_note**；star_rating 1–4；留空則渲染觀望。
        - qsrec：category 僅 EQUITY；與 trade_legs 對齊；每筆 internal_reasoning + narrative；**`regime` 欄請省略**（管線會以加密段 market.regime 對齊 JSON，避免與【今日市場模式】不一致）。

        嚴禁 DATA_MISSING 方括號標記字面；嚴禁 multi_timeframe_tool 字樣。
    """)

_INSTITUTIONAL_VOICE_RULE = dedent("""\
    【機構級寫作｜Bloomberg 式】
    讀者為專業經理人；文字如刀鋒，拒絕話癆與討好。
    - 禁用名詞教學：不解釋什麼是 VIX、RSI（直接給讀數與市場含義）。
    - 禁用口語連接與填充：雖然、但是、因為、所以、值得注意的是、綜合以上、總結來說、我們認為、由此可見。
    - 標點：因果並列優先用分號（；）銜接，避免「因為…所以…」拖句。
    - 數據驅動：主要陳述須緊扣具體數字或百分比（例：營收成長 65.5%；禁「表現很好」空話）。
    """)

_THINK_SHOW_ZONE_RULE = dedent("""\
    【思考區 vs 展示區（強制）】
    - 每筆 trade_legs 與 qsrec：先寫滿 `internal_reasoning`（多空權衡、數據衝突、選點依據；可較長）。
      該欄不會出現在 Telegram 戰報正文，也不會進入對外 QSREC JSON。
    - 再寫 `narrative`：僅保留榨乾後的 1～2 句展示用敘事；禁止把 internal_reasoning 整段貼進 narrative。
    - 每則 news：`internal_reasoning` 可放簡短研判草稿；`summary`／`investment_takeaway`／`editor_consensus` 僅留對外洗練句。
    """)

_INSTITUTIONAL_PHASE_A_RULE = dedent("""\
    【華爾街級 Phase A｜投資命題與假設（CryptoSection 必填）】
    - `investment_thesis_one_liner`：一句可檢驗主命題（≤90 字），須涵蓋**加密與美股**主軸或明確寫出跨資產邏輯；禁內部標籤。
    - `thesis_supporting_points`：**恰好 3 條**字串，每條 ≤72 字；須可對照儀表板或新聞中的具體讀數／事件。
    - `thesis_contrary_points`：**恰好 3 條**字串，每條 ≤72 字；為對稱反駁（流動性、宏觀、估值、監管等），禁只寫「波動大」。
    - `key_assumptions_lines`：**2–4 條**字串，每條 ≤80 字（利率路徑、盈利共識、流動性、資料可得性等）。
    - `narrative_invalidation_summary`：1–2 句 ≤160 字——**敘事級**失效條件（非單筆進場停損）：何種證據若出現則須重估本日主命題。若宏觀段已寫 VIX 期限結構為 **Contango**，失效條件**不得**單獨依賴「轉為 Backwardation」除非同段已給出期限結構來源與定義；否則改用**現貨 VIX 門檻**或**與上文一致**之可觀測條件。
    - 免責聲明由管線固定注入 Telegram，**勿**在 JSON 內自行撰寫長段法律免責。
    """)

_INSTITUTIONAL_PHASE_B_RULE = dedent("""\
    【華爾街級 Phase B｜組合、機率與新聞定價（CryptoSection + 每則 NewsItem）】
    - `portfolio_framing_summary`：2–4 句 ≤280 字——加密＋美股合計曝險意圖、淨方向、與 SPY／BTC 相關性直覺、是否對沖（無對沖亦須明說）。
    - `scenario_probability_notes`：**恰好三行**（字串內換行），每行 ≤72 字，**每行內容不要**再以 `·` 或 `•` 開頭（模板會自動加項目符號）；格式示例：
      樂觀：…（機率 30%）
      基準：…（機率 45%）
      悲觀：…（機率 25%）
      三個百分比須為整數且**合計 100**。
    - **每則** news（index 1–6）須填 `pricing_note`，**僅能**為下列字面之一（與模板 `<code>` 完全一致）：
      「未定價／增量資訊」「大致已定價」「已高度反應」——用於標註該則相對盤面是否已 priced-in。
    """)

_INSTITUTIONAL_PHASE_C_RULE = dedent("""\
    【華爾街級 Phase C｜估值錨、事件日曆、流動性（CryptoSection + trade_legs）】
    - `crypto_cycle_valuation_notes`：1–3 句 ≤220 字——BTC 週期位置與鏈上估值錨（NVT/MVRV 等）對價格含義；數字須與加密儀表板一致。**禁止**「下一次減半／減半前夕／區塊高度 840,000」等敘述（易與已發生事件混淆且非本管線鏈上驗證欄位）；週期僅能寫**工具已回傳**之 MVRV/NVT 或定性「減半後週期」等不含**未來具體日期與高度**之語句。
    - `equity_valuation_framing`：2–4 句 ≤320 字——AI 權值相對大盤、盈利修正／利率對倍數壓力；勿發明儀表未列之精確本益比。
    - `event_calendar_lines`：**3–6 條**字串，每條 ≤96 字，**每條開頭須含日期**（`MM/DD` 或 `YYYY-MM-DD`）＋事件類型（財報/Fed/期權到期/解鎖等）；僅寫已公告或可核之日程，**禁止捏造**未證實日期。**禁止**列入「BTC 減半／halving／區塊高度 840,000」等未經本管線鏈上高度工具驗證之日程（管線可能逕行移除）；期權名目金額等**僅能**寫入日曆列，**不得**剪貼進無關新聞的 `investment_takeaway`。
    - **每筆** `trade_legs`（加密與美股，可執行腿）須填 `liquidity_execution_note`：一句 ≤100 字——ADV/買賣價差/大額可行性或建議限價區間（定性即可）；加密可寫主要所深度。
    """)

_EDITOR_RULE = dedent("""\
    【主編共識與排版紅線】
    1. 【極致洗鍊｜手機優先】避險基金晨報語氣：高信號密度、零贅詞、不寫長篇「內心戲」推演。
    2. 【黑名單封殺】你的輸出【絕對禁止】包含以下字眼或結構：
       - 禁止印出「(嚴格要求...)」或「[IMPACT...]」等標籤。
       - 禁止印出任何 Python 函數名稱（如 multi_timeframe_tool）。
    3. 【專業交易欄位必備】每筆建議必須包含：進場、目標、停損、觸發模式、建倉邏輯、失效條件、倉位建議、敘事邏輯（欄位名須可辨識，供系統驗證）。
    4. 【量化風控必備】每筆建議必須包含：R:R、最大回撤風險、預期勝率（%）、Signal Score（0-100）。
    5. 【缺值處理】若關鍵欄位 N/A 超過 3 項，必須加註「低置信度」並說明資料缺失原因與替代指標（見【避險基金極簡閱讀】字數上限）。
    6. 【資料載荷】結尾 QSREC JSON 不得遺漏，且欄位需與交易內容一致。
    """)
_REGIME_POSITION_POLICY = dedent("""\
    【Regime 風險預算（硬規則）】
    - risk_off：單筆建議倉位上限 5%，總風險預算 20%，信心上限 ⭐️⭐️⭐️
    - neutral：單筆建議倉位上限 10%，總風險預算 40%
    - risk_on：單筆建議倉位上限 15%，總風險預算 60%
    必須在交易段落前輸出「今日風險預算」摘要，並讓每筆 position_pct 與 regime 一致。""")
_DATA_RULES = dedent("""\
    【新鮮度】新聞事件／報導時間戳須在 **36 小時內**（相對本輪管線執行時刻）；超時 **必須捨棄並重搜**，禁止把逾時素材改標為「分析」硬塞；仍無合格素材則走 partial tier／減則，**嚴禁捏造**。
    【嚴禁播報系統錯誤】若任何 Tool 回傳 `[DATA_MISSING...]`、`失敗` 或 `API 未設定`，絕對禁止將這些錯誤訊息寫成新聞！請直接忽略該工具的輸出。若無足夠真實新聞，寧可減少新聞數量，也絕不允許播報系統日誌！""")

_TOOL_TRUTH_RULE = dedent("""\
    【工具輸出與缺數敘述（防幻覺）】
    - **嚴禁**在任何可見欄位貼上工具內部字樣 **`[DATA_MISSING:...]`**（會觸發 Gate「資料缺失欄位」）；請改寫為自然語句或以 value=`N/A` 表示，並簡述原因（≤30 字）。
    - CoinGlass／ETF／爆倉／OI：若工具為 `[DATA_MISSING:coinglass_*]` 或含 401／Upgrade plan，僅能表述為「第三方衍生品數據源未回傳或訂閱方案不含該端點」；嚴禁寫成「資料庫 API 連線異常」「內部 API 故障」等未經證實說法。
    - 若儀表板已出現 Binance 備援、資金費率或多空比等數值，不得稱「籌碼面全缺失」；應寫「CoinGlass 不可用，已採備援／近似指標觀察短線情緒」。
    - **美股基本面（精簡）**：營收、淨利、現金流等敘述必須來自 `financial_datasets_tool` 回傳。儀表板 **僅要求 anchor：`NVDA`、`MSFT` 各至少兩行** MetricLine，label 皆含 **`FinancialDatasets`** 與該代號，優先 **營收**、**營收同比%**（次選 **自由現金流**；缺欄則 value=`N/A` 並 ≤20 字原因）。**其餘 watchlist 檔位**：每檔 **至多三行**（同上三指標擇優），避免儀表板過長；禁止整檔濃縮成單行卻在正文大段複述未列示之財務數字。
    - **AI 族群市場（可交易讀數）**：僅能複述 `ai_sector_market_tool` 回傳之 **SMH／SOXX／NVDA／MSFT／GOOGL／SPY** 收盤與 1D／5D 報酬；每標的一行 MetricLine，**label 須含 ticker 與「yfinance」** 字樣；禁止發明股價或報酬。
    - AI 儀表板（HuggingFace／OpenRouter／RSS）：**敘事參考、非股價訊號**；禁止發明工具未提供的欄位，**嚴禁**出現以下字樣作為指標名：「AI Token Market Cap」「OpenRouter API Request Rank」「OpenRouter Request Vol」「AI Sector Sentiment」「Error Rate（排行）」；**至多兩行**；僅能複述 `ai_momentum_tool` 回傳中 **排序最前之一至二則** 模型行或 RSS 備援標題（勿列 Top5）；缺資料則單行 value=`N/A`（≤30 字原因）—不得捏造數字。""")

_NEWS_FMT = dedent("""\
    【新聞資料欄位規格（純資料，非排版）】
    - 幣圈與 AI 共 6 則新聞，使用連續索引：1..6（禁止用 1./2./3. 取代欄位）。
    - 每則需包含：index、timestamp（UTC+8）、title、source_and_nature、summary、investment_takeaway、editor_consensus。
    - summary：1 句核心事實（≤40 字，禁止主觀評論）。
    - investment_takeaway：1~2 句（≤90 字）。**每一則**須含至少一個阿拉伯數字，且該數字須能對到**同一大段（加密或 AI）區塊①儀表板**已輸出之讀數（例：加密段寫「BTC 日線 RSI 38.6」時，儀表板須已有對應 RSI 讀數；可寫與儀表一致的小數）。**禁止**在儀表板未出現該列時寫入精確報價或比率（如 SOL 現價、BTC Dominance 百分比、未列標的之 OI）；缺欄則改寫質性句或「見上方儀表板」並改引用儀表既有指標。
    - **加密新聞（index 1–3）**：若引用 **BTC MA20／MA50 價位**，須與區塊① **`BTC MA20（日線）`／`BTC MA50（日線）`** 之 value 一致（管線可由 yfinance 注入；若該列 value 為 N/A 則不得寫精確 MA 價）。
    - **AI 產業新聞（index 4–6）**：**三則須為 AI／雲端／半導體供應鏈或模型基建之獨立事件**；**禁止**以加密資產盤面、VIX 期限結構或純 BTC 技術面作為任一則之主標題或主摘要（跨市場傳導僅可於 `internal_reasoning` 一句帶過，**不得**作為 `investment_takeaway` 主數字錨點）。`investment_takeaway` 的**主數字錨點**必須來自 **AI 區塊①**（優先 **yfinance 族群** 之收盤或 1D／5D%；次選 FinancialDatasets 營收／同比%／FCF；再次 HuggingFace 下載／按讚）。**禁止**以 **BTC／ETH／SOL 現價、BTC RSI、VIX、DXY** 等精確數字作為主論據（該類讀數屬加密段或「宏觀連結」）；**SPY 若已列於 AI 區塊① yfinance 列**可作為主錨點之一。**禁止**以未出現在 AI 區塊①的 SPY 數字當主論據。
    - **validate_report「投資解讀量化」**：渲染為 `<i>投資解讀</i>：…`；**同一段落內**須有至少一個數字錨點（可為負數費率如 -0.0008%、多空比、Put/Call、金額）；僅「見儀表板」而無任何數字會觸發 Gate。
    - editor_consensus：1 句（≤28 字）且點名具體標的。
    - **pricing_note（Phase B）**：每則必填，僅能為「未定價／增量資訊」「大致已定價」「已高度反應」之一；標註該事件相對現價是否已充分反應。
    - **跨板塊新聞**：單則若同時涉及加密與美股／AI，必須一句寫明傳導鏈（風險偏好、資金流、beta 等）；禁止無機制硬接。
    - 禁止輸出任何 HTML/Markdown 標籤與排版符號，僅輸出可映射 schema 的純文字欄位值。""")

_DASHBOARD_FMT = dedent("""\
    【儀表板資料欄位規格（純資料，非排版）】
    - 以一個 MetricLine 對應一個指標：label、value、可選 status_emoji（✅/❌/⬜）。
    - value 只放讀值或 N/A；不要夾帶 HTML/Markdown。
    - 缺資料時 value 請填 N/A，必要時在相鄰敘述欄位補充原因，不要同一欄塞多指標。
    - regime 評分卡：第一行給 market.regime + score_suffix（如（+4/6）），其餘逐行放入 scorecard_lines。
    - 宏觀利率硬規則：10Y/2Y/SOFR 僅允許 0~20%；利差僅允許 +/-1000bp；超界請填 N/A。
      ⚠️ 嚴禁捏造利率：若工具未回傳有效值，必須填 N/A，禁止根據記憶填寫任何百分比。
    - 不得混用單位（% 與 bp），不得把年份/成交量/情緒百分比誤寫成利率。
    - Source observability（SourceHealth/SourceErrors/SourceQuota）由 pipeline 注入，儀表板資料本身不要重複輸出。
    - 估值與動能並存時（例如 NVT 偏高但 RSI 偏低）：用一句話區分尺度——NVT 偏中長期網路價值／流量評估，RSI 偏短期動能；避免讀者誤解為同一維度自相矛盾。
    - 若 N/A 過多（超過 3 個），必須在報告中明確加入以下兩行：
      「資料缺失原因：[說明哪些數據源本日未回應]」
      「替代指標：[說明使用何種替代觀察]」
      Gate 系統會驗證這兩行是否同時存在，缺少任一行將阻擋推送。
    - **24h 爆倉**：若 CoinGlass／備援皆無清算數字，儀表板須至少一行點名「第三方未回傳 24h 爆倉」並引導讀者改看資金費率／OI／多空比；若全文儀表板完全未出現「爆倉」或「清算」字樣，組裝階段會自動補一行 ⬜ 備註（仍應優先由你主動寫入以免語氣重複）。
    - **BTC 均線**：若工具未在儀表板輸出 MA20／MA50，組裝階段可自動注入 **`BTC MA20（日線）`／`BTC MA50（日線）`**（yfinance 日線）；請勿在儀表板另寫與該備援相衝突的 MA 讀數。
    - **AI 區塊①順序（建議）**：先列 **ai_sector_market_tool（yfinance 族群）** → **financial_datasets（NVDA+MSFT 各≥2 行；其餘 watchlist 每檔≤3 行）** → **ai_momentum_tool（至多 2 行敘事參考）**，以利讀者區分「可交易讀數」與「開源熱度」。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質與可信度分級（A/B/C 或 0~100）、
    並標註是否已被主流媒體二次驗證（是/否），輸出 2~3 條。
    統一欄位順序（掃讀一致）：傳聞一句（未確認）｜來源：…｜可信度：…｜主流媒體二次驗證：是/否；勿把可信度寫在句首、勿省略「未確認」。
    格式範例（至少擇一）：
    - 「...（未確認）｜來源：供應鏈側寫｜可信度：B｜主流媒體二次驗證：否」
    - 「...（未確認）｜來源：社群截圖｜可信度：72/100｜主流媒體二次驗證：否」
    ⚠️ 每條必須包含「可信度：A/B/C」或「可信度：數字/100」，缺少此標記將觸發 Gate 驗證失敗。
    ⚠️ **（未確認）傳聞禁止標「可信度：A」**：A 僅用於官方或主流媒體已報導之可驗證事件；句中含「（未確認）」者，可信度請用 B 或 C（或數字分級換算後低於 75 分之等級）。
    🚫 若 rumor_scanner_tool 回傳 [DATA_MISSING] 或無任何可信傳聞，輸出單行「· 本日無可信傳聞」即可。
       **嚴禁在工具回傳空值或 DATA_MISSING 時自行捏造傳聞內容。**
    🚫 **禁止**以英文簡寫取代欄位名（如 `MSM re-verify`）；必須使用完整 **「主流媒體二次驗證：是」** 或 **「主流媒體二次驗證：否」**。""")

_REGIME_PARSE_RE = re.compile(
    r'(?:市場機制評分|市場機制|market[\s_]?regime|今日市場模式)[：:\s]*'
    r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)',
    re.IGNORECASE,
)
_CHATTER_CRED_RE = re.compile(
    r'可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b'
    r'|來源[：:]\s*[ABC](?:級|等級)?'
    r'|可信度\s*[ABC](?:級|等)?'
    r'|(?:Grade|Credibility)\s*[：:]\s*(?:A|B|C|\d{1,3})\b',
    re.IGNORECASE,
)


def _parse_regime_from_scorecard(scorecard_text: str) -> str | None:
    """從 regime_scorecard_tool 輸出中解析 risk_on/risk_off/neutral。"""
    m = _REGIME_PARSE_RE.search(scorecard_text)
    if not m:
        return None
    # Normalize variant spellings (risk-on, risk on) to canonical underscore form.
    raw = m.group(1).lower().replace("-", "_").replace(" ", "_")
    if raw.startswith("risk_on"):
        return "risk_on"
    if raw.startswith("risk_off"):
        return "risk_off"
    if raw == "neutral":
        return "neutral"
    return None


def _ensure_chatter_credibility(chatter: list) -> list:
    """Post-process chatter items: auto-append C-grade credibility marker if missing."""
    if not chatter:
        return chatter if chatter is not None else []
    result = []
    for item in chatter:
        text = item.text
        if not _CHATTER_CRED_RE.search(text):
            logger.warning("chatter item missing credibility marker, auto-injecting C grade")
            text = text.rstrip() + "｜可信度：C｜主流媒體二次驗證：否"
            item = item.model_copy(update={"text": text})
        result.append(item)
    return result


_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL 及當日選定美股標的等數值，
    以及 RSI(14)、MA20/MA50、VIX 期限結構等技術指標，
    必須直接使用上方【系統強制即時報價】+【技術指標與結構】Context；不得自行捏造或改寫。""")

_EARNINGS_ANALYSIS_WALL_STREET_RULE = dedent("""\
    【華爾街級財報分析｜美股／AI 標的】（凡觸及財報、法說、季報窗口或 exclusion【財報聚焦日】時必守）
    - **敘事骨架**（讀者版）：**一句結論**（營收／獲利相對敘事：僅能寫「優於／遜於／大致符合**已列新聞**之法說敘述」；無新聞佐證則僅能寫「季報數字已出／待法說」）→ **一句證據**（必含工具已列之**阿拉伯數字**：營收、營收同比%、FCF、毛利率等擇一，來自 `financial_datasets_tool` 或 AI 區塊① FinancialDatasets 列）→ **一句含義**（對估值倍數、Capex 週期、或指引不確定性之**機構式**一句，禁空談「長期看好」）。
    - **beat／miss／超預期（賣方口徑硬規則）**：**僅當該則新聞的 `title` 或 `summary` 字面出現**對照共識或預期的表述時，`investment_takeaway`／`editor_consensus`／區塊④ 方可使用 **beat、miss、超預期、遜於預期、優於共識、低於共識、EPS beat、revenue beat** 等字樣。可接受觸發字樣包含（中英擇一即可）：**共識、預期、預估、華爾街、分析師預期、Street、consensus、estimate、expected**。若標題／摘要**僅寫**「公布季報／營收／EPS 數字」而**無**上述對照語，**禁止**寫 beat/miss，僅能寫「季報數字已披露；與前季／同比見工具列」。
    - **前瞻指引／FY／次季展望**：**營收指引、EPS 指引、FY26、下季展望、raised／lowered guidance** 等**僅能**複述**同一則**已列新聞之 `title` 或 `summary` 字面；若新聞未載明，**僅能**寫「指引／FY 展望待法說或 IR 更新」，**禁止**從記憶或臆測補全。
    - **禁止**：臆造「共識 EPS 數值」「beat/miss **幅度**（如 cents／%）」「Street 預期具體數字」——除非**同一則新聞**正文已寫明；禁止複述記憶中的歷史季報；禁止與儀表板已列季報數字**矛盾**。
    - **主編共識／投資解讀**：須點名**定價**（已反應／增量資訊）與**下一個催化**（指引、下季能見度、監管、供應鏈），並與 `pricing_note` 一致；避免「震盪整理」「靜待明確」等無信息增益句。
    - **區塊④與 QSREC**：`pick_reason`、`signal_conflict_summary`、`trade_legs.narrative` 須能**回溯**到區塊①同一季報讀值或已報導法說要點；觀望須寫「財報後波動／指引不明」等**可驗證**理由，不得與多頭敘事無接縫跳轉。
    - **跨段**：加密段不得發明美股財報數字；`equity_valuation_framing` 須與當日利率敘事（宏觀）及財報線一致（倍數壓力／盈利韌性擇一論述，須有錨點）。""")

# Crypto／AI 研究員 task 共用注入（與逐行展開等價，避免重複字面值）
_CREW_RULE_BLOCK = (
    _DATA_RULES.rstrip()
    + "\n"
    + _TOOL_TRUTH_RULE.rstrip()
    + "\n"
    + _QUOTE_RULE.rstrip()
    + "\n"
    + _EARNINGS_ANALYSIS_WALL_STREET_RULE.rstrip()
)

_NARRATIVE_CONSISTENCY_RULE = dedent("""\
    【敘事與數據一致】引用 BTC/指數/均線時，須與【技術指標與結構】的趨勢描述一致：
    若 Context 為「多頭排列（價>MA20>MA50）」或現價高於 MA50，不得寫「跌破 MA50」或「跌破均線」；
    若為「空頭排列（價<MA20<MA50）」或現價低於 MA50，不得寫「站上 MA50」。不確定時改寫為「若跌破/若站上」等條件句。""")

_TRADE_RULE = dedent("""\
    · <b>$代幣/股票 (操作方向)</b>｜現價：$真實最新報價｜信心：[你必須在這裡輸出 1~4 顆 ⭐️ 符號，例如 ⭐️⭐️⭐️，絕對不可留白]
    · 進場：<code>$數值</code>｜目標：<code>$數值</code> (+Y%)｜停損：<code>$數值</code> (-Z%)
    · 風控：<code>R:R = 1:X</code>｜最大回撤風險：<code>-Z%</code>｜預期勝率：<code>W%</code>｜Signal Score：<code>S/100</code>
    · 觸發模式：（單行 ≤55 字，具體價位/時間框）
    · 建倉邏輯：（單行 ≤55 字，分批條件壓縮為短語）
    · 失效條件：（單行 ≤55 字，須有實質觸發，**禁止空白**）
    · 倉位建議：佔總資金比例（單行；**主 regime 為 neutral/risk_on 時嚴禁寫「依 risk_off」「高風險環境 risk_off」**）
    · 敘事邏輯：（單行 ≤35 字，點名催化或數據）
    請確保每個數值都用 <code> 標籤包覆，勿轉換為 Markdown 格式。""")

_RISK_MODE_RULE = dedent("""\
    【市場模式聯動風控】
    - 全文只能有一個主 market_regime（risk_on / neutral / risk_off）；嚴禁在不同段落切換 regime。
    - 允許情境分析條件句：可使用「若轉為 risk_off 則…」「若 VIX 突破 25 則切換至…」等 if…then 語句描述替代情境，但主 regime 判定不變。
    - 若今日市場模式為 risk_off：所有交易建議信心水準上限降一級（最高只能 ⭐️⭐️⭐️），並在敘事中明確標註「減倉/輕倉」。
    - 若主判定為 neutral 或 risk_on：嚴禁在敘事中寫「高風險環境 risk_off」「Market Regime: risk_off」「依 risk_off」等與主判定矛盾的 regime 標籤；**「· <b>美股部位框</b>」整行括號內僅能標示與【今日市場模式】相同之主判定**（neutral／risk_on／risk_off），主判定為 neutral 或 risk_on 時 **禁止** 寫「（risk_off）」。若要表達謹慎，僅可寫「VIX 偏高、採保守倉位／減碼」，且「今日風險預算」行須與主 regime 一致。
    - **加密區交易段落前固定三行順序**（validate_report 會截斷檢查）：① `本日選擇理由：…` ② `今日風險預算：…` ③ `訊號衝突摘要：…`（內文兩句精簡：空方主線｜多方主線；**勿**在 JSON 欄位內再寫「訊號衝突摘要：」「╌辯論摘要╌」「最強空方論點：」等小標——Jinja 已印標題；無衝突時內文可寫「無顯著多空衝突。」）→ 再進入交易條目。嚴禁把「本日選擇理由」放在風險預算或訊號衝突之後。
    - **AI 美股區交易段落前**：① `本日選擇理由：…` ② `訊號衝突摘要：…` →（可選美股部位框）→ `· $<b>…`；不重複輸出「今日風險預算」整行（見【AI 段風險預算銜接】）。""")

_PAIR_TRADE_RULE = dedent("""\
    【配對交易單位一致性】
    - 若輸出配對交易（如 $BTC / $SOL），必須明確標註「單位：BTC/SOL 比值」或「單位：價差」。
    - 現價/進場/目標/停損必須使用同一單位，禁止混用單幣現價與比值。
    - 若標的寫為 $BTC/SOL (LONG) 且單位為「比值」，表示看多 BTC/SOL 比值（相對強弱），建倉邏輯必須與之一致；嚴禁寫「多 BTC 疊加空 SOL」這類對沖腿描述。若策略確為對沖，應改標為 SHORT 比值或分拆兩筆單幣並分開列示。""")

_CRYPTO_TRADE_MUTEX_RULE = dedent("""\
    【加密 精準操作 唯一性】加密市場僅允許一段「資金流向與精準操作」主體（標題可寫或不寫括號內 Crypto，二擇一即可，勿重複兩種標題）。
    若已輸出含進場/目標/停損數值的可執行建議，嚴禁在同一加密區塊末尾再追加第二個「區塊④」或「觀望模式、暫不開新倉」段落；觀望模式僅能在完全不提供具體進出場價位時單獨使用。
    **validate_report 機檢**：自「資金流向與精準操作」起至 🤖 AI 主段之前，若出現**肯定**「觀望模式」「資料不足觀望」「暫不開新倉」任一字樣，則同段不得再出現三行皆帶數字的「進場／目標／停損」— 請二擇一（要觀望就全段勿列數字價位；要給單就刪觀望用語）。若意指「並非觀望／非觀望模式」，請寫「非觀望模式」或「已脫離觀望」等完整否定句，避免只寫「觀望模式」造成機檢誤判。勿在加密段誤貼「暫不提供股票進出場價格」（該句僅屬美股段）。""")

# tracker.py 解析用的機器可讀區塊格式（Telegram 不渲染，純文字標記）
# 欄位：asset=代號大寫不含$, entry/target/stop=純數字, target_pct/stop_pct=百分比數字,
#        confidence=1~4, category=CRYPTO|EQUITY, current_price=現價數字
_TRADE_JSON_RULE = dedent("""\
    === 系統強制驗證區塊 ===
    在報告最後輸出 `[QSREC_START]` 與 `[QSREC_END]` 包住的 JSON 陣列：
    [QSREC_START]
    [
      {"asset": "代號", "direction": "LONG/SHORT", "current_price": 數字, "entry": 數字, "target": 數字, "stop": 數字, "confidence": 數字, "category": "CRYPTO/EQUITY", "narrative": "敘事...", "trigger": "觸發條件", "invalidation": "失效條件", "position_pct": 數字, "timeframe": "持倉週期", "selection_score": 數字, "catalyst_score": 數字, "flow_score": 數字, "technical_score": 數字, "risk_fit_score": 數字, "execution_score": 數字, "alt_candidate_score": 數字, "score_gap": 數字, "repeat_days": 整數}
    ]
    [QSREC_END]
    規則：數字欄位不可加引號、asset 不含 $、必須是合法 JSON、所有建議放在同一陣列。
    評分欄位規則（0~100）：
    - selection_score（最終總分）
    - catalyst_score / flow_score / technical_score / risk_fit_score / execution_score（五維拆分）
    - alt_candidate_score（同類次佳標的分數）
    - score_gap = selection_score - alt_candidate_score（不得亂填）
    - repeat_days（連續同標天數，當天首次選用可填 0）
    可附加欄位：rr_ratio、max_drawdown_pct、expected_win_rate、signal_score、regime。
    P4 三情境分析欄位（confidence ≥ 3 強制填；< 3 可 null）：bull_scenario、base_scenario、bear_scenario。
    【方向唯一｜硬 Gate】同一 JSON 陣列內，每個 (category, asset) 組合**最多一筆**；禁止出現兩筆皆為 EQUITY+NVDA（或任一 ticker）卻一筆 LONG、一筆 SHORT。若盤點後發現兩筆同代號，請刪併為單一淨方向或改正其中一筆的 asset／direction 筆誤。若需多空對沖敘事，請改為**比值／價差**單筆（見【配對交易單位一致性】）或兩檔**不同 ticker**；否則 validate_report 會回報「QSREC 同資產方向互斥」並擋推送。
    【正文對齊】區塊④內每個 `· $<b>代號</b> (LONG)` 或 `(SHORT)` 交易行，其方向必須與 QSREC 內同 asset、同 category 的 `direction` 一致（加密／美股分開檢視）。""")

_MTF_CONF_RULE = dedent("""\
    === 交易建議（通用）===
    每筆必須呼叫 multi_timeframe_tool('標的')，僅輸出自然語言（禁止函數名）：
    - 三時框同向 → ⭐️⭐️⭐️⭐️
    - 兩同向一中性 → ⭐️⭐️⭐️
    - 分歧 → ⭐️⭐️ 或 ⭐️""")

_BRIEF_V2_RULE = dedent("""\
    【日報 V2｜決策優先與版面（硬規則）】
    1) 【今日主敘事】緊接在【今日市場模式】與其評分卡明細之後，必須單獨一行：
       · 今日主敘事：<b>…</b>（僅 1 句、≤45 字；總結當日最大驅動與對倉位的含義；不得與主 regime 矛盾）
    2) 【語氣校準】主 regime 為 neutral／risk_on，或關鍵資料為 N/A 導致不確定時：禁止「歷史底部明確」「絕對」「確定暴漲／見頂」「絕佳進場點」「必漲／必跌」；改用「若…則…」「在…條件下」「機率偏…」「證據仍不足」。
    3) 【儀表板可讀性】區塊①每行僅一個指標；若該數值為 <code>N/A</code>，必須換行另起一小點，並使用人類分析師語氣說明。例如：
       ✅ 正確：「· 備註：第三方 API 暫未提供最新下載數據」
       ❌ 錯誤：「· 備註：數據源正常回傳 N/A」或「API 失敗」
    4) 【Source 三行】區塊①儀表板內禁止輸出整行【SourceHealth】/【SourceErrors】/【SourceQuota】；pipeline 僅於後台 logger 記錄，讀者版 Telegram 不顯示。儀表板內若要交代資料健康，僅能用一句自然語言。
    """)

_AI_RISK_BRIDGE_RULE = dedent("""\
    【AI 段風險預算銜接（與加密段一致）】
    加密戰報上半部已宣告全報「今日風險預算」與主 regime；本 AI 段嚴禁再寫第二組與之衝突的「總風險預算 XX%」整行（避免讀者看到 40% 與 20% 兩套總框）。
    【validate_report 硬性順序（區塊④）】本段**必須**在「訊號衝突摘要」「美股部位框」「第一筆 · $<b>… 交易行前」先寫獨立一行「本日選擇理由：…」（僅屬 AI/美股，不可沿用加密段那一句）。違者系統判定「AI 區缺少本日選擇理由」並阻擋推送。
    【覆寫上方「交易段落前今日風險預算」】本段交易區前不要重複輸出「今日風險預算：…」整行；在「本日選擇理由」之後輸出「訊號衝突摘要：…」，再輸出（可選）一行：
    · <b>美股部位框</b>：兩檔合計建議不超過總資金 <code>10%</code>（主 regime 為 neutral）、<code>15%</code>（risk_on）、<code>4%</code>（risk_off）；括號內 regime **必須與全文【今日市場模式】主判定一致**（主判定 neutral／risk_on 時 **嚴禁** 在該行寫「（risk_off）」）。單筆仍須遵守【Regime 風險預算】之單筆上限；總組合曝險以上方加密段「今日風險預算」為準。
    """)

_READER_QUALITY_RULE = dedent("""\
    【讀者面一致（機構簡報）】
    - **禁止內部營運用語**：敘述段落（選擇理由、訊號衝突、新聞解讀、呢喃等）不得出現「pipeline」「BQ」「自動補註」「主編次日應…」等後台或編輯備註；同標延續僅用讀者向表述（如「連日維持與昨日相同建議標的」開頭之一句），其後接市場理由。（尾端 [QSREC_START] JSON 載荷不在此限。）
    - **VIX 措辭**：若【今日市場模式】評分卡將 VIX 列為中性區間（⬜ 或該項 (0) 分），正文、宏觀連結、AI 段避免「飆升」「恐慌性」等與中性區間矛盾的詞；若波動邊際升高，請寫「相對前日變化」或「仍處評分卡區間但邊際走高」。
    - **新聞跨域**：單則〔新聞〕若連結 BTC／加密與美股／AI 板塊，該則至少一句寫明傳導鏈（風險偏好、去槓桿、同日資金流或 beta 等）；禁止無機制的一句硬接。列為傳聞或 Unverified 者須降調為市場討論。
    - **🤖 AI 段「本日選擇理由」**：首句為可執行結論（方向／框架），其後至多 2 句佐證；其餘分流至「訊號衝突摘要」。全段宜 ≤約 120 中文字。
    - **trade_legs.position_pct**：結構化輸出每筆必填正數百分比（與 regime 單筆上限一致），禁止空字串，讀者版交易卡須顯示具體建議倉位。組裝階段會將**兩檔及以上美股**合計縮放至與主 regime 一致之合計上限（neutral 10%／risk_on 15%／risk_off 4%），並先逐筆壓至單筆上限。
    """)

_ALT_PICK_DIVERSITY_RESEARCH_RULE = dedent("""\
    【候選多樣性｜研究員】
    在研判／新聞內文須至少點名 2 個「不在」【避免重複】中「過去 3 天已建議標的」清單內的替代代號（若該段未列出清單，則點名 2 個與你首選主線不同的代號），
    各用一句說明為何未選為今日主線，再收斂至最終新聞焦點與標的。
    若提示含「昨日」或 BigQuery 昨日 QSREC 主標／首選代號：上述 2 個候選須**明確異於**該主標（不可僅重述同一 ticker），除非後續區塊④已採「重複選用理由」路徑。
    **產業／市值廣度**：除非當日新聞主角無可替代，否則優先從**與昨日兩檔美股不同產業或不同市值帶**的標的中選主線；NVDA／MSFT／BTC 等僅在催化明確或退階敘事時作首選，避免讀者感覺「永遠同一組票」。
    """)

_HIT_STOP_STRATEGIST_RULE = dedent("""\
    【停損系統回饋｜主編必答】若前置蒐集或【避免重複】曾出現「觸及停損」或 HIT_STOP 相關列點：必須在 signal_conflict_summary 中反映。⚠️ 嚴禁照抄「因近期停損，是否調降...」這種問答句格式！請用流暢的機構語氣直接陳述結論。例如：「受近期連續停損影響，已將權重降至 3% 並下調信心星級以防禦風險。」若無停損，可寫「無近期停損回饋，權重未因 HIT_STOP 調整」。
    """)

_GATE_VALIDATE_PICK_RULE = dedent("""\
    【validate_report 動態選幣／選股（與 main.py 機檢對齊｜違者 STRICT_CONSISTENCY_GATE 擋推送）】
    1) **兩段各寫一次「本日選擇理由：」**——加密區塊④寫**加密專用**一句；🤖 AI 市場區塊④再寫**美股專用**一句。嚴禁只寫在加密段而 AI 段留白。
    2) **固定順序（加密區塊④）**：`本日選擇理由：…` → `今日風險預算：…` → `訊號衝突摘要：…` → 第一筆 `· $<b>標的` 交易行。（理由內文勿出現「今日風險預算」「訊號衝突」開頭行，以免截斷錯誤。）
    3) **固定順序（AI 區塊④）**：`本日選擇理由：…` → `訊號衝突摘要：…` →（可選）`· <b>美股部位框</b>：…` → `· $<b>標的` 交易行。
    4) **加密理由**（純文字 ≥34 字）：須滿足下列**任一**——(a) 同句（或連續一段）內可讓系統辨識 **≥2 類**催化／鏈上線索關鍵詞，建議從「新聞／催化／ETF／監管／鏈上／交易所／淨流／資金費率／多空比／OI／未平倉／現貨／清算／**期貨／衍生品／CME／恐慌貪婪（恐懼貪婪）**」等任選**兩個不同概念**寫入；(b) **1 類**催化＋明確 **大型幣／流動性／退階／缺乏其他催化** 等退階語；(c) **1 類**催化且全文 **≥72 字**並**逐一點名** QSREC 內**每一檔**加密 asset（含比值如 BTC/SOL 須**同時出現 BTC 與 SOL** 字樣）。
    5) **美股理由**（純文字 ≥38 字）：須滿足下列**任一**——(a) **≥2 類**基本面／新聞線索，請【務必】從以下關鍵詞池中直接選用至少兩個字眼寫入句子：「新聞／財報／法說／資料中心／GPU／拉貨／Capex／合約／指引／IPO／核電／基礎設施」；(b) **1 類**＋直接寫出「權值／大型股／ETF／BOTZ／ARKQ／流動性」等退階語；(c) **1 類**且 **≥80 字**並點名兩檔 ticker（與 QSREC EQUITY 一致）。
    6) **【最高警戒：昨日標的對照】** 若你今日推薦的代號與【避免重複】區塊的標的**完全相同**：
       你【必須】在「本日選擇理由」的【最開頭前 6 個字】寫上「重複選用理由：」。
       ✅ 正確範例：「重複選用理由：BTC 跌破 MA50，防禦性空單具備連日持有價值...」
       ❌ 錯誤範例：「本日推薦 BTC 是因為...」或「World Foundation 大額減持...」
       絕對禁止遺漏此前綴，否則系統將視為惡意重複推單並強制攔截！
       * 絕對強制：QSREC JSON 內的 score_gap 欄位【絕對不能小於 12.00】！若你決定連持昨日標的，請直接給予 score_gap=15.00 等高分差，否則系統 Python Gate 將直接崩潰並攔截你的報告！
       * 最佳解法：請直接從今日的新聞催化劑中選擇【全新】的標的，避開這個複雜的重複檢查。
    7) **美股輪動（最常漏）**：若【上期建議追蹤】或任務提示顯示「昨日兩檔美股 ticker」與今日 QSREC **完全一致**，**🤖 AI 區塊④** 的 `本日選擇理由：` **整段內**必須含 **`重複選用理由：`**（或 **`重複選股理由：`**／**`連日維持`**／**`維持昨日兩檔`** 等系統認可片語）——**寫在加密段無效**；並確保兩檔 ticker 代號仍出現在理由或緊隨交易行。
    8) **禁止貼工具錯誤碼**：戰報正文嚴禁出現字面 **`[DATA_MISSING:`**（validate_report 會當成「資料缺失欄位」）；缺資料僅能寫 `<code>N/A</code>` 或一句「第三方資料源未回傳」。
    9) **QSREC 與區塊④方向一致**：JSON 內每一檔 `asset` 的 `LONG`/`SHORT` 須與對應 `· $` 交易行括號內方向相同；同一 category 下同一 ticker 不得在 QSREC 出現兩筆相反方向（機檢硬擋）。
    """)

_EXEC_SUMMARY_RULE = dedent("""\
    【執行摘要（Executive Summary）— 報告最頂部，CIO 30 秒閱讀】
    在 exec_summary 欄位填入 3~5 條 bullet，每條 ≤50 字，涵蓋：
    · 今日核心 Thesis（一句話說明最大驅動力）
    · 最高信心交易（標的 + 方向 + 簡要理由）
    · 主要尾部風險（最可能讓部位失效的一個因子）
    · 宏觀立場（利率/美元/VIX 對今日操作的含義）
    · 市場模式摘要（regime + 主要訊號來源）
    · **語氣與節奏**：每條優先「主詞＋一因一果」短句；單條內避免用分號串超過兩個轉折；讀起來像口播給 CIO，避免堆疊術語與長從句。
    · **與主 regime 對齊**：主判定為 neutral 或 risk_on 時，摘要用語須一致——避免「極致防禦」「全面去槓桿」等僅適用主 risk_off 的強語氣（除非該 bullet 為明確 if…then 替代情境）。
    · **分域敘事**：同一 bullet 內**禁止**無因果硬併「加密專屬題材」與「美股 ticker／財報句」。若需跨域，該 bullet **必須**用一句點明傳導（例：風險偏好／流動性／同一供應鏈或監管事件）；其餘加密 thesis 只寫加密 bullet，美股只寫美股 bullet。
    · **跨資產框定**（與上款並存）：僅當加密主倉與美股主倉方向**明顯相反**時，**必須**用其中一則 bullet（≤40 字）寫清**組合邏輯**（beta 對沖／sector tilt／期限或政策因子分離／僅小倉結構多 擇一），避免讀者以為自相矛盾。
    · **去重**：3～5 條內避免**兩條以上**重複同一維度組合（例如多條同寫 VIX＋恐懼指數＋資金費率）；儘量 **一條宏觀／波動**、**一條加密技術或情緒**、**一條當日主題**（法律／地緣／單一催化）各帶增量訊息。
    · **禁統計口號**：不得單獨使用「歷史顯示／統計上常見／往往反彈」等無來源回測句；若需提及極端恐懼，僅能寫**當日工具讀值**（例：Fear&Greed=14 屬 Extreme Fear）並可選一句定性，**禁止**宣稱具體歷史勝率或樣本除非該數字來自工具輸出。
    格式範例：「→ BTC 多頭排列完整，ETF 淨流入連三日，進場信心 4 星」
    ⚠️ 嚴禁重複正文內容、嚴禁泛泛而談（如「市場混亂」「保持謹慎」）。""")

_HEDGE_FUND_BRIEF_RULE = dedent("""\
    【避險基金極簡閱讀（手機優先，與 Gate 對齊）】
    - 語氣：多空避險基金晨報——只給可執行結論與必要證據，禁止長篇教學、重複鋪墊、自我辯論。
    - **精緻度**：段落之間留一條「讀者腦內換氣」— 先結論再一句證據；避免單段內把加密破位與個股財報硬縫成一句，除非已寫明因果鏈（見【執行摘要】分域敘事）。
    - **必留關鍵字**（系統會驗證）：加密段須含「今日風險預算」「訊號衝突摘要」「本日選擇理由」；AI 段須含「訊號衝突摘要」「本日選擇理由」（AI 段不重複「今日風險預算」整行，見【AI 段風險預算銜接】）。
    - 「本日選擇理由：」可為單行或連續短段，但**必須完整出現在**「今日風險預算／訊號衝突／第一筆 · $ 交易行」**之前**；並遵守【validate_report 動態選幣／選股】的長度與關鍵詞／點名規則。
    - 宏觀框架（🏛️）：≤4 行 bullet，每行 ≤60 字。
    - 呢喃／傳聞：維持每條 1 句，總長寧短勿長。
    - **數字錨點**：VIX／BTC 現價／關鍵均線等已在區塊①列示者，核心新聞與呢喃**避免再次完整複誦同一數字**；必要時指稱「見儀表板」或只寫 delta／情境。
    - **交易卡失效條件**：若寫入具體 **MA 價位、VIX 門檻、現價比較**，須與**同段或宏觀已列讀數**一致；儀表未列之價位不得憑空填寫。
    """)

_X_HIGHLIGHTS_SECTION_LABEL_RULE = dedent("""\
    【區塊②b｜x_highlights】選填；內容為**主編主題式觀點摘要**（非即時 X API 時間軸、亦非單則推文截錄）。無資料可留空；若有，每條須可獨立閱讀，勿宣稱為官方推文原文。
    """)

_CRYPTO_LAYOUT_RULE = dedent("""\
    === 排版順序（Crypto）===
    1) <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
    1b) 【執行摘要】（exec_summary，見【Executive Summary】規則）：3~5 條 bullet，置於標題之後、上期建議追蹤之前。
    2) 【上期建議追蹤】：若提示區已給 HTML，僅能原樣貼上一段、嚴禁自行增刪列或補寫歷史進場（後端亦會覆寫為 BigQuery 權威版本）。
    3) 【今日市場模式】與評分卡明細（取自 review_task）
    3b) 【今日主敘事】一行（見【日報 V2】）
    4) 🏛️ 宏觀框架（取自 macro_context_tool）
       【強制輸出以下四行，若工具失敗填 `N/A`，但行本身不可省略】
       · 📐 BTC 相關係數：BTC/SPX X.XX｜BTC/DXY X.XX｜BTC/GLD X.XX｜BTC/NDX X.XX（取自 correlation_matrix_tool；若失敗填 N/A）
       · 📊 估值錨：MVRV X.XXx（區間）｜NVT XX（區間）｜BTC Dominance XX%（取自 valuation_anchor_tool；若失敗填 N/A）
       · 🕰 歷史類比：最近似 YYYY-MM-DD（相似度 XX/100），30日後 +/-X.X%｜中位勝率 X/3（取自 historical_analog_tool；若失敗填 N/A）
    5) 📊 加密市場：
       - 區塊① 儀表板（宏觀/技術/籌碼；嚴格套用儀表板格式）
         【強制加入以下兩行至儀表板，若工具失敗填 `N/A`，但行本身不可省略】
         · 🏦 CME COT：機構 +X,XXX（週▲/▼）｜槓桿 +X,XXX（週▲/▼）（取自 cot_positioning_tool；若失敗填 N/A）
         · 🔒 GBTC X.XX%｜ETHE X.XX%（取自 grayscale_premium_tool；若失敗填 N/A）
       - 區塊② 核心新聞 3 則（〔新聞 1〕～〔新聞 3〕，套用新聞格式）
       - 區塊②b 主題式觀點摘要（x_highlights；無資料可跳過，見【區塊②b｜x_highlights】）
       - 區塊③ 市場呢喃與傳聞 2~3 條
       - 區塊④ 資金流向與精準操作：1 單邊 + 1 配對
         【動態選幣規則】禁止每次固定選 BTC/SOL。必須根據以下優先順序動態選出本日標的：
         (a) 優先選今日新聞中有明確催化劑的幣種（如 ETF 核准/拒絕、主網升級、大額清算、機構買入）
         (b) 次選鏈上指標異動最顯著的幣種（SOPR 偏離/交易所淨流出/OI 暴增）
         (c) 最後才考慮 BTC/ETH 等大型幣（僅在無其他明顯催化劑時）
         配對交易必須選擇強弱分化最明顯的兩幣，禁止用 BTC/SOL 當預設配對
         【強制對齊規則】區塊④推薦的兩檔標的，【必須】是你在區塊②新聞中點名看好/看空的標的！嚴禁在新聞寫 A，交易卻無故選擇舊標的 B。除非舊標的出現極端技術面破位，否則優先交易今日新聞的主角。
        【昨日標的對照】提示區「過去 3 天已建議標的」＋ BigQuery 昨日 QSREC：若本日加密 QSREC 與昨日**完全相同**（同幣種／同配對），必須二選一：(1) 至少更換一檔或一改配對腿；(2) 在「本日選擇理由」首段寫明「重複選用理由：〔全新催化／連日持有依據〕」，且 QSREC 需填可驗證分差（score_gap，預設需 >= 12）。否則 validate_report 硬性失敗並整報重試。
         每次必須說明「本日選擇理由：…」（完整規則見【validate_report 動態選幣／選股】；須寫在今日風險預算／訊號衝突／第一筆 · $ 交易行之前）
         【情境分析】每筆信心 ≥ 2 星時，三情境**僅填** trade_legs / QSREC 的 bull/base/bear_scenario 欄位（供結構化驗證）；讀者版 Telegram 精簡交易卡**不**另印情境段落，勿在正文重複貼三情境。
    6) 最後必須輸出 QSREC JSON 區塊""")

_SCENARIO_RULE = dedent("""\
    【三情境分析（P4 新增 | 信心 ≥ 2 星強制填入）】
    每筆 confidence ≥ 2 的 QSREC，在 QSREC JSON 內必須補充以下三個欄位（字串，≤40字/項）：
    · bull_scenario  — 🐂 樂觀情境：目標價 + 觸發條件（例：突破 70k 且 ETF 淨流 >5億 → 目標 76k）
    · base_scenario  — ⚖️ 基準情境：預期走勢 + 估計機率（例：震盪整理後突破，機率 55%）
    · bear_scenario  — 🐻 悲觀情境：失效位 + 觸發條件（例：跌破 63k 且資金費率轉負 → 止損）
    confidence < 2 時可留 null，但不得輸出空字串。""")

_DEBATE_SUMMARY_RULE = dedent("""\
    【Risk Critic 辯論摘要（P4 新增 | 必填）】
    Risk Critic 任務輸出末尾用兩句話總結多空（可各一行）；主編（quant_strategist）將精髓**轉寫**進 JSON 的 `signal_conflict_summary`：
    · 禁止輸出「╌辯論摘要╌」「最強空方論點：」「多方反駁核心：」等框架字樣（讀者版模板已印「訊號衝突摘要：」）。
    · 內文僅保留可讀結論：空方一句、多方一句（可用全形｜同一行），勿整段複製辯論逐字稿。""")

_AI_LAYOUT_RULE = dedent("""\
    === 排版順序（AI）===
    1) 🏛️ 宏觀框架：本戰報將接在加密戰報之後，前段已含完整宏觀數據；本節僅輸出「承上宏觀」+ 一句主編共識（如 10Y/VIX 對美股影響），勿重複貼上美債/SOFR/利差整段。
    2) 🤖 AI 市場：
       - 主標題固定輸出 `🤖 AI 市場`；禁止改寫為「🤖 AI 與美股市場」或同義變體，且整篇只能出現一個 AI 主標題。
       - 區塊① AI 儀表板：**先** yfinance 族群（SMH／SOXX／NVDA／MSFT／GOOGL／SPY）**再** FinancialDatasets（**NVDA、MSFT 各≥2 行**；其餘 watchlist **每檔≤3 行**）**最後** 開源動能 **至多 2 行**（敘事參考）；缺值 <code>N/A</code>
       - 區塊② AI 產業新聞 3 則：必須與幣圈完全相同格式，逐則以 `〔新聞 4〕[MM/DD HH:MM UTC+8]` … `〔新聞 6〕[MM/DD HH:MM UTC+8]` 開頭（嚴禁只用英文標題起句、嚴禁省略 UTC+8），主題涵蓋基建/投資案/模型各 1
       - 區塊②b 主題式觀點摘要（x_highlights；無資料可跳過，見【區塊②b｜x_highlights】）
       - 區塊③ 產業鏈呢喃 2~3 條（每條必含可信度：可寫「可信度：B」或「來源：B級」或 0~100 分，與加密呢喃／傳聞區格式對齊，供系統驗證）
       - 區塊④ AI 精準操作 2 檔：
         【新聞格式再確認】區塊②三則必須各以 `〔新聞 4〕`…`〔新聞 6〕` + `[MM/DD HH:MM UTC+8]` 開頭，含 <blockquote> 摘要，嚴禁縮成 `1. 2. 3.` 段落。
         【動態選股規則】禁止固定使用特定股票。必須根據以下優先順序動態選出本日 2 檔：
         (a) 優先選今日 AI 新聞中直接點名且有具體財務/產品事件的美股（如財報、拉貨、合約）
         (b) 次選 **ai_sector_market_tool** 已列之強弱標的或 **ai_momentum_tool** 模型名對應之上市股票（如 Meta、Microsoft、AMD）
         (c) 最後才考慮 AI 基建通殺標的（如 ETF BOTZ/ARKQ）
         (d) **廣度**：兩檔盡量橫跨不同子產業或市值帶（雲／晶片／設備／軟體等）；避免連日同為 NVDA+MSFT 組合除非當日新聞主角僅此二者且已走【重複選用理由】路徑。
         【強制對齊規則】區塊④推薦的兩檔標的，【必須】是你在區塊②新聞中點名看好/看空的標的！嚴禁在新聞寫 A，交易卻無故選擇舊標的 B。除非舊標的出現極端技術面破位，否則優先交易今日新聞的主角。
         【昨日標的對照】若本日兩檔美股 QSREC 與昨日 BQ 紀錄**完全相同**，必須更換至少一檔，或在 **🤖 本段**「本日選擇理由」內寫明「重複選用理由：…」（勿只寫在加密段），且 QSREC 需填可驗證分差（score_gap，預設需 >= 12）。否則 validate_report 硬性失敗。
         每次必須說明「本日選擇理由：…」（**僅寫於本 AI 段**，完整規則見【validate_report 動態選幣／選股】；須寫在訊號衝突／美股部位框／第一筆 · $ 交易行之前）
         【美股交易卡價位｜硬規則】每檔 `trade_legs` 的 `current_price`、`entry`、`target`、`stop` 須為**具體數字**（可含千分位；模板會加 $）；**禁止** `N/A`、`$N/A`、`TBD`、空字串充當可執行價。若 `multi_timeframe_tool` 或報價路徑無法取得可信價位：改為**觀望模式**並宣告「暫不提供股票進出場價格」，**勿**輸出帶 N/A 的精準操作行。（管線組裝會**備援**以 yfinance 最近收盤補現價／進場，並在 R:R 與最大回撤欄位可解析時**機械推算**目標／停損；仍以工具即時價為優先，備援僅降低 Gate「不可執行」誤報。）
    3) 最後必須輸出 QSREC JSON 區塊""")


def _make_llm(model: str, *, max_retries: int = 3, timeout: int = 120) -> LLM:
    """建立單一 LLM 實例，自動從環境變數取得對應 API key。"""
    env_key = _API_KEY_MAP.get(model, "")
    api_key = os.getenv(env_key) if env_key else None
    return LLM(model=model, api_key=api_key, max_retries=max_retries, timeout=timeout)


def _make_llm_with_fallback(role: str, *, max_retries: int = 3, timeout: int = 120) -> LLM:
    """嘗試 fallback chain 中第一個有 API key 的 model；全部缺 key 則用 chain 首項（讓 runtime 報錯）。"""
    chain = _FALLBACK_CHAINS.get(role, [])
    for model in chain:
        env_key = _API_KEY_MAP.get(model, "")
        api_key = os.getenv(env_key) if env_key else None
        if api_key:
            if model != chain[0]:
                logger.info("LLM fallback: role=%s, primary=%s unavailable (no key), using %s", role, chain[0], model)
            return LLM(model=model, api_key=api_key, max_retries=max_retries, timeout=timeout)
    # 全部都沒有 key，用 primary 讓 runtime 報出有意義的錯誤
    logger.warning("No API key found for any model in %s fallback chain %s", role, chain)
    return LLM(model=chain[0] if chain else "openai/gpt-4o-mini", max_retries=max_retries, timeout=timeout)


def _get_llms_for_crew(use_fallback_llm: bool) -> dict:
    """Primary 依 fallback chain 選可用 LLM；use_fallback_llm=True 時全用 GPT 降低凌晨靜默失敗。

    正常路徑：
      researcher       → Grok（real-time 資料 + tool calling）
      risk_critic      → Gemini 3 Flash（thinking + 長上下文辯論）
      quant_strategist → Gemini 3 Flash（thinking + structured outputs）
    """
    if use_fallback_llm:
        gpt = _make_llm(MODEL_GPT)
        return {"grok": gpt, "gpt": gpt, "gemini": gpt, "gpt_nano": gpt}
    return {
        "grok":     _make_llm_with_fallback("grok"),
        # 5→4：503/超時重試尾延遲在長管線中會明顯疊加；仍保留足夠韌性
        "gemini":   _make_llm_with_fallback("gemini", max_retries=4, timeout=180),
        "gpt_nano": _make_llm_with_fallback("gpt_nano", max_retries=3, timeout=60),
    }


class CryptoResearchCrew:
    def __init__(self, use_fallback_llm: bool = False):
        llms = _get_llms_for_crew(use_fallback_llm)
        grok, gemini = llms["grok"], llms["gemini"]

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，產出 3 則高衝擊幣圈新聞。",
            backstory="冷靜量化研究員，專注流動性、槓桿與聰明錢行為。",
            llm=grok,
            tools=_crypto_researcher_tools(),
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席幣圈風險審計員",
            goal="對幣圈新聞做反向辯論，以評分卡判定 market_regime。",
            backstory="反身性風險審計者，負責挑錯、驗證與量化機制判斷。",
            llm=gemini,
            allow_delegation=False,
            tools=[regime_scorecard_tool, macro_context_tool],
            verbose=_VERBOSE,
        )

        self.quant_strategist = Agent(
            role="機構策略主編（加密市場）",
            goal="整合研究成果，輸出戰報上半部。",
            backstory="最終排版與風控守門員；嚴守【思考區／展示區】與【機構級寫作】Bloomberg 式洗練。",
            llm=gemini,
            tools=[coinglass_data_tool, ml_quant_tool, multi_timeframe_tool],
            verbose=_VERBOSE,
        )

    def run(
        self,
        exclude_context: str | None = None,
        price_context: str = "",
        prev_recs_block: str = "",
        agreed_regime: str | None = None,
        langgraph_debate_context: str | None = None,
        recent_lessons: str = (
            "[系統反思記憶] 近期無停損紀錄，請維持客觀的風險控管。"
        ),
    ):
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
        regime_lock_notice = (
            f"\n【⚠️ Pipeline 鎖定 market_regime = {agreed_regime}】"
            f" 全文 regime 欄位必須一律使用 {agreed_regime}，嚴禁輸出其他 regime 值。\n"
            if agreed_regime else ""
        )
        debate_ctx = (
            f"\n【LangGraph 辯論摘要（必須納入最終判斷）】\n{langgraph_debate_context}\n"
            if (langgraph_debate_context or "").strip() else ""
        )
        _sentiment_instr = (
            "· sentiment_score_tool(news_and_tweets=<將上方新聞標題與摘要拼接後傳入>)（可選：時間緊可跳過；情緒 -1～+1）\n"
            if not _PIPELINE_SKIP_SENTIMENT_SCORE
            else "· （PIPELINE_SKIP_SENTIMENT_SCORE：勿呼叫 sentiment_score_tool）情緒維度請綜合 fear_greed_tool 與新聞語意於研判中簡述。\n"
        )

        _crypto_common_header = dedent(f"""
            {_CREW_RULE_BLOCK}
            {excl}
            {debate_ctx}
        """).strip()

        if _crew_parallel_research_enabled():
            logger.info("CryptoResearchCrew: parallel researcher tasks (async_execution x3) enabled")
            crypto_data_task = Task(
                description=dedent(f"""
                    【加密市場 — 純數據與鏈上（Grok｜可與其他子任務並行）】
                    {ctx}
                    {_crypto_common_header}
                    === 必須呼叫 ===
                    · coinglass_data_tool：格式 'metric:SYMBOL'（預設 BTC）
                      必查 BTC：funding_rate / liquidations / long_short_ratio / options_info
                      若研判涉及 ETH/SOL 等，額外查 'funding_rate:ETH'、'liquidations:SOL' 等
                    · fear_greed_tool()
                    · etf_flow_tool()（禁止猜測 ETF 數字）
                    · onchain_metrics_tool()（SOPR / 交易所淨流向 / 活躍地址 / NUPL）

                    產出：結構化 bullet 摘要（數值須來自工具回傳）；禁止捏造。
                """),
                expected_output="加密市場數據指標摘要",
                agent=self.crypto_researcher,
                async_execution=True,
            )
            crypto_macro_task = Task(
                description=dedent(f"""
                    【加密市場 — 宏觀與機構籌碼（Grok｜可並行）】
                    {ctx}
                    {_crypto_common_header}
                    === 必須呼叫 ===
                    · econ_calendar_tool()
                    · correlation_matrix_tool()
                    · valuation_anchor_tool()
                    · cot_positioning_tool()
                    · grayscale_premium_tool()
                    · historical_analog_tool()

                    產出：宏觀日曆、相關係數、估值錨、COT、GBTC/ETHE、歷史類比之摘要 bullet；禁止捏造。
                """),
                expected_output="加密市場宏觀與籌碼指標摘要",
                agent=self.crypto_researcher,
                async_execution=True,
            )
            crypto_news_task = Task(
                description=dedent(f"""
                    【加密市場 — 新聞、傳聞與情緒（Grok｜可並行）】
                    {ctx}
                    {_crypto_common_header}
                    === 必須呼叫 ===
                    · cryptopanic_tool('bitcoin')
                    · cryptopanic_tool('ethereum altcoin defi')
                    · rss_feed_tool('crypto')
                    · newsapi_tool('crypto ETF regulation blockchain market')
                    · gnews_tool('Ethereum altcoin DeFi Layer2 crypto market')
                    · rumor_scanner_tool('crypto whale ETF flow OR altcoin catalyst OR DeFi exploit OR Layer2 upgrade')
                    · market_search_tool('crypto market altcoin DeFi Layer2 catalyst liquidity derivatives')

                    {_ALT_PICK_DIVERSITY_RESEARCH_RULE}

                    === 幣圈新聞（3 則）===
                    {_NEWS_FMT}
                    每則研判 2~3 句，必須點名受影響標的；禁止捏造來源。

                    === 可選（時間緊可略過）===
                    {_sentiment_instr}

                    另附 1～2 句市場呢喃式短評（口語、非標題），供主編參考。
                """),
                expected_output="3 則加密貨幣新聞結構化初稿與呢喃",
                agent=self.crypto_researcher,
                async_execution=True,
            )
            crypto_research_tasks = [crypto_data_task, crypto_macro_task, crypto_news_task]
            review_context = crypto_research_tasks
            final_context = [*crypto_research_tasks]
        else:
            logger.info("CryptoResearchCrew: single-block researcher (CREW_DISABLE_ASYNC_RESEARCH)")
            crypto_task = Task(
                description=dedent(f"""
                    【加密市場情報收集 — Grok】
                    {ctx}

                    {_CREW_RULE_BLOCK}
                    {excl}
                    === 數據來源（必須全部呼叫）===
                    · coinglass_data_tool：支援多幣種查詢，格式 'metric:SYMBOL'（預設 BTC）
                      必查 BTC：funding_rate / liquidations / long_short_ratio / options_info
                      若新聞涉及 ETH/SOL 等山寨幣，額外查詢該幣衍生品：如 'funding_rate:ETH'、'liquidations:SOL'
                    · fear_greed_tool()（恐懼與貪婪指數）
                    · etf_flow_tool()（BTC Spot ETF 每日資金流，禁止自行猜測 ETF 數據）
                    · econ_calendar_tool()（本週宏觀經濟日曆，禁止自行猜測 FOMC/CPI 日期）
                    · cryptopanic_tool('bitcoin')（BTC 原生新聞）
                    · cryptopanic_tool('ethereum altcoin defi')（ETH / 山寨幣 / DeFi 新聞，補充多幣種視角）
                    · rss_feed_tool('crypto')（CoinDesk / TheBlock / Cointelegraph 免費 RSS，優先取用）
                    · newsapi_tool('crypto ETF regulation blockchain market')（主流財經：幣圈監管/ETF/機構動態）
                    · gnews_tool('Ethereum altcoin DeFi Layer2 crypto market')（多語言 + 山寨幣補充）
                    · rumor_scanner_tool('crypto whale ETF flow OR altcoin catalyst OR DeFi exploit OR Layer2 upgrade')
                    · market_search_tool('crypto market altcoin DeFi Layer2 catalyst liquidity derivatives')
                    · onchain_metrics_tool()（P2 鏈上深度：SOPR / 交易所淨流向 / 活躍地址數 / NUPL）
                    {_sentiment_instr}
                    · correlation_matrix_tool()（BTC 與 SPX/DXY/GLD/NDX 30日相關係數，識別當前市場模式）
                    · valuation_anchor_tool()（MVRV proxy + NVT Ratio + BTC Dominance；提供估值錨，判斷當前是否高估/低估）
                    · cot_positioning_tool()（CFTC COT 報告：CME 比特幣期貨機構淨倉 + 週變化，辨別機構是加倉還是撤倉）
                    · grayscale_premium_tool()（GBTC/ETHE 折溢價；溢價高 = 機構需求旺，折價大 = 拋售壓力）
                    · historical_analog_tool()（搜尋與當前技術結構最相似的歷史時期，報告其後 30/60/90 日報酬作為參考基準）

                    {_ALT_PICK_DIVERSITY_RESEARCH_RULE}

                    === 幣圈新聞（3 則）===
                    {_NEWS_FMT}
                    研判：2~3 句，必須明確說明哪個標的受影響
                    禁止捏造來源。
                """),
                expected_output="3 則幣圈新聞結構化初稿。",
                agent=self.crypto_researcher,
            )
            crypto_research_tasks = [crypto_task]
            review_context = [crypto_task]
            final_context = [crypto_task]

        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — Gemini】
                {ctx}
                {regime_lock_notice}
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

                {_DEBATE_SUMMARY_RULE}
            """),
            expected_output="宏觀框架、風險審計與可審計 regime 評分卡；末尾兩句多空結論（勿再用╌辯論摘要╌框架）。",
            agent=self.risk_critic,
            context=review_context,
        )

        final_report_task = Task(
            description=build_crypto_structured_final_prompt(
                ctx=ctx,
                prev_recs_ctx=prev_recs_ctx,
                today_str=today_str,
                agreed_regime=agreed_regime,
            )
            + "\n\n"
            + _REFLECTION_DYNAMIC_RISK_RULE,
            expected_output="符合 CryptoSection schema 的 JSON 物件；qsrec 為 CRYPTO 建議陣列。",
            agent=self.quant_strategist,
            context=[*final_context, review_task],
            output_pydantic=CryptoSection,
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.risk_critic, self.quant_strategist],
            tasks=[*crypto_research_tasks, review_task, final_report_task],
            process=Process.sequential,
        )
        try:
            scratchpad.set_tool_invocation_lane("crypto")
            kickoff_result = crew.kickoff(inputs={"recent_lessons": recent_lessons})
        finally:
            scratchpad.set_tool_invocation_lane(None)
        section = kickoff_to_pydantic(kickoff_result, CryptoSection)
        section.chatter = _ensure_chatter_credibility(section.chatter)
        return section


class AIResearchCrew:
    def __init__(self, use_fallback_llm: bool = False):
        llms = _get_llms_for_crew(use_fallback_llm)
        grok, gemini = llms["grok"], llms["gemini"]

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="收集 AI 市場核心資訊並輸出 3 則可交易新聞。",
            backstory="科技產業鏈研究員，聚焦可驗證催化。",
            llm=grok,
            tools=[
                market_search_tool,
                newsapi_tool,
                rss_feed_tool,
                gnews_tool,
                ai_sector_market_tool,
                ai_momentum_tool,
                financial_datasets_tool,
                rumor_scanner_tool,
            ],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席 AI 市場辯論員",
            goal="對 AI 新聞做反向辯論，引用宏觀框架強化論點。",
            backstory="對估值泡沫與敘事偏差高度敏感，善用利率與財報催化分析 AI 板塊。",
            llm=gemini,
            allow_delegation=False,
            tools=[macro_context_tool],
            verbose=_VERBOSE,
        )

        self.quant_strategist = Agent(
            role="機構策略主編（AI 市場）",
            goal="整合 AI 研究成果輸出戰報下半部。",
            backstory="最終格式與可操作性守門；嚴守【思考區／展示區】與【機構級寫作】Bloomberg 式洗練。",
            llm=gemini,
            tools=[multi_timeframe_tool],
            verbose=_VERBOSE,
        )

    def run(
        self,
        exclude_context: str | None = None,
        price_context: str = "",
        agreed_regime: str | None = None,
        langgraph_debate_context: str | None = None,
        recent_lessons: str = (
            "[系統反思記憶] 近期無停損紀錄，請維持客觀的風險控管。"
        ),
    ):
        excl = (
            f"\n【避免重複】昨日已涵蓋：\n{exclude_context}\n"
            if exclude_context else ""
        )
        year = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m")
        ctx = f"\n【系統強制即時報價】\n{price_context}\n"
        regime_lock_notice = (
            f"\n【⚠️ Pipeline 鎖定 market_regime = {agreed_regime}】"
            f" 全文 regime 欄位必須一律使用 {agreed_regime}，嚴禁輸出其他 regime 值。\n"
            if agreed_regime else ""
        )
        debate_ctx = (
            f"\n【LangGraph 辯論摘要（必須納入最終判斷）】\n{langgraph_debate_context}\n"
            if (langgraph_debate_context or "").strip() else ""
        )

        _ai_common_header = dedent(f"""
            {_CREW_RULE_BLOCK}
            {excl}
            {debate_ctx}
        """).strip()

        if _crew_parallel_research_enabled():
            logger.info("AIResearchCrew: parallel researcher tasks (async_execution x2) enabled")
            ai_data_task = Task(
                description=dedent(f"""
                    【AI 市場 — 財報與模型熱度（Grok｜可與新聞子任務並行）】
                    {ctx}
                    {_ai_common_header}
                    === 必須呼叫 ===
                    · ai_sector_market_tool()（AI／半導體 ETF 與龍頭＋SPY 收盤與 1D／5D%）
                    · ai_momentum_tool('openrouter_rankings')（開源模型熱度；預設趨勢優先）
                    · financial_datasets_tool：query 留空或 \"watchlist\"（NVDA、MSFT、AAPL 年度；儀表板每檔≥3 行基本面）

                    產出：族群報價、模型熱度與 watchlist 財務要點之結構化摘要；禁止捏造數字。
                """),
                expected_output="AI 模型熱度與相關美股財務摘要",
                agent=self.ai_researcher,
                async_execution=True,
            )
            ai_news_task = Task(
                description=dedent(f"""
                    【AI 市場 — 新聞與傳聞（Grok｜可並行）】
                    {ctx}
                    {_ai_common_header}
                    === 必須呼叫 ===
                    · market_search_tool('AI data center GPU semiconductor infrastructure {year}')
                    · market_search_tool('data center power supply nuclear energy AI {year}')
                    · newsapi_tool('AI data center GPU cloud computing semiconductor')
                    · rss_feed_tool('ai')（TechCrunch / VentureBeat AI RSS，優先取用）
                    · gnews_tool('artificial intelligence GPU infrastructure semiconductor')
                    · rumor_scanner_tool('AI infrastructure supply chain risk')

                    {_ALT_PICK_DIVERSITY_RESEARCH_RULE}

                    產出 AI 新聞 3 則，每則格式：
                    {_NEWS_FMT}
                    🤖 研判：2~3 句，必須點名受影響美股或 ETF；禁止捏造來源。
                """),
                expected_output="3 則 AI 產業新聞結構化初稿",
                agent=self.ai_researcher,
                async_execution=True,
            )
            ai_research_tasks = [ai_data_task, ai_news_task]
            review_context_ai = ai_research_tasks
            final_context_ai = [*ai_research_tasks]
        else:
            logger.info("AIResearchCrew: single-block researcher (CREW_DISABLE_ASYNC_RESEARCH)")
            ai_task = Task(
                description=dedent(f"""
                    【AI 市場情報收集 — Grok】
                    {ctx}

                    {_CREW_RULE_BLOCK}
                    {excl}
                    必呼叫 ai_sector_market_tool()；ai_momentum_tool('openrouter_rankings')。
                    必呼叫 financial_datasets_tool：query 留空或 \"watchlist\"（NVDA、MSFT、AAPL 年度；儀表板每檔≥3 行）；若新聞點名其他美股，追加 financial_datasets_tool('TICKER') 或 financial_datasets_tool('TICKER:quarterly')。
                    搜尋：
                    · rss_feed_tool('ai')（TechCrunch / VentureBeat AI RSS，優先取用）
                    · newsapi_tool('AI data center GPU cloud computing semiconductor')（Bloomberg / Reuters AI 報導）
                    · gnews_tool('artificial intelligence GPU infrastructure semiconductor')（多語言補充）
                    · market_search_tool('AI data center GPU semiconductor infrastructure {year}')
                    · market_search_tool('data center power supply nuclear energy AI {year}')
                    · rumor_scanner_tool('AI infrastructure supply chain risk')

                    {_ALT_PICK_DIVERSITY_RESEARCH_RULE}

                    產出 AI 新聞 3 則，每則格式：
                    {_NEWS_FMT}
                    🤖 研判：2~3 句，必須點名受影響美股或 ETF
                """),
                expected_output="3 則 AI 新聞結構化初稿。",
                agent=self.ai_researcher,
            )
            ai_research_tasks = [ai_task]
            review_context_ai = [ai_task]
            final_context_ai = [ai_task]

        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Gemini】
                {_QUOTE_RULE}
                {_NARRATIVE_CONSISTENCY_RULE}
                {ctx}
                {regime_lock_notice}
                === 宏觀框架（美股利率敏感性）===
                必須呼叫 macro_context_tool()，輸出美債利率、殖利率曲線、Fed 預期、本週財報，
                分析這些宏觀變數對本日 AI 新聞點名之美股標的的下一步影響。

                === 新聞辯論 ===
                對 3 則 AI 新聞逐條提出反向觀點（每則 2~3 句）；引用 BTC/均線時須與上方【技術指標與結構】一致。

                {_DEBATE_SUMMARY_RULE}
            """),
            expected_output="宏觀框架分析、3 則 AI 新聞辯論觀點，末尾含╌辯論摘要╌兩行。",
            agent=self.risk_critic,
            context=review_context_ai,
        )

        final_report_task = Task(
            description=build_ai_structured_final_prompt(ctx=ctx, agreed_regime=agreed_regime)
            + "\n\n"
            + _REFLECTION_DYNAMIC_RISK_RULE,
            expected_output="符合 AISection schema 的 JSON 物件；qsrec 為 EQUITY 建議陣列。",
            agent=self.quant_strategist,
            context=[*final_context_ai, review_task],
            output_pydantic=AISection,
        )

        crew = Crew(
            agents=[self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[*ai_research_tasks, review_task, final_report_task],
            process=Process.sequential,
        )
        try:
            scratchpad.set_tool_invocation_lane("ai")
            kickoff_result = crew.kickoff(inputs={"recent_lessons": recent_lessons})
        finally:
            scratchpad.set_tool_invocation_lane(None)
        section = kickoff_to_pydantic(kickoff_result, AISection)
        section.chatter = _ensure_chatter_credibility(section.chatter)
        return section


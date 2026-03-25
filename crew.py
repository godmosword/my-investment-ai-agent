import logging
import os
import re
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from config import MODEL_CLAUDE, MODEL_GEMINI, MODEL_GROK, MODEL_GPT
from crew_output_parse import kickoff_to_pydantic
from schemas import AISection, CryptoSection
from tools import (
    ai_momentum_tool,
    coinglass_data_tool,
    correlation_matrix_tool,
    cryptopanic_tool,
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
    x_search_tool,
)

logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")

# 每個角色的 LLM fallback chain：主 LLM 失敗時依序嘗試下一個
_FALLBACK_CHAINS: dict[str, list[str]] = {
    "grok": [MODEL_GROK, MODEL_CLAUDE, MODEL_GPT],
    "gpt": [MODEL_GPT, MODEL_CLAUDE, MODEL_GROK],
    "gemini": [MODEL_GEMINI, MODEL_GPT, MODEL_CLAUDE],
}

_API_KEY_MAP: dict[str, str] = {
    MODEL_GROK: "XAI_API_KEY",
    MODEL_GPT: "OPENAI_API_KEY",
    MODEL_GEMINI: "GEMINI_API_KEY",
    MODEL_CLAUDE: "ANTHROPIC_API_KEY",
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
        {_EXEC_SUMMARY_RULE}
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
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_CRYPTO_TRADE_MUTEX_RULE}
        {_BRIEF_V2_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {ctx}
        {prev_recs_ctx}

        {_MTF_CONF_RULE}
        {_SCENARIO_RULE}

        === 填入 CryptoSection 欄位 ===
        - report_title_date: 使用 {today_str}
        - market.regime / score_suffix / scorecard_lines：承接上一任務評分卡，regime 僅 risk_on|risk_off|neutral。
        - narrative_of_day：今日主敘事一句 ≤45 字。
        - macro_framework_lines：≤4 行宏觀 bullet。
        - dashboard：幣圈儀表板，每列 MetricLine；缺值 value="N/A"。
        - news：3 則 index 1–3；timestamp_line 必含 UTC+8；investment_takeaway 至少一個數字化數據。
        - chatter：2–3 則呢喃，含可信度與（未確認）。
        - pick_reason / risk_budget_summary / signal_conflict_summary：供區塊④，順序與 Gate 一致。
        - trade_legs：若可執行則填 ExecutableTradeLeg（asset 勿含 $ 於欄位內由模板加）；R:R 等放於 rr 等字串欄位。
          star_rating 1–4。若無法給價則 trade_legs 留空（由管線渲染觀望模式）。
        - qsrec：與 trade_legs 方向一致；category 僅 CRYPTO；數字欄位為 JSON number；填滿選分與 repeat_days 等 Gate 欄位。

        嚴禁在字串中出現字面 DATA_MISSING 方括號標記（改 N/A 或自然語）；嚴禁函數名 multi_timeframe_tool。
    """)


def build_ai_structured_final_prompt(*, ctx: str, agreed_regime: str | None = None) -> str:
    """最終任務：結構化 AISection（無排版指令）。"""
    regime_lock = (
        f"\n【⚠️ Pipeline 鎖定 market_regime = {agreed_regime}】"
        f" QSREC 每筆 regime 欄位必須使用 {agreed_regime}，嚴禁混用其他 regime 值。\n"
        if agreed_regime else ""
    )
    return dedent(f"""
        {_STRUCTURED_IO_HEADER}
        【AI 美股 — 最終整合主編】
        {regime_lock}
        {_QUOTE_RULE}
        {_NARRATIVE_CONSISTENCY_RULE}
        {_TOOL_TRUTH_RULE}
        {_RISK_MODE_RULE}
        {_REGIME_POSITION_POLICY}
        {_PAIR_TRADE_RULE}
        {_BRIEF_V2_RULE}
        {_GATE_VALIDATE_PICK_RULE}
        {_AI_RISK_BRIDGE_RULE}
        {ctx}

        {_MTF_CONF_RULE}
        {_SCENARIO_RULE}

        === 填入 AISection 欄位 ===
        - macro_bridge_lines：承上宏觀，勿重貼完整美債段。
        - dashboard：AI 儀表板 MetricLine 列表；若使用 financial_datasets_tool，每檔相關美股至少一行 label 含 FinancialDatasets 與代號。
        - news：3 則 index 4–6，格式同加密新聞欄位語意。
        - chatter：2–3 產業鏈呢喃含可信度。
        - pick_reason / signal_conflict_summary / us_equity_allocation_note：遵守 AI 段 Gate（不重複今日風險預算整行）。
        - trade_legs：兩檔美股為主；star_rating 1–4；留空則渲染觀望。
        - qsrec：category 僅 EQUITY；與 trade_legs 對齊。

        嚴禁 DATA_MISSING 方括號標記字面；嚴禁 multi_timeframe_tool 字樣。
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
    【新鮮度】新聞必須在 48h 內；超時跳過重搜。
    【嚴禁播報系統錯誤】若任何 Tool 回傳 `[DATA_MISSING...]`、`失敗` 或 `API 未設定`，絕對禁止將這些錯誤訊息寫成新聞！請直接忽略該工具的輸出。若無足夠真實新聞，寧可減少新聞數量，也絕不允許播報系統日誌！""")

_TOOL_TRUTH_RULE = dedent("""\
    【工具輸出與缺數敘述（防幻覺）】
    - **嚴禁**在任何可見欄位貼上工具內部字樣 **`[DATA_MISSING:...]`**（會觸發 Gate「資料缺失欄位」）；請改寫為自然語句或以 value=`N/A` 表示，並簡述原因（≤30 字）。
    - CoinGlass／ETF／爆倉／OI：若工具為 `[DATA_MISSING:coinglass_*]` 或含 401／Upgrade plan，僅能表述為「第三方衍生品數據源未回傳或訂閱方案不含該端點」；嚴禁寫成「資料庫 API 連線異常」「內部 API 故障」等未經證實說法。
    - 若儀表板已出現 Binance 備援、資金費率或多空比等數值，不得稱「籌碼面全缺失」；應寫「CoinGlass 不可用，已採備援／近似指標觀察短線情緒」。
    - **美股基本面**：營收、淨利、現金流、毛利率、EPS、資產負債等敘述必須來自 `financial_datasets_tool` 回傳；複述時 AI 儀表板須至少一行 MetricLine 的 label 同時含 **`FinancialDatasets`** 與該 ticker（如 NVDA），value 僅用工具數字或 N/A。
    - AI 儀表板（HuggingFace／OpenRouter）：禁止發明工具未提供的欄位，**嚴禁**出現以下字樣作為指標名：「AI Token Market Cap」「OpenRouter API Request Rank」「OpenRouter Request Vol」「AI Sector Sentiment」「Error Rate（排行）」；每行一個指標；僅能複述 `ai_momentum_tool` 回傳中的 **TopN: 模型名（下載｜按讚）** 或 RSS 備援標題；缺資料則 value=`N/A`，另補一句原因（≤45 字）—不得捏造數字。""")

_NEWS_FMT = dedent("""\
    【新聞資料欄位規格（純資料，非排版）】
    - 幣圈與 AI 共 6 則新聞，使用連續索引：1..6（禁止用 1./2./3. 取代欄位）。
    - 每則需包含：index、timestamp（UTC+8）、title、source_and_nature、summary、investment_takeaway、editor_consensus。
    - summary：1 句核心事實（≤40 字，禁止主觀評論）。
    - investment_takeaway：1~2 句（≤90 字），至少引用 1 個當日數據（如 funding/RSI/MA/ETF）。
    - editor_consensus：1 句（≤28 字）且點名具體標的。
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
    - 若 N/A 過多（超過 3 個），必須在報告中明確加入以下兩行：
      「資料缺失原因：[說明哪些數據源本日未回應]」
      「替代指標：[說明使用何種替代觀察]」
      Gate 系統會驗證這兩行是否同時存在，缺少任一行將阻擋推送。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質與可信度分級（A/B/C 或 0~100）、
    並標註是否已被主流媒體二次驗證（是/否），輸出 2~3 條。
    格式範例（至少擇一）：
    - 「...（未確認）｜來源：供應鏈側寫｜可信度：B｜主流媒體二次驗證：否」
    - 「...（未確認）｜來源：社群截圖｜可信度：72/100｜主流媒體二次驗證：否」
    ⚠️ 每條必須包含「可信度：A/B/C」或「可信度：數字/100」，缺少此標記將觸發 Gate 驗證失敗。
    🚫 若 rumor_scanner_tool 回傳 [DATA_MISSING] 或無任何可信傳聞，輸出單行「· 本日無可信傳聞」即可。
       **嚴禁在工具回傳空值或 DATA_MISSING 時自行捏造傳聞內容。**""")

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
            text = text.rstrip() + "｜可信度：C（自動補填）"
            item = item.model_copy(update={"text": text})
        result.append(item)
    return result


_QUOTE_RULE = dedent("""\
    【實盤價格強制查核】關於 DXY、VIX、IBIT、SPY、BTC、SOL 及當日選定美股標的等數值，
    以及 RSI(14)、MA20/MA50、VIX 期限結構等技術指標，
    必須直接使用上方【系統強制即時報價】+【技術指標與結構】Context；不得自行捏造或改寫。""")

_NARRATIVE_CONSISTENCY_RULE = dedent("""\
    【敘事與數據一致】引用 BTC/指數/均線時，須與【技術指標與結構】的趨勢描述一致：
    若 Context 為「多頭排列（價>MA20>MA50）」或現價高於 MA50，不得寫「跌破 MA50」或「跌破均線」；
    若為「空頭排列（價<MA20<MA50）」或現價低於 MA50，不得寫「站上 MA50」。不確定時改寫為「若跌破/若站上」等條件句。""")

_TRADE_RULE = dedent("""\
    · <b>$代幣/股票 (操作方向)</b>｜現價：$真實最新報價｜信心水準：⭐️⭐️⭐️⭐️
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
    - 若主判定為 neutral 或 risk_on：嚴禁在敘事中寫「高風險環境 risk_off」「Market Regime: risk_off」「依 risk_off」等與主判定矛盾的 regime 標籤；若要表達謹慎，僅可寫「VIX 偏高、採保守倉位／減碼」，且「今日風險預算」行須與主 regime 一致。
    - **加密區交易段落前固定三行順序**（validate_report 會截斷檢查）：① `本日選擇理由：…` ② `今日風險預算：…` ③ `訊號衝突摘要：…`（單行 ≤75 字；無衝突時寫「訊號衝突摘要：無顯著多空衝突。」）→ 再進入 `· $<b>…` 交易條目。嚴禁把「本日選擇理由」放在風險預算或訊號衝突之後。
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
    3) 【儀表板可讀性】區塊①每行僅一個指標；<code>N/A</code> 或數值後若需補充說明（如 CoinGlass 權限），必須換行另起一句，嚴禁黏成同一行（禁止出現 <code>N/A</code> 緊接英文字母）。
    4) 【Source 三行】區塊①儀表板內禁止輸出整行【SourceHealth】/【SourceErrors】/【SourceQuota】（pipeline 會於 QSREC 前統一注入）；儀表板內若要交代資料健康，僅能用一句自然語言，勿複製三行欄位。
    """)

_AI_RISK_BRIDGE_RULE = dedent("""\
    【AI 段風險預算銜接（與加密段一致）】
    加密戰報上半部已宣告全報「今日風險預算」與主 regime；本 AI 段嚴禁再寫第二組與之衝突的「總風險預算 XX%」整行（避免讀者看到 40% 與 20% 兩套總框）。
    【validate_report 硬性順序（區塊④）】本段**必須**在「訊號衝突摘要」「美股部位框」「第一筆 · $<b>… 交易行前」先寫獨立一行「本日選擇理由：…」（僅屬 AI/美股，不可沿用加密段那一句）。違者系統判定「AI 區缺少本日選擇理由」並阻擋推送。
    【覆寫上方「交易段落前今日風險預算」】本段交易區前不要重複輸出「今日風險預算：…」整行；在「本日選擇理由」之後輸出「訊號衝突摘要：…」，再輸出（可選）一行：
    · <b>美股部位框</b>：兩檔合計建議不超過總資金 <code>10%</code>（主 regime 為 neutral）、<code>15%</code>（risk_on）、<code>4%</code>（risk_off）；單筆仍須遵守【Regime 風險預算】之單筆上限；總組合曝險以上方加密段「今日風險預算」為準。
    """)

_GATE_VALIDATE_PICK_RULE = dedent("""\
    【validate_report 動態選幣／選股（與 main.py 機檢對齊｜違者 STRICT_CONSISTENCY_GATE 擋推送）】
    1) **兩段各寫一次「本日選擇理由：」**——加密區塊④寫**加密專用**一句；🤖 AI 市場區塊④再寫**美股專用**一句。嚴禁只寫在加密段而 AI 段留白。
    2) **固定順序（加密區塊④）**：`本日選擇理由：…` → `今日風險預算：…` → `訊號衝突摘要：…` → 第一筆 `· $<b>標的` 交易行。（理由內文勿出現「今日風險預算」「訊號衝突」開頭行，以免截斷錯誤。）
    3) **固定順序（AI 區塊④）**：`本日選擇理由：…` → `訊號衝突摘要：…` →（可選）`· <b>美股部位框</b>：…` → `· $<b>標的` 交易行。
    4) **加密理由**（純文字 ≥34 字）：須滿足下列**任一**——(a) 同句（或連續一段）內可讓系統辨識 **≥2 類**催化／鏈上線索關鍵詞，建議從「新聞／催化／ETF／監管／鏈上／交易所／淨流／資金費率／多空比／OI／未平倉／現貨／清算」等任選**兩個不同概念**寫入；(b) **1 類**催化＋明確 **大型幣／流動性／退階／缺乏其他催化** 等退階語；(c) **1 類**催化且全文 **≥72 字**並**逐一點名** QSREC 內**每一檔**加密 asset（含比值如 BTC/SOL 須**同時出現 BTC 與 SOL** 字樣）。
    5) **美股理由**（純文字 ≥38 字）：須滿足下列**任一**——(a) **≥2 類**基本面／新聞線索，建議「新聞／財報／法說／資料中心／GPU／拉貨／Capex／合約／指引」等任選兩概念；(b) **1 類**＋ **權值／大型股／ETF／BOTZ／ARKQ／流動性** 等退階語；(c) **1 類**且 **≥80 字**並點名兩檔 ticker（與 QSREC EQUITY 一致）。
    6) **與昨日 BigQuery QSREC 完全相同時**（加密或美股）：
       - **優先換標**：至少換一檔或改配對腿（最簡單、最安全）。
       - **若確有連持理由**：在該類別「本日選擇理由」**開頭**寫 **`重複選用理由：…`**（具體新催化或連日持有依據），**且同時滿足**：
         * QSREC 每筆 `score_gap = selection_score − alt_candidate_score` **必須 ≥ 12**
         * 具體作法：若 selection_score=85，則 alt_candidate_score **最高 73**；若 selection_score=80，最高 68；以此類推
         * alt_candidate 必須是**真實存在的次佳選項**，不得為縮小差距而刻意調高其分數
       - **若無法構造 ≥12 分差**，代表今日敘事不足以支撐連選 → **必須改選新標的**，不得強行填寫重複理由
       - 違反以上任一條件，整報驗證失敗、無法推送。
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
    格式範例：「→ BTC 多頭排列完整，ETF 淨流入連三日，進場信心 4 星」
    ⚠️ 嚴禁重複正文內容、嚴禁泛泛而談（如「市場混亂」「保持謹慎」）。""")

_HEDGE_FUND_BRIEF_RULE = dedent("""\
    【避險基金極簡閱讀（手機優先，與 Gate 對齊）】
    - 語氣：多空避險基金晨報——只給可執行結論與必要證據，禁止長篇教學、重複鋪墊、自我辯論。
    - **必留關鍵字**（系統會驗證）：加密段須含「今日風險預算」「訊號衝突摘要」「本日選擇理由」；AI 段須含「訊號衝突摘要」「本日選擇理由」（AI 段不重複「今日風險預算」整行，見【AI 段風險預算銜接】）。
    - 「本日選擇理由：」可為單行或連續短段，但**必須完整出現在**「今日風險預算／訊號衝突／第一筆 · $ 交易行」**之前**；並遵守【validate_report 動態選幣／選股】的長度與關鍵詞／點名規則。
    - 宏觀框架（🏛️）：≤4 行 bullet，每行 ≤60 字。
    - 呢喃／傳聞：維持每條 1 句，總長寧短勿長。
    """)

_CRYPTO_LAYOUT_RULE = dedent("""\
    === 排版順序（Crypto）===
    1) <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
    1b) 【執行摘要】（exec_summary，見【Executive Summary】規則）：3~5 條 bullet，置於標題之後、上期建議追蹤之前。
    2) 【上期建議追蹤】：若提示區已給 HTML，僅能原樣貼上一段、嚴禁自行增刪列或補寫歷史進場（後端亦會覆寫為 BigQuery 權威版本）。
    3) 【今日市場模式】與評分卡明細（取自 review_task）
    3b) 【今日主敘事】一行（見【日報 V2】）
    4) 🏛️ 宏觀框架（取自 macro_context_tool）
       · 若 correlation_matrix_tool 有回傳，在宏觀框架末尾加一行：「📐 BTC 相關係數：BTC/SPX X.XX｜BTC/DXY X.XX｜BTC/GLD X.XX」
       · 若 valuation_anchor_tool 有回傳，在宏觀框架末尾加一行：「📊 估值錨：MVRV X.XXx（區間）｜NVT XX（區間）｜BTC Dominance XX%」
    5) 📊 加密市場：
       - 區塊① 儀表板（宏觀/技術/籌碼；嚴格套用儀表板格式）
       - 區塊② 核心新聞 3 則（〔新聞 1〕～〔新聞 3〕，套用新聞格式）
       - 區塊②b X 推文精選（無資料可跳過）
       - 區塊③ 市場呢喃與傳聞 2~3 條
       - 區塊④ 資金流向與精準操作：1 單邊 + 1 配對
         【動態選幣規則】禁止每次固定選 BTC/SOL。必須根據以下優先順序動態選出本日標的：
         (a) 優先選今日新聞中有明確催化劑的幣種（如 ETF 核准/拒絕、主網升級、大額清算、機構買入）
         (b) 次選鏈上指標異動最顯著的幣種（SOPR 偏離/交易所淨流出/OI 暴增）
         (c) 最後才考慮 BTC/ETH 等大型幣（僅在無其他明顯催化劑時）
         配對交易必須選擇強弱分化最明顯的兩幣，禁止用 BTC/SOL 當預設配對
        【昨日標的對照】提示區「過去 3 天已建議標的」＋ BigQuery 昨日 QSREC：若本日加密 QSREC 與昨日**完全相同**（同幣種／同配對），必須二選一：(1) 至少更換一檔或一改配對腿；(2) 在「本日選擇理由」首段寫明「重複選用理由：〔全新催化／連日持有依據〕」，且 QSREC 需填可驗證分差（score_gap，預設需 >= 12）。否則 validate_report 硬性失敗並整報重試。
         每次必須說明「本日選擇理由：…」（完整規則見【validate_report 動態選幣／選股】；須寫在今日風險預算／訊號衝突／第一筆 · $ 交易行之前）
         【情境分析】每筆交易行信心 ≥ 3 星時，在敘事邏輯之後附上三情境（填入 trade_legs 的 bull/base/bear_scenario 欄位）：
         🐂 牛：[觸發條件 → 目標]（例：突破 74k + ETF 流入 > $5億 → 78k，機率 30%）
         ⚖️ 基：[主要情境 + 機率]（例：震盪 70-74k 整理，機率 55%）
         🐻 熊：[失效條件 → 止損]（例：日線收破 MA20 → 停損 69.5k，機率 15%）
    6) 最後必須輸出 QSREC JSON 區塊""")

_SCENARIO_RULE = dedent("""\
    【三情境分析（P4 新增 | 信心 ≥ 3 星強制填入）】
    每筆 confidence ≥ 3 的 QSREC，在 QSREC JSON 內補充以下三個選填欄位（字串，≤40字/項）：
    · bull_scenario  — 🐂 樂觀情境：目標價 + 觸發條件（例：突破 70k 且 ETF 淨流 >5億 → 目標 76k）
    · base_scenario  — ⚖️ 基準情境：預期走勢 + 估計機率（例：震盪整理後突破，機率 55%）
    · bear_scenario  — 🐻 悲觀情境：失效位 + 觸發條件（例：跌破 63k 且資金費率轉負 → 止損）
    confidence < 3 時可留 null，但不得輸出空字串。""")

_DEBATE_SUMMARY_RULE = dedent("""\
    【Risk Critic 辯論摘要（P4 新增 | 必填）】
    Risk Critic 任務輸出末尾必須以下格式輸出辯論精髓（2行，每行 ≤35字）：
    ╌ 辯論摘要 ╌
    · 最強空方論點：[一句核心空方依據]
    · 多方反駁核心：[一句主編最終為何選多/空的反駁或確認]
    此區塊由主編（quant_strategist）原文轉錄至報告 signal_conflict_summary，
    使讀者在最終報告中清楚看到多空辯論結論。""")

_AI_LAYOUT_RULE = dedent("""\
    === 排版順序（AI）===
    1) 🏛️ 宏觀框架：本戰報將接在加密戰報之後，前段已含完整宏觀數據；本節僅輸出「承上宏觀」+ 一句主編共識（如 10Y/VIX 對美股影響），勿重複貼上美債/SOFR/利差整段。
    2) 🤖 AI 市場：
       - 主標題固定輸出 `🤖 AI 市場`；禁止改寫為「🤖 AI 與美股市場」或同義變體，且整篇只能出現一個 AI 主標題。
       - 區塊① AI 儀表板（HuggingFace / OpenRouter 模型熱度 Top5；缺值 <code>N/A</code>）
       - 區塊② AI 產業新聞 3 則：必須與幣圈完全相同格式，逐則以 `〔新聞 4〕[MM/DD HH:MM UTC+8]` … `〔新聞 6〕[MM/DD HH:MM UTC+8]` 開頭（嚴禁只用英文標題起句、嚴禁省略 UTC+8），主題涵蓋基建/投資案/模型各 1
       - 區塊②b X 推文精選（無資料可跳過）
       - 區塊③ 產業鏈呢喃 2~3 條（每條必含可信度：可寫「可信度：B」或「來源：B級」或 0~100 分，與加密呢喃／傳聞區格式對齊，供系統驗證）
       - 區塊④ AI 精準操作 2 檔：
         【新聞格式再確認】區塊②三則必須各以 `〔新聞 4〕`…`〔新聞 6〕` + `[MM/DD HH:MM UTC+8]` 開頭，含 <blockquote> 摘要，嚴禁縮成 `1. 2. 3.` 段落。
         【動態選股規則】禁止固定使用特定股票。必須根據以下優先順序動態選出本日 2 檔：
         (a) 優先選今日 AI 新聞中直接點名且有具體財務/產品事件的美股（如財報、拉貨、合約）
         (b) 次選 ai_momentum_tool 回傳模型排名中，對應的上市公司股票（如 Meta, Google, Microsoft, AMD 等）
         (c) 最後才考慮 AI 基建通殺標的（如 ETF BOTZ/ARKQ）
        【昨日標的對照】若本日兩檔美股 QSREC 與昨日 BQ 紀錄**完全相同**，必須更換至少一檔，或在 **🤖 本段**「本日選擇理由」內寫明「重複選用理由：…」（勿只寫在加密段），且 QSREC 需填可驗證分差（score_gap，預設需 >= 12）。否則 validate_report 硬性失敗。
         每次必須說明「本日選擇理由：…」（**僅寫於本 AI 段**，完整規則見【validate_report 動態選幣／選股】；須寫在訊號衝突／美股部位框／第一筆 · $ 交易行之前）
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
    """Primary 依 fallback chain 選可用 LLM；use_fallback_llm=True 時全用 GPT 降低凌晨靜默失敗。"""
    if use_fallback_llm:
        gpt = _make_llm(MODEL_GPT)
        return {"grok": gpt, "gpt": gpt, "gemini": gpt}
    return {
        "grok": _make_llm_with_fallback("grok"),
        "gpt": _make_llm_with_fallback("gpt"),
        "gemini": _make_llm_with_fallback("gemini", max_retries=5, timeout=180),
    }


class CryptoResearchCrew:
    def __init__(self, use_fallback_llm: bool = False):
        llms = _get_llms_for_crew(use_fallback_llm)
        grok, gpt, gemini = llms["grok"], llms["gpt"], llms["gemini"]

        self.crypto_researcher = Agent(
            role="加密市場情報研究員",
            goal="收集完整加密市場數據，產出 3 則高衝擊幣圈新聞。",
            backstory="冷靜量化研究員，專注流動性、槓桿與聰明錢行為。",
            llm=grok,
            tools=[market_search_tool, newsapi_tool, rss_feed_tool, gnews_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, fear_greed_tool, etf_flow_tool, econ_calendar_tool, x_search_tool, onchain_metrics_tool, sentiment_score_tool, correlation_matrix_tool, valuation_anchor_tool],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席幣圈風險審計員",
            goal="對幣圈新聞做反向辯論，以評分卡判定 market_regime。",
            backstory="反身性風險審計者，負責挑錯、驗證與量化機制判斷。",
            llm=gpt,
            allow_delegation=False,
            tools=[regime_scorecard_tool, macro_context_tool],
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

    def run(self, exclude_context: str | None = None, price_context: str = "",
            prev_recs_block: str = "", agreed_regime: str | None = None):
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

        crypto_task = Task(
            description=dedent(f"""
                【加密市場情報收集 — Grok】
                {ctx}

                {_DATA_RULES}
                {_TOOL_TRUTH_RULE}
                {_QUOTE_RULE}
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
                · x_search_tool('crypto ETF bitcoin ethereum altcoin DeFi liquidation whale')（供 X 推文精選區塊使用）
                · onchain_metrics_tool()（P2 鏈上深度：SOPR / 交易所淨流向 / 活躍地址數 / NUPL）
                · sentiment_score_tool(news_and_tweets=<將上方新聞標題 + X 推文拼接後傳入>)（可選 / optional：若時間緊迫可跳過；社群情緒量化 -1 到 +1）
                · correlation_matrix_tool()（BTC 與 SPX/DXY/GLD/NDX 30日相關係數，識別當前市場模式）
                · valuation_anchor_tool()（MVRV proxy + NVT Ratio + BTC Dominance；提供估值錨，判斷當前是否高估/低估）

                === 幣圈新聞（3 則）===
                {_NEWS_FMT}
                研判：2~3 句，必須明確說明哪個標的受影響
                禁止捏造來源。
            """),
            expected_output="3 則幣圈新聞結構化初稿。",
            agent=self.crypto_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【幣圈辯論與風險審計 — GPT】
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
            expected_output="宏觀框架、風險審計與可審計 regime 評分卡，末尾含╌辯論摘要╌兩行。",
            agent=self.risk_critic,
            context=[crypto_task],
        )

        final_report_task = Task(
            description=build_crypto_structured_final_prompt(
                ctx=ctx,
                prev_recs_ctx=prev_recs_ctx,
                today_str=today_str,
                agreed_regime=agreed_regime,
            ),
            expected_output="符合 CryptoSection schema 的 JSON 物件；qsrec 為 CRYPTO 建議陣列。",
            agent=self.quant_strategist,
            context=[crypto_task, review_task],
            output_pydantic=CryptoSection,
        )

        crew = Crew(
            agents=[self.crypto_researcher, self.risk_critic, self.quant_strategist],
            tasks=[crypto_task, review_task, final_report_task],
            process=Process.sequential,
        )
        section = kickoff_to_pydantic(crew.kickoff(), CryptoSection)
        section.chatter = _ensure_chatter_credibility(section.chatter)
        return section


class AIResearchCrew:
    def __init__(self, use_fallback_llm: bool = False):
        llms = _get_llms_for_crew(use_fallback_llm)
        gpt, grok, gemini = llms["gpt"], llms["grok"], llms["gemini"]

        self.ai_researcher = Agent(
            role="前沿 AI 市場研究員",
            goal="收集 AI 市場核心資訊並輸出 3 則可交易新聞。",
            backstory="科技產業鏈研究員，聚焦可驗證催化。",
            llm=gpt,
            tools=[
                market_search_tool,
                newsapi_tool,
                rss_feed_tool,
                gnews_tool,
                ai_momentum_tool,
                financial_datasets_tool,
                rumor_scanner_tool,
                x_search_tool,
            ],
            verbose=_VERBOSE,
        )

        self.risk_critic = Agent(
            role="首席 AI 市場辯論員",
            goal="對 AI 新聞做反向辯論，引用宏觀框架強化論點。",
            backstory="對估值泡沫與敘事偏差高度敏感，善用利率與財報催化分析 AI 板塊。",
            llm=grok,
            allow_delegation=False,
            tools=[macro_context_tool],
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

    def run(self, exclude_context: str | None = None, price_context: str = "",
            agreed_regime: str | None = None):
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

        ai_task = Task(
            description=dedent(f"""
                【AI 市場情報收集 — GPT】
                {ctx}

                {_DATA_RULES}
                {_TOOL_TRUTH_RULE}
                {_QUOTE_RULE}
                {excl}
                呼叫 ai_momentum_tool('openrouter_rankings')。
                必呼叫 financial_datasets_tool：query 留空或 \"watchlist\"（一次取 NVDA、MSFT、AAPL 年度摘要）；若新聞點名其他美股，追加 financial_datasets_tool('TICKER') 或 financial_datasets_tool('TICKER:quarterly')。
                搜尋：
                · rss_feed_tool('ai')（TechCrunch / VentureBeat AI RSS，優先取用）
                · newsapi_tool('AI data center GPU cloud computing semiconductor')（Bloomberg / Reuters AI 報導）
                · gnews_tool('artificial intelligence GPU infrastructure semiconductor')（多語言補充）
                · market_search_tool('AI data center GPU semiconductor infrastructure {year}')
                · market_search_tool('data center power supply nuclear energy AI {year}')
                · rumor_scanner_tool('AI infrastructure supply chain risk')
                · x_search_tool('NVIDIA AI GPU data center OpenAI Anthropic Microsoft')（取得 AI 板塊 X/Twitter 即時推文）

                產出 AI 新聞 3 則，每則格式：
                {_NEWS_FMT}
                🤖 GPT 研判：2~3 句，必須點名受影響美股或 ETF
            """),
            expected_output="3 則 AI 新聞結構化初稿。",
            agent=self.ai_researcher,
        )

        review_task = Task(
            description=dedent(f"""
                【AI 市場辯論審計 — Grok】
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
            context=[ai_task],
        )

        final_report_task = Task(
            description=build_ai_structured_final_prompt(ctx=ctx, agreed_regime=agreed_regime),
            expected_output="符合 AISection schema 的 JSON 物件；qsrec 為 EQUITY 建議陣列。",
            agent=self.quant_strategist,
            context=[ai_task, review_task],
            output_pydantic=AISection,
        )

        crew = Crew(
            agents=[self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[ai_task, review_task, final_report_task],
            process=Process.sequential,
        )
        section = kickoff_to_pydantic(crew.kickoff(), AISection)
        section.chatter = _ensure_chatter_credibility(section.chatter)
        return section


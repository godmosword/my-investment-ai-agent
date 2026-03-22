import logging
import os
from datetime import datetime, timedelta, timezone
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from config import MODEL_CLAUDE, MODEL_GEMINI, MODEL_GROK, MODEL_GPT
from tools import (
    ai_momentum_tool,
    coinglass_data_tool,
    cryptopanic_tool,
    econ_calendar_tool,
    etf_flow_tool,
    fear_greed_tool,
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
    - **嚴禁**在戰報任何讀者可見段落貼上工具內部字樣 **`[DATA_MISSING:...]`**（會觸發 Gate「資料缺失欄位」）；請改寫為自然語句或單獨一行 <code>N/A</code> 並簡述原因（≤30 字）。
    - CoinGlass／ETF／爆倉／OI：若工具為 `[DATA_MISSING:coinglass_*]` 或含 401／Upgrade plan，僅能表述為「第三方衍生品數據源未回傳或訂閱方案不含該端點」；嚴禁寫成「資料庫 API 連線異常」「內部 API 故障」等未經證實說法。
    - 若儀表板已出現 Binance 備援、資金費率或多空比等數值，不得稱「籌碼面全缺失」；應寫「CoinGlass 不可用，已採備援／近似指標觀察短線情緒」。
    - AI 儀表板（HuggingFace／OpenRouter）：禁止發明工具未提供的欄位，**嚴禁**出現以下字樣作為指標名：「AI Token Market Cap」「OpenRouter API Request Rank」「OpenRouter Request Vol」「AI Sector Sentiment」「Error Rate（排行）」；每行一個指標；僅能複述 `ai_momentum_tool` 回傳中的 **TopN: 模型名（下載｜按讚）** 或 RSS 備援標題；缺資料則單獨一行 <code>N/A</code>，**換行**後一句說明原因（≤45 字）—不得捏造數字。""")

_NEWS_FMT = dedent("""\
    【新聞編號強制】幣圈與 AI 共 6 則新聞，**每一則開頭必須是** `〔新聞 1〕`…`〔新聞 6〕`（全篇連續編號），**嚴禁**僅用 `1.` `2.` `3.` 當新聞編號（易與辯論／呢喃列表混淆）；辯論段落可用自由列表。
    〔新聞 N〕[MM/DD HH:MM UTC+8] <b>新聞標題</b>（來源：xxx｜性質：confirmed / likely / unverified rumor）
    <blockquote>摘要：（1 句核心事實，≤40 字，禁止主觀評論）</blockquote>
    投資解讀：（1~2 句、總字數 ≤90；至少嵌入 1 個當日數據 <code>…</code>，如資金費率/RSI/MA/ETF）
    💎主編共識：（1 句 ≤28 字，必須點名具體標的）
    【格式紅線】嚴禁在最終戰報中印出「📍 受影響資產」、「📈 做多機會」、「📉 做空風險」、「⏱️ 時效」、「🎯 IMPACT」等原始標籤符號，必須轉化為自然語言！""")

_DASHBOARD_FMT = dedent("""\
    儀表板格式：每項獨立一行，數值部分【必須】用 <code> 標籤包覆。
    · <b>指標名</b> <code>數值</code>（可選 ▲/▼ 幅度於同一 <code> 內，勿冗長解釋）
    缺資料寫單獨一行 <code>N/A</code>，說明文字**換行**再寫，禁止同一行塞多個指標或 N/A 後黏接英文。
    【今日市場模式】下之 regime 評分：第一行保留 `【今日市場模式】regime（±n/6）`；第二行起改用**極簡**呈現——每個指標僅 `✅/❌/⬜` + 簡稱 + <code>讀數</code>，**避免**逐條複製長算式如 `數值(>門檻)→±1`（門檻結果已含在 ✅❌⬜）。
    宏觀利率欄位（10Y/2Y/SOFR/利差）硬規則：
    - 10Y/2Y/SOFR 僅可輸出 0~20% 的數值；超出或不確定一律輸出 <code>N/A</code>。
    - 利差僅可輸出 +/-1000bp 內；超出或口徑不明一律輸出 <code>N/A</code>。
    - 不得混用單位（% / bp），不得把年份、成交量、情緒百分比誤寫成利率。
    【Source 三行】儀表板內勿輸出【SourceHealth】/【SourceErrors】/【SourceQuota】整行（pipeline 會於 QSREC 前統一注入，見【日報 V2】）。
    若關鍵欄位 N/A 超過 3 項，必須在該區塊加註：<b>低置信度</b>，
    並補「資料缺失原因」與「替代指標」（合計 ≤120 字、最多兩行；須符合【工具輸出與缺數敘述】）。""")

_CHATTER_FMT = dedent("""\
    呢喃/傳聞：僅未確認訊息，排除官方已證實事件
    每條 1 句、結尾標註（未確認）、附來源性質與可信度分級（A/B/C 或 0~100）、
    並標註是否已被主流媒體二次驗證（是/否），輸出 2~3 條。
    格式範例（至少擇一）：
    - 「...（未確認）｜來源：供應鏈側寫｜可信度：B｜主流媒體二次驗證：否」
    - 「...（未確認）｜來源：社群截圖｜可信度：72/100｜主流媒體二次驗證：否」""")


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
    【方向唯一】同一 JSON 陣列內，相同 category + 相同 asset（例：兩筆皆 EQUITY+MSFT）不得同時出現 LONG 與 SHORT；若需對沖請改為單筆淨方向或合併敘事，否則 validate_report 失敗。""")

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
    6) **與昨日 BigQuery QSREC 完全相同時**（加密或美股）：要嘛至少換一檔／一改配對腿；要嘛在**該類別**的「本日選擇理由」開頭寫 **`重複選用理由：…`**（具體新催化或連日持有依據），且 QSREC 內 **`score_gap` ≥ 12**（或 selection_score − alt_candidate_score 可驗證）。否則整報驗證失敗。
    7) **美股輪動（最常漏）**：若【上期建議追蹤】或任務提示顯示「昨日兩檔美股 ticker」與今日 QSREC **完全一致**，**🤖 AI 區塊④** 的 `本日選擇理由：` **整段內**必須含 **`重複選用理由：`**（或 **`重複選股理由：`**／**`連日維持`**／**`維持昨日兩檔`** 等系統認可片語）——**寫在加密段無效**；並確保兩檔 ticker 代號仍出現在理由或緊隨交易行。
    8) **禁止貼工具錯誤碼**：戰報正文嚴禁出現字面 **`[DATA_MISSING:`**（validate_report 會當成「資料缺失欄位」）；缺資料僅能寫 `<code>N/A</code>` 或一句「第三方資料源未回傳」。
    """)

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
    2) 【上期建議追蹤】：若提示區已給 HTML，僅能原樣貼上一段、嚴禁自行增刪列或補寫歷史進場（後端亦會覆寫為 BigQuery 權威版本）。
    3) 【今日市場模式】與評分卡明細（取自 review_task）
    3b) 【今日主敘事】一行（見【日報 V2】）
    4) 🏛️ 宏觀框架（取自 macro_context_tool）
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
    6) 最後必須輸出 QSREC JSON 區塊""")

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
            tools=[market_search_tool, newsapi_tool, rss_feed_tool, gnews_tool, coinglass_data_tool, rumor_scanner_tool, cryptopanic_tool, fear_greed_tool, etf_flow_tool, econ_calendar_tool, x_search_tool, onchain_metrics_tool, sentiment_score_tool],
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
            prev_recs_block: str = ""):
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
                · x_search_tool('crypto ETF bitcoin ethereum altcoin DeFi liquidation whale')（取得 X/Twitter 即時情緒推文，供 X 推文精選區塊使用）
                · onchain_metrics_tool()（P2 鏈上深度：SOPR / 交易所淨流向 / 活躍地址數 / NUPL）
                · sentiment_score_tool(news_and_tweets=<將上方新聞標題 + X 推文拼接後傳入>)（P2 社群情緒量化：-1 到 +1）

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
            """),
            expected_output="宏觀框架、風險審計與可審計 regime 評分卡。",
            agent=self.risk_critic,
            context=[crypto_task],
        )

        final_report_task = Task(
            description=build_crypto_final_prompt(
                ctx=ctx,
                prev_recs_ctx=prev_recs_ctx,
                today_str=today_str,
            ),
            expected_output="一份純淨的 HTML 戰報。報告的最末端必須、絕對要包含 [QSREC_START] 到 [QSREC_END] 的 JSON 陣列。若遺漏 JSON，你的任務將被判定為徹底失敗！",
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
    def __init__(self, use_fallback_llm: bool = False):
        llms = _get_llms_for_crew(use_fallback_llm)
        gpt, grok, gemini = llms["gpt"], llms["grok"], llms["gemini"]

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
                {_TOOL_TRUTH_RULE}
                {_QUOTE_RULE}
                {excl}
                呼叫 ai_momentum_tool('openrouter_rankings')。
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

                === 宏觀框架（美股利率敏感性）===
                必須呼叫 macro_context_tool()，輸出美債利率、殖利率曲線、Fed 預期、本週財報，
                分析這些宏觀變數對本日 AI 新聞點名之美股標的的下一步影響。

                === 新聞辯論 ===
                對 3 則 AI 新聞逐條提出反向觀點（每則 2~3 句）；引用 BTC/均線時須與上方【技術指標與結構】一致。
            """),
            expected_output="宏觀框架分析與 3 則 AI 新聞辯論觀點。",
            agent=self.risk_critic,
            context=[ai_task],
        )

        final_report_task = Task(
            description=build_ai_final_prompt(ctx=ctx),
            expected_output="一份純淨的 HTML 戰報。報告的最末端必須、絕對要包含 [QSREC_START] 到 [QSREC_END] 的 JSON 陣列。若遺漏 JSON，你的任務將被判定為徹底失敗！",
            agent=self.quant_strategist,
            context=[ai_task, review_task],
        )

        crew = Crew(
            agents=[self.ai_researcher, self.risk_critic, self.quant_strategist],
            tasks=[ai_task, review_task, final_report_task],
            process=Process.sequential,
        )
        return crew.kickoff()


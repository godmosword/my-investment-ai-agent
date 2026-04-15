# 日報 V2（版面與敘事規格）

本文件對齊 `crew.py` 內 **【日報 V2】** 與 **【AI 段風險預算銜接】**，目標是：**30 秒讀懂 regime 與主線、可執行交易不超量、全文只有一套總風險敘事**。

## 1. 區塊順序（加密上半部）

1. 標題（含日期）；**機構固定免責**（`<blockquote>…不構成…`）置於 **【機構速讀｜命題與情境】** 標題**之前**，不再緊接標題後顯示。
2. 【執行摘要】（若有）
3. **掃讀順序**一行（模板固定，引導先讀市場模式再讀儀表板）
4. 【上期建議追蹤】（BQ 權威；LLM 勿改寫）
5. 【今日市場模式】+ **極簡**評分呈現（✅❌⬜ + 讀數，避免長算式列）
6. **· 今日主敘事：** 單句（≤45 字），與主 regime 一致
7. 🏛️ 宏觀框架
7b. **【預測市場熱門】**（可選）— Polymarket Gamma 即時熱門二元市場；`assemble` 注入 `prediction_market_highlight_lines`；`PREDICTION_MARKETS_IN_BRIEF=0` 可關閉。選題：`PREDICTION_MARKETS_KEYWORDS`（逗號分隔，命中題目優先；不足 3 條則退回原 24h 成交量排序）、`PREDICTION_MARKETS_DENYLIST`（逗號分隔，預設含 nba／rebounds 等體育統計向關鍵字）過濾後再排序。API 層可選：`PREDICTION_MARKETS_TAG_IDS`（逗號分隔之 `tag_id`，見 Gamma `GET /tags`）、`PREDICTION_MARKETS_EXCLUDE_TAG_IDS`（排除用 tag；請求僅帶第一個 `exclude_tag_id`）；tag 篩選仍不足 3 條時會再合併**無 tag** 之全域成交量後援。
8. 📊 加密市場：區塊①～④（① 儀表板可含管線注入之分區小標：宏觀／衍生品／鏈上／技術；④ 開頭可有一行 **部位摘要**）
9. 🤖 AI 市場：**🤖 區塊①**～④（讀者版抬頭與加密段「區塊①」區分；內容規則同儀表板／新聞／呢喃／精準操作）
10. 【機構速讀｜命題與情境】— 投資命題、支持·反駁、假設、失效、組合框架、三情境、估值錨、事件日曆（**2–3 條**支持／反駁，投行速讀）
11. （系統注入）【SourceHealth】等三行 — 置於 **QSREC 前**、`templates/telegram_report.j2`；**勿寫在儀表板內**
12. `[QSREC_START]` …（與 AI 段 QSREC 合併為同一陣列時由 pipeline 拼接）

**Telegram HTML 與免責（產品約定）**：戰報 HTML 僅允許白名單標籤（`b` `i` `u` `s` `code` `blockquote` `a`），見 `telegram_sender.sanitize_telegram_html`；**不採** `<tg-spoiler>`，以免與 Gate／去標籤邏輯不一致。免責維持 `<blockquote>` 與模板位置；AI 儀表抬頭維持 **🤖 區塊①**（與加密段「區塊①」字樣區隔靠前綴符號）。

## 2. 區塊順序（AI 下半部）

（已併入上一節第 9 步。）精準操作：**部位摘要（可選）** → **本日選擇理由** → **訊號衝突摘要** → **美股部位框** → 交易卡（不要第二份「今日風險預算：總風險預算 XX%」）。

## 3. 語氣（neutral / 缺資料）

- 禁止：歷史底部明確、必漲必跌、絕佳進場點等**過度確定**用語。
- 允許：若…則…、證據不足、機率偏…、條件式風控。

## 4. 儀表板可讀性

- 每行一個指標；`<code>N/A</code>` 後若需說明，**換行**再寫，避免 `N/ACoinGlass…`。
- Pipeline 會執行 `_fix_glued_na_suffix` 作為保險。

## 5. Gate / 驗證（`main.py`）

- **多組總風險預算百分比衝突**：`validate_report` 會提示整併。
- **QSREC 同 category + 同 asset 不得 LONG+SHORT 並存**：否則驗證失敗並觸發重試。

## 6. 避險基金極簡閱讀（手機優先）

- 提示詞：`crew.py` → `_HEDGE_FUND_BRIEF_RULE`（與 Gate 對齊：**保留**「今日風險預算」「訊號衝突摘要」「本日選擇理由」等關鍵字，縮短內文）。
- 交易欄位：仍須 R:R、最大回撤、勝率、Signal Score、觸發／建倉／失效／敘事—**欄位不刪**，改為單行字數上限。
- 「本日選擇理由」須滿足 `validate_report` 動態選幣／選股長度與關鍵詞（不可為了極簡而低於門檻）。

## 7. 相關程式

- 提示詞：`crew.py` → `_BRIEF_V2_RULE`、`_AI_RISK_BRIDGE_RULE`、`_HEDGE_FUND_BRIEF_RULE`
- 後處理：`main.py` → `_fix_glued_na_suffix`、`_postprocess_report_for_resilience`

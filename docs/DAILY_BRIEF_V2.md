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
7b. **【預測市場熱門】**（可選，production 預設關閉）— Polymarket Gamma 即時熱門二元市場；僅 `PREDICTION_MARKETS_IN_BRIEF=1` 時由 `assemble` 注入 `prediction_market_highlight_lines`，預設不佔用 Telegram 版面。選題：`PREDICTION_MARKETS_KEYWORDS`（逗號分隔，命中題目優先；不足 3 條則退回原 24h 成交量排序）、`PREDICTION_MARKETS_DENYLIST`（逗號分隔，預設含 nba／rebounds 等體育統計向關鍵字）過濾後再排序。API 層可選：`PREDICTION_MARKETS_TAG_IDS`（逗號分隔之 `tag_id`，見 Gamma `GET /tags`）、`PREDICTION_MARKETS_EXCLUDE_TAG_IDS`（排除用 tag；請求僅帶第一個 `exclude_tag_id`）；tag 篩選仍不足 3 條時會再合併**無 tag** 之全域成交量後援。
8. 📊 加密市場：區塊①～④（① 儀表板可含管線注入之分區小標：宏觀／衍生品／鏈上／技術；④ 開頭可有一行 **部位摘要**）
9. 🤖 AI 市場：**🤖 區塊①**～④（讀者版抬頭與加密段「區塊①」區分；AI 儀表板定位為**可交易雷達**：可交易市場 → 基本面／財報錨點 → 需求代理；其下可有 pipeline 產生之 **【財報雷達｜未來 7 天】** 事件預告，不含 EPS／營收共識 forecast）
10. 【機構速讀｜命題與情境】— 投資命題、支持·反駁、假設、失效、組合框架、三情境、估值錨、事件日曆（**2–3 條**支持／反駁，投行速讀）
10b. **〔時事多觀點〕**（**可選**，Phase 5）— 置於 **【機構速讀】之後**、**【SourceHealth】／QSREC 之前**；僅在 **`BRIEF_CURRENT_AFFAIRS=1`** 且結構化 `current_affairs_roundtable` 非空時由模板插入；預設關閉時與既有 **full** 輸出 **byte-identical**。可選 **`STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1`** 強檢 HTML（須同設 `BRIEF_CURRENT_AFFAIRS=1`）。
11. （系統注入）【SourceHealth】等三行 — 置於 **QSREC 前**、`templates/telegram_report.j2`；**勿寫在儀表板內**
12. `[QSREC_START]` …（與 AI 段 QSREC 合併為同一陣列時由 pipeline 拼接）

**Telegram HTML 與免責（產品約定）**：戰報 HTML 僅允許白名單標籤（`b` `i` `u` `s` `code` `blockquote` `a`），見 `telegram_sender.sanitize_telegram_html`；**不採** `<tg-spoiler>`，以免與 Gate／去標籤邏輯不一致。免責維持 `<blockquote>` 與模板位置；AI 儀表抬頭維持 **🤖 區塊①**（與加密段「區塊①」字樣區隔靠前綴符號）。

## 2. 區塊順序（AI 下半部）

（已併入上一節第 9 步。）精準操作：**部位摘要（可選）** → **本日選擇理由** → **訊號衝突摘要** → **美股部位框** → 交易卡（不要第二份「今日風險預算：總風險預算 XX%」）。AI 儀表板不再把模型下載榜當作可交易讀數；HuggingFace／OpenRouter／RSS 僅能作 0–1 行需求代理，且須明確連到已列 ticker 或 ETF，否則省略。

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

## 8. 低風險格式規則（2026-04 補強）

在不擴充 Telegram HTML 白名單前提下（仍限 `b/i/u/s/code/blockquote/a`），套用下列 formatter 規則：

- **重點數字**：`執行摘要` 行內數字（價格／百分比）可用 `<b>` 強調，避免每行堆疊 emoji。
- **手機行寬**：摘要與敘事行建議 `<= 70` 字；過長優先在 `，。；｜` 斷句（軟換行）。
- **交易卡欄位順序固定**：`現價 → 計畫(進場/目標/停損) → 執行 → 失效 → 敘事 → 流動性/執行`。
- **分隔線節制**：`────────────` 以 4 條內為原則，避免視覺疲勞。
- **次要訊號弱化**：Polymarket 預設移出 production 版面；chatter 與區塊②b 僅保留增量資訊，避免重複儀表板／新聞／交易理由。

> 產品決策延續：不採 `<pre>`、`<details>`、`<summary>`、`<br>`；`🤖 區塊①` 命名維持不變。

### 建議 rollout（A/B/C）

- **Phase A（立即）**：摘要數字強調、軟換行、emoji 降噪、分隔線節制（不改 Gate 契約）。
- **Phase B（低風險）**：次要資訊下沉與段落節奏調整（不改標題/區塊識別）。
- **Phase C（產品實驗）**：可選雙訊息推送（完整版＋輕量版）；先做 1–2 週 A/B 觀測。

### 驗收指標

- `validate_report` blocking 率不得上升。
- Telegram parser entity error 率不得上升。
- 交易段欄位完整率（進場/目標/停損/失效）維持或提升。
- 手機端可讀性代理指標改善（超長行數下降）。

# Brief Block Reference（區塊對照表）

> Phase 2 交付物之一：列出 `brief_profiles.BLOCK_IDS` 中每個區塊在「後端模板 / `DailyBriefReport` 欄位 / 前端 `structuredBlockContent.kind` / 前端專用元件」四個維度的對照，便於新增區塊或重構時維持一致性。
>
> 來源：
> - 後端：`brief_profiles.BLOCK_REGISTRY`（`templates/daily_brief_jinja/` 內 `_<block>.j2` 巨集）
> - 前端結構化：`data-verification-ui/src/components/report/structuredBlockContent.js`
> - 前端派送：`data-verification-ui/src/components/report/BlockSection.jsx`
> - 前端 legacy 後援：`data-verification-ui/src/components/report/legacyBlockContent.js`

## 1. 對照表

| # | block_id | 後端巨集（`BLOCK_REGISTRY`） | 主要 `DailyBriefReport` 欄位 | 結構化 `kind` | 前端專用元件 | 備註 |
|---|---|---|---|---|---|---|
| 1 | `header` | `_header.j2` → `telegram_header` | `crypto.report_title_date` | `text` | `TextSummaryBlock` | 僅日期標題 |
| 2 | `exec_summary` | `_exec_summary.j2` → `telegram_exec_summary` | `crypto.exec_summary[]`、`crypto.investment_thesis_one_liner` | `text` | `TextSummaryBlock` | 投資命題 + 子彈列點 |
| 3 | `previous_recs` | `_previous_recs.j2` → `telegram_previous_recs` | `previous_recs_html` | `html` | `TrustedHtmlBlock` | 由後端渲染為 HTML |
| 4 | `market_mode` | `_market_mode.j2` → `telegram_market_mode` | `crypto.market.regime`、`crypto.market.scorecard_lines`、`crypto.narrative_of_day` | `text` | `TextSummaryBlock` | 制度 / 評分卡 / 主敘事 |
| 5 | `macro_framework` | `_macro_framework.j2` → `telegram_macro_framework` | `crypto.macro_framework_lines[]` | `text` | `TextSummaryBlock` | 多行文字列表 |
| 6 | `prediction_markets` | `_prediction_markets.j2` → `telegram_prediction_markets` | `crypto.prediction_market_highlight_lines[]` | `text` | `TextSummaryBlock` | 候選：未來可升級為條列卡片 |
| 7 | `crypto_dashboard` | `_crypto_dashboard.j2` → `telegram_crypto_dashboard` | `crypto.dashboard[]` | `metrics` | `MetricsDashboardBlock` | 已有專用元件 |
| 8 | `crypto_news` | `_crypto_news.j2` → `telegram_crypto_news` | `crypto.news[]` | `news_items` | `NewsItemsBlock` | 已有專用元件 |
| 9 | `crypto_chatter` | `_crypto_chatter.j2` → `telegram_crypto_chatter` | `crypto.chatter[]`、`crypto.x_highlights[]` | `text` | `TextSummaryBlock` | 候選：可升級為 ChatterBlock（作者/情緒） |
| 10 | `crypto_trades` | `_crypto_trades.j2` → `telegram_crypto_trades` | `crypto.trade_legs[]`、`crypto.crypto_block4_recommendation_line` | `trades` | `TradesBlock` | 已有專用元件 |
| 11 | `ai_bridge` | `_ai_bridge.j2` → `telegram_ai_bridge` | `ai.macro_bridge_lines[]` | `text` | `TextSummaryBlock` | 多行文字列表 |
| 12 | `ai_dashboard` | `_ai_dashboard.j2` → `telegram_ai_dashboard` | `ai.dashboard[]` | `metrics` | `MetricsDashboardBlock` | 已有專用元件 |
| 13 | `ai_news` | `_ai_news.j2` → `telegram_ai_news` | `ai.news[]` | `news_items` | `NewsItemsBlock` | 已有專用元件 |
| 14 | `ai_chatter` | `_ai_chatter.j2` → `telegram_ai_chatter` | `ai.chatter[]`、`ai.x_highlights[]` | `text` | `TextSummaryBlock` | 候選：同 `crypto_chatter` |
| 15 | `ai_trades` | `_ai_trades.j2` → `telegram_ai_trades` | `ai.trade_legs[]`、`ai.ai_block4_recommendation_line` | `trades` | `TradesBlock` | 已有專用元件 |
| 16 | `current_affairs_roundtable` | `_roundtable.j2` → `telegram_roundtable` | `current_affairs_roundtable.{topic, voices[]}` | `roundtable` | `CurrentAffairsRoundtableBlock` | 已有專用元件 |
| 17 | `institutional_view` | `_institutional_view.j2` → `telegram_institutional_view` | `crypto.investment_thesis_one_liner`、`crypto.thesis_*`、`crypto.key_assumptions_lines[]`、`institutional_disclaimer_html` | `text` / `html` / `institutional_split` | `TextSummaryBlock` / `TrustedHtmlBlock` / `InstitutionalViewBlock` | 三種 kind 路徑皆已處理 |
| 18 | `source_health` | `_source_health.j2` → `telegram_source_health` | `source_observability_block`（文字或 HTML） | `text` 或 `html` | `TextSummaryBlock` / `TrustedHtmlBlock` | 依內容是否含 `<` 自動切換 |
| 19 | `qsrec` | `_footer_tail.j2` → `telegram_footer_tail` | `crypto.qsrec[]`、`ai.qsrec[]`、`low_confidence_disclaimer` | `trades` | `TradesBlock` | 已有專用元件（低信心 disclaimer） |

## 2. `kind` → 前端元件派送表

| `kind` | 元件（`blocks/`） | 來源 |
|---|---|---|
| `text` | `TextSummaryBlock` | 純文字多段落 |
| `html` | `TrustedHtmlBlock` | 白名單 sanitize 過的 HTML |
| `metrics` | `MetricsDashboardBlock` | `DashboardEntry[]` |
| `news_items` | `NewsItemsBlock` | `NewsItem[]` |
| `trades` | `TradesBlock` | `{ rows, introHtml?, disclaimer? }` |
| `roundtable` | `CurrentAffairsRoundtableBlock` | `{ topic, voices[] }` |
| `institutional_split` | `InstitutionalViewBlock` | `{ thesisText, disclaimerHtml }` |
| `skip` | — | `BlockSection` 直接 `return null` |

注意：`NewsLinesBlock` 存在於 `blocks/` 但目前 `structuredContentForBlock` 不會回傳 `news` kind；僅供 `legacyContentForBlock` 後援使用。

## 3. 缺漏與補齊狀態（Phase 2）

- ✅ 19 個 `block_id` 全部在 `structuredContentForBlock` 有對應分支，無 fall-through。
- ✅ `legacyBlockContent.blockSectionTitle` 對 19 個 `block_id` 皆有中文標題，確保 structured 與 legacy 路徑一致。
- ✅ `BlockSection.jsx` 已覆蓋全部 `kind`；無未處理的回傳形態。

## 4. 可選專用元件（未實作，供後續 PR 評估）

| 區塊 | 現況 | 建議升級 |
|---|---|---|
| `prediction_markets` | 以 `text` 渲染多行字串 | `PredictionMarketBlock`：機率 / 到期 / 事件聚合卡 |
| `crypto_chatter` / `ai_chatter` | 以 `text` 串接 `chatter[].text` + `x_highlights[]` | `ChatterBlock`：保留作者、情緒、連結；`x_highlights` 另行小節 |
| `macro_framework` / `ai_bridge` | 以 `text` 多行 | `BulletListBlock`：條列卡加標記，仍相容 `text` 後援 |

> 這些屬於 UX 強化，不影響 V2 結構化合約（`structuredBlockContent` 輸出仍可回傳 `text`，升級時再新增 `kind` 與對應元件即可）。

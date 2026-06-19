# Options Flow + GEX — Portal 前端設計

> 狀態：**設計稿（design only）**，尚未實作 React。後端讀取 API 已就緒（[`api_routers/options.py`](../api_routers/options.py)）。
> 對齊：5 板塊 IA（`/news` `/dashboard` `/insights` `/columns` `/portfolio`）、[`Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md)、CHANGELOG **2026-06-19**。
> 紅線：數字由 Python 算好經 API 注入；前端只渲染，不自算；缺料顯示 `[DATA_MISSING]`／pending 狀態，不捏造。

## 1. 後端契約（已實作，placement-independent）

| Endpoint | 用途 | 回應（data） | 回應（pending） |
|----------|------|--------------|-----------------|
| `GET /api/options/summary` | watchlist 級 GEX + 異常流計數 | `{enabled:true, watchlist, items:[{underlying, gex:{total_gex,call_gex,put_gex,spot_price,regime,trade_date}, unusual_count}]}` | `{enabled:false, reason:"polygon_options_pending", hint, watchlist, items:[]}` |
| `GET /api/options/gex/{sym}` | 單標的最新 GEX + 60 日歷史 | `{enabled:true, underlying, gex, history:[{trade_date,total_gex,call_gex,put_gex,spot_price}]}` | `{enabled:false, reason:"polygon_options_pending"}` |
| `GET /api/options/flow/{sym}` | 單標的近期異常流訊號 | `{enabled:true, underlying, signals:[{trade_date,option_ticker,signal_type,score,premium,volume,open_interest,rationale}]}` | `{enabled:false, reason:"polygon_options_pending"}` |

**三態**：`enabled:false`（Polygon 未上線 → pending 卡）／`enabled:true` 但空（`reason:"no_data_yet"` → 等首跑）／`enabled:true` 有資料。前端對三態各有對應 UI，契約上線前後不變。

## 2. IA placement（**待使用者確認**）

選項（建議 A）：

- **A（建議）Insights 新分頁「選擇權流」**：`insights-tab-options`，承接既有 symbol-level 分析（與 `SymbolDeepDive` 同調）。symbol 由 `?symbol=` 或 watchlist 選擇。
- **B Dashboard GEX 條**：GEX 屬市場結構（造市商定位），可在 `DashboardHome` 加一條「半導體 GEX 概覽」strip（watchlist summary），symbol 細節仍跳 Insights。
- **C 兩者都做（分期）**：Phase 1 = Insights 分頁（完整）；Phase 2 = Dashboard 概覽 strip + `SymbolDeepDive` 內嵌 GEX 小卡。

> 預設推 **A**（最小、symbol 導向、與現有 Insights 慣例一致）。確認後再開 React 實作。

## 3. 資料層（react-query hooks，新增於 [`useApi.js`](../data-verification-ui/src/hooks/useApi.js)）

```js
export function useOptionsSummary() { /* GET /api/options/summary; refetch 對齊 terminal interval */ }
export function useOptionsGex(symbol) { /* enabled: !!symbol */ }
export function useOptionsFlow(symbol) { /* enabled: !!symbol */ }
```

沿用既有 `isHardApiError` / `getTerminalRefetchIntervalMs` 慣例；pending（`enabled:false`）視為**正常回應**不報錯。

## 4. 元件樹（Phase 1 — Insights 分頁 A）

```
modules/insights/pages/OptionsFlowHome.jsx        // 分頁容器（lazy，對齊 InsightsHome Suspense）
  ├─ OptionsPendingCard.jsx                        // enabled:false → 顯示 reason + hint（上線步驟）
  ├─ OptionsWatchlistStrip.jsx                     // summary items：每標的 GEX regime chip + unusual 計數
  ├─ GexPanel.jsx                                  // 單標的：total/call/put GEX 讀數 + 正負 gamma regime
  │    └─ GexHistoryChart.jsx                       // 60 日 total_gex 折線（lightweight-charts，lazy）
  └─ UnusualFlowTable.jsx                           // 近期訊號：type/score/premium/volume/rationale；桌機表格 + 手機卡片
```

- **狀態樣式**：pending → `OptionsPendingCard`；`no_data_yet` → 空狀態「等待首次管線執行」；有資料 → 正常。
- **regime 色**：正 gamma（抑制波動）綠、負 gamma（放大波動）紅；數字一律照 API，不在前端重算或換單位。
- **a11y / 觸控**：沿用 44px 觸控、`data-testid`（`insights-tab-options`、`options-watchlist`、`gex-panel`、`unusual-flow-table`、`options-pending`）。

## 5. 分期任務（待 placement 確認後進 `/agent-action`）

| Phase | 範圍 | 驗證 |
|-------|------|------|
| F1 | hooks + `OptionsFlowHome` + pending/empty/data 三態 + watchlist strip | `npm run lint` + 新 E2E `options-flow-route.spec.js`（mock API 三態） |
| F2 | `GexPanel` + `GexHistoryChart`（lightweight-charts lazy） | E2E：有資料時渲染圖與讀數 |
| F3 | `UnusualFlowTable`（桌機/手機） + symbol 切換（`?symbol=`） | E2E：切換標的更新 flow |
| F4（選） | Dashboard GEX 概覽 strip（placement B/C） | `dashboard-route.spec.js` 擴充 |

每階段：mock API server（[`e2e/mock-api-server.mjs`](../data-verification-ui/e2e/mock-api-server.mjs)）補三個 endpoint fixture；`npm run lint && npm run build && npm run test:e2e` 綠才算完成。

## 6. 上線相依（與後端一致）

1. Polygon Options 訂閱 + `POLYGON_API_KEY`（Secret Manager）。
2. 跑 `scripts/options_flow_tick.py` 或 GH workflow 產生 BQ 歷史。
3. 設 `OPTIONS_GEX_HISTORY_TABLE` / `OPTIONS_UNUSUAL_TRADES_TABLE`（未設 → API 回 pending，前端顯示等待卡，**不阻塞**其他板塊）。

> 在 1–3 完成前，前端可先以 mock fixture 開發與 E2E；pending 狀態本身就是正式 UI 的一環。

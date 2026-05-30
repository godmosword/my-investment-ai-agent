# Code Review Request — Q-Silicon Frontend UI/UX Implementation

請 review 下列檔案（相對於 repo 根目錄 `data-verification-ui/src/`）。Build 預期通過（`npm run build`）。請獨立審查 **正確性、品質、安全性、可維護性**。

## Modified files

- `src/index.css` — responsive breakpoints（768px、1280px）、`.side-nav`、`.sse-dot`
- `src/app/layout/Shell.jsx` — SideNav、內層 wrapper、`md:flex-row`
- `src/components/SymbolCandleChart.jsx` — period tabs、MA20/MA50、volume histogram
- `src/modules/insights/pages/InsightsHome.jsx` — regime glow、`SignalPipeline`
- `src/components/report/blocks/MetricsDashboardBlock.jsx` — SVG sparkline
- `src/components/report/blocks/NewsItemsBlock.jsx` — urgency、`UrgencyBadge`
- `src/App.jsx` — root `ErrorBoundary`
- `src/components/common/AsOfChip.jsx` — `role="status"`、`aria-label`
- `src/components/BottomNav.jsx` — `nav` / `NavLink` `aria-label`

## New files

- `src/app/layout/SideNav.jsx`
- `src/modules/investment-analysis/pages/AnalysisHome.jsx`
- `src/modules/industry-trends/pages/IndustriesHome.jsx`
- `src/modules/quant-trading/pages/QuantHome.jsx`
- `src/components/ErrorBoundary.jsx`

## Stack / context

- React 18, React Router 6, TanStack Query, Tailwind, lightweight-charts v5
- Theme: `#070a12`, accent `#2ee6be`, `#8b5cf6`
- API hooks: `src/hooks/useApi.js` — 請核對新頁面 hook 簽名
- Tokens: `src/design/tokens.js` + `index.css` CSS variables

## E2E（請對照選擇器是否仍命中）

此專案 Playwright spec 位於 **`data-verification-ui/e2e/`**，目前為 **8** 支 `*.spec.js`（非 10）：

- `structured-report-route.spec.js`
- `positions-route.spec.js`
- `cross-page-btc-price.spec.js`
- `today-btc-mismatch-banner.spec.js`
- `briefs-alias-route.spec.js`
- `terminal-state-matrix.spec.js`
- `terminal-spy-mismatch.spec.js`
- `nvda-cross-route-banner.spec.js`

Layout 新增 `SideNav`、桌面版結構變更時需特別檢查。

## Reviewer 優先熱點（必查）

1. **`SymbolCandleChart`**：`createChart` effect 與 `hasVolume` / 初次是否有資料的 **lifecycle**；`filteredData` 與 ref 掛載順序是否可能造成圖表永不建立或 volume 軸漏建。
2. **`SseDot` / SSE**：須與 **`useWarRoomSse` / `WarRoomSseProvider`** 單一連線一致（含 `VITE_SSE_STREAM_KEY` query）；禁止重複 `EventSource` 又漏 key。
3. **`useApi.js`**：`useMetricsLatest`、`useExecutionIntents` 與 `AnalysisHome` / `IndustriesHome` / `QuantHome` 的 **payload 欄位**（例如 `paper_fill_price` / `paper_exit_price`、`PAPER_CLOSED`）是否一致。

## 請檢查項目

- Loading / error / empty 狀態
- 記憶體：`EventSource`、chart teardown、`ResizeObserver`
- 圖表：period 切換時 series / markers 是否一致
- 衍生數值：NaN、null clamp
- ARIA / 鍵盤
- CSS：breakpoint 與 Tailwind 是否衝突（例如 `.metrics-grid` cascade）
- React：`useEffect` / `useCallback` deps、list keys、stale closure

## 輸出格式

依嚴重度列出：**CRITICAL / HIGH / MEDIUM / LOW**，每則含檔案路徑、說明、建議修復。

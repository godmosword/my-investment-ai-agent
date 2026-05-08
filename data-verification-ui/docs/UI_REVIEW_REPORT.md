# UI Code Review Report — Q-Silicon PWA（交接計畫對照）

本報告依 [`docs/UI_REVIEW_PROMPT.md`](UI_REVIEW_PROMPT.md) 範圍與優先熱點整理；**本次 session 已合併修正**若干 HIGH 項目，下列「修復狀態」供驗收對照。

## CRITICAL

**（已修復）QuantHome 與 `execution_intents` 契約不一致**

- **問題**：前端使用 `paper_entry`／`paper_exit` 與 `CLOSED`／`EXITED`，後端／JSONL 契約為 **`paper_fill_price`／`paper_exit_price`**、狀態 **`PAPER_CLOSED`**（見 repo 根目錄 [`execution_intents.py`](../../execution_intents.py)、[`test_paper_execution.py`](../../test_paper_execution.py)）。
- **影響**：勝率／平均盈虧 KPI 與表格進出場價錯誤或永遠為空。
- **修復**：[`QuantHome.jsx`](../src/modules/quant-trading/pages/QuantHome.jsx) 改以 **`paper_fill_price`／`paper_exit_price` 為主**（保留舊別名 fallback）、已結算列含 **`PAPER_CLOSED`**（並保留 `CLOSED`／`EXITED` legacy）；**StatusPill** 補 **`PAPER_*`**；文案欄位 **`thesis_one_liner`** fallback。

## HIGH

**（已修復）SideNav 重複 `EventSource` 且未帶 `stream_key`**

- **問題**：[`SideNav.jsx`](../src/app/layout/SideNav.jsx) 另開 `/api/stream/war-room`，與既有橋接重複，且漏 **`VITE_SSE_STREAM_KEY`**。
- **修復**：[`useWarRoomSse.js`](../src/hooks/useWarRoomSse.js) 改為 **`WarRoomSseProvider`**（單一連線 + query）；[`App.jsx`](../src/App.jsx) 以 Provider 包住應用；**刪除** `WarRoomSseBridge.jsx`；**`SseDot`** 改 **`useWarRoomSseStatus()`** 僅顯示狀態。
- **殘餘風險**：`EventSource` `onerror` 後瀏覽器會自動重連；狀態燈可能短暫 **`error`** — 屬平台行為，非重複連線問題。

**（已修復）SymbolCandleChart：空資料時無 `ref`、chart effect 依賴 `[]` + `hasVolume`**

- **問題**：初次無 OHLC 時提早 return 導致 **`rootRef` 未掛載**；資料晚到時圖表永不建立；volume 與建立時 **`hasVolume`** 不同步。
- **修復**：[`SymbolCandleChart.jsx`](../src/components/SymbolCandleChart.jsx) 以 **`hasPriceData`** 驅動建立／銷毀 chart，`useEffect` 依賴 **`[hasPriceData, hasVolume]`**；移除不當 **`eslint-disable`**。

**（已修復）`.metrics-grid` 桌面四欄被後置 base 規則覆蓋**

- **修復**：[`index.css`](../src/index.css) 將 **mobile-first `.metrics-grid` base** 前移，`@media (min-width: 768px)` 之 **`repeat(4, 1fr)`** 可正常生效。

## MEDIUM

**圖表在 `hasVolume` false→true 時會整張重建**

- **說明**：現行以重建 chart 確保 histogram／scale 正確；若頻繁切換 period 導致 **`hasVolume`** 閃爍，可能有輕微閃爍或 **`fitContent`** 重算。
- **建議（第二波）**：改為 **`removeSeries`／`addSeries`** 或固定保留 volume scale，僅更新資料。

**E2E 與 nav 結構**

- **範圍**：[`e2e/`](../e2e/) 共 **8** 支 `*.spec.js`（見交接計畫）；**SideNav／Shell** 變更後請對照 **`nav`／連結／role** 是否仍命中。
- **建議**：於 CI 跑 **`npm run test:e2e`**（ mock 環境就緒時）。

## LOW

- **`useWarRoomSse.js` 使用 `createElement` 避免 `.js` 檔 JSX**：可維護；若團隊偏好可改 **`useWarRoomSse.jsx`**。
- **QuantHome `reference_entry_price` 作為進場顯示 fallback**：僅顯示用途；與紙上成交價 **`paper_fill_price`** 語意不同 — 可於 UI 標註「參考／成交」若需更嚴格。

---

## Reviewer 執行核對（指令）

- `cd data-verification-ui && npm run build && npm run lint`
- （可選）`npm run test:e2e`

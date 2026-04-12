# Bloomberg Terminal 對齊藍圖（Q-Silicon）

本文件定義「對齊 Bloomberg Terminal」在本 repo 的可驗收範圍：  
重點是 **機構工作流與資料可審計性**，不是外觀複製。

關聯文件：
- 儀表板與 API 契約：[docs/DASHBOARD_CONTRACT.md](docs/DASHBOARD_CONTRACT.md)
- 產品與技術路線：[docs/ROADMAP_VISION.md](docs/ROADMAP_VISION.md)
- 工程待辦總表：[TODOS.md](TODOS.md)

---

## 1) 對齊原則（Scope）

1. 對齊「工作方式」：多資產監控、時間序列 + 事件、投組風險框架、快速切換。
2. 對齊「資料密度」：每個關鍵數值皆能標示來源與時間（as-of）。
3. 對齊「可審計性」：所有客觀數字必須可回溯到工具/BQ，不可由 LLM 推導。
4. 不對齊「專有資產」：Bloomberg 專有欄位、聊天網路、品牌 UI 不納入。

---

## 2) 紅線（不可破）

1. 客觀數據只能來自工具層/BigQuery；不得在渲染層捏造。
2. `validate_report` 仍是日報可信度的最終 Gate，不因終端化放寬。
3. API/PWA 僅做讀取與監控，不替代主管線事實產生流程。

---

## 3) 能力映射（Terminal Capability Map）

| Terminal 能力 | 現況 | 下一步 |
|---|---|---|
| 多監控清單（Launchpad） | War Room + 多頁面 | **Phase 2**：Terminal v2 多分組 + 模板（`qs_terminal_workspace_v2`）、v1 遷移 |
| Symbol 深度頁 | `/api/symbols/{ticker}/snapshot` + Terminal 卡 | **Phase 2**：跨頁 `SymbolFocusBar`（`qs_symbol_focus_v1`）與卡片「設為全域關注」 |
| 事件與價格關聯 | 報告有結構化建議、圖表有時序 | OHLC 上疊加 QSREC/事件標記 |
| 投組/風險 | trades/performance + open positions | watchlist／symbol focus 已接；狀態面板持續迭代 |

---

## 4) 驗收清單（Phase 0 Definition of Done）

以下 15 條至少通過 12 條，才可宣稱「Bloomberg 對齊 Phase 0」：

1. 單一 ticker 可在一頁看到「快照 + 趨勢 + 建議摘要」。
2. 每個 KPI 顯示 `as_of`（時間戳）與資料來源說明。
3. API 鍵名與 [docs/DASHBOARD_CONTRACT.md](docs/DASHBOARD_CONTRACT.md) 一致。
4. 錯誤態明確（不可靜默失敗）；可區分網路錯誤 vs 無資料。
5. demo/mock 與實盤資料視覺上可辨識（提示條）。
6. 同一 ticker 在 Today / Charts / 新頁顯示一致。
7. watchlist/workspace 可保存與恢復（至少 localStorage）。
8. workspace 允許快速重排卡片順序（不需重新載入）。
9. OHLC 圖可疊加 QSREC 事件點（entry/target/stop）。
10. 事件標記僅來自結構化資料，不從自由文字猜測。
11. API 端點有 pytest 覆蓋（正常、404、參數錯誤、BQ 異常）。
12. 前端新增視圖不破壞既有路由與底部導覽。
13. 變更同步更新 CHANGELOG + TODOS（雙向對齊）。
14. 不新增會破壞 Telegram HTML 白名單的輸出流程。
15. 不引入未審核的即時付費資料依賴。

---

## 5) 分階實作路徑（Execution Slices）

1. **Slice A**：Symbol Snapshot API + 測試 + 契約欄位。  
2. **Slice B**：PWA Symbol 深度頁（快照、趨勢、報告連結）。  
3. **Slice C**：Workspace（可儲存、可重排）串接 Symbol 卡。  
4. **Slice D**：OHLC + QSREC/事件標記。  
5. **Phase 2**：Workspace 分組／模板、跨頁 Symbol Context、Streamlit 與 API 共用 snapshot 組裝（`symbol_snapshot_service` + 可選 `SYMBOL_SNAPSHOT_HTTP_BASE`）。

每個 slice 落地後都需同步更新 [CHANGELOG.md](CHANGELOG.md) 與 [TODOS.md](TODOS.md)。

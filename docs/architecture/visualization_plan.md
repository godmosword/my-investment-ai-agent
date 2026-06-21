# 視覺化 UX/UI 計劃 — 剩餘工作與維護

> **說明**：本檔保留 **原則**、**已封存至 CHANGELOG 之交付索引**，以及 **未完成 backlog**。完整已交付行為請以 **[`CHANGELOG.md`](../../CHANGELOG.md)** 為準（尤其 **`## 2026-04-18`** 之 `### Added`／`### Changed`／`### Docs`）。日報後端模組化 Phase 1–5 見 [`modularization_plan.md`](modularization_plan.md)（維護導覽）。
>
> **長線願景對照**：[`ROADMAP_VISION.md`](../ROADMAP_VISION.md) 方向 1（穩定視覺化）、演進藍圖 Phase 4（須產品拍板）。階段 A–D **速覽**見本檔 [附錄](#appendix-stages-abcd)。
>
> **三條產出線**：Telegram HTML 日報、Streamlit War Room（[`dashboard.py`](../../dashboard.py)）、PWA Terminal（[`data-verification-ui/`](../../data-verification-ui/)）。
>
> 關聯：[`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md)、[`BLOOMBERG_ALIGNMENT.md`](../BLOOMBERG_ALIGNMENT.md)、[`TERMINAL_MID_TIER_ROADMAP.md`](../TERMINAL_MID_TIER_ROADMAP.md)、[`DAILY_BRIEF_V2.md`](../DAILY_BRIEF_V2.md)、[`PWA_WEB_PUSH.md`](../PWA_WEB_PUSH.md)、[`PWA_OFFLINE.md`](../PWA_OFFLINE.md)。
>
> **Phase 1（隊列 27）**：staging 端到端執行稿、環境核對與 **TODOS／CHANGELOG 回填模板**見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)（與 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **Phase 1** 小節對齊）。

---

## 1) 產品與設計原則（不變）

1. **紅線不動**：LLM 不捏造客觀數字；UI 只讀／可寫範圍遵循專案契約；Telegram HTML 白名單不放寬。
2. **單一 schema、多層呈現**：`DailyBriefReport`（Pydantic）為 SSOT；各端為 presentation。
3. **Profile-aware**：UI 可顯示／切換讀取用 profile（不擅自改 production 管線 `REPORT_PROFILE`）。
4. **as-of 一等公民**：時間戳與來源可辨；mock／staging 有 banner。
5. **漸進增強**：REST → SSE → Web Push；保守離線策略下 API **不快取**。
6. **`REPORT_PROFILE=full`** 與 Telegram 凍結基線 **byte-identical** 不可退（與 modularization 紅線一致）。

---

## 2) 已交付（索引 — 不重複實作細節）

| 標籤 | 摘要 | 出處 |
|------|------|------|
| **V1** Design Foundation | `tokens.js`、`DESIGN.md`、共用元件（AsOfChip、ProvenancePopover、ProfileBadge、GateStatusBadge 等）、Tailwind extend、dev `/design` | CHANGELOG **2026-04-18** `### Added` |
| **V2** 結構化 Report 主線 | `GET /api/reports/{date}/structured`、`StructuredReportView`、`structuredBlockContent`／`legacyBlockContent`、Gate 橫幅與區塊級 badge | CHANGELOG **2026-04-18**；[`api.py`](../../api.py)；[`test_report_structured_api.py`](../../test_report_structured_api.py) |
| **V3** 局部 | `?profile=`、`BriefProfileBar`、`GET /api/reports?profile=`（Archive 列表）、`GET /api/brief-layouts`、`GET /api/reports/profile-stats` | [`api.py`](../../api.py)；[`test_reports_profile_api.py`](../../test_reports_profile_api.py) |
| **V4** 局部 | `GateIssuesDrawer`／`GateIssuesNavigator`、`SymbolCandleChart` markers、`CurrentAffairsRoundtableBlock.jsx` | `data-verification-ui/src/components/` |
| **原 V6 主線** | **`dashboard/theme.py`**、**`st.tabs`**（Overview／Profile／Gate／Roundtable）、**`DASHBOARD_AUTO_REFRESH_SEC`** | CHANGELOG **2026-04-18** `### Added` |
| **離線** | Workbox：**API NetworkOnly**；[`PWA_OFFLINE.md`](../PWA_OFFLINE.md) | CHANGELOG **2026-04-18** |

以下「痛點」僅列出 **仍待 backlog 補齊** 者（已解決者已自舊版刪除，避免與現況矛盾）。

---

## 3) 剩餘 Backlog（可驗收）

### Phase 1 — 隊列 27（staging 關帳，repo 已備執行稿）

- **Repo**：[`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)（環境表、步驟、完成標準、回填剪貼範本）；總表對齊見 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **Phase 1**。
- **人類 staging**：`BRIEF_CURRENT_AFFAIRS=1` 下跑通後，依該檔「回填到哪裡」更新 `TODOS.md` 隊列 **27** 或頂部同步狀態；可選 `CHANGELOG` `### Ops`。

### V2 — 結構化 Report（補齊）

- [x] **`exec_summary`／`market_mode`**：`ExecSummaryBlock`／`MarketModeBlock`；`structuredBlockContent` 輸出結構化 payload（命題／條列、制度／敘事／評分卡），legacy 以 `fallbackText` 承接舊版摘要。
- [x] **`crypto_dashboard`／`current_affairs_roundtable` 專用呈現 + 可驗收錨點**：`BlockSectionShell` 可選 **`data-section`**（對應 `block_id`）；[`MetricsDashboardBlock`](../../data-verification-ui/src/components/report/blocks/MetricsDashboardBlock.jsx)／[`CurrentAffairsRoundtableBlock`](../../data-verification-ui/src/components/report/blocks/CurrentAffairsRoundtableBlock.jsx) 接上；E2E mock 補 `crypto.dashboard`／根層 `current_affairs_roundtable`；[`structured-report-route.spec.js`](../../data-verification-ui/e2e/structured-report-route.spec.js) 斷言 `data-section`／`data-testid="current-affairs-roundtable-topic"`。
- [ ] 其餘 **`block_id` 專用 JSX 元件**（如 News、…）逐步取代 placeholder／僅 legacy 路徑（依 `BLOCK_REGISTRY` 對照表擴充）。
- [ ] 可選：**BQ 或集中儲持久化 `DailyBriefReport` JSON** 供營運稽核（現以本機 JSON／`raw_data`／`.qsilicon` 為主）。

### V3 — Profile／Layout UX

- [x] **`useBriefLayouts` 版面預覽 UI**（唯讀；API 回傳 **`applies_to_profile`／`blocks`／`parse_error`**，`BriefLayoutsReference` 展開順序）。
- [x] Archive：**profile 分布視覺化** — **`GET /api/reports/profile-stats`** + **`BriefProfileStatsBar`**（結構化旗標路徑）。

### V4 — Roundtable + 互動（收尾）

- [x] **Mock／Playwright 結構化 smoke**：`mock-api-server` 含 `current_affairs_roundtable`／`crypto.dashboard` 時，PWA 區塊視圖可驗 **`data-section`** 與 **`current-affairs-roundtable-topic`**。**Phase 1**：端到端 staging 手順／回填模板見 [`docs/STAGING_CURRENT_AFFAIRS_SMOKE.md`](../../docs/STAGING_CURRENT_AFFAIRS_SMOKE.md)（**人類**關帳；非 CI）。
- [ ] Streamlit **Gate／Roundtable** 分頁已於 v4 交付；若與 PWA **像素級**仍差異，逐項列 issue 對照（regime／typography）。

### V5 — 即時化與通知

- [x] **SSE 全頁**：`/api/stream/war-room` → **`metrics`／`report`／`positions.open`／`war-room`** 等 **invalidate**（`VITE_SSE_ENABLED=1`）；意圖 PATCH 成功時同步。
- [x] **Web Push 深連結**：`service-worker.js` **`notificationclick`** → **`report_date` + `block_id`** 深連結；與 [`PWA_WEB_PUSH.md`](../PWA_WEB_PUSH.md) 契約一致。
- [x] **Today 離線橫幅**：`/today` 在 `navigator.onLine===false` 時顯示 **`data-testid="today-offline-banner"`**（可選 **預快取** `/today`／最新報告、**as_of** 離線提示仍為後續；API 仍 **NetworkOnly**，見 [`PWA_OFFLINE.md`](../PWA_OFFLINE.md)）。
- [x] **`/settings`**：**`/settings`** 路由 + BottomNav；**VAPID／Register／API URL**、**SW**、**`qsilicon_push_prefs`**；測試推送仍以 **`POST /api/push/test-send`**（管理金鑰）為準。

### V6 — 戰情室與 PWA 視覺對齊（剩餘）

- [ ] Symbol 快照區與 **`TerminalSymbolCard`** **同構**（provenance／格式）。
- [ ] regime／KPI **Streamlit ↔ PWA** 細節一致（theme v4 後逐項對照）。

---

## 4) 跨 Phase 契約

| 契約 | 屬於 |
|------|------|
| 新 API 同步 [`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md) | V2／V3／V5 |
| Gate／profile UI：**pytest（API）** + 前端測試／E2E 視需要 | V2 起 |
| Telegram HTML 白名單不擴 | 全部 |

---

## 5) 風險與對策（摘要）

| 風險 | 對策 |
|------|------|
| PWA 快取誤傷新資料 | 維持 API NetworkOnly；顯示 **as_of** + 手動刷新 |
| 結構化 API 與 schema 漂移 | 端點 pytest；重大 schema 變更進 CHANGELOG |
| Web Push 靜默失敗 | `/settings` 訂閱狀態 + 測試推送（待做） |

---

## 6) 延伸閱讀

- 日報模組化（Phase 1–5）：[`modularization_plan.md`](modularization_plan.md)
- Bloomberg 對齊：[`BLOOMBERG_ALIGNMENT.md`](../BLOOMBERG_ALIGNMENT.md)
- Terminal 中段：[`TERMINAL_MID_TIER_ROADMAP.md`](../TERMINAL_MID_TIER_ROADMAP.md)

---

<a id="appendix-stages-abcd"></a>

## 附錄：階段 A–D 路線速覽

**目的**：把「圖表／Terminal／Telegram 附圖」與 **資料信任邊界**（工具層、BQ、已選公開 API）對齊。**契約主檔**：[`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md)。

### 紅線（全階段共通）

1. **不得讓 LLM 捏造圖上客觀數字**：敘事與 `<code>` 仍依日報 Gate；圖表僅展示可追溯序列或已注入 context 之值。
2. **單一路徑語意**：改 `symbol_snapshot_service`／`api.py`／PWA 消費欄位時，**同步**契約與（若使用）OpenAPI。
3. **分階交付**：重大行為變更以 **環境開關** 或獨立 PR 收斂。

### 階段 A — 契約與可追溯性（優先）

**目標**：OHLC、`/quote` last、`latest_metrics`（BQ）三條來源與 `price_alignment` 語意寫進契約；Streamlit Symbol 快照提供可讀口徑（對齊 T2a／T2c）。
**狀態（2026-04-14）**：✅ 已落地。

### 階段 B — PWA／Terminal（讀者端體驗）

溯源 UI、`price_alignment.aligned === false` 的非靜默提示、輪詢與快取節奏（對齊 T2b、T3c、`docs/TERMINAL_MID_TIER_ROADMAP.md`）。

### 階段 C — Telegram `visualizer.py`（可選強化）

**現況**：[`visualizer.py`](../../visualizer.py) `generate_quant_chart()` — Matplotlib 四面板；**目標（漸進）**：可選只吃管線已驗證序列；以 **flag** 保留現行 fallback。

### 階段 D — 長線（產品拍板後）

K 線疊加 Entry／Target／Stop（對齊 ROADMAP Phase 4）；建議在 **T5a** 與意圖敘事穩定後再接。

### 與 TODOS 對照

| 計畫階段 | TODOS 錨點 |
|----------|------------|
| A | **T2a**、**T2c** |
| B | **T2b**、**T3a–T3c**、Terminal M1–M3 已交付基礎上強化 |
| C | 管線附圖；變更時跑 `main` smoke 路徑相關測試 |
| D | **T5a**／**T5b**、演進藍圖 Phase 4 |

---

## 修訂紀錄

- **2026-04-14**：初版 — 階段 A–D；階段 A 契約 + Streamlit 口徑落地。
- **2026-04-18**：合併 backlog 主文與階段 A–D 附錄（rebase）。
- **2026-06-20（VU 視覺升級 Phase 1）**：共用圖表 kit（`charts/themedChart`/`ChartStates`/`GammaBarChart`）+ Options by-strike GEX + Dashboard regime tokens 對齊；VU2–VU5（Portfolio/News/Columns/Report/Streamlit V6）為 backlog。見 CHANGELOG **2026-06-20**。

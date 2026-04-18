# 視覺化 UX/UI 計劃（Visualization Plan）

> **目標**：在 **不破壞紅線**（無數據幻覺、Telegram HTML 白名單、`validate_report` Gate、`ThreadPoolExecutor` 雙線程安全、API/PWA 只讀）前提下，把日報模組化（Phase 1–5）與 Terminal 中段路線（M1–M5）累積的能力，轉化為 **一致、可審計、可客製** 的視覺化體驗。
>
> **三條產出線**：
> 1. **Telegram HTML 日報**（機構讀者，單向推送）
> 2. **Streamlit War Room**（內部戰情室，`dashboard.py`）
> 3. **PWA Terminal**（對外讀取＋紙上執行，[`data-verification-ui/`](data-verification-ui/)）
>
> 關聯文件：[`modularization_plan.md`](modularization_plan.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)、[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)、[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)。

---

## 0) 起點盤點（現況與已完成的模組化能量）

### 模組化已完成（可被 UI 吃下去的能力）

| 來自 modularization_plan | 可供 UI 使用的契約 |
|---|---|
| **Phase 1** — `templates/blocks/*.j2` 原子化 macro | 每個日報區塊都是獨立命名 macro，UI 可按 **block_id** 呈現／折疊／重排 |
| **Phase 2** — `brief_profiles.py`（`BLOCK_IDS`／`PROFILES`／`BLOCK_REGISTRY`）＋ `REPORT_PROFILE` | UI 可讀 `profile` 決定要顯示哪些區塊、掃讀順序 |
| **Phase 3** — `validate_report(..., profile=)`、Phase A/B/C profile-aware | UI 可顯示 **Gate 狀態**（通過／issues 清單）與新鮮度提示 |
| **Phase 4a** — `crypto-only` profile | PWA 可新增「加密專用視圖」(crypto-only mode) |
| **Phase 4b** — YAML layout 覆寫（`config/brief_layouts/`） | UI 可讀同一 YAML 或走 API 拿 **區塊順序**，做「使用者自訂排版」 |
| **Phase 4c** — BQ `profile` 欄位（`llm_run_log`／`gate_failure_log`） | 戰情室可依 profile 切片統計（失敗率、模型耗時） |
| **Phase 5** — 〔時事多觀點〕Roundtable（`CurrentAffairsRoundtable` schema） | UI 可原生渲染 voice 卡片（多觀點並陳），不用 parse HTML |

### 既有 UI 實作清單

- **Telegram**：[`templates/telegram_report.j2`](templates/telegram_report.j2) → [`templates/profiles/telegram_{full,lite,crypto_only}.j2`](templates/profiles/) → `blocks/*.j2`；白名單 `<b><i><u><s><code><blockquote><a>`。
- **Streamlit**（`dashboard.py`）：Plotly gauge／trend、BQ 載入、Symbol 快照 expander、5 min 自動刷新、內嵌 CSS／`COLORS` dict。
- **PWA**（`data-verification-ui/`）：React 18 + Vite + Tailwind + React Query + `lightweight-charts` + Recharts；路由 `/`、`/charts`、`/trades`、`/terminal`（lazy）、`/archive`、`/report/:date`；共享 `SymbolFocusBar`、`BottomNav`；Terminal 頁輪詢 45s（env 可調）；Web Push／SSE 皆可選開啟。
- **靜態圖**：`visualizer.py` Matplotlib 3-panel BTC 儀表板（Telegram 附件）。
- **API**（`api.py`）：`/api/metrics/*`、`/api/symbols/{s}/snapshot|quote`、`/api/execution-intents*`、`/api/stream/war-room`（SSE）、`/api/push/*`。

### 目前痛點（Phase 目標的反面）

1. **三線資料形狀不一**：Telegram 是 HTML 字串，Streamlit 直接戳 BQ，PWA 走 API — 模組化後的 **結構化 `DailyBriefReport`** 尚未在 PWA 原生呈現（仍以 HTML 貼回 Archive/Report）。
2. **設計語言分裂**：Streamlit 走深色漸層 + 自訂 CSS；PWA 走 Tailwind（目前偏中性）；沒有共用 token（顏色、間距、regime 狀態色）。
3. **data_provenance 只在 Terminal 顯示**：Today／Report／Archive 沒有一致的 **as-of + 來源** 呈現（BLOOMBERG Phase 0 §2 要求）。
4. **Profile 沒曝光給 UI**：讀者看不到「現在是哪種版型」、也不能切換。Phase 5 的〔時事多觀點〕在 PWA 無對應元件。
5. **Gate 失敗訊號只在 BQ**：`gate_failure_log` 沒有 UI 呈現，失敗當下無法在戰情室／PWA 溯因。
6. **事件疊加稀疏**：OHLC 圖還沒普遍疊加 QSREC 進出場點（BLOOMBERG Phase 0 §9）。
7. **行動裝置體驗未打磨**：PWA 已是 mobile-first，但 `TradeCard`／`Report` 長文排版、離線快取、通知點擊深連結仍未完整。

---

## 1) 產品與設計原則

1. **紅線不動**：LLM 不產生客觀數字；UI 只讀／唯一寫入為 `execution_intents` 狀態；Telegram 白名單不放寬。
2. **單一來源、雙層渲染**：`DailyBriefReport`（Pydantic）是 SSOT；Telegram／PWA／Streamlit 皆為 **同一 schema** 的 presentation layer。
3. **Profile-aware 全線**：UI 顯示 `profile` badge；可依 profile 隱藏／凸顯區塊；Archive 可篩選。
4. **as-of 一等公民**：每個 KPI／段落顯示時間戳與來源；mock／staging 明確可辨（延用 demo banner pattern）。
5. **漸進增強**：先 REST 輪詢，再 SSE，再 Web Push；先手機再桌機；先深色（機構風）再淺色。
6. **可切片交付**：每 Phase 可獨立 ship，`REPORT_PROFILE=full` 與凍結基線 **byte-identical** 不可退。

---

## 2) Phase 總覽

| Phase | 範圍 | 核心交付 | 依賴 | 預設狀態 |
|:---:|------|----------|------|----------|
| **V1** 設計基礎（Design Foundation） | 設計 token、共用組件、`DESIGN.md` | 統一色板／字級／regime 狀態色；`as_of` chip、provenance popover、profile badge 組件 | 無 | 可立刻開工 |
| **V2** 結構化 Report 視圖 | PWA `/report/:date` 改吃 `DailyBriefReport` JSON；block-level 渲染 | `GET /api/reports/{date}/structured`（新端點或擴欄位）；block 元件對應 `BLOCK_REGISTRY`；Gate 狀態列 | mod Phase 1–3；擴充 `api.py` | 預設關閉（feature flag） |
| **V3** Profile／Layout UX | PWA／Streamlit 顯示並切換 profile；讀 `config/brief_layouts/` YAML | profile 切換器（URL `?profile=lite`）；layout preview；Archive 篩選 | mod Phase 2／4a／4b | 預設 `full`，不改管線 |
| **V4** Roundtable + 互動增強 | 〔時事多觀點〕專屬元件；事件疊加 OHLC；Gate 失敗摘要 | `RoundtableVoices` 卡片 grid；`SymbolCandleChart` 疊加 QSREC；Gate issues drawer | mod Phase 5；BQ `gate_failure_log` | 預設關閉 |
| **V5** 即時化與通知 | SSE 全頁接通；Web Push 深連結；離線 PWA | SSE invalidate React Query；push click → `/report/{date}#block-id`；service worker 快取 | Terminal M4；Web Push infra | Opt-in env |
| **V6** 戰情室重塑（Streamlit → 共用 token） | `dashboard.py` 用共通 token／組件；新增 gate／profile／roundtable tabs | Streamlit 元件與 PWA 一致的 KPI 卡；profile tab；gate fail tab | V1 token；V3 profile | 內部用不影響外部 |

> **不在 Scope**：Telegram HTML 排版重寫（仍走 blocks macro；白名單鎖死）、桌面原生 app、付費終端、實下單。

---

## 3) 各 Phase 詳情

### V1 — 設計基礎（Design Foundation）

**目標**：在任何視覺改版前，先把「設計語言」落成一份可引用的 token 與共用組件。

**可交付**：
- `data-verification-ui/src/design/tokens.js` — 顏色（regime ON/中性/OFF、grid、surface、accent）、字級、間距、radius、shadow（與既有 Vite 專案一致；計畫稿若寫 `tokens.ts` 以本檔為準）。
- `DESIGN.md`（repo 根）— 品牌 tone、深色為主、禁用 emoji 敘事（對齊 `docs/DAILY_BRIEF_V2.md` §寫作規則）。
- `data-verification-ui/src/components/common/` — `AsOfChip`、`ProvenancePopover`、`ProfileBadge`、`GateStatusBadge`、`SourceLink`、`MockBanner`。
- Tailwind config 擴充：將 token 對應 `theme.extend.colors.regime.*`。

**可驗收**：
- **`/design` 路由（dev-only）** 或後續 Storybook 可以看到全部組件；`AsOfChip` 支援 **`asOf` + `source`**；`ProvenancePopover` 支援 **`data_provenance`** JSON 結構。
- Streamlit 端 token 對齊：**移至 [V6](#v6--戰情室重塑streamlit--共用-token)**（首階僅 PWA + Tailwind，避免混拆 `dashboard.py`）。

**風險**：低。純前端／樣式重構。

---

### V2 — 結構化 Report 視圖

**目標**：PWA `/report/:date` 從「貼 HTML」升級成「消費 `DailyBriefReport` JSON 原生渲染」，讓每個 block 可折疊、引用、分享、Gate 錯誤落在對應 block 上。

**可交付**：
- **後端**：在 `api.py` 擴充 `GET /api/reports/{date}` 回應（或新端點 `GET /api/reports/{date}/structured`），含 `profile`、`block_ids`（來自 `brief_profiles.BLOCK_REGISTRY`）、`daily_brief_report` pydantic dump、`gate_summary`（`validate_report` 結果摘要）。若 BQ 沒存 JSON，走 repository re-parse from scratchpad／`REPORT_ARCHIVE_JSON`。
- **前端**：
  - `src/components/report/` — 每個 `block_id` 一支元件：`DashboardBlock`、`MacroEarningsBlock`、`NewsBlock`、`MurmursBlock`、`TradesBlock`、`PortfolioFramingBlock`、`ScenarioBlock`、`EventCalendarBlock`、`InstitutionalSummaryBlock`、`CurrentAffairsRoundtableBlock`（V4 完整，V2 先 placeholder）。
  - `Report.jsx` 改為 **block 遍歷**，每個 block 套 `<AsOfChip/>` 與 `<GateStatusBadge/>`（若該 block 觸發 gate issue）。
  - 錨點跳轉：`/report/:date#block-news` 支援 Telegram／email／push 深連結。

**可驗收**：
- 同一份 `full` 報告，PWA block 順序與 Telegram byte-identical fixture 對應；`lite`、`crypto-only` 僅顯示 profile 對應 blocks。
- `validate_report` issues 清單可在 UI 中 hover block 看到；CRITICAL 以紅底（不同於 mock banner）。
- Gate 旗標：feature flag `VITE_STRUCTURED_REPORT=1`，預設關閉；flag 關閉時仍走舊 HTML 注入路徑，不回歸。

**風險**：中。需確保後端序列化契約與 Pydantic schema 同步；需有 smoke test 對比「structured render 的文字節點集合 ⊆ HTML 文字節點」。

**進度（2026-04-18）**：已交付 **`GET /api/reports/{date}/structured`** 封套（`profile`、`block_ids`、`block_registry`、`legacy`）；後端可自 **`DAILY_BRIEF_JSON_DIR`／`.qsilicon/daily_brief_reports/{date}.json`／`logs/run_YYYYMMDD_*/raw_data.json`** 載入 **`DailyBriefReport`**，並合併 **`validate_structured_report`** 與 **`.qsilicon/last_gate_failure`** 為 **`gate_summary`**（`issues_by_block`、`issues_unmapped`）；pytest 見 [`test_report_structured_api.py`](test_report_structured_api.py)。PWA **`VITE_STRUCTURED_REPORT=1`** + `StructuredReportView`：頁級／區塊級 **`AsOfChip`**、**`GateStatusBadge`**（依 `gate_summary.issues_by_block`）、Gate 失敗橫幅；legacy 欄位仍作占位。**尚缺**：逐 block 專用元件（`DashboardBlock`、…）與 BQ 持久化 JSON（營運可先用本機 JSON／管線 `raw_data`）。

---

### V3 — Profile／Layout UX

**目標**：讓讀者與內部都能「看見並切換」版型，讓 Phase 2／4a／4b 的能量走到使用者面前。

**可交付**：
- **URL / State**：`/report/:date?profile=lite`、`/today?profile=crypto-only`；React Query 依 profile key 快取。
- **Profile Switcher**：在 `SymbolFocusBar`（或新 `BriefProfileBar`）加下拉選單；選 `full`／`lite`／`crypto-only`；YAML 檔案清單走 **`GET /api/brief-layouts`**（列 `config/brief_layouts/*.yaml`；PWA 可選 [`useBriefLayouts`](data-verification-ui/src/hooks/useApi.js)）。
- **Layout Preview**：內部 staging 可上傳 YAML 預覽 block 順序（唯讀，不寫回）。
- **Archive 篩選**：`Archive.jsx` 依 profile tag 篩；BQ `llm_run_log.profile`（Phase 4c）為資料源。
- **Streamlit**：War Room 頂部加 profile tab（依 `gate_failure_log.profile` 分面）。

**可驗收**：
- 切換 profile 不重載整頁；`refetchInterval` 與 Terminal 節奏保持一致。
- 管線端 **完全不受影響**：UI 切 profile 僅改 render，不打管線；production cron 仍由 `REPORT_PROFILE` env 決定（鎖定 `full`）。
- Archive 可看到 profile 分布統計（小柱狀圖）。

**風險**：低–中。後端新端點需 pytest；注意 `BRIEF_LAYOUT_FILE` 在 UI 端只做讀取展示，不改 `_validate_report_profile_env` 行為。

---

### V4 — Roundtable + 互動增強

**目標**：把 Phase 5 的〔時事多觀點〕、BLOOMBERG Phase 0 §9（事件疊加 OHLC）、Gate 失敗可見性一次補到位。

**可交付**：
- **Roundtable**：`CurrentAffairsRoundtableBlock.jsx`；每個 `RoundtableVoice` 一張卡，包含 `voice_name`、`stance`、`evidence_anchor`、`risk_flag`；行動裝置直立堆疊、桌面 3 欄。
- **事件疊加**：`SymbolCandleChart.jsx` 增補 `markers` props，從 `/api/symbols/{s}/snapshot.recommendations`（QSREC entry/target/stop）產生 `lightweight-charts` markers；hover 顯示 signal_id。
- **Gate Issues Drawer**：共用元件，從 `gate_summary.issues` 渲染；CRITICAL／WARN／INFO 分色；點 issue → 跳 block 錨點。
- **Streamlit**：新增「Gate 失敗近 7 日」tab（讀 `gate_failure_log`，依 profile 分面）。

**可驗收**：
- Phase 5 實際啟用（`BRIEF_CURRENT_AFFAIRS=1` + `STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1` staging）時，PWA 與 Telegram 呈現一致 voice 順序。
- K 線 markers 僅來自結構化 `recommendations`，不 parse 自由文字（對齊 BLOOMBERG §9–10）。
- Gate drawer 的 issues 總數 = `validate_report` 回傳 issues 數。

**風險**：中。`lightweight-charts` marker API 需鎖版本；Roundtable CSS 需與其他 block 保持 tone 一致。

---

### V5 — 即時化與通知

**目標**：讓「感覺即時」從 Terminal 擴散到 Today／Report；Web Push 真正把讀者帶回對應 block。

**可交付**：
- **SSE 全頁**：`/api/stream/war-room` invalidate React Query key（`war-room/latest`、`metrics/latest`），在 Today／Terminal 兩頁啟用；`VITE_SSE_ENABLED=1`。
- **Web Push 深連結**：service worker `notificationclick` 依 payload `report_date` + `block_id` 跳 `/report/:date#block-id`；後端 `POST /api/push/test-send` 擴 payload schema。
- **離線快取**：service worker 預快取 `/today` 最新一份、`/report/:latest`；離線時顯示「最後同步 as_of」。
- **通知設定頁**：`/settings`（新路由）切換訂閱、測試推送、顯示 VAPID 狀態；仍遵循 `docs/PWA_WEB_PUSH.md`。

**可驗收**：
- 手機關網開啟 PWA 仍可看到最後報告（含 mock banner）；連網自動同步。
- 點擊推送 → 深連結錨點正確；未訂閱時設定頁引導訂閱而非靜默失敗。
- 無 SSE／Web Push env 時，UI 完全 graceful（回退到輪詢）。

**風險**：中–高。PWA 快取策略錯誤會看到舊資料；以「as_of 顯示 + 強制刷新按鈕」緩解。

---

### V6 — 戰情室重塑（Streamlit → 共用 token）

**目標**：把 V1 的 token 與 V2–V4 的概念回灌到 `dashboard.py`，讓內部戰情室不再與 PWA 視覺分裂。

**可交付**：
- 抽 `dashboard/theme.py`（或 YAML）= V1 token JSON 的 Python 鏡像；`dashboard.py` 不再內嵌大段 CSS。
- 新 tabs：**Profile 分面**、**Gate 失敗近 7 日**、**Roundtable 檢視**（把 BQ 中 Phase 5 輸出 JSON 原生展開）。
- Symbol 快照區塊與 PWA Terminal `TerminalSymbolCard` 同構（複用 provenance popover 概念）。
- 5 min 自動刷新改為 **可調**（env `DASHBOARD_AUTO_REFRESH_SEC`，預設 300）。

**可驗收**：
- 內部使用者在 Streamlit 與 PWA 切換時，regime 狀態色、KPI 格式、as_of chip **視覺一致**。
- `dashboard.py` 行數下降（CSS 外移）；ruff／smoke 不回歸。

**風險**：低。Streamlit 是純內部，變更不觸 Telegram／Gate 紅線。

---

## 4) 跨 Phase 的交付契約

| 契約 | 屬於 |
|------|------|
| 每個 Phase 都要更新 [`CHANGELOG.md`](CHANGELOG.md) 與 [`TODOS.md`](TODOS.md)（雙向對齊） | 所有 |
| 任何新 API 端點須同步 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) | V2／V3／V5 |
| 新增視覺元件須加 Storybook／dev 路由展示 | V1 起 |
| 任何 Gate／profile 相關 UI 須有 pytest（API）＋ Vitest／Playwright（PWA）覆蓋 | V2 起 |
| `REPORT_PROFILE=full` 與凍結基線 byte-identical 不可退 | 全部（紅線） |
| Telegram HTML 白名單不擴 | 全部（紅線） |

---

## 5) 立即可動（建議首 PR 範圍）

1. 建 `data-verification-ui/src/design/tokens.ts` + Tailwind extend（V1 起手）。
2. `AsOfChip`、`ProvenancePopover`、`ProfileBadge`、`GateStatusBadge` 四個無狀態元件。
3. 在 `Today.jsx` 與 `TerminalSymbolCard.jsx` 先套 `AsOfChip`（最小侵入性）。
4. 更新 `docs/DASHBOARD_CONTRACT.md` 附註「V1 design token 路徑」；`CHANGELOG` 新開 `## 2026-04-18 — Visualization V1`（待 ship）。
5. 不觸 `api.py`、不觸管線；smoke 必須全綠。

---

## 6) 風險與對策

| 風險 | 對策 |
|------|------|
| PWA 改版破壞既有 mock／demo 行為 | 保留 `utils/mockToday.js`；所有新元件支援 `isMock` prop；沿用 demo banner |
| 結構化 API 與 Pydantic schema 漂移 | V2 後端端點加 pytest；CI 比對 `DailyBriefReport.model_json_schema()` hash |
| 設計 token 雙端不同步 | token 來源單一（TS 檔），Python 端用生成腳本或簡單 import JSON |
| Web Push 靜默失敗導致使用者誤以為有通知 | `/settings` 顯示訂閱狀態 + 測試按鈕；必要時改 SSE 為主推 |
| Streamlit 重構拖累內部使用 | V6 最後做；期間 PWA 已成熟 |

---

## 7) 延伸閱讀

- 日報模組化（已完成 Phase 1–5）：[`modularization_plan.md`](modularization_plan.md)
- Bloomberg 對齊驗收：[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)
- Terminal 中段（M1–M5）：[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)
- API／UI 契約：[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)
- Web Push：[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)
- 日報寫作與排版規則：[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)

# Q-Silicon Terminal 前端骨架規劃

> 入口網站架構設計：五模組 Portal，基於現有 `data-verification-ui` 演化

---

## 技術棧決策

**結論：擴展現有 `data-verification-ui`（Vite + React），重構目錄為「模組化」結構。**

### 比較

| 選項 | 優點 | 缺點 |
|------|------|------|
| **擴展現有 Vite 專案（採用）** | 已有 PWA 設定、API 接線、localStorage 邏輯；不打掉重練 | 未來若要 SSR 要遷移 |
| 重起 Next.js App Router | SSR、RSC、Route Groups 對 portal 場景很好 | 遷移成本高；現階段不需要 SEO |

**判斷依據：** 自用階段用 Vite 完全夠，現有 `/terminal` 路由可直接演化。等未來真要開放外部用戶再考慮 Next.js。

---

## 目錄結構

```
data-verification-ui/
├── src/
│   ├── app/
│   │   ├── App.tsx
│   │   ├── Router.tsx           ← 模組路由中心
│   │   └── layout/
│   │       ├── Shell.tsx        ← 側邊導航 + 頂部狀態列
│   │       └── ModuleNav.tsx    ← 五模組切換
│   ├── modules/
│   │   ├── daily-brief/         ← 現有日報板塊
│   │   │   ├── pages/
│   │   │   ├── components/
│   │   │   ├── api/             ← /api/briefs/*
│   │   │   └── types.ts
│   │   ├── investment-analysis/ ← 初期 stub
│   │   ├── position-management/ ← 初期 stub
│   │   ├── industry-trends/     ← 初期 stub
│   │   └── quant-trading/       ← 初期 stub
│   ├── shared/
│   │   ├── api/                 ← 共用 API client（auth、error handling）
│   │   ├── components/          ← 共用 UI primitives
│   │   ├── hooks/
│   │   └── types/               ← 共用 Pydantic → TS schema
│   └── main.tsx
├── public/
└── vite.config.ts
```

### 關鍵設計原則

- 每個模組在 `modules/{name}/` 下自成一體，有自己的 `pages/`、`components/`、`api/`、`types.ts`
- 模組間**禁止直接 import**彼此的內部代碼，只能透過 `shared/` 或 API
- **未來若真要拆 repo，直接把 `modules/{name}/` 目錄整個搬走即可獨立**

---

## API 分層設計

### Backend 路由規劃（FastAPI `api.py`）

```
FastAPI Backend (api.py)
├── /api/briefs/*          ← 日報（現有邏輯）
│   ├── GET  /profiles     ← 可用 profile 列表
│   ├── POST /generate     ← 觸發日報
│   └── GET  /{run_id}     ← 查閱歷史
├── /api/analysis/*        ← 投資分析
│   ├── GET  /companies/{symbol}/snapshot
│   └── POST /companies/{symbol}/deep-dive
├── /api/positions/*       ← 倉位管理
│   ├── GET  /portfolio
│   ├── POST /intents
│   └── GET  /risk-metrics
├── /api/industries/*      ← 產業趨勢
│   └── GET  /themes/{theme_id}
├── /api/quant/*           ← 量化交易
│   ├── GET  /signals
│   ├── POST /backtest
│   └── GET  /intraday-monitor
└── /api/shared/*          ← 跨模組共用
    ├── GET  /symbols/{symbol}/quote
    └── GET  /symbols/{symbol}/snapshot
```

### 實作策略

- 所有 endpoint 在 `api.py` 用 FastAPI `APIRouter` 分檔案管理
- 每個模組的 router 獨立檔案：`qsilicon/daily_brief/api_router.py`、`qsilicon/positions/api_router.py` 等
- `api.py` 只做組裝：`app.include_router(daily_brief.router, prefix="/api/briefs")`

---

## 認證設計

**現階段策略：單一 master key**

```bash
# 環境變數
QSILICON_MASTER_KEY=<random-hex-32>

# 所有 /api/* request 需要 header: X-Q-Silicon-Key
```

**理由：**
- 實作簡單，不需要 user database
- 自用場景完全夠用
- 未來若真要多用戶再引入 JWT / OAuth
- **避免現在就過度設計**

---

## 五模組 MVP Scope

| 模組 | MVP 最小範圍 | 代碼來源 |
|------|-------------|---------|
| daily-brief | 現有日報，加 profile selector UI | 現有 `main.py` / `crew.py` |
| investment-analysis | 個股 snapshot 頁面（股價、基本面、近期新聞）| 新邏輯 |
| position-management | Paper portfolio 顯示（讀 `paper_execution.py` 輸出）| 現有 `execution_intents.py` / `paper_execution.py` |
| industry-trends | 單一 theme 頁面（例：半導體封裝），純閱讀 | 新邏輯 |
| quant-trading | Signal 列表 + 簡單回測結果顯示 | 現有 `backtest.py` / `monitor_intraday.py` |

---

## 開發順序建議

1. **先把 Portal Shell 做起來**（導航、佈局、auth），接上 daily-brief 模組
2. **第二個做 position-management**
   - 已有 `paper_execution.py` 和 `execution_intents.py` 代碼基礎
   - 搬過來最快，風險最低
3. **第三做 industry-trends**
   - 純閱讀型
   - 技術風險最低
4. **investment-analysis 和 quant-trading 最後做**
   - 這兩個需要最多新邏輯

### 為何這個順序

**先做 Shell + daily-brief** 是為了驗證整個骨架能跑；**接著挑有現成代碼的模組**（positions、industries）讓前期快速有成果；**複雜的新邏輯放最後**（analysis、quant），等骨架穩定再投入。

---

## 給 Claude Code / Cursor 的實作 Prompt

```
Task: Restructure data-verification-ui into modular architecture for
Q-Silicon Terminal Portal.

Context files to read first:
- data-verification-ui/src/ (current structure)
- data-verification-ui/package.json
- data-verification-ui/vite.config.ts
- api.py (current FastAPI endpoints)

Phase 1 deliverables (this task):

1. Create new directory structure under data-verification-ui/src/:
   - app/layout/ (Shell.tsx, ModuleNav.tsx)
   - modules/{daily-brief,investment-analysis,position-management,
     industry-trends,quant-trading}/
   - shared/{api,components,hooks,types}/

2. Move existing /terminal route code into modules/daily-brief/.
   Other four modules should have placeholder pages that render
   "Coming soon: {module name}".

3. Implement Shell.tsx with:
   - Left sidebar with 5 module links (use lucide-react icons)
   - Top status bar showing current time (Asia/Taipei) and build version
   - Main content area rendering <Outlet />

4. Set up react-router-dom routes:
   - / → redirect to /briefs
   - /briefs → modules/daily-brief
   - /analysis → modules/investment-analysis
   - /positions → modules/position-management
   - /industries → modules/industry-trends
   - /quant → modules/quant-trading

5. shared/api/client.ts: axios instance that:
   - Reads VITE_API_URL (fallback to same-origin)
   - Adds X-Q-Silicon-Key header from localStorage key 'qsi_master_key'
   - On 401, redirect to a simple key-input page

6. shared/components/: extract any genuinely reusable UI from existing
   /terminal code. Do not over-extract; only move things used in 2+ places.

Constraints:
- Do NOT import between modules/{a}/ and modules/{b}/ directly. Only via shared/.
- Existing /terminal functionality must still work after restructure
  (routes may change, but behavior preserved).
- Tailwind classes must use utility classes only (no custom @apply blocks).
- Keep single-file artifacts where possible; do not split components into
  tiny files prematurely.

Out of scope for this task:
- Backend API changes
- New business logic for modules 2–5 (placeholders only)
- Authentication UI beyond the 401 key-input page

Deliverables:
- Full new directory structure with placeholder pages
- One PR-ready commit with all changes
- Updated README in data-verification-ui/ explaining new structure
```

---

## 驗收清單

> **2026-05-04 對齊現況**：勾選以 **本 PR** 為準。設計稿曾寫 `shared/api/client.ts`／axios；repo 實作為 [`data-verification-ui/src/lib/siliconApiHeaders.js`](../../data-verification-ui/src/lib/siliconApiHeaders.js) + [`useApi.js`](../../data-verification-ui/src/hooks/useApi.js)／[`pushClient.js`](../../data-verification-ui/src/pushClient.js)。根路徑 **`/`** 已 **`Navigate` → `/briefs`**；**Today** 掛 **`/today`**。

- [x] 五個模組目錄建立完成，皆有 placeholder page（`modules/*/pages/*Home.jsx` + `daily-brief/pages/DailyBriefPage.jsx`）
- [x] Shell 導航可切換五個模組，URL 對應正確（`app/layout/Shell.jsx` + `ModuleNav.jsx` → `/briefs`、`/analysis`、`/positions`、`/industries`、`/quant`）
- [x] 現有 `/terminal` 功能遷移到 `modules/daily-brief/` 後行為一致（`/briefs` 與 `/terminal` 同掛 `DailyBriefPage`）
- [x] 單一 API 出口正確處理 `VITE_API_URL` + `X-Q-Silicon-Key`（`siliconApiHeaders.js`：`localStorage.qsi_master_key` 優先於 `VITE_QSILICON_KEY`；`useApi.js`／`pushClient.js`）
- [x] 401 回應時跳轉專用 key-input 頁（`/api-key`；`VITE_E2E=1` 時不跳轉）；並 dispatch `qsilicon:api-unauthorized`
- [x] 模組之間無直接 `modules/A` → `modules/B` import（`eslint.config.js`：`import/no-restricted-paths`）
- [x] PWA 離線快取仍正常運作（`service-worker.js` 未因 Portal 重構移除；`/api` NetworkOnly 策略維持）
- [x] Playwright E2E 測試通過（含 `briefs-alias-route` 等；`npm run test:e2e`）

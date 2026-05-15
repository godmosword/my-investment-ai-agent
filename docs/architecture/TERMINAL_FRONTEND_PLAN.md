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

> **現況（2026-05）**：repo 為 **Vite + React（`.jsx`）**，入口 **`src/main.jsx`** → **`src/app/App.jsx`**（路由內嵌於 `App.jsx`；歷史設計稿曾列 `Router.jsx`）；佈局 **`app/layout/Shell.jsx`** + **`ModuleNav.jsx`**。共用 HTTP：**[`lib/siliconApiHeaders.js`](../../data-verification-ui/src/lib/siliconApiHeaders.js)** + **[`hooks/useApi.js`](../../data-verification-ui/src/hooks/useApi.js)**（`X-Q-Silicon-Key`、401→`/api-key`）；**無** `shared/api/client.ts`（設計稿 axios 路徑仍列於下方 Prompt／驗收清單「設計錨點」）。後端增量路由見 repo 根目錄 **[`api_routers/`](../../api_routers/)**（`CHANGELOG` **2026-05-06**）。**Phase 2（2026-05-14）**：Command Bar **`terminal-crew-status-hud`**（輪詢 `GET /api/run-crew/status`）；Workspace **`storage` + `qsi_workspace_changed`** 跨分頁同步（[`workspaceSync.js`](../../data-verification-ui/src/constants/workspaceSync.js)）。**Phase 4 IA（讀者層×工作台層）**：產品敘事、原則、A／B／C 分段與**滾動實作規劃**見 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **§0 Phase 4**；**本檔**負責 PWA **路由／模組邊界**、**驗收清單**與 **`DASHBOARD_CONTRACT.md`** 同步；實作切片對齊 **`TODOS.md` 隊列 44**。

```
data-verification-ui/
├── src/
│   ├── main.jsx
│   ├── app/
│   │   ├── App.jsx
│   │   ├── Router.jsx           ← 模組路由中心
│   │   └── layout/
│   │       ├── Shell.jsx        ← 側邊導航 + 頂部狀態列
│   │       └── ModuleNav.jsx    ← 五模組切換
│   ├── modules/
│   │   ├── daily-brief/         ← 日報／原 /terminal
│   │   │   └── pages/
│   │   ├── investment-analysis/
│   │   ├── position-management/
│   │   ├── industry-trends/
│   │   └── quant-trading/
│   ├── hooks/                   ← useApi、War Room SSE 等
│   ├── lib/                     ← siliconApiHeaders 等
│   ├── components/              ← 跨路由共用（Terminal、Report…）
│   ├── pages/                   ← Today、ApiKey…
│   └── …
├── public/
└── vite.config.js
```

### 關鍵設計原則

- 每個模組在 `modules/{name}/` 下自成一體，有自己的 `pages/`、`components/`、`api/`、`types.ts`
- 模組間**禁止直接 import**彼此的內部代碼，只能透過 `shared/` 或 API
- **未來若真要拆 repo，直接把 `modules/{name}/` 目錄整個搬走即可獨立**

### Phase 4 IA（讀者層 × 工作台層）

與 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **§0 Phase 4** 對齊：**同一 Portal、不同資訊密度**；`/news`、`/columns` 偏讀者；`/insights`、`/dashboard`、`/portfolio` 偏工作台。**本檔**補工程邊界如下（敘事／原則／紅線以 Master Plan 為準）：

| 項目 | 本檔責任 |
|------|----------|
| **路由與模組** | 變更集中在 `data-verification-ui/src/app/App.jsx`、`src/modules/news/`、`src/modules/columns/`、`src/modules/insights/` 等；不新增「第二套 App」路由樹。 |
| **Shell 共用** | `Shell.jsx`／`TerminalCommandBar.jsx` 行為調整須與 Phase 4「情境化」一致；全站 401／金鑰行為不變。 |
| **驗收** | 每切片至少一條 Playwright smoke（可擴充 `news-route`／`queue43-cross-board`／新 spec）；必要時補 `docs/DASHBOARD_CONTRACT.md` 列點。 |
| **對齊待辦** | 實作優先序與切片編號見 [`TODOS.md`](../../TODOS.md) **隊列 44**。 |

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

> **沿革（避免與現況脫節）**：下述英文區塊為 Phase 1 **草擬**時的「future state」，曾列 `Shell.tsx`、`ModuleNav.tsx`、`shared/api/client.ts`。**現況以本節下方 §驗收清單與 repo 為準**（2026-05 起）：
>
> - Shell／導航：`data-verification-ui/src/app/layout/Shell.jsx`、`ModuleNav.jsx`（非 `.tsx`）。
> - API：`src/lib/siliconApiHeaders.js` + `src/hooks/useApi.js` + `pushClient.js`；**無** `shared/api/client.ts`（設計稿 axios 單一 client 仍以驗收清單註記為錨點，見上表與 CHANGELOG 2026-05-04）。
> - 目錄：`modules/*/pages/*Home.jsx`、`modules/daily-brief/pages/DailyBriefPage.jsx`；模組間禁互 import（`eslint.config.js`：`import/no-restricted-paths`）。
> - 後端：FastAPI 以 [`api_routers/`](../../api_routers/) 增量 `include_router`，見 [`api.py`](../../api.py)。
>
> **新功能開發**：先讀現檔再改；對齊 [`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](../../ENV_TEMPLATE.txt)。

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

---

## 修訂紀錄（本檔）

- **2026-05-16**：補 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **§0 Phase 4 IA** 交叉引用（現況段落）；新增 **「### Phase 4 IA」** 工程責任表；對齊 **`TODOS` 隊列 44**；校正路由敘述為 **`App.jsx` 內嵌路由**（設計稿 `Router.jsx` 僅作沿革）。

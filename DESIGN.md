# Q-Silicon PWA — 設計語言（Design Foundation）

本文件對齊 [`visualization_plan.md`](docs/architecture/visualization_plan.md) Phase **V1**：在視覺改版與新元件開發前，統一 **品牌語氣**、**深色機構風**、與 **implementation 真相來源**（避免文件與程式不一致）。

## 品牌與語氣

- **讀者**：機構／專業使用者；語調中性、可審計，避免社群梗與過度口語。
- **視覺預設**：深色儀表板為主（[`data-verification-ui/src/index.css`](data-verification-ui/src/index.css) `:root`）；青綠 **accent** 僅作強調，避免彩虹式裝飾。
- **敘事／emoji**：對齊 [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) — Telegram HTML 白名單與寫作規範仍以該文件為準；PWA 可較彈性但仍避免以 emoji 代替論證。

## Design tokens（單一來源）

| 類型 | 檔案 | 說明 |
|------|------|------|
| 色票、`regime`、`qs.*`、Tailwind 延伸 | [`data-verification-ui/src/design/tokens.js`](data-verification-ui/src/design/tokens.js) | **Canonical**（專案為 JS／Vite；計畫稿中的 `tokens.ts` 以此檔為準）。 |
| Tailwind 綁定 | [`data-verification-ui/tailwind.config.js`](data-verification-ui/tailwind.config.js) | `theme.extend` 自 `tokens.js` 匯入。 |

組件預覽（僅開發環境）：路由 **`/design`** — [`DesignShowcase.jsx`](data-verification-ui/src/pages/DesignShowcase.jsx)。

## 審計與資料新鮮度

- **`AsOfChip`**：`as-of` 時間戳 + 資料來源（對齊 BLOOMBERG Phase 0 §2）。
- **`ProvenancePopover`**：`GET /api/symbols/{symbol}/snapshot` 之 **`data_provenance`**。
- **`GateStatusBadge`**：對應 `validate_report`／結構化檢查摘要；報告頁區塊級錯誤見 `/report/:date` 結構化視圖。

## Streamlit

戰情室 [`dashboard.py`](dashboard.py) 與本 token **視覺對齊**排入 [`visualization_plan.md`](docs/architecture/visualization_plan.md) Phase **V6**，避免首階混拆後端戦情室。

---

## 資訊架構（IA）與導覽角色

**路由群組**（見 [`App.jsx`](data-verification-ui/src/App.jsx)）：

| 群組 | 路由 | 說明 |
|------|------|------|
| 主功能 | `/news`、`/dashboard`、`/insights`、`/columns`、`/portfolio` | 科技即時報／數據儀表板／投資觀點／科技專欄／持倉 |
| 延伸視圖 | `/archive`、`/report/:date` | 存檔與單日結構化報告 |
| 系統 | `/settings`、`/api-key`、`/report/:date` | 設定、金鑰、單日報告 |

**斷點與殼層**：

- **`<768px`**：[`Shell`](data-verification-ui/src/app/layout/Shell.jsx) 不顯示側欄；僅 **[`BottomNav`](data-verification-ui/src/components/BottomNav.jsx)**（主功能五項＋設定）為主模組導覽；主內容於 [`<main className="page-content">`](data-verification-ui/src/App.jsx)。
- **`≥768px`**：顯示 **[`SideNav`](data-verification-ui/src/app/layout/SideNav.jsx)**（主功能＋設定，含 SSE 狀態燈）；BottomNav 隱藏。

**SideNav vs BottomNav**：SideNav = 桌面完整 IA；BottomNav = 小螢幕唯一主模組導覽。兩者不同時出現。

**桌面主內容可讀寬**：`≥768px` 時 `.page-content` **max-width 1120px**、水平置中（超寬螢幕可讀性）。若某頁未來需全寬圖表，另加例外 class（例如 `page-content--full-bleed`）並於此文件註記。

---

## Portal Phase 4（讀者層 × 工作台層）

對齊 [`docs/architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) **§ Phase 4 IA**、[`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) **§0 Phase 4**。**常數與跨板塊文案** 以 [`data-verification-ui/src/constants/portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js)（`PORTAL_PHASE4_GATE0`、`PORTAL_PHASE4_CTA`、`newsContextHref`／`columnsContextHref`／`insightsSymbolHref`、`getTerminalCommandBarPlaceholder`）為 **implementation 真相來源**；本節描述產品可驗收行為，若與程式不一致，以程式為準並應回寫本檔。

### 首屏視線順序（讀者層 vs 工作台層）

ASCII 僅供 QA／人測對齊視線（**非** pixel 佈局契約）。

**讀者層**（`/news`、`/columns`）— 低密度、可掃讀：

```
[ Shell 頂欄／Command Bar ]
[ Reader intro 條 — 單一主任務；例：news-reader-layer-intro ]
[ 若有 ?focus=SYM：focus badge／篩選提示 ]
[ 主內容：digest 卡片流或專欄列表；避免首屏多區高密度 HTML 報價矩陣 ]
[ 主 CTA（accent）與次要連結 — 見下「CTA 視覺層級」]
[ GlobalWatchlistDock（浮動）]
```

**工作台層**（`/insights`、`/dashboard`、`/portfolio`）— 較高密度、可操作：

```
[ Shell 頂欄／Command Bar — GO／RUN 語感 placeholder ]
[ Workbench intro 條 — 三工作台導引／密度收斂 ]
[ 主戰場（tabs／KPI／圖表／表格；遵守 Gate 0 首屏高密度區 ≤3 等決議）]
[ 回向讀者層 CTA — 字串來自 PORTAL_PHASE4_CTA ]
[ GlobalWatchlistDock ]
```

### 融合深連結（`?focus=`）— 使用者看見什麼

適用 **`/news?focus=SYM`**、**`/columns?focus=SYM`**（helpers：`newsContextHref`、`columnsContextHref`）。下列為 **fusion 層** 狀態（與下方全站 KPI／圖表矩陣分開敘述）。

| 狀態 | 觸發／條件 | 使用者看見什麼 |
|------|------------|----------------|
| **Loading** | 列表／digest 請求進行中 | 頁或區塊 skeleton；**不**顯示假標的／假新聞；導覽與 Command Bar 除非該頁另有規則否則可互動。 |
| **Empty** | API 成功但列表為空（無 focus 或與 focus 無關之空態） | 「無資料／無可顯示項目」類短文案；不強制顯示 focus badge。 |
| **No match** | 有 `?focus=SYM` 且載入完成，但沒有任何列／卡匹配該 symbol | 「無符合 SYM 的項目」+ 清除篩選或前往 **`/insights?symbol=`** 之導引（雙向融合）；可並存「已篩選 SYM」badge 與空內容。 |
| **Error** | 列表 API 失敗 | 錯誤短句 + 重試；**不**捏造匹配結果；`?focus` 保留與否依該頁實作。 |

### 讀者層 90 秒驗收腳本（產品／可用性）

**非** Playwright 替代品；E2E 仍以 `phase4-ia-portal.spec.js` 等為準。供 44a 人測簽名或 demo 勾選。

1. **0–15s**：`<768px` 開 `/news` — 見 reader intro、首屏無多區報價矩陣；BottomNav 可切主要模組。
2. **15–45s**：點單一主 CTA（`accent`）往 **`/insights`** — 見 workbench intro、首屏區塊數合理（與 44b tab／dock 等一致）。
3. **45–75s**：從工作台 **`回到新聞脈動`**（`PORTAL_PHASE4_CTA.workbenchToNews`）— 讀者密度不變；Command Bar placeholder 為讀者向字串。
4. **75–90s**：`/news?focus=NVDA`（或測試環境已知 symbol）— 符合上表 Loading／Empty／No match／Error 之一，**無**幻覺報價。

### Command Bar — 讀者頁 placeholder 策略

- **實作**：`getTerminalCommandBarPlaceholder(pathname)` — `/news`、`/columns` 與其他路徑文案不同。
- **意圖**：讀者頁偏 **搜尋／跳轉**（主題、路由、`SYM GO`）；工作台保留 **RUN／狀態機** 語感，避免混讀。
- **小螢幕**：長 placeholder 可能截斷 — 以元件 **`aria-label` 全句** 為準（實作見 `TerminalCommandBar.jsx`）。
- **可選後續（非承諾）**：在 reader intro 下以 `<details>` 或 drawer 收合「指令範例」，縮短單行 placeholder；若採納須同步 `portalPhase4.js` 與 E2E。

### CTA 視覺層級與 `PORTAL_PHASE4_CTA`

- **主 CTA**：與 **Accent 與 Accent2** 小節一致 — 同一視窗／同一折疊視區內 **建議至多一顆** `accent` 主按鈕；次要動作用 outline／ghost 或文字連結。
- **文案**：跨板塊人話 CTA 一律經 **`PORTAL_PHASE4_CTA`** +（必要時）**`ctaWithSymbol`**；避免 JSX 內重複硬編同義句。
- **層級**：intro 內「去觀點工作台」為 **Tier 1**；卡片內「在新聞中查 SYM」為 **Tier 2**；工作台「回到新聞脈動」為 **Tier 1 返程**。

### Skip link 與鍵盤順序（P2 — 已落地）

- **實作**：[`Shell.jsx`](data-verification-ui/src/app/layout/Shell.jsx) 於主欄頂部提供 **`href="#main-content"`** 之 **略過導覽至主內容**（`.skip-to-main`；螢幕外隱藏、`focus-visible` 時顯示）；[`App.jsx`](data-verification-ui/src/App.jsx) 將 `<main>` 設 **`id="main-content"`** 與 **`tabIndex={-1}`** 以利 hash 後焦點落點。
- **驗收**：Playwright [`skip-link.spec.js`](data-verification-ui/e2e/skip-link.spec.js) 確認 focus → click 後 **`#main-content` 取得焦點**。與 **Command Bar**／**`Ctrl/Cmd+K`** 並存時未改既有快捷鍵邏輯；若日後調整 tab order 請同步跑該 spec。

---

## 介面狀態矩陣（使用者看見什麼）

對齊 KPI／圖表／連線指示區塊；實作時優先重用 `.loading`、既有錯誤橫幅或 `data-testid` 以利 E2E。

| | KPI／metric grid | 主要圖表區 | SSE／連線指示 |
|--|------------------|------------|----------------|
| **Loading** | 區塊內骨架或「載入中…」，不顯示假數字 | 佔位或輕量 spinner，不繪製空白欺騙性走勢 | SideNav 底部：**SSE 連線中…**（灰點）；或未啟用時不顯示 |
| **Empty** | 單行說明「無資料／無快照」，必要時導向設定或換標的 | 簡短「無 OHLC／無序列」+ 可選換 symbol | 不適用（SSE 關閉時區塊可缺省） |
| **Error** | 單行錯誤＋可選重試；不重複堆疊多張卡片 | API／網路錯誤文案＋重試；圖表容器不切換假資料 | **連線失敗**（紅點）+ `title`／`aria-label` 說明 |

---

## 首次開啟 storyboard（信任與動線）

1. 進入預設路由（`/insights`）：深色殼層與單一 accent 強調，第一印象為「儀表／終端」而非行銷頁。
2. 側欄或底部導覽可見完整模組邊界；專業使用者快速判断「日報／分析／量化」分區。
3. 資料區若載入：短暫 loading，無捏造報價；若見 **AsOfChip／Provenance**：強化可審計感。
4. SSE 啟用時，角落連線狀態提供「即時管線」信任訊號（連線中／已連線／失敗）。
5. 首次受阻（401、離線）：導向清晰下一步（API 金鑰、離線橫幅），不中斷全殼導覽。

---

## Accent 與 Accent2（語意）

對齊 [`tokens.js`](data-verification-ui/src/design/tokens.js) `palette.accent`／`palette.accent2`：

- **`accent`（cyan）**：主 CTA、導覽使用中態、主標題品牌強調、資料新鮮度與可審計狀態。**唯一**與「下一步行動」競爭的強調色。
- **`accent2`（amber）**：次要強調、**圖表輔助系列**、警示／pending 標籤區隔；**不得**與主按鈕／主連結 active 態同色競爭視覺優先級。

---

## 響應式與無障礙（a11y）

- **平板 `768px–1279px`**：維持側欄 + 單欄主內容；與 `1280px+` 差異主要為側欄寬度（見 [`index.css`](data-verification-ui/src/index.css)）。細修可在後續迭代獨立 media query。
- **`:focus-visible`**：所有可聚焦連結／按鈕須有鍵盤可見焦環（對比比率足夠，優先沿用 `--accent`）。
- **觸控目標**：主要導覽連結（SideNav、BottomNav）**最小約 44×44 CSS px**。
- **地標**：`<main id="main-content" className="page-content" tabIndex={-1}>`；`nav` 使用 **`aria-label`**（「主導航」「主導航（底部）」）。**Skip link** 見 **Portal Phase 4** 末節「Skip link 與鍵盤順序（P2 — 已落地）」。

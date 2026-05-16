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

- **`<768px`**：[`Shell`](data-verification-ui/src/app/layout/Shell.jsx) 不顯示側欄；顯示 **[`ModuleNav`](data-verification-ui/src/app/layout/ModuleNav.jsx)**（Portal 模組快捷，補 [`BottomNav`](data-verification-ui/src/components/BottomNav.jsx) 未含之四模組）+ **BottomNav**（主功能五項＋設定）；主內容於 [`<main className="page-content">`](data-verification-ui/src/App.jsx)。
- **`≥768px`**：顯示 **[`SideNav`](data-verification-ui/src/app/layout/SideNav.jsx)**（主功能＋分析模組＋設定）；**ModuleNav 隱藏**（避免與 SideNav「分析模組」區塊重複）；BottomNav 隱藏。

**SideNav vs ModuleNav**：SideNav = 完整 IA（含 SSE 狀態燈）；ModuleNav = 僅小螢幕用的 Portal 模組橫列。**不重複出現在桌面**。

**桌面主內容可讀寬**：`≥768px` 時 `.page-content` **max-width 1120px**、水平置中（超寬螢幕可讀性）。若某頁未來需全寬圖表，另加例外 class（例如 `page-content--full-bleed`）並於此文件註記。

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
- **觸控目標**：主要導覽連結（ModuleNav、BottomNav）**最小約 44×44 CSS px**。
- **地標**：`<main className="page-content">`；`nav` 使用 **`aria-label`**（「主導航」「Portal 模組」「主導航（底部）」）。**Skip link** 若需另開切片再補。

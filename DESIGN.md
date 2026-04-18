# Q-Silicon PWA — 設計語言（Design Foundation）

本文件對齊 [`visualization_plan.md`](visualization_plan.md) Phase **V1**：在視覺改版與新元件開發前，統一 **品牌語氣**、**深色機構風**、與 **implementation 真相來源**（避免文件與程式不一致）。

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

戰情室 [`dashboard.py`](dashboard.py) 與本 token **視覺對齊**排入 [`visualization_plan.md`](visualization_plan.md) Phase **V6**，避免首階混拆後端戦情室。

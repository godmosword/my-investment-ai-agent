# 視覺化路線計畫（Visualization Plan）

**目的**：把「圖表／Terminal／Telegram 附圖」與 **資料信任邊界**（工具層、BQ、已選公開 API）對齊，避免同一符號在不同介面出現**無解釋的數字分歧**。  
**契約主檔**：[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)。  
**長線願景對照**：[`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) 方向 1（穩定視覺化）、演進藍圖 Phase 4（K 線疊加進出場等，須產品拍板）。

---

## 紅線（全階段共通）

1. **不得讓 LLM 捏造圖上客觀數字**：敘事與 `<code>` 仍依日報 Gate；圖表僅展示可追溯序列或已注入 context 之值。  
2. **單一路徑語意**：改 `symbol_snapshot_service`／`api.py`／PWA 消費欄位時，**同步**契約與（若使用）OpenAPI。  
3. **分階交付**：重大行為變更以 **環境開關** 或獨立 PR 收斂，避免一次改動 Telegram 出報路徑與 Terminal 同檔。

---

## 階段 A — 契約與可追溯性（優先）

**目標**：把 **OHLC（K 線）**、**`/quote` last**、**`latest_metrics`（BQ）** 三條來源的用途與 `price_alignment` 語意寫進契約；Streamlit Symbol 快照區塊提供**可讀口徑**（對齊 T2a／T2c）。

| 交付 | 說明 |
|------|------|
| 契約擴充 | [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) — 「視覺化與數字段語意」專節 |
| 戰情室 | [`dashboard.py`](dashboard.py) — Symbol 快照 expander 內 **ℹ️ 口徑**（可摺疊），必要時反映目前 payload 之 `price_alignment.aligned` |
| 索引 | [`CLAUDE.md`](CLAUDE.md) `docs/` 索引列本檔 |

**驗收**：人讀契約即可回答「K 線用的哪條 close、卡片上 last 從哪來、與 BQ 儀表不同是否預期」。

**狀態（2026-04-14）**：✅ 已落地（本 repo 提交）。

---

## 階段 B — PWA／Terminal（讀者端體驗）

**目標**：溯源 UI、`price_alignment.aligned === false` 的**非靜默**提示、輪詢與快取節奏（對齊 **T2b**、**T3c**、`docs/TERMINAL_MID_TIER_ROADMAP.md`）。

| 切片 | 代表檔案／行為 |
|------|----------------|
| 溯源摺疊 | `data_provenance` 於 Terminal 卡片可讀 |
| 分歧提示 | [`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) |
| 效能 | [`useApi.js`](data-verification-ui/src/hooks/useApi.js)、`VITE_TERMINAL_POLL_MS` |

---

## 階段 C — Telegram `visualizer.py`（可選強化）

**現況**：[`visualizer.py`](visualizer.py) `generate_quant_chart()` — Matplotlib 四面板，**yfinance + Binance funding**，與日報區塊① `<code>` **未必同一注入鏈**。  
**目標（漸進）**：可選改為只吃 **管線已驗證序列** 或與 tools 對齊之 fetch；以 **flag** 保留現行 fallback，維持出報穩定。

---

## 階段 D — 長線（產品拍板後）

**目標**：K 線疊加 Entry／Target／Stop（對齊 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) Phase 4）、與 `execution_intents`／紙上交易／QSREC 契約一致；建議在 **T5a**（日報深連結）與意圖敘事穩定後再接。

---

## 與 TODOS 對照

| 計畫階段 | TODOS 錨點 |
|----------|------------|
| A | **T2a**、**T2c** |
| B | **T2b**、**T3a–T3c**、Terminal M1–M3 已交付基礎上強化 |
| C | 管線附圖，非獨立 T 編號；變更時跑 `main` smoke 路徑相關測試 |
| D | **T5a**／**T5b**、演進藍圖 Phase 4 |

---

## 修訂紀錄

- **2026-04-14**：初版 — 階段 A–D；階段 A 契約 + Streamlit 口徑落地。

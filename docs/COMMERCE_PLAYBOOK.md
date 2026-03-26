# 商業化假設與使用者路徑（Direction 1B）

本文件收斂 **1–2 條核心使用者路徑** 與 **付費假設**，供驗證後再導入 Auth／Stripe（與日報管線解耦）。

## 核心路徑 A：每日三分鐘決策

1. 開啟 **PWA 今日** 或 **Telegram 推播** → 看 regime badge 與四格 KPI。  
2. 下捲 **鏈上情緒**（SOPR／情緒／淨流向）與 **QSREC 卡片**。  
3. 需要歷史時 → **存檔**頁單日報告。

**可驗證價值**：節省自行聚合多源數據的時間；與 `daily_metrics`／Gate 一致。

## 核心路徑 B：交易追蹤與停損回饋

1. **交易**頁篩選 OPEN／HIT_STOP。  
2. 對照日報「本日選擇理由」與 tracker 敘事。  
3. 管線已將 **HIT_STOP** 注入隔日 exclusion context（見 `bigquery_writer`）。

**可驗證價值**：閉環學習敘事是否改善後續星級與方向。

## 付費假設（待驗證）

| 假設 | 驗證方式 | 若成立 → 技術選型方向 |
|------|-----------|------------------------|
| 用戶願為「推播 + 完整歷史」付費 | 等候名單、定價問卷 | Stripe Checkout + 登入後解鎖 BQ 讀取 API |
| 用戶只願為「社群／討論」付費 | Discord／論壇導流 | 與日報分離，避免動 Gate |
| 機構願為「私有部署」付費 | B2B 訪談 | 合約 + 不經公用 PWA |

## 技術選型（假設成立後）

- **Auth**：Firebase Auth（手機號／Google）或自建 JWT（FastAPI `HTTPBearer`）。  
- **付費**：Stripe Checkout／Customer Portal；**訂閱狀態**存在 Stripe + 後端快取，不寫入 `main.py` Gate。  
- **Landing**：靜態頁（Vite 或 `docs/` 託管）與 PWA 分離域名或 path prefix。

## 禁止事項

- 未驗證轉換前，**不要**在 KPI 上放硬付費牆（損害信任與對齊 Streamlit 免金鑰體驗）。  
- 付費層僅能 **遮罩讀取權限**，不得改寫工具層數字。

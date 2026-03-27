# 四職能 Crew + Arbiter 路線圖（BL-11）

現況：**Growth** 試點（`crew_company.py`、`COMPANY_CREW_ENABLED`）、[`company_ops_schemas.py`](../company_ops_schemas.py)、Dashboard「公司戰情」讀取快照。

## 目標架構

| 職能 | 產出（示意） | 下游 |
|------|----------------|------|
| Growth | 敘事／市場擴張假設 | Arbiter 輸入 |
| Product | 路線圖／指標建議 | 同上 |
| Finance | 單位經濟／預算約束 | 同上 |
| Engineering | 技術債／產能 | 同上 |
| **Arbiter** | 合併為單一 structured 決策 | War Room 顯示、可選注入日報 context |

## 實作順序（建議）

1. 每職能 **獨立 task + 固定 JSON schema**（擴充 `company_ops_schemas`）。  
2. **不**自動合併至日報正文，直到 Arbiter 通過 schema 驗證與人類抽樣審核。  
3. Dashboard：由單一 `company_run_latest.json` 擴充為版本化目錄（例如按日期）。  
4. 與 `signal_weights_store` 類似，為 company 輸出加 **版本與回滾**。

## 紅線

- LLM 不得捏造財務數字；若無工具資料，欄位填 N/A 或省略並在 schema 註記。  
- 與日報管線並行時，預設 **關閉** 注入，避免拖長 `main.py` 執行時間。

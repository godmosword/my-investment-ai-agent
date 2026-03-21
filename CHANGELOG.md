# Changelog

本檔案記錄專案重要功能與行為變更。

## 2026-03-21

### Added
- **選幣／選股理由驗證**：`validate_report` 檢查加密與美股區「本日選擇理由」是否含足夠關鍵線索（催化/鏈上 vs 財報/新聞等）或退階說明，並是否點名 QSREC 內該類所有標的；**允許連日同標的**。交易觀望時略過；`STRICT_PICK_JUSTIFICATION=0` 關閉。
- **新聞 Gate 分級**：`validate_report` 將 **交易觀望**（`trade_watch_mode`）與 **新聞資料不足分段**（`partial_news_ok`）解耦；後者須 3~5 則〔新聞 N〕、〔新聞 1~3〕齊備、UTC+8 全過、且文內宣告不補虛構 + 【新聞資料狀態】或 `[REPORT_TIER:PARTIAL_NEWS]`（後處理在 3~5 則時自動注入）。環境變數 **`ALLOW_PARTIAL_NEWS_GATE`**（預設 `1`）可關閉分段。僅 **觀望模式** 等才放寬 R:R／勝率／投資解讀量化；僅分段不再因「出現新聞資料狀態」就放寬交易欄位。

### Changed
- **上期建議追蹤**：BigQuery 以 **canonical asset**（`$`/空白/`-` 正規化）做 `PARTITION BY`；`save_recommendations` 同日同標的只保留最後一筆；合併戰報後 **`main._inject_canonical_prev_recs_block`** 以 BQ 權威 HTML **覆寫** LLM 產出之【上期建議追蹤】，避免模型自行膨脹多列。
- **`validate_report`**：宏觀異常改為僅在含 **美債** 之行解析 10Y/2Y 數值%，並縮窄 SOFR 行判斷，降低敘事句誤觸發；新聞 UTC+8 計數前剔除【新聞資料狀態】等噪音行；傳聞可信度接受 **來源：B級** 等格式。
- **`crew`**：配對比值 LONG 與建倉敘事一致；AI 區強制〔新聞 4〕～〔新聞 6〕+ UTC+8；產業鏈呢喃需含可信度；加密區註明上期區塊後端可覆寫。

## 2026-03-20

### Changed
- **上期建議追蹤**（`tracker.load_previous_recs_block`）：同一 `report_date + asset` 以 `ROW_NUMBER` 去重，優先 `OPEN`、否則最新 `created_at`，避免同日多筆 QSREC 造成同標的多空重複列。
- **`validate_report`**：要求全篇至少 6 個 `〔新聞 N〕`；主 regime 為 neutral/risk_on 時禁止交易／風險預算段誤用「依 risk_off」等敘述；AI 儀表板區掃描常見幻覺欄位字串；美債 10Y/2Y 與「利差 %」口徑一致性檢查（約 10Y−2Y）。
- **後處理**：若注入後仍缺任一 `SourceHealth`/`SourceErrors`/`SourceQuota`，會再清一次殘行並重新注入完整區塊。
- **`crew`**：新聞強制 `〔新聞 1〕`…`〔新聞 6〕`（AI 區為 4–6）；AI 儀表板禁字清單加強；倉位示例避免 neutral 時寫「risk_off」。

## 2026-03-15

### Changed（GitHub Actions）
- **CI**（`ci.yml`）：`pull_request` 仍全跑；`push main` 僅在 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow 等路徑變更時跑 Lint+Test。
- **部署**（`deploy.yml`）：**移除** `push` 自動觸發，改為僅 **`workflow_dispatch`**（Actions → Run workflow）；執行時仍先 `workflow_call` `ci.yml` 再建映像與 Cloud Run Job 部署。
- `README.md`：同步說明「push 不自動部署、手動 Deploy workflow」。

## 2026-03-08

### Added
- 新增來源可觀測欄位：`SourceHealth`、`SourceErrors`、`SourceQuota`，並納入報告後處理與驗證規則。
- 新增來源健康分數機制（NewsAPI/GNews/Apify），支援 7 天半衰期，讓來源排序偏向近期穩定表現。
- 新增來源錯誤分類統計：`429`、`400`、`timeout`、`5xx`、`other`。
- 新增來源配額控管與成本保護：可設定每日上限，且依健康分數動態收斂可用配額。

### Changed
- `market_search_tool` 由固定 fallback 順序改為「健康分數驅動的動態來源優先序」。
- 報告 resilience 後處理強化：若缺少來源可觀測欄位，會自動注入固定區塊。
- `README.md` 更新為目前 agent 模型、工具組合、資料源策略與新環境變數。

### Persistence
- 來源健康狀態持久化升級：
  - 本地：`.source_health.json`
  - 雲端：BigQuery `source_health_stats`（可透過 `DISABLE_SOURCE_HEALTH_BQ=1` 關閉）

### Validation
- 已完成語法檢查、既有單元測試與 lint 檢查，未引入新錯誤。

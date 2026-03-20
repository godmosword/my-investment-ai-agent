# Changelog

本檔案記錄專案重要功能與行為變更。

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

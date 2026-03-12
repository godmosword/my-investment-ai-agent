# Changelog

本檔案記錄專案重要功能與行為變更。

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

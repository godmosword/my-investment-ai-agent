-- Phase 4c：日報 BQ 稽核表新增 `profile`（與 REPORT_PROFILE／validate_report 對齊）
--
-- 管線首次寫入時會以 API 自動補欄（見 bigquery_writer.write_llm_run_log /
-- write_gate_failure_log）。若舊表需先手動加欄，可於 BQ 主控台執行下列語句
--（將 my-project 換成實際 GCP project id）。
-- 若報錯 duplicate column name，表示欄已存在，可略過該句。
--
-- Phase 4d 提醒：若環境從未成功跑過帶 schema 更新之寫入、或希望部署前顯式對齊 schema，
-- 建議在 staging／production 先執行本檔 ALTER；部署 runbook 見 docs/DEPLOY_RUNBOOK.md。
--
-- LLM 執行摘要（預設 {PROJECT}.market_data.llm_run_log）

ALTER TABLE `my-project.market_data.llm_run_log`
ADD COLUMN profile STRING;

-- Gate 失敗結構化日誌（表名須與 config.GATE_FAILURE_LOG_TABLE 一致，預設 market_data.gate_failure_log）

ALTER TABLE `my-project.market_data.gate_failure_log`
ADD COLUMN profile STRING;

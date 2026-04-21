# Gate 失敗內部儀表（維護者）

對齊 TODOS「Gate 儀表板（內部）」：**不必等新程式**，可先用現有 SQL／試算表／Looker。

## 資料來源

- BigQuery 表：與 [`config.py`](../config.py) `GATE_FAILURE_LOG_TABLE` 一致（預設 `{GCP_PROJECT_ID}.market_data.gate_failure_log`）。
- 寫入條件：管線 `validate_report` 產生 issues 且 `GATE_FAILURE_BQ_LOG` 未關閉；見 [`bigquery_writer.write_gate_failure_log`](../bigquery_writer.py)。

## 建議第一頁內容

1. **近 14 日**每日失敗筆數、`blocking_count` 加總（趨勢圖）。
2. **Top `issues_preview`** 或 fingerprint 聚合（與 [`docs/SQL/gate_failure_weekly_summary.sql`](SQL/gate_failure_weekly_summary.sql) 類似）。
3. **環境維度**（若表未存 env，可在排程註解或獨立維度表手動標註 staging／prod）。

## 與 Terminal / PWA 觀測對齊（T1b）

- `api.py` 已有可選 **`API_HTTP_REQUEST_LOG=1`** middleware，對 `/api/*` 記錄 `path`、`method`、`status`、`elapsed_ms`；可先用 log 做輕量觀測，再決定是否升級成 BQ / Looker 指標。
- 若要對齊前端 `WarRoom` / `Terminal` 的錯誤態，至少要能回答三件事：
  1. 是 **5xx / exception**，還是 **4xx / schema / invalid JSON**。
  2. 是 **整體端點失敗**，還是 **局部來源漂移**（例如 `snapshot` 仍可顯示，但 `quote` / `price_alignment` 為 `N/A`）。
  3. 問題是 **延遲升高** 還是 **資料來源變更**。
- 內部儀表第一版不必新增表；先把以下欄位在 log / 查詢層能看見即可：
  - `/api/symbols/{symbol}/snapshot`、`/api/symbols/{symbol}/quote`、`/api/war-room/latest` 的 `status` 與 `elapsed_ms`
  - `price_alignment.aligned` 的 `true / false / null` 三態分佈（可由 staging / probe 另行抽樣）
  - `data_provenance` 與 UI 文案是否仍一致（見 [`docs/DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md)）

## CLI 草稿輸出

本機有憑證時可跑：

```bash
python3 scripts/gate_failure_hint_digest.py
```

產出 Markdown 供貼內部文件，再進 [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](GATE_FAILURE_HINT_WORKFLOW.md) 人審流程。

## 修訂紀錄

- **2026-04-04**：初版（連結 SQL、BQ 表、digest script）。

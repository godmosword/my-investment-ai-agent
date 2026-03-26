# Q-Silicon — 工程與產品待辦（彙總）

本檔為 **全 repo 待辦與完成度的唯一彙總**（含舊 `TODOS` 條目、`docs/` 計劃書缺口、路線圖對照）。  
**每次合併有意義的改版**：請在 [`CHANGELOG.md`](CHANGELOG.md) 寫一筆（日期區塊），並在本檔調整對應項目的狀態。

---

## 狀態圖例

| 符號 | 意義 |
|------|------|
| ✅ | 已落地且可指到檔案／測試；營運設定若需人工（如 GitHub Environment）會註明 |
| 🔶 | 邏輯或文件已有，**缺測試、文件、上線策略或營運關閉動作** |
| ⬜ | 尚未實作或規格未寫 |

---

## 已完成並驗證

### A. 基礎與可觀測性

| ID | 項目 | 佐證／驗證 |
|----|------|------------|
| DONE-A1 | API 回應 schema guard | [`api_schema.py`](api_schema.py)、[`test_api_schema.py`](test_api_schema.py) |
| DONE-A2 | 盤中監控與 workflow | [`monitor_intraday.py`](monitor_intraday.py)、[`.github/workflows/monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) |
| DONE-A3 | LLM run log → BigQuery | [`bigquery_writer.py`](bigquery_writer.py) `write_llm_run_log`、[`main.py`](main.py)、[`test_llm_run_log.py`](test_llm_run_log.py) |
| DONE-A4 | 新聞新鮮度 **機檢邏輯**（預設關） | [`report_validator.py`](report_validator.py) `_check_news_freshness` 等；**啟用與文件**仍見 Backlog BL-02 |

### B. 產品路線（對 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)）

| ID | 項目 | 佐證／驗證 |
|----|------|------------|
| DONE-B1 | 路線願景文件 | [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) |
| DONE-B2 | 方向 1B 使用者路徑／付費假設（文件） | [`docs/COMMERCE_PLAYBOOK.md`](docs/COMMERCE_PLAYBOOK.md)（**實作 Auth／Stripe** 未做，見 BL-10） |
| DONE-B3 | 方向 2A 權重版本化＋可選注入 context | [`signal_weights_store.py`](signal_weights_store.py)、[`scripts/write_ml_weights.py`](scripts/write_ml_weights.py)、[`bigquery_writer.py`](bigquery_writer.py) `fetch_exclusion_context`、`WEIGHTS_CONTEXT_ENABLED` |
| DONE-B4 | 方向 2B Scout 流程與檢查清單（文件） | [`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)（**自動週報腳本**未做，見 BL-09） |
| DONE-B5 | 方向 3A schema + Growth 試點 crew | [`company_ops_schemas.py`](company_ops_schemas.py)、[`crew_company.py`](crew_company.py)、`COMPANY_CREW_ENABLED`、[`test_company_ops_schemas.py`](test_company_ops_schemas.py) |
| DONE-B6 | 方向 3B War Room 唯讀（試點） | [`dashboard.py`](dashboard.py)「公司戰情」區塊、`load_company_war_room_snapshot`（**四職能自動產出**未做，見 BL-11） |
| DONE-B7 | 橫切：日報潤稿（可選） | [`report_editor.py`](report_editor.py)、[`main.py`](main.py) `_maybe_editor_polish_html`、`EDITOR_AGENT_ENABLED`、[`test_report_editor.py`](test_report_editor.py)、[`scratchpad.py`](scratchpad.py) `append_editor_result` |
| DONE-B8 | 方向 1A 儀表／PWA／API KPI 對齊（實作） | [`dashboard.py`](dashboard.py)、[`api.py`](api.py)、[`data-verification-ui/`](data-verification-ui/)（**逐圖表「契約表」文件化**仍見 BL-08） |

### C. CI／部署

| ID | 項目 | 佐證／驗證 |
|----|------|------------|
| DONE-C1 | `deploy` job 使用 `environment: production` | [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) 第 39 行；**GitHub 後台是否設定 Required reviewers** 須營運確認（未完成則 BL-06 仍算開放） |

### D. 測試與 Lint（例行）

| 項目 | 指令 |
|------|------|
| Smoke | `python3 -m pytest -m smoke -v` |
| 全量 | `python3 -m pytest -v` |
| Lint | `ruff check .` |

---

## 待辦清單（Backlog）

### P0 — 建議下一波（高影響／可行性高）

| ID | 狀態 | 項目 | 說明與主要路徑 |
|----|------|------|----------------|
| **BL-01** | ⬜ | 啟動期 **critical env fail-fast** | 擴充 [`main.py`](main.py) `_validate_required_keys()` 或新增 `_validate_critical_env()`：依 `SKIP_TELEGRAM`／`SKIP_BIGQUERY` 等路徑，條件式要求 Telegram／GCP／data API；對齊 `_log_api_key_inventory`「建議／備援」群組與 README／`ENV_TEMPLATE.txt`。 |
| **BL-02** | 🔶 | **新聞新鮮度 Gate** 上線 | 邏輯已在 `report_validator`；**仍缺**：專項測試（新鮮／過舊／無時間戳／跨日／白名單）、README + **`ENV_TEMPLATE.txt` 變數說明**（`STRICT_NEWS_FRESHNESS_GATE`、`NEWS_FRESHNESS_WINDOW_HOURS`、`NEWS_FRESHNESS_SOURCE_WHITELIST`）、營運 rollout；可選管線傳入 `report_dt`。 |

### P1 — 架構與 Autoresearch

| ID | 狀態 | 項目 | 說明與主要路徑 |
|----|------|------|----------------|
| **BL-03** | ⬜ | **`tools.py` 模組化** | 依來源拆檔（crypto／macro／equities／search／quant），根目錄 `tools.py` 僅 re-export；避免循環 import。 |
| **BL-04** | ⬜ | **Autoresearch：`docs/AUTORESEARCH_LOOP.md`** | 定義誰產生 diff、apply／revert 狀態機、`runs.jsonl` plateau 讀取；見 [`docs/autoresearch.plan.md`](docs/autoresearch.plan.md) 與其中 **UNRESOLVED**。 |
| **BL-05** | ⬜ | **Autoresearch：bench 入口** | 計劃書 Day 2 要求例如 `scripts/bench_autoresearch.sh`（`METRIC key=value`）；**目前 `scripts/` 僅** `write_ml_weights.py`、`inject_test_data.py`。 |
| **BL-06** | 🔶 | **生產部署人工閘門（營運閉環）** | 程式已 `environment: production`；**需**：GitHub **Environments → production → Required reviewers**、deploy runbook 更新。 |

### P2 — 安全與加固

| ID | 狀態 | 項目 | 說明與主要路徑 |
|----|------|------|----------------|
| **BL-07** | ⬜ | **bench `METRIC` 完整性防偽** | 計劃見舊 TODOS：在 bench 腳本（待 BL-05）對 `METRIC` 輸出做來源綁定或至少風險註解。 |

### P3 — 遠期

| ID | 狀態 | 項目 | 說明與主要路徑 |
|----|------|------|----------------|
| **BL-08** | ⬜ | **Gate 失敗 → BQ 結構化 log → 週期分析** | 先只做寫入與分類；自動改 prompt 需防注入與人工審核。 |

### 產品／路線延伸（非阻塞日報）

| ID | 狀態 | 項目 | 說明 |
|----|------|------|------|
| **BL-09** | ⬜ | **Scout 週報自動化** | 候選清單產生腳本（GitHub Search API 等）；仍須 **人類 PR**，與 [`docs/oss_candidates/README.md`](docs/oss_candidates/README.md) 流程一致。 |
| **BL-10** | ⬜ | **商業化實作** | Auth／Stripe／API 授權讀 BQ；[`COMMERCE_PLAYBOOK.md`](docs/COMMERCE_PLAYBOOK.md) 為假設階段。 |
| **BL-11** | ⬜ | **四職能 Crew + Arbiter 執行層** | 目前僅 Growth 試點 + Pydantic schema；Product／Finance／Engineering 自動產出與仲裁尚未接線。 |
| **BL-12** | 🔶 | **儀表板「契約」完整文件化** | ROADMAP 1A：每圖表／KPI 標註來源、更新頻率、缺資料行為；可集中補在 README 或 `docs/DASHBOARD_CONTRACT.md`。 |

---

## 產品路線對照（`ROADMAP_VISION` 完成度）

| 區塊 | 目標 | 完成度 | 備註 |
|------|------|--------|------|
| 1A | 視覺化正確性 + KPI 對齊 | 🔶 | 實作已有；契約文件見 BL-12 |
| 1B | 路徑 + 付費假設 | 🔶 | 文件 ✅；付費實作 ⬜（BL-10） |
| 2A | 權重閉環 | ✅ | 儲存、注入、回滾、測試 |
| 2B | Scout + 部署閘門 | 🔶 | 流程文件 ✅；週報腳本 ⬜；deploy 程式 ✅、審批設定 🔶 |
| 3A | Arbiter schema + Growth | ✅ | 試點 crew + schema |
| 3B | 四職能 + War Room | 🔶 | War Room 讀快照 ✅；四職能 ⬜（BL-11） |
| 橫切 | 潤稿 Agent | ✅ | 可關閉、Gate 後驗、`<code>` 保護 |

---

## Repo 掃描紀錄（靜態搜尋）

**掃描日：2026-03-25**（之後請在每次大整理時更新本段日期與摘要）

| 搜尋 | 結果 |
|------|------|
| `*.py` 中 `# TODO` / `# FIXME` / `# XXX` | **無** |
| `tools.py` 含「TODO／未完成」 | 僅一般中文或網域字串（如 hackernoon），**非**工程待辦 |
| `docs/autoresearch.plan.md` | 仍描述 7 日衝刺；**bench 腳本與 LOOP 規格**與 repo 現況落差 → 已收斂為 BL-04、BL-05、BL-07 |
| `scripts/` | 無 `bench_autoresearch.sh` → BL-05 |

---

## 舊「優先順序速覽」對照

| 舊列點 | 現編號 |
|--------|--------|
| critical env | BL-01 |
| 新聞新鮮度 | BL-02 |
| tools.py 分割 | BL-03 |
| Gate 自動學習 | BL-08 |
| Autoresearch loop spec | BL-04 |
| deploy 人工審批 | BL-06（+ DONE-C1） |
| METRIC 完整性 | BL-07 |

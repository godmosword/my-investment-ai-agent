# Q-Silicon 產品與技術路線願景（ROADMAP_VISION）

**待辦與完成度**以 [`TODOS.md`](../TODOS.md) 為唯一彙總（含 Backlog 編號與掃描紀錄）；**本文件**收斂三條產品與架構主線、紅線、以及與該彙總的對照。改版紀錄見 [`CHANGELOG.md`](../CHANGELOG.md)。

---

## 紅線（全路線共通）

1. **資料信任邊界**：可驗證報價、技術與宏觀數字由 **工具層／BigQuery** 注入；LLM 與潤稿層 **不得** 捏造或改寫 `<code>` 內客觀數值、新聞時間結構、QSREC 標記。
2. **自動化與部署**：OSS 導入、實驗合併須經 **CI + 人類 PR review**；生產部署見 [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) 的 `environment: production`（於 GitHub **Settings → Environments** 設定必要審批者後始生效）。
3. **付費與日報解耦**：商業化（Auth／Stripe）應主要發生在 **API／PWA 讀取層**，避免削弱 `validate_report` 權威。

---

## 方向 1 — 穩定視覺化、UI/UX、商業化假設

| 階段 | 內容 | Repo 對應 |
|------|------|-----------|
| 1A | 儀表板契約：標註資料來源／更新頻率／缺資料行為 | [`dashboard.py`](../dashboard.py) 鏈上與衍生品區塊、KPI；[`data-verification-ui`](../data-verification-ui/) 與 [`api.py`](../api.py) 對齊 |
| 1B | 使用者路徑收斂、付費假設驗證、技術選型 | [`docs/COMMERCE_PLAYBOOK.md`](COMMERCE_PLAYBOOK.md) |

**與 TODOS 對照**：Critical env、新聞新鮮度 rollout、Streamlit／PWA 一致性能降低誤判與客訴。

---

## 方向 2 — 自動迭代與受控 OSS 融合

| 階段 | 內容 | Repo 對應 |
|------|------|-----------|
| 2A | 回測權重 → 版本化儲存 → 可選注入 crew context（含回滾） | [`signal_weights_store.py`](../signal_weights_store.py)、[`scripts/write_ml_weights.py`](../scripts/write_ml_weights.py)、[`bigquery_writer.fetch_exclusion_context`](../bigquery_writer.py) |
| 2B | Scout 週報候選、威脅建模、人類 PR；deploy 人工閘門 | [`docs/oss_candidates/README.md`](oss_candidates/README.md)、`deploy.yml` |

**與 TODOS 對照**：`tools.py` 拆分利於審計 OSS 邊界；Autoresearch 相關條目與本方向 **Scout** 可共用「候選 → PR」語意，但 **不得** 略過人類 merge。

---

## 方向 3 — Multi-agent 延伸至「新創公司」隱喻

| 階段 | 內容 | Repo 對應 |
|------|------|-----------|
| 3A | Arbiter／部門備忘 JSON schema；試點 **Growth** 敘事 crew | [`company_ops_schemas.py`](../company_ops_schemas.py)、[`crew_company.py`](../crew_company.py)、環境變數 `COMPANY_CREW_ENABLED` |
| 3B | 四職能擴充 + Company War Room 唯讀頁 | Streamlit「公司戰情（試點）」區塊讀取 [`.qsilicon/company_run_latest.json`](../.gitignore)（執行時寫入，勿提交） |

**與 TODOS 對照**：延遲與 token 預算隨 agent 數增加；需與 `CREW_FUTURE_TIMEOUT_SEC` 一併評估。

---

## 橫切：日報潤稿 Agent

在 `render` + `_post_process_html_for_gate` 之後、`validate_report` 之前，可選執行 [`report_editor.py`](../report_editor.py)（`EDITOR_AGENT_ENABLED=1`）。詳見 `ENV_TEMPLATE.txt` 與 [`test_report_editor.py`](../test_report_editor.py)。

---

## 修訂紀錄

- 2026-03：初版，對齊三方向計劃與 repo 落地檔案。

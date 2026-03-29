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

<a id="roadmap-evolution-condensed"></a>

## 演進藍圖（跨階技術路線，精簡）

由「日報／量化腳本管線」往「開源 SaaS 可跑、可執行、可圖像化與多媒體 IP」延伸的**第二條長軸**（與上方方向 1–3 並列參考）。**時程為規劃用**；與 Gate／資料紅線衝突時以本檔 [紅線](#紅線全路線共通) 與 [`TODOS.md`](../TODOS.md) [維護者意見](../TODOS.md#維護者意見執行順序與取捨) 為準。**可勾選細項與巢狀待辦**見 [`TODOS.md` — 演進藍圖](../TODOS.md#roadmap-technical-saas-execution-brain)。

- **Phase 1（0–1 個月）— 開源與容錯**：`MOCK_APIS` + `tests/fixtures/mock_data/` + `api.py`／`tools.py` 外部 HTTP 短路；`BaseTool` + `plugins/` 動態掛載（對齊 `TOOLS_MODULARIZATION_PLAN`）；`docker-compose` 一鍵 **FastAPI + Vite PWA + Redis**。
- **Phase 2（1–3 個月）— 訊號→執行**：獨立 **`execution_engine`**（CCXT、Alpaca 或 IBKR）、自 BQ 讀 **QSREC** 做 **TWAP／VWAP** 紙上／模擬；**Monitor V2** 以 **WebSocket** 為主、觸價（如擊穿 `stop`）→ 平倉路徑 + **Telegram** 緊急推播。
- **Phase 3（3–6 個月）— 次世代大腦**：**LangGraph**（或同等）試點重構 `crew.py`，**Conditional Edge** 驅動查證子任務；**Bull／Bear** 三輪辯論 + Strategist 收斂，輸出仍過 **`validate_report`**。
- **Phase 4（6 個月以上）— 觀測與 IP**：**Glassbox** 導入 **lightweight-charts**，K 線疊 **Entry／Target／Stop**；**RAG**（戰報／停損向量化 + 前端問答）；**語音晨報**（講稿 Agent + TTS + Telegram）。

---

## 橫切：日報潤稿 Agent

在 `render` + [`report_html_postprocess.post_process_html_for_gate()`](../report_html_postprocess.py) 之後、`validate_report` 之前，可選執行 [`report_editor.py`](../report_editor.py)（`EDITOR_AGENT_ENABLED=1`）。詳見 `ENV_TEMPLATE.txt` 與 [`test_report_editor.py`](../test_report_editor.py)。

---

## 修訂紀錄

- 2026-03-29：新增 [演進藍圖（精簡）](#roadmap-evolution-condensed)（Phase 1–4），與 [`TODOS.md`](../TODOS.md) 演進藍圖章節雙向對照。
- 2026-03：初版，對齊三方向計劃與 repo 落地檔案。

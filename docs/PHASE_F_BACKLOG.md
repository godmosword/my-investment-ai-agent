# Phase F — 長期路線備忘（1B / 2B / Direction 3）

本檔為 [TODOS.md](../TODOS.md) 與計劃「階段 F」之執行索引，**非**一次性實作範圍。

**未完成項決策評分**（Pri 1–9、Phase 1–4／階段 E 濃縮四維表、新建議 backlog、建議開工順序）：見 [TODOS.md — 未完成項四維評分與新建議（2026-04）](../TODOS.md#未完成項四維評分與新建議2026-04)。

## Direction 1B — 商業化

- 實作入口：[`docs/COMMERCE_NEXT_STEPS.md`](COMMERCE_NEXT_STEPS.md)
- 技術主線：Firebase Auth、`api.py` 擴充、Stripe Checkout/Webhook、API tier、多租戶 Telegram、Landing。

## Direction 2B — OSS Scout

- 現有腳本：[`scripts/oss_scout_candidates.py`](../scripts/oss_scout_candidates.py)
- CI 手動 workflow：[`.github/workflows/weekly-scout.yml`](../.github/workflows/weekly-scout.yml)
- 後續：HuggingFace／GraphQL、提案 Agent、**人類 merge** 之開 PR 流程。

## Direction 2A — 週期回測寫權重

- 手動 workflow：[`.github/workflows/weekly-backtest.yml`](../.github/workflows/weekly-backtest.yml)（需 `GCP_SA_KEY`；見 workflow 註解）。

## Direction 3 — Company Multi-Agent

- 路線圖：[`docs/COMPANY_CREW_ROADMAP.md`](COMPANY_CREW_ROADMAP.md)
- 現有試點：`crew_company.py`、`COMPANY_CREW_ENABLED`、Streamlit 讀快照。

---

<a id="roadmap-phases-1-4-condensed"></a>

## 演進藍圖 — Phase 1–4（精簡）

與上方 1B／2A／2B／Direction 3 **正交**：描述「開源可跑 → 執行層 → 圖工作流 → 儀表與 IP」的長期技術堆疊。**完整勾選與子任務**見 [`TODOS.md`](../TODOS.md#roadmap-technical-saas-execution-brain)；願景與紅線對照見 [`docs/ROADMAP_VISION.md`](ROADMAP_VISION.md#roadmap-evolution-condensed)。

- **Phase 1（0–1 個月）**：Mock 模式（`ENV_TEMPLATE`：`MOCK_APIS`、fixtures、`api.py`／`tools.py` 攔截 HTTP）、Tool Plugin（`BaseTool`、`plugins/`）、Docker Compose（FastAPI + `data-verification-ui` + Redis）。
- **Phase 2（1–3 個月）**：`execution_engine`（CCXT、Alpaca／IBKR、QSREC→TWAP／VWAP 模擬）；`monitor_intraday` **V2**（WebSocket、觸發停損→平倉 + Telegram）。
- **Phase 3（3–6 個月）**：LangGraph 類圖工作流、條件分支與查證子任務；Bull／Bear 多輪辯論 + 主編收斂（仍過 Gate）。
- **Phase 4（6 個月以上）**：Glassbox + lightweight-charts 疊加進出場；RAG 對話；語音晨報（講稿 + TTS + Telegram）。

## 修訂紀錄

- 2026-04-04：檔首補連結至 `TODOS.md` **未完成項四維評分與新建議（2026-04）**（含本檔涵蓋之 1B／2B／Direction 3 與 Phase 1–4 之濃縮評分表）。
- 2026-03-29：新增本節「演進藍圖 Phase 1–4（精簡）」，與 `TODOS.md`／`ROADMAP_VISION.md` 對照。

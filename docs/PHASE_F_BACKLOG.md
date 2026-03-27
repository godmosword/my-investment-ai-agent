# Phase F — 長期路線備忘（1B / 2B / Direction 3）

本檔為 [TODOS.md](../TODOS.md) 與計劃「階段 F」之執行索引，**非**一次性實作範圍。

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

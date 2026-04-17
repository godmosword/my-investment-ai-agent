# ADR 與架構決策索引

本頁連結 repo 內已落地的 **架構決策記錄（ADR）** 與相鄰設計稿，便於 onboarding 與審閱。

| 文件 | 主題 |
|------|------|
| [ADR_OFFICE_HOURS_TOOLS_PLATFORM.md](ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) | `tools` 套件、`MOCK_APIS`、Office Hours 工具平台 |
| [TOOLS_MODULARIZATION_PLAN.md](TOOLS_MODULARIZATION_PLAN.md) | `tools_legacy` 拆分路線 |
| [GATE_INTERNAL_DASHBOARD.md](GATE_INTERNAL_DASHBOARD.md) | Gate 失敗內部儀表（BQ／digest） |
| [GATE_FAILURE_HINT_WORKFLOW.md](GATE_FAILURE_HINT_WORKFLOW.md) | Gate 失敗 → 人審提示流程 |
| [CRITICAL_ENV_POLICY.md](CRITICAL_ENV_POLICY.md) | `PIPELINE_STRICT_ENV` 與啟動契約 |
| [STAGING_THRESHOLD_EXPERIMENT.md](STAGING_THRESHOLD_EXPERIMENT.md) | 選標／rotation 閾值 staging 實驗 |
| [TERMINAL_MID_TIER_ROADMAP.md](TERMINAL_MID_TIER_ROADMAP.md) | Terminal 中段 M1–M5 |
| [PWA_WEB_PUSH.md](PWA_WEB_PUSH.md) | Web Push（Redis、VAPID、`pywebpush`、可選 BQ） |
| [SQL/price_probe_log.sql](SQL/price_probe_log.sql) | 實盤 BQ vs yfinance 觀測表（`scripts/symbol_price_probe.py`） |
| [BLOOMBERG_ALIGNMENT.md](BLOOMBERG_ALIGNMENT.md) | Terminal 對齊 Phase 0 驗收 |
| [ADR_CURRENT_AFFAIRS_ROUNDTABLE.md](ADR_CURRENT_AFFAIRS_ROUNDTABLE.md) | 〔時事多觀點〕區塊、`BRIEF_DYNAMIC_RENDER`、strict Gate |

## 修訂紀錄

- **2026-04-14**：初版索引（G-7：集中 ADR／設計稿連結；不含自動生成內容）。
- **2026-04-14（二）**：補 [`PWA_WEB_PUSH.md`](PWA_WEB_PUSH.md)。
- **2026-04-27**：補 [`ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)。

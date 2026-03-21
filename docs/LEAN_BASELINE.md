# Lean Baseline

> 目的：在重構前先建立可量測基準，避免「感覺變快」但不可驗證。  
> **本檔由助理代填「可自動取得」欄位**；完整日報 wall time 須在你本機／Cloud Run（有 API 金鑰）補上。

## 1) 日報執行樣本（3 次）

**狀態：待你在有金鑰環境補齊**（每次跑 `python main.py` 後填表）。

| run_id | 日期 | wall_time_sec | 是否成功 | 失敗型態 | 可用性(1-5) | 備註 |
|---|---|---:|---|---|---:|---|
| — | — | — | — | — | — | 請填：實際或乾跑（可設 `SKIP_TELEGRAM=1` `SKIP_BIGQUERY=1` 仍會耗 LLM） |
| — | — | — | — | — | — | 同上 |
| — | — | — | — | — | — | 同上 |

**本機非 LLM 參考（僅供 CI 節奏，不代表日報）**

- `pytest -q`（完整）：約 **0.5–1.0s** 量級（本機 2026-03 實測 **142 passed**）；實際依機器與依賴載入而異。

## 2) 文檔分類（排除 `.agents/`，僅 `git ls-files '*.md'`）

| 檔案 | 分類 | 理由 |
|---|---|---|
| README.md | 保留 | 權威產品與操作說明 |
| CLAUDE.md | 保留 | 權威開發／工具規範 |
| AGENTS.md | 保留 | Cursor Cloud / 代理說明 |
| gstack.md | 保留 | 本專案 gstack slash 技能手冊 |
| CHANGELOG.md | 保留 | 版本與變更紀錄 |
| docs/DAILY_BRIEF_V2.md | 保留 | 日報 V2 版面／敘事規格 |
| docs/ADOPTION_DEXTER_CONCEPTS.md | 保留 | Dexter 式導入計畫 |
| docs/COST_PER_MODEL.md | 保留 | 模型成本參考 |
| docs/OPENAI_COST_ESTIMATE.md | 保留 | 成本估算參考 |
| docs/PHASE_GATES.md | 保留 | Lean 分期進出條件 |
| docs/REPORT_COMPARE_STAGING.md | 保留 | REPORT_COMPARE 操作與 staging |
| docs/LEAN_BASELINE.md | 保留 | 本基準表（可持續更新） |

**合併／刪除**：目前無強制合併項；若未來與 README 重複，可將 `docs/COST_*` 整併進 README 一節後標「刪除」。

## 3) CI 基準（最近 5 次，不含 queue、不含手動重跑）

**狀態：此環境無法呼叫 GitHub API**；請在本機已登入 `gh` 時執行：

```bash
cd /path/to/investment-ai-agent
gh run list --workflow=ci.yml --limit 5
# 於 Actions UI 開啟各 run → 點 job「full」或「quick」查看 Duration（以頁面為準，非 queue）
```

| workflow | job | duration_sec | commit |
|---|---|---:|---|
| CI | quick（PR） | 待填 | 待填 |
| CI | full（main 等） | 待填 | 待填 |
| … | … | … | … |

## 4) 後續目標映射

- SC-1：文檔入口收斂（README + CLAUDE）
- SC-2：規則重複抽離
- SC-3：token 成本下降
- SC-4：PR 回饋時間下降
- SC-5/SC-6：輸出契約與 gate 正確性

## 5) 簽核（Phase 2 開工 gate）

- [ ] 上表 **§1** 已填滿 3 次日報樣本  
- [ ] **§3** 已自 GitHub 補 5 次 CI duration  
- **Owner / 日期**：________________

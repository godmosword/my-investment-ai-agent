# Phase 3: LangGraph 雙軌部署與測試計畫 (Shadow Mode Deployment)

## 實作狀態

> **2026-04-08 更新**：Steps 1–3 已於先前迭代中完成實作。本文件作為架構決策紀錄 (ADR) 保存。

| Step | 狀態 | 位置 |
|------|------|------|
| Step 1: 環境變數開關 | ✅ 已完成 | `config.py:38`, `ENV_TEMPLATE.txt:85` |
| Step 2: `main.py` 雙軌切換 | ✅ 已完成 | `main.py:621–688` |
| Step 3: Pydantic 無縫對接 | ✅ 已完成 | `graph/graph_crew.py:68–107` |
| Step 4: 本地乾跑測試 | 待執行 | 見下方指令 |

---

## 階段目標

我們已經成功建構了次世代的 LangGraph 認知引擎（`graph_state.py`, `graph_nodes.py`, `graph_crew.py`）。本階段的目標是將新大腦**安全且無損地**接入主程式 `main.py`。

採用「雙軌制 (Shadow Mode)」，透過環境變數作為切換開關，確保在不干擾現有生產環境 (CrewAI) 的前提下，進行新架構的本地端測試與資料對齊。

---

## 架構說明

### 引擎切換流程

```
main.py → _run_pipeline_once()
    │
    ├─ USE_LANGGRAPH_ENGINE=1 ──→ run_langgraph_category("CRYPTO")
    │                              run_langgraph_category("AI")
    │                              ↓
    │                         CryptoSection | AISection (Pydantic)
    │
    └─ USE_LANGGRAPH_ENGINE=0 ──→ CryptoResearchCrew().run()
       (預設)                      AIResearchCrew().run()
                                   ↓
                              CryptoSection | AISection (Pydantic)
                                   ↓
                         assemble_daily_brief_report(crypto_section, ai_section, ...)
                                   ↓
                         render_telegram_daily_brief(report_model)
```

### LangGraph 節點 DAG

```
START → data_gatherer → {bull_agent, bear_agent} → arbiter
                                                        │
                                          needs_deep_dive?
                                                        │
                                    ┌───── Yes ─────────┤
                                    ↓                   │ No
                             deep_research              ↓
                                    └──────────→ final_formatter → END
```

遞迴上限：40 次（`graph_crew.py:100`）；預設最大深度：2（`max_research_depth=2`）。

---

## 環境變數

```env
# 認知引擎切換 (Cognitive Engine Toggle)
# 設為 1 啟動次世代 LangGraph 狀態機，設為 0 則使用傳統 CrewAI 流水線
USE_LANGGRAPH_ENGINE=0

# LangGraph 輔助開關
GRAPH_ENABLE_TOOL_CALLS=1         # 0 可停用所有工具呼叫（適合單元測試）
LANGGRAPH_SKIP_FORMATTER_CREW=0   # 1 可略過最終 Crew，改用直接 JSON 輸出
```

---

## Step 4: 本地乾跑測試 (Local Dry Run)

```bash
USE_LANGGRAPH_ENGINE=1 SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py
```

### 觀測指標

1. 終端機 Log 應出現：
   - `USE_LANGGRAPH_ENGINE=1, running LangGraph shadow engine.`（`main.py:622`）
   - data_gatherer、arbiter 等節點的執行訊息
   - `shadow_benchmark langgraph_dual_crew elapsed_sec=...` 計時輸出

2. 最終報告結構應與舊版 CrewAI 排版一致（Telegram HTML 格式）。

### 工具呼叫停用模式（無 API key 環境）

```bash
USE_LANGGRAPH_ENGINE=1 GRAPH_ENABLE_TOOL_CALLS=0 SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py
```

---

## 防禦與退場機制 (Rollback Strategy)

未來部署上線後，如果發現 LangGraph 消耗的 Token 暴增，或是發生預期外的死迴圈，維護者只需在 GCP Cloud Run 或 GitHub Secrets 中將 `USE_LANGGRAPH_ENGINE` 改回 `0`，下一次排程就會瞬間切換回 CrewAI 大腦。

成本為零、風險為零的熱切換。

---

## 相關文件

- [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) — Tools 平台決策
- [`docs/TOOLS_MODULARIZATION_PLAN.md`](TOOLS_MODULARIZATION_PLAN.md) — Tools 模組化計畫
- [`graph/graph_crew.py`](../graph/graph_crew.py) — 引擎入口 `run_langgraph_category()`
- [`graph/graph_nodes.py`](../graph/graph_nodes.py) — 6 個節點實作
- [`graph/graph_state.py`](../graph/graph_state.py) — 共享 State TypedDict

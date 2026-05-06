# Reviewer Loop 設計文件

> LangGraph Phase 3.5：`trade_picker_node` → `reviewer_node` 自動反思迴圈設計

> **狀態（2026-04-21）**：第一版已落地於 `graph/`：`trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`，並新增 `write_reviewer_log` 與 `docs/SQL/reviewer_log.sql`。實作保留設計紅線：Reviewer 只查 trade 邏輯，不取代 `validate_report`／Telegram HTML Gate。

---

## 設計原則

**不要一上來就純 LLM reviewer。** 採用兩層檢查：Python 先擋、LLM 只查 Python 抓不到的。

---

## 兩層檢查架構

### Layer 1：Python Rules（確定性，無 token 成本）

先擋掉明顯錯誤，完全不呼叫 LLM：

```
確定性檢查（Python）：
├── ticker 存在性：check against assets_universe
├── 方向一致性：long position 的 stop < entry < target
├── 數字合理性：stop loss / entry 距離在合理 % 範圍
├── 重複標的：trade_watch 內不能重複
└── Slim Schema 欄位完整性：所有必要欄位非空
```

### Layer 2：LLM Reviewer（只查 Python 抓不到的）

只有 Layer 1 通過才進入 LLM 檢查：

```
narrative 矛盾檢查（LLM）：
├── thesis 與 trade direction 是否一致
│   （例：看空 BTC 但建議 long BTC spot）
├── trade_watch 標的是否出現在 raw_data 的 candidates
│   （防幻覺標的）
└── 風險論述與 stop loss 設定是否對齊
```

---

## State Machine 流程

```
                    ┌──────────────────┐
                    │   trade_picker   │ ←────┐
                    └────────┬─────────┘      │
                             ↓                │
                    ┌──────────────────┐      │
                    │  python_validate │      │
                    └────────┬─────────┘      │
                      fail ↓     ↓ pass       │
                    ┌─────────┐  │            │
                    │ reject  │  │            │
                    └────┬────┘  ↓            │
                         │  ┌──────────────┐  │
                         │  │ llm_reviewer │  │
                         │  └──────┬───────┘  │
                         │    fail ↓   ↓ pass │
                         └─────┐   │   │      │
                               ↓   ↓   ↓      │
                         ┌──────────────┐     │
                         │ should_retry │─────┘
                         └──────┬───────┘  retries < 2
                                ↓ retries ≥ 2
                         ┌──────────────┐
                         │ degrade_node │ → 保留最後版本 + 警示 flag
                         └──────┬───────┘
                                ↓
                              END
```

---

## State 欄位新增

```python
# graph/graph_state.py 增補
class GraphState(TypedDict):
    # ... existing fields
    trade_candidates: list[TradeIdea]      # picker 產出
    review_issues: list[ReviewIssue]       # reviewer 回饋
    revision_count: int                    # retry 計數
    review_history: list[ReviewRound]      # 審計軌跡（BQ 寫入用）
    trade_watch_final: list[TradeIdea]     # 最終採用版本
    degraded: bool                         # 是否走降級路徑
```

---

## Hard Cap 與降級策略

### Cap = 2 次

- picker 原始 + 2 次 revision = 最多 3 個版本
- 一次 LLM reviewer call 約 3–5 秒
- 3 個版本已經是 15 秒延遲上限，再多對日報場景是過度投資

### 降級路徑（選項 B：保留最後版本 + 警示）

**比較：**

| 選項 | 優點 | 缺點 |
|------|------|------|
| A：回傳空 trade_watch + 降級 flag | 乾淨，不給用戶錯誤訊號 | 用戶看不到任何 trade idea，體驗差 |
| **B（採用）**：保留最後一版 + Telegram HTML 加警示 | 資訊不流失，用戶能自己判斷 | 需要 render 層支援警示樣式 |

### 實作

- Slim Schema 加 `_review_warnings: list[str]` 欄位
- Render 時以 `<i>⚠️ 審查未通過: {原因}</i>` 呈現

---

## BigQuery 觀測表

寫入 `reviewer_log`，用於日後調參與品質追蹤：

```sql
-- docs/SQL/reviewer_log.sql
CREATE TABLE `qsilicon.reviewer_log` (
  run_id STRING,
  profile STRING,                   -- 'full' | 'lite' | 'crypto-only'
  track STRING,                     -- 'crypto' | 'ai'
  revision_count INT64,
  python_fail_reasons ARRAY<STRING>,
  llm_fail_reasons ARRAY<STRING>,
  degraded BOOL,
  final_trade_count INT64,
  total_latency_ms INT64,
  created_at TIMESTAMP
);
```

---

## 給 Claude Code / Cursor 的實作 Prompt

```
Task: Implement reviewer_node and reflection loop in graph/graph_nodes.py

Context files to read first:
- graph/graph_state.py (current GraphState definition)
- graph/graph_crew.py (current graph wiring)
- schemas.py (TradeIdea and related Pydantic models)
- assets_universe.py (for ticker existence check)

Requirements:
1. Add new state fields: trade_candidates, review_issues, revision_count,
   review_history, trade_watch_final, degraded
2. Implement three nodes:
   - python_validate_node (deterministic, no LLM)
   - llm_reviewer_node (uses ChatOpenAI with Slim Schema ReviewerVerdict)
   - degrade_node (marks degraded=True, copies last candidates)
3. Add conditional edges:
   - python_validate: pass → llm_reviewer, fail → should_retry
   - llm_reviewer: pass → next stage, fail → should_retry
   - should_retry: retries<2 → trade_picker (with feedback), else degrade
4. Hard cap: revision_count max = 2
5. All nodes must handle exceptions and route to END on unexpected errors
6. Write reviewer_log entry to BQ via bigquery_writer.py (new function
   write_reviewer_log)

Constraints (from Q-Silicon red lines):
- Reviewer checks logic only, NEVER format
- Slim Schema for LLM output (only verdict + issues list, no full rewrite)
- Python validate runs FIRST, LLM reviewer only if Python passes
- Graph must always reach END, even on reviewer exceptions

Do not modify:
- schemas.py (extend in graph_state.py only)
- Existing CrewAI paths (this is LangGraph-only change)

Deliverables:
- graph/graph_nodes.py (new nodes added)
- graph/graph_crew.py (wiring updated)
- graph/graph_state.py (state fields added)
- bigquery_writer.py (write_reviewer_log added)
- docs/SQL/reviewer_log.sql (new)
- test_reviewer_loop.py (smoke + boundary tests)
```

---

## 歷史設計驗收清單（已對齊 2026-04-21 實作）

> 下表是原設計清單的現況對照，不再代表「全部未完成」。行為變更以
> [`CHANGELOG.md`](../../CHANGELOG.md) **2026-04-21**、[`test_reviewer_loop.py`](../../test_reviewer_loop.py)
> 與 [`scripts/verify_graph_gate.sh`](../../scripts/verify_graph_gate.sh) 為準。

| 原設計要求 | 現況 |
|------------|------|
| `python_validate_node` deterministic 檢查 | 已落地於 `graph/graph_nodes.py`；測試覆蓋 pass/fail、重複標的、空候選等路徑。 |
| `llm_reviewer_node` 使用 Slim Schema，不做完整 rewrite | 已落地；預設仍受 `GRAPH_LLM_TRADE_REVIEWER`／`GRAPH_LLM_TRADE_PICKER` 控制。 |
| Hard cap 在 `revision_count >= 2` 時強制 degrade | 已落地並由 `test_reviewer_loop.py` 覆蓋。 |
| 節點例外不繞過 Graph 出口契約 | 變更時須跑 `scripts/verify_graph_gate.sh`；Reviewer 不取代 `validate_report`。 |
| BQ `reviewer_log` 表可寫入 | `bigquery_writer.write_reviewer_log` 與 [`docs/SQL/reviewer_log.sql`](../SQL/reviewer_log.sql) 已入庫；`SKIP_BIGQUERY`／`REVIEWER_LOG_BQ` 控制寫入。 |
| smoke／boundary test | [`test_reviewer_loop.py`](../../test_reviewer_loop.py) 已覆蓋主要 reviewer loop 路徑。 |
| 降級警示 | 實作以 reviewer issue／degraded 狀態併入既有輸出路徑；仍不得繞過 Telegram HTML 白名單。 |

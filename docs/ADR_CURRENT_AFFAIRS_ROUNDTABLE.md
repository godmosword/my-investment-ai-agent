# ADR: 〔時事多觀點〕`current_affairs_roundtable`

## 狀態

已採納（2026-04-27）

## 背景

`modularization_plan.md` 將粗粒度 `BLOCK_IDS` 定為約 **18** 區塊；Phase 5 新增 **`current_affairs_roundtable`** 成為可選 **第 19** 邏輯區塊（僅 `full` 模板插入；`lite`／`crypto-only` 不含）。

## 決策

1. **區塊歸屬**：`current_affairs_roundtable` 列於 `brief_profiles.BLOCK_IDS`／`BLOCK_REGISTRY`，但 **不** 寫入 `CryptoSection`／`AISection`，而是 **`DailyBriefReport.current_affairs_roundtable`**（Optional），避免雙 Crew schema 分叉。
2. **產出（5b）**：單一 **無 tools** Crew task（[`current_affairs_crew.py`](../current_affairs_crew.py)），輸入為 **已組裝之** `CryptoSection`／`AISection` 的儀表板摘錄 + 新聞標題；失敗回 `None`，**不阻擋**主報告。
3. **CrewAI vs LangGraph**：兩路徑均在 **`main._run_pipeline_once`** 於雙軌完成後、**`assemble_daily_brief_report` 之前** 觸發（與 `source_observability_lines` 並行），避免改 `graph/` 狀態機主結構。
4. **錨點白名單**：LLM 填寫之 `dashboard_anchors` 會與 **實際 `MetricLine.label`** merge，使 `evidence_anchor` 可通過 Pydantic 驗證；仍須遵守「不捏造儀表外數字」之 crew 提示詞紅線。
5. **動態組版（4d 後續）**：`BRIEF_DYNAMIC_RENDER=1` 且 `BRIEF_LAYOUT_FILE` 造成 **`profile_block_ids("full")` ≠ 內建 `PROFILES["full"]`** 時，[`report_render.render_telegram_daily_brief`](../report_render.py) 走 macro 串接；**預設關閉** 以維持 **Phase 0 byte-identical**。

## 後果

- 啟用 `BRIEF_CURRENT_AFFAIRS=1` 時多一次 **nano** LLM 呼叫（成本／延遲）；可改 env 或關閉。
- `STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1` 建議搭配 **`main.py` 已傳 `structured_report=`** 至 `validate_report`，否則僅 HTML 層檢查。

## 替代方案（未採）

- 每 voice 一 Agent：成本與 ThreadPool 複雜度上升（見 `modularization_plan` 附錄 B）。
- 將 roundtable 嵌進 `CryptoSection`：迫使 LangGraph `CryptoSection.model_validate` 與 crew schema 同步擴充，侵入面較大。

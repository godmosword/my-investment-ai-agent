# Staging smoke：〔時事多觀點〕（`BRIEF_CURRENT_AFFAIRS=1`）

對齊 [`visualization_plan.md`](architecture/visualization_plan.md) §3 與 TODOS **隊列 27** — 在 **staging** 驗證 roundtable 管線、HTML Gate、與 PWA／Telegram 結構化檢視一致；**不在 CI 自動執行**（需真實 LLM／Telegram／或手動對照）。

## 前置

- Staging 後端與日報管線可跑完一輪 `full`。
- `BRIEF_CURRENT_AFFAIRS=1`；可選 `STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE=1` 做嚴檢。
- 若要比對結構化 JSON：`BRIEF_CURRENT_AFFAIRS_JSON`（單行）僅供測試覆寫，勿用於 production。

## 步驟

1. 觸發一輪日報（與平時相同入口）。
2. **Telegram**：確認〔時事多觀點〕區塊出現、HTML 白名單標籤正確、無未宣告之 `[DATA_MISSING:*]`（除非上游真缺）。
3. **PWA**（`/briefs` 或 `/terminal`）：開啟同日結構化報告；對照 `current_affairs_roundtable` 與 Telegram 敘事一致。
4. （可選）`BRIEF_DYNAMIC_RENDER=1` 時確認動態渲染與 Gate 無誤擋。

## 完成標準

- 至少一則 staging 日報：Telegram 與 PWA 在 roundtable 區塊 **語意一致**；`validate_report`／`report_html_gates` 無誤擋。
- 結果請在 [`TODOS.md`](../TODOS.md) 隊列 **27** 或同步狀態行註記日期（與 [`CHANGELOG.md`](../CHANGELOG.md) `### Ops` 可選）。

## 相關

- [`ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)
- [`current_affairs_crew.py`](../current_affairs_crew.py)、[`main.py`](../main.py) ThreadPool 並行與 `structured_report` 注入

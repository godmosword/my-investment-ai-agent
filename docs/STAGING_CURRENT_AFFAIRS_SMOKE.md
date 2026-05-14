# Staging smoke：〔時事多觀點〕（`BRIEF_CURRENT_AFFAIRS=1`）

> **Phase 1（隊列 27／日報可信）**：本檔為 **repo 側可交付的執行稿與回填模板**；實際 smoke **須在 staging 由人類（或經授權的排程）觸發**，**不在 CI 自動執行**（需真實 LLM／Telegram／或手動對照）。架構目錄判讀總規則見 [`architecture/Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) **§0** 與其下 **Phase 0**；視覺化 backlog 對照見 [`architecture/visualization_plan.md`](architecture/visualization_plan.md) §3。

對齊 [`architecture/visualization_plan.md`](architecture/visualization_plan.md) §3 與 [`TODOS.md`](../TODOS.md) **隊列 27**。

## 一句話目標

在 **staging**、`BRIEF_CURRENT_AFFAIRS=1` 下，驗證 roundtable 管線、HTML Gate、與 **Telegram vs PWA 結構化** 敘事一致；`validate_report`／`report_html_gates` **無誤擋**。

## 前置核對表（請逐項填值或勾選）

| 欄位 | 例／說明 |
|------|----------|
| **報告日 `DATE`** | `YYYY-MM-DD`（與 Telegram／PWA 對照同一日） |
| **後端版本** | image tag、deploy commit、或 `git rev-parse --short HEAD` |
| **`REPORT_PROFILE`** | staging 建議先跑 **`full`** 一輪再視需要切 `lite` |
| **`BRIEF_CURRENT_AFFAIRS`** | **`1`** |
| **`STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE`** | `0` 或 `1`（嚴檢；首次建議 `0` 再升） |
| **`BRIEF_DYNAMIC_RENDER`** | `0`／`1`（若本輪要驗動態組版與 Gate） |
| **`BRIEF_CURRENT_AFFAIRS_JSON`** | 僅**測試覆寫**時填；**production 勿用** |
| **PWA 入口** | 與團隊慣例一致：`/briefs`、`/terminal`（redirect）、或 Insights 結構化檢視 |

## 步驟

1. 觸發一輪日報（與平時相同入口）。
2. **Telegram**：確認〔時事多觀點〕／roundtable 區塊出現、HTML **白名單**標籤正確、無未宣告之 `[DATA_MISSING:*]`（除非上游真缺）。建議記 **message 連結或 id** 以利稽核。
3. **PWA**：開啟**同日**結構化報告（上表入口）；對照 `current_affairs_roundtable` 與 Telegram **語意一致**（不必字句級相同，但事實與立場不可打架）。
4. （可選）`BRIEF_DYNAMIC_RENDER=1` 時確認動態渲染與 Gate **無誤擋**。

## 完成標準

- 至少一則 staging 日報：Telegram 與 PWA 在 roundtable 區塊 **語意一致**；`validate_report`／`report_html_gates` 無誤擋。
- 依下方「回填到哪裡」更新 **`TODOS.md`**（必填其一）；可選 **`CHANGELOG.md`** `### Ops`。

## 回填到哪裡（關帳）

完成後 **至少擇一**（建議 1+2）：

1. **[`TODOS.md`](../TODOS.md)「下一批隊列」第 27 條**：在該條末尾 **括號註記** 一次結果（見下方剪貼範本）。
2. **[`TODOS.md`](../TODOS.md) 頂部「同步狀態」**：新增一行 **日期 + PASS/FAIL + 操作者**（與隊列 27 對齊即可）。
3. （可選）[`CHANGELOG.md`](../CHANGELOG.md) **`### Ops`**：同日一行（**僅在确有 staging 結果時**）。

### 剪貼範本（貼在隊列 27 該行末尾）

```text
（staging smoke 2026-05-20: PASS — alice；PROFILE=full；STRICT_CA_RTG=0）
```

將 `2026-05-20`／`alice`／旗標改為實際值；若 FAIL 請寫 **`FAIL`** 並附一句原因（例如 Gate 名稱或 `[DATA_MISSING:…]`）。

## （可選）同日驗 Reviewer rollout（隊列 35）

若該 staging 亦啟用 Graph reviewer，可**併行**執行 [`REVIEWER_PRODUCTION_ROLLOUT.md`](REVIEWER_PRODUCTION_ROLLOUT.md) 與 [`scripts/verify_reviewer_rollout_env.py`](../scripts/verify_reviewer_rollout_env.py)（可選 `--probe-api-base`）。**不作為**本 smoke 的硬性前置；兩條隊列可分開關帳。

## 相關

- [`ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)
- [`current_affairs_crew.py`](../current_affairs_crew.py)、[`main.py`](../main.py) ThreadPool 並行與 `structured_report` 注入

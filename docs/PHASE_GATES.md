# Phase Gates

本文件定義 Lean Architecture Reset 的分期進出條件（entry/exit）、回滾條件與責任界線。

## 全域規則

- 每個 phase 單獨 branch 與 PR，不可跨 phase 混改。
- 單一 PR 檔案觸及預算：`<= 8` 檔；新增模組 `<= 2`。
- 任一 phase 發生輸出契約退化（Telegram 格式、QSREC、validate gate）即回滾到上一個 phase tag。

## Phase 1 — Document & Policy Freeze

**Entry**
- 已有核准設計稿。
- 指定 owner 與時程（2-3 天時間盒）。

**Exit**
- 權威主文固定：`README.md` + `CLAUDE.md`。
- 例外清單固定：`.cursorrules`、`AGENTS.md`（以 `CLAUDE.md` 為引用源）。
- 產出 `docs/LEAN_BASELINE.md`（耗時、CI 時間、文檔分類）。

**Rollback trigger**
- 文檔變更造成執行流程敘述與實際代碼矛盾且無法在同 PR 修正。

## Phase 2 — Core Extraction

**Entry**
- Phase 1 完成且 baseline 有簽核。
- 已定義抽離清單（至少 3 個重複規則片段）。

**Exit**
- 重複規則抽離至 `core/policy` 或等價集中模組。
- Prompt contract tests 全綠。
- 等價性測試（抽離前後）全綠。

**Rollback trigger**
- 抽離後 `validate_report` 結果與 baseline 出現不可接受偏差。

## Phase 3 — Pipeline Rewire

**Entry**
- Phase 2 全綠，並建立 dual-run compare（僅記錄差異）。
- 本 repo 已內建：`REPORT_COMPARE_MODE=1` 時，每次 `validate_report` 後會比對 `_validate_report_candidate`（目前與 legacy 等價；重構後替換候選實作）。

**Exit**
- `main.py` 以 orchestrator 為主，核心規則由抽離模組提供。
- dual-run compare 連續樣本差異在可接受範圍。

**Rollback trigger**
- 新舊路徑差異導致輸出契約退化或 hard fail 率上升。

## Phase 4 — CI / Deploy Fast Path

**Entry**
- 已有 smoke 測試集合。

**Exit**
- PR：`ruff + smoke`。
- main/deploy：full pytest。
- 兩條路徑結果可審計，且主幹安全性不下降。

**Rollback trigger**
- PR 快速路徑造成主幹回歸率上升或漏攔截關鍵問題。

## Phase 5 — Evidence & Metrics

**Entry**
- 前四 phase 穩定。

**Exit**
- 產出可讀報表：token、耗時、失敗率（僅白名單欄位，禁存 prompt 原文）。
- 形成 baseline vs current 對照。

**Rollback trigger**
- 指標蒐集引入敏感資料或對主流程延遲造成顯著負擔。

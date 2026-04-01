# OSS 候選週報（Scout 流程 · Direction 2B）

本目錄存放 **人類審閱用** 的開源候選清單，**不**代表已合併至主線。

## 每週產出（建議檔名）

- `YYYY-MM-DD-candidates.json`：GitHub Search 結果（機讀）  
- `YYYY-MM-DD-digest.json`：各 repo 之 README 摘錄 + metadata（機讀）  
- `YYYY-MM-DD-revision-plan-draft.md`：研究稿（人讀；Jinja 模板 [`templates/oss_weekly_plan.md.j2`](../../templates/oss_weekly_plan.md.j2)）  
- **`TODOS.md`** 內 **「OSS Scout 週報（自動）」**：每週插入**研究稿／digest／candidates 連結**、**精簡摘要表**（Repo｜適配｜★）與**短勾選**（僅 ``repo`` 名；`fit_rationale` 等長欄位只在研究稿與 JSON）（**是否實作由維護者決定**）

## 一鍵管線（本機或 CI）

```bash
# 需 GITHUB_TOKEN（提高 Search API 額度）
export GITHUB_TOKEN=...
# 可選：SCOUT_GITHUB_QUERY、SCOUT_SORT（stars|forks|updated|…）、SCOUT_PER_PAGE
python scripts/oss_weekly_pipeline.py

# 僅產檔、不改 TODOS.md：
OSS_WEEKLY_SKIP_TODOS=1 python scripts/oss_weekly_pipeline.py
```

分步：

1. [`scripts/oss_scout_candidates.py`](../../scripts/oss_scout_candidates.py) — `--out-json docs/oss_candidates/DATE-candidates.json`  
2. [`scripts/oss_repo_digest.py`](../../scripts/oss_repo_digest.py) — 餵入上一步 JSON，`--out-json …-digest.json`  
3. 通常直接使用 **`oss_weekly_pipeline.py`** 即可。

**排程**：[`.github/workflows/weekly-scout.yml`](../../.github/workflows/weekly-scout.yml) — 每週一 UTC 06:00 + `workflow_dispatch`；上傳 artifact；有變更時 **bot commit push**（`contents: write`）。

## 威脅建模檢查清單（合併 PR 前必做）

1. **License** 與本專案 MIT/Apache 等是否相容；是否要求網路回傳 telemetry。  
2. **維護度**：最後提交、issue 回應、是否 archived。  
3. **依賴**：transitive deps 是否引入未審核二進位或 post-install 腳本。  
4. **與資料紅線**：套件是否會在執行期發起未預期外連（與 `.cursorrules` 對齊）。

## 合併流程

候選 → spike 分支 → `ruff` + `pytest -m smoke` → **人類 PR review** → merge。

自動化 bot **不得**在無 `environment: production` 審批時觸發 Cloud Run 部署（見 `.github/workflows/deploy.yml`）。**週報腳本不得自動修改 `requirements.txt` 或合併第三方程式碼**。

## 適配度說明

[`scripts/oss_suitability.py`](../../scripts/oss_suitability.py) 以 stars、活躍度、license、README 長度與關鍵字做 **1–5 啟發式評分**，**非 LLM**，僅供排程；高分配對仍需人工判斷業務相關性。

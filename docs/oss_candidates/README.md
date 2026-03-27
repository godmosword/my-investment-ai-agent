# OSS 候選週報（Scout 流程 · Direction 2B）

本目錄存放 **人類審閱用** 的開源候選清單，**不**代表已合併至主線。

## 每週產出（建議檔名）

- `YYYY-MM-DD-candidates.md`：人讀摘要（repo、用途、風險標籤）  
- `YYYY-MM-DD-candidates.json`：機讀（名稱、license、stars、last_push、score、notes）

## 威脅建模檢查清單（合併 PR 前必做）

1. **License** 與本專案 MIT/Apache 等是否相容；是否要求網路回傳 telemetry。  
2. **維護度**：最後提交、issue 回應、是否 archived。  
3. **依賴**：transitive deps 是否引入未審核二進位或 post-install 腳本。  
4. **與資料紅線**：套件是否會在執行期發起未預期外連（與 `.cursorrules` 對齊）。

## 合併流程

候選 → spike 分支 → `ruff` + `pytest -m smoke` → **人類 PR review** → merge。

自動化 bot **不得**在無 `environment: production` 審批時觸發 Cloud Run 部署（見 `.github/workflows/deploy.yml`）。

## 自動化（可選）

可另建腳本呼叫 GitHub Search API 產生上述 JSON；本 repo 預設以 **人工維護** 為主，避免未審查依賴進主線。

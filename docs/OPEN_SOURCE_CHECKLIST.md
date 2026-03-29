# 開源前檢查清單（機密與合規）

本檔不含任何金鑰或 token，僅列**必做步驟**與**建議工具**。開源後請仍定期重跑秘密掃描。

---

## 1. 歷史與工作區秘密掃描（必做）

在專案根目錄執行（需已安裝 [gitleaks](https://github.com/gitleaks/gitleaks)）：

```bash
gitleaks detect --source . -v
```

- **須為 0 findings** 才可視為「掃描乾淨」；若有命中，先處理再公開倉庫。
- 可另用 [TruffleHog](https://github.com/trufflesecurity/trufflehog) 對遠端做二次驗證：

```bash
trufflehog git file://. --no-update
```

歷史中的外洩有時驗證器無法線上確認；僅用 `--only-verified` 可能漏報，清歷史後請以 **第 3.3 節** 的指令再驗證。

**本倉庫狀態（供維護者內部追蹤）**

- 目前 **HEAD** 之 [`.env.example`](../.env.example) 為占位字串（`your_*_here`），與 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 意圖一致。
- **Git 提交歷史**：已以 `git filter-repo` 自**全分支**移除舊版 `.env.example` 後再補回乾淨範本，並已 **force-push** 至 `origin`（見 [`CHANGELOG.md`](../CHANGELOG.md) Security 條目）。維護者以 `gitleaks detect --source . -c .gitleaks.toml` 掃描提交歷史應為 **0 findings**；`trufflehog git file://.` 亦應為 **0**。
- **仍須留意**：在 **force-push 之前**產生的 **fork／鏡像／他人本機舊 clone**，其物件庫仍可能保留舊 blob；上游無法代為刪除，僅能請對方更新或刪 fork。
- **金鑰輪替**：曾出現在舊歷史中的金鑰仍應視風險已發生而 **輪替**（維護者已輪替之 provider 亦建議保留在 Runbook 紀錄）。

---

## 2. 工作區與 `.gitignore`（必做）

| 項目 | 動作 |
|------|------|
| `.env` | 確認**未**被 `git add`；僅留在本機。本 repo 已於 [`.gitignore`](../.gitignore) 忽略 `.env`。 |
| `*.json` 服務帳戶 | 已忽略通用 `*.json` 與 `*-credentials.json` 等；開源前執行 `git ls-files '*.json'` 確認無誤提交。 |
| `.qsilicon/scratchpad/` | 已忽略；可能含工具／報告片段，勿強制加入版控。 |
| `.claude/settings.json` | 若含本機路徑或個人設定，開源前請人工檢視；可改為範例檔或移除敏感欄位。 |

---

## 2.1 本機清場清單（開源／打包／換機前）

目的：避免把**本機才有的檔案**一併打包、上傳或誤提交。

- [ ] **`.env`**：僅本機；確認 `git status` 未出現；`git check-ignore -v .env` 應顯示被忽略。
- [ ] **`.env.*` 備份**：`.env.backup`、`.env.local`、下載資料夾內複本、雲碟同步目錄內複本。
- [ ] **第二份 clone／worktree**：其他路徑是否仍有舊 `.env`。
- [ ] **Shell**：`~/.zshrc`、`~/.zprofile` 是否 `export` 過金鑰（開源截圖／錄影前暫時註解）。
- [ ] **GCP 本機檔**：`GOOGLE_APPLICATION_CREDENTIALS`、`~/.config/gcloud/sa-key.json` 等，勿複製進 repo。
- [ ] **`.qsilicon/scratchpad/`、`.qsilicon/last_gate_failure/`**：若曾開啟，內文可能含工具回傳片段；打包 zip 前排除整個 `.qsilicon/`。
- [ ] **`data-verification-ui/node_modules/`**：一般不入庫；若本地存在，`gitleaks --no-git` 可能掃到依賴內測試字串（誤報）；開源以 **遠端僅追蹤原始碼**為準。
- [ ] **`.claude/` 下大檔／worktree／vendor 技能**：若目錄極大或含二進位，開源前決定是否整包排除（見 [`.gitignore`](../.gitignore) 規則）。
- [ ] **剪貼簿／截圖／錄屏**：發 PR、寫 README、錄 demo 前確認畫面無 terminal 內金鑰。

---

## 3. 歷史中的機密：輪替與清除（強烈建議）

若曾將真實金鑰寫進**已推送**的 commit：

1. **先輪替**所有曾出現在歷史中的供應商金鑰（**輪替優先於「只刪檔案」**）。  
   你已更換 XAI／OpenAI／Gemini／Telegram Bot 時，仍請核對：**OpenRouter、CoinGlass、CryptoQuant、CryptoPanic、NewsAPI、GNews、FMP、RapidAPI、Apify、FRED、Financial Datasets** 等是否也曾出現在舊版 `.env.example` 或他處；若有，一併輪替。
2. **再改寫 Git 歷史**（會改寫所有 commit SHA，需協調協作者 **全部重新 clone**）。
3. 公開後在 GitHub 啟用 **Secret scanning**、**Push protection**（依方案可用性）。

### 3.1 推薦做法：用 `git-filter-repo` 從歷史移除 `.env.example` 再補回乾淨版

適用：舊 commit 的 `.env.example` 曾含真值，**目前 HEAD 已是占位符**。  
工具：[git-filter-repo](https://github.com/newren/git-filter-repo)（優先於已進入維護模式的 filter-branch）。

**本倉庫：此流程已由維護者執行完畢**（含 `git push --force --all`／`--tags`）。若你從 `origin` **新 clone**，取得的是淨化後歷史；若你手上是 **force-push 前的舊目錄**，請**刪除後重新 clone**，勿在舊倉上 merge。其他 fork 是否已更新，請各 fork 擁有者自行處理。

**事前（其他專案複用本節時使用）**

- [ ] 通知所有協作者：即將 **force-push**，完成後請 **刪除舊 clone 並重新 clone**（勿在舊倉上 merge）。
- [ ] **備份**：`git clone --mirror <遠端URL> investment-ai-agent-backup.git`
- [ ] 將**目前乾淨**的 `.env.example` 複製到 repo **外**，例如：  
  `cp .env.example /tmp/.env.example.sanitized`

**執行（在專案根目錄）**

```bash
# 安裝（擇一）
# brew install git-filter-repo
# pip install git-filter-repo

# 從「整段歷史」刪除該檔（所有 commit 內的 .env.example 都會消失）
git filter-repo --path .env.example --invert-paths --force
```

`git filter-repo` 預設會**移除 `origin` remote**（防誤推）。接下來：

```bash
# 把乾淨範本放回工作區
cp /tmp/.env.example.sanitized .env.example
git add .env.example
git commit -m "docs: restore .env.example with placeholders only"

# 接回遠端（URL 改成你的）
git remote add origin <你的_GitHub_repo_URL>
git push --force --all origin
git push --force --tags origin
```

**若曾誤提交 `.env`（整檔）**：可改為 `--path .env --invert-paths`（或併用多個 `--path`），並確認之後永遠不要將 `.env` 加入版控。

### 3.2 替代：`--replace-text`（檔名仍保留，只洗掉字串）

若你希望**保留歷史上「有 .env.example 這個檔」的紀錄**，但把特定字串換成占位符：

1. 在本機建立 **`replacements.txt`（不要 commit）**，格式見 [git-filter-repo replace-text](https://htmlpreview.github.io/?https://github.com/newren/git-filter-repo/blob/docs/html/git-filter-repo.html#_replace_text)（`literal:舊字串==>新字串` 或 `regex:...==>...`）。  
2. **舊字串內容即為機密**，檔案僅能留在本機或用完即刪。  
3. 執行：`git filter-repo --replace-text replacements.txt --force`  
4. 同樣需 **force-push** 並協調協作者。

### 3.3 清歷史後驗證

```bash
# 應為 0 findings（掃描「已提交」歷史；使用本 repo 的 .gitleaks.toml）
gitleaks detect --source . -c .gitleaks.toml -v

# 二次驗證（JSON 行輸出；勿將含 Raw 的輸出貼進公開 issue）
trufflehog git file://. --no-update
```

說明：若你本機仍有 `.env`，執行 `gitleaks detect --source . --no-git` **仍可能**命中本機檔案，屬預期；**開源判準以「遠端 clone 無 .env」且 **歷史掃描為 0** 為主**。

### 3.4 無法協調 force-push 時

可新建 **乾淨倉庫**（只匯入目前樹狀目錄、不帶歷史），或請 GitHub Support／企業版流程協助（視方案而定）。

---

## 4. GitHub 設定（建議）

- **Branch protection**：`main` 要求 PR、required checks（如 `CI — Lint & Test`）。
- **Dependabot** 或類似依賴更新（可選）。
- **License**：根目錄放置 `LICENSE`（MIT/Apache-2.0 等）並在 `README` 註明。

---

## 5. 文件與範本（建議）

- 對外僅保留 **`ENV_TEMPLATE.txt`** / **`.env.example`** 之**占位符**；勿在 issue、Wiki、截圖中貼真鑰。
- `README` 中專案 ID、Telegram、GCP 等僅描述**變數名稱**，不給實值。

---

## 6. 開源後維護（建議）

- 每季或重大改版前重跑：`gitleaks detect --source . -v`。
- 新協作者 onboarding：強調 `.env` 不入庫、PR 前本地跑掃描可選。

---

## 7. 參考連結

- [GitHub — Secret scanning](https://docs.github.com/en/code-security/secret-scanning)
- [gitleaks](https://github.com/gitleaks/gitleaks)
- [TruffleHog](https://github.com/trufflesecurity/trufflehog)

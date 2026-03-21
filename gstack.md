# gstack 使用手冊

## 什麼是 gstack

gstack 是 Y Combinator 總裁 Garry Tan 開源的 AI 技能集合（[GitHub](https://github.com/garrytan/gstack)），把 Cursor / Claude Code 變成一支虛擬工程團隊。所有功能都透過 **斜線指令（slash command）** 在 AI 聊天視窗內呼叫，不是終端機 CLI。

## 安裝

```bash
git clone https://github.com/garrytan/gstack.git ~/gstack
cd ~/gstack && ./setup --host auto
```

安裝後會在 `~/.claude/skills/` 建立 symlink；Cursor 會自動掃描。若要讓專案內其他人也能用，可在專案根目錄建立 `.agents/skills/gstack` 指向同一份。

前置需求：**Git**、**Bun**（v1.0+）。

## 在哪裡使用

在 Cursor 的 **Chat / Agent / Composer** 視窗直接輸入斜線指令，例如 `/review`。不要在終端機輸入。

## 驗證安裝

- `~/.claude/skills/` 下有 `browse`、`review`、`ship` 等 symlink
- `~/.claude/skills/gstack/browse/dist/browse` 二進位檔存在
- 對話框輸入 `/browse` 不會報錯

> `command -v gstack` 找不到是正常的，gstack 不會把指令寫入 PATH。

---

## 推薦工作流程

```
構思 → 規劃 → 開發 → 審查 → 測試 → 發版 → 回顧
```

| 階段 | 建議指令 |
|------|---------|
| 構思 | `/office-hours` |
| 規劃 | `/plan-ceo-review` → `/plan-eng-review` → `/plan-design-review` |
| 開發 | `/careful` · `/guard` · `/freeze`（安全護欄） |
| 審查 | `/review` → `/design-review` |
| 測試 | `/qa` 或 `/qa-only` · `/browse` |
| 發版 | `/ship` → `/document-release` |
| 回顧 | `/retro` |

---

## 專家角色（15 個）

### /office-hours — 產品辦公室時間

把你的想法丟給 AI「產品顧問」，它會重新框架問題、寫設計文件、拆出可交付切片。適合什麼都還沒定的階段。

```
/office-hours
我想在日報管線加入「歷史績效追蹤」，讓用戶看到過去建議的命中率。
請幫我釐清：核心價值、MVP 範圍、需要哪些數據源。
```

### /plan-ceo-review — CEO 視角審方案

用創辦人視角挑戰你的方案：範圍該擴大還是縮小？有沒有「10 倍好」的替代路線？

```
/plan-ceo-review
方案：在 main.py 用雙 pipeline 隔離 Crypto / AI 執行緒。
請挑戰假設：這值得做嗎？有更小的槓桿點嗎？
```

### /plan-eng-review — 工程經理鎖架構

鎖定架構、畫資料流圖、列測試矩陣、抓邊界條件。大改 `crew.py` / `tools.py` / BigQuery 前先跑一輪。

```
/plan-eng-review
要在 tools.py 新增一個 CryptoQuant tool，必須有 _get_cache/_set_cache。
請輸出：資料流、快取 key 設計、ThreadPool 安全注意事項、測試清單。
```

### /plan-design-review — 設計師審需求

從使用者體驗角度檢視：資訊層級、手機可讀性、互動邏輯。適合改 `dashboard.py` 前。

```
/plan-design-review
請 review Streamlit 戰情室的版面：手機寬度下是否堪用？機構交易員最常看的指標有沒有被埋太深？
```

### /design-consultation — 設計諮詢

針對特定 UI 元件或流程做一對一設計諮詢，比 `/plan-design-review` 更聚焦。

```
/design-consultation
Telegram 戰報的 HTML 排版：用 <code> 對齊數據 vs 用 emoji 區隔，哪種在手機上更好讀？請給 before/after 範例。
```

### /review — PR 級結構審查

對 branch diff 做合併前檢查：SQL 安全、機密洩漏、LLM 信任邊界、條件式副作用。

```
/review
請針對目前 branch vs main 的 diff 做 review，重點查機密是否誤提交、
LLM 是否可能輸出未驗證數據。列出 P0 / P1 / P2。
```

### /investigate — 深度調查

對疑難雜症做根因分析，適合「不知道壞在哪裡」的情境。

```
/investigate
main.py 跑到第 3 輪 retry 時偶爾卡住不回傳。
請查 ThreadPoolExecutor 的 Future 是否有 hang、timeout 設定是否足夠。
```

### /design-review — 成品設計審查

程式碼寫完後、從設計面檢查實際產出是否符合規格。與 `/plan-design-review`（規劃階段）互補。

```
/design-review
dashboard.py 已更新完畢。請檢查實際 Streamlit 元件是否與先前 /plan-design-review 的建議一致，
抓出漏改的地方。
```

### /qa — 完整品質測試

用真實無頭 Chromium 開啟你的 staging 網址，走完主要流程、抓 console 錯誤、找破版，**並自動修復發現的 bug**。

```
/qa https://my-staging.example.com
請走一次：首頁 → 戰情室 → 展開 BTC widget → 重新整理。
列出 bug 清單並嘗試修復。
```

### /qa-only — 只測不修

和 `/qa` 一樣做瀏覽器測試，但**只回報問題，不自動改 code**。適合只想拿測試報告的情境。

```
/qa-only https://my-staging.example.com
請做探索式測試，給我一份純 bug 清單（含重現步驟與截圖），不要改任何檔案。
```

### /ship — 發版流程

自動 sync main → 跑測試 → review diff → 更新 CHANGELOG → commit → push → 開 PR。

```
/ship
目標：把 feature/hedge-fund-brief 合併進 main。
本 repo 沒有 pytest，請改跑 ruff check 做為驗證步驟。
```

### /document-release — 撰寫發版文件

根據 diff / CHANGELOG 產出面向用戶的 release note。

```
/document-release
請根據最近 5 個 commit 的 diff，寫一份簡短的 release note（中文），
重點說明使用者會感受到的變化。
```

### /retro — 週回顧

分析 commit 歷史、工作模式、程式碼品質指標，產出每週回顧報告。

```
/retro
過去一週主要改了 main.py / crew.py / tools.py。
請做 retro：什麼做得好、重複踩的雷、下週 3 個可執行行動。
```

### /browse — 無頭瀏覽器

用 Playwright Chromium 開任何網頁：導航、點擊、填表、截圖、讀 DOM、查 console log。約 100ms 一條命令。

```
/browse https://example.com
請截圖首頁、檢查有無 console error、回報頁面載入時間。
```

### /setup-browser-cookies — 設定瀏覽器 Cookie

為 `/browse` 和 `/qa` 預先注入認證 cookie，讓無頭瀏覽器能存取需要登入的頁面。

```
/setup-browser-cookies
我需要測試一個需要登入的 staging 環境，請幫我設定 session cookie。
```

---

## 強力工具（6 個）

### /codex — Codex 模式

切換到 Codex 風格的工作模式。

```
/codex
請用 Codex 模式幫我重構 tools.py 裡的快取邏輯。
```

### /careful — 小心模式

啟動護欄：限制 AI 只能動指定檔案，其餘必須先問你。防止大範圍誤改。

```
/careful
接下來只允許修改 test_report_output_validator.py，
不要動 .env、不要改部署 workflow。要動別的先問我。
```

### /freeze — 凍結檔案

完全鎖定指定檔案或目錄，任何寫入操作都會被攔截。

```
/freeze
請凍結 main.py 和 .github/workflows/，這輪只改 crew.py。
```

### /unfreeze — 解除凍結

解除先前 `/freeze` 設定的鎖定。

```
/unfreeze
crew.py 改完了，請解除 main.py 的凍結，我要同步更新。
```

### /guard — 守衛模式

持續監控：每次改動前自動檢查是否觸碰了不該碰的區域。比 `/careful` 更主動。

```
/guard
監控 .env 和所有 *credentials* 檔案，只要有任何讀寫意圖就立刻警告我。
```

### /gstack-upgrade — 更新 gstack

檢查並安裝 gstack 最新版本。

```
/gstack-upgrade
請檢查是否有新版並完成更新。
```

---

## 本專案建議

| 情境 | 指令 |
|------|------|
| 改 `crew.py` 的 Agent / Task 架構 | `/plan-eng-review` → 開發 → `/review` |
| 改 `dashboard.py` 的 Streamlit 版面 | `/plan-design-review` → 開發 → `/design-review` |
| 改 `tools.py` 新增外部 API tool | `/plan-eng-review`（含快取設計） → `/careful`（鎖其他檔） → 開發 → `/review` |
| Telegram 戰報排版調整 | `/design-consultation` → 開發 → `/review` |
| 部署後驗證 Streamlit | `/qa https://...` 或 `/browse https://...` |
| 週末收尾 | `/retro` |

## 故障排除

```bash
cd ~/.claude/skills/gstack && ./setup
```

若仍無法觸發：

1. 重新開啟 Cursor
2. 確認 `~/.claude/skills/` 有 `browse`、`review` 等 symlink
3. 確認 `browse/dist/browse` 二進位檔存在
4. 執行 `/gstack-upgrade` 確保版本最新

# last30days-skill 與 Q-Silicon（可用性、Pilot、信任邊界、併入策略）

上游專案：[mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill)（MIT License）。本檔為本 repo 的**落地註記**；skill **不**作為 submodule／必要相依。

---

## 1. 結論（能不能用）

- **能用**：以 Claude Code plugin、ClawHub，或手動 `git clone … ~/.claude/skills/last30days` 安裝即可；與本 repo 目錄無耦合。
- **不能**在未設防下當 **`python main.py` 日報主路資料源**：skill 聚合 Reddit／X／YouTube／HN／Polymarket／web 等**社群與敘事**訊號，與 [.cursorrules](../../.cursorrules) **無菌管線**（客觀報價／指標須由 Python 工具注入、主路徑不以 X 為新聞依賴）的**信任邊界不同**。
- **併入本 repo 的預設決策（產品／工程）**：**路徑 A + B**（見 §6）。路徑 C／D 需另開 ADR 與明確授權。

---

## 2. 安裝（官方摘要）

```bash
# Claude Code（推薦）
/plugin marketplace add mvanhorn/last30days-skill
/plugin install last30days@last30days-skill

# 或手動
git clone https://github.com/mvanhorn/last30days-skill.git ~/.claude/skills/last30days
mkdir -p ~/.config/last30days
# 依上游 README 建立 ~/.config/last30days/.env（chmod 600）
```

- 專案級覆寫可放 **`.claude/last30days.env`**（repo 根目錄；**勿提交金鑰**）。
- 完整環境變數與 X／ScrapeCreators 說明見上游 [README](https://github.com/mvanhorn/last30days-skill/blob/main/README.md)。

---

## 3. Pilot 紀錄（本機／CI 環境快照）

以下在 **clone 上游至 `/tmp/last30days-skill`** 的環境執行，供團隊對照；**非**你方生產金鑰狀態。

### 3.1 `python3 scripts/last30days.py --diagnose`

範例輸出（節錄）：

- `openai`: 視環境而異（本機若有 `OPENAI_API_KEY` 或 Codex login 則為 true）。
- `reddit_public`: true（公開 Reddit JSON 等路徑可用性由腳本判定）。
- `bird_installed`: true；`bird_authenticated`: 無 cookie 時 false。
- `hackernews` / `polymarket`: 通常 true（無金鑰公開 API）。
- `youtube`: 需 `yt-dlp` 在 PATH。
- `tiktok` / `instagram`: 通常需 `SCRAPECREATORS_API_KEY`（上游 v2.9 預設路徑）。

### 3.2 `--mock --quick` 煙霧

- **Wall time**：約 **25–30s**（含狀態面板與 fixture 路徑；實際完整研究上游標稱約 **2–8 分鐘**，`--quick`／`--deep` 可調）。
- **本環境備註**：HN 曾出現 `SSL: CERTIFICATE_VERIFY_FAILED`（python.org 版 Python 常見；上游 README 建議跑 Install Certificates 或改用 Homebrew Python）。

### 3.3 建議你方補跑的 2–3 個主題（含金鑰後）

在具完整 `.env` 的機器上執行，並把延遲／費用觀感記入內部筆記即可：

1. `CrewAI daily brief validation gate`
2. `institutional crypto research telegram brief`
3. `NVDA data center capex narrative last 30 days`

指令範例：

```bash
python3 scripts/last30days.py --quick --emit md "institutional crypto research workflow"
```

---

## 4. 信任邊界：last30days 輸出 ↔ Q-Silicon 戰報

對照 [docs/DAILY_BRIEF_V2.md](../DAILY_BRIEF_V2.md) 四區塊與 [`report_html_gates.py`](../../report_html_gates.py) 精神。

| last30days 產出性質 | 可如何使用 | **禁止** |
|---------------------|------------|----------|
| 社群敘事、趨勢、引用連結 | **人工**改寫後參考區塊②b「主題式觀點摘要」語氣；`TODOS.md`／產品研究 | 當作儀表板數字、進出場價、RSI／VIX／資金費率等**唯一**依據 |
| Polymarket／「賠率」敘事 | 可作**脈絡**（與工具讀數分開寫） | 冒充 FRED／交易所**官方報價**或填補 `[DATA_MISSING:…]` 的硬數字 |
| Prompt／工作流建議 | 改善 **crew 提示**或內部 runbook | 繞過 `validate_report` 或注入未消毒 HTML |
| 多源評分／去重概念 | 啟發路徑 **C**（見 §6）在 `tools.py` 對**白名單 API** 的設計 | 預設把 X 搜尋接回日報主路（違反現行紅線） |

**原則**：數字與標的客觀欄位仍以 [`tools.py`](../../tools.py) 與既有新聞工具（如 `newsapi_tool`／`gnews_tool`，見 [`crew.py`](../../crew.py)）為準；last30days 為 **R&D／編輯輔助**。

---

## 5. 治理與隱私（摘要）

- 查詢主題會送到上游列舉的第三方（ScrapeCreators、OpenAI、X GraphQL／xAI、Brave、Parallel、OpenRouter 等）；細節見上游 **Security & Privacy** 表。
- 金鑰僅放 `~/.config/last30days/.env` 或 `.claude/last30days.env`，**勿**寫入本 repo `.env` 並提交。

---

## 6. 併入層級（A–D）與**本 repo 預設**

| 路徑 | 內容 | 本 repo 狀態 |
|------|------|----------------|
| **A** | 零程式碼：各人安裝 skill | **採用** |
| **B** | 流程合併：研究產出放 `docs/research/` 或私人筆記，不進管線 | **採用**（本檔即 B 的錨點） |
| **C** | 僅借「多源檢索 → 評分 → 去重」概念，在 Python／**白名單來源**實作；新 tool 須 `_get_cache`／`_set_cache` | **未實作**；需產品拍板與 ADR |
| **D** | cron／自動注入 crew／`main.py` | **不建議**；與紅線衝突風險高，須紅線修訂 + ADR |

**`choose-merge-tier` 決議**：預設 **A + B**。若未來執行 **C**，必須另建 ADR、feature flag、測試與 `CHANGELOG.md` 條目，且 **`main.py` 預設路徑不變**。

---

## 7. 路徑 C 的前置條件（optional-adr）

在**未**選擇路徑 C 前：**無需**新增 ADR 檔。

若啟動路徑 C，最低限度：

1. **ADR**（建議 `docs/adr/00xx-last30days-concepts-tools.md`）：允許的資料源清單、與 X 主路禁令的關係。
2. **`ENV_TEMPLATE.txt`**：新開關與金鑰說明。
3. **測試**：新邏輯需 pytest（含 smoke／boundary 適用範圍）。
4. **CHANGELOG.md**：使用者可見行為變更說明。

---

## 8. 與本專案現有模組的關係

- **Crew 新聞**：`crypto_news_task`／`ai_news_task` 以 NewsAPI／GNews 等為主；與 last30days **平行**，非替代。
- **`x_search_tool`**：仍存在於 `tools.py`，但**非**日報 crew 預設主路；不得藉 last30days 將 X 敘事升格為「無菌數字」來源。

---

## 9. 修訂紀錄

| 日期 | 說明 |
|------|------|
| 2026-03-29 | 初版：pilot 快照、邊界表、A+B 預設、路徑 C 的 ADR 前置 |

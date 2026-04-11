# OSS 研究 — 訂閱取代堆疊（手動稿，2026-04-22）

- **來源**：維護者整理之「付費終端／SaaS → 開源替代」清單，對齊 [TODOS — OSS 開源生態整合計畫](../../TODOS.md#oss-開源生態整合計畫oss-integration-roadmap) Phase 1–4。
- **產物**：[`2026-04-22-candidates.json`](2026-04-22-candidates.json)、[`2026-04-22-digest.json`](2026-04-22-digest.json)（**精簡欄位**；README 全文請上 GitHub 自拉）。
- **互補**：每週 topic 搜尋稿仍見 [`2026-04-01-revision-plan-draft.md`](2026-04-01-revision-plan-draft.md)（量化金融廣域候選）。

---

## 總表：替換敘事 → Repo → 本專案對接

| # | 付費敘事（外部說法） | 開源／工具 | TODOS Phase／小項 |
|---|----------------------|------------|-------------------|
| 1 | TradingView Pro | [tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) | Phase 2 — 戰情室 K 線 |
| 2 | Bloomberg（宏觀） | [mortada/fredapi](https://github.com/mortada/fredapi) | Phase 1 — FRED／`macro_context_tool` |
| 3 | 回測平台 | [evan-kolberg/prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) | Phase 4 — Nautilus／`backtest.py` |
| 4 | Real-time dashboard | [txbabaxyz/polyrec](https://github.com/txbabaxyz/polyrec) | Phase 2 — 終端監控參考 |
| 5 | Bot 框架 | [dylanpersonguy/Polymarket-Trading-Bot](https://github.com/dylanpersonguy/Polymarket-Trading-Bot) | Phase 4 — 策略逆向／trade_picker context |
| 6 | Execution + infra | [ent0n29/polybot](https://github.com/ent0n29/polybot) | Phase 3 — OMS 參考 |
| 7 | Paper trading | [agent-next/polymarket-paper-trader](https://github.com/agent-next/polymarket-paper-trader) | Phase 3 — Paper forward test |
| 8 | Token 節流 | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | Phase 1 — rtk 代理 |
| 9 | CLI agent 替代敘事 | [block/goose](https://github.com/block/goose) | Phase 1 — 本機開發 Agent |
| 10 | Kreo（仍付費） | Telegram 第三方 | **不入 OSS 主線**；見下方 |

---

## 逐項：威脅建模（README 四點）與紅線

以下 **License／維護度／依賴／外連** 合併 PR 前須自 GitHub 與 release 再核一次；此處為**靜態審閱筆記**。

### 1. tradingview/lightweight-charts

- **對接**：[`data-verification-ui/`](../../data-verification-ui/) Phase 2 圖表；僅前端 bundle，不經日報 LLM 產數字。
- **紅線**：圖表資料仍須來自已核准之 API／tools；Telegram 戰報 HTML 白名單不變。
- **風險**：bundle 大小與 CSP；無 server 則 telemetry 由宿主頁決定。

### 2. mortada/fredapi

- **對接**：[`tools_legacy.py`](../../tools_legacy.py) `macro_context`／FRED 路徑；`fredapi` 可簡化序列碼取得，**不得**讓 LLM 自行填 CPI 等數字。
- **紅線**：與現有 FRED 工具單一來源一致；合併前確認授權（多為 MIT／BSD 類，以 repo 為準）。

### 3. evan-kolberg/prediction-market-backtesting

- **對接**：[`backtest.py`](../../backtest.py)、Phase 4「機構回測」；與日報 **prediction_markets** 敘事分層（回測 ≠ 當日現價）。
- **風險**：Nautilus／adapter 依賴重；建議 fork 只讀 spike，不直接進 `main` 依賴樹直到審閱。

### 4. txbabaxyz/polyrec

- **對接**：[`monitor_intraday.py`](../../monitor_intraday.py) CLI 體驗參考；**非**日報資料主路徑。
- **風險**：即時 feed 與 ToS；若內嵌商業 API 金鑰模式須與 `ENV_TEMPLATE` 分離。

### 5. dylanpersonguy/Polymarket-Trading-Bot

- **對接**：Phase 4「策略指南」自然語言 context；TypeScript 主體，**不**建議整包 vendor 進 Python 管線。
- **風險**：策略多、外連多；只採**文件與介面借鏡**，併入前須 supply-chain 審查。

### 6. ent0n29/polybot

- **對接**：Phase 3 OMS／Kafka／ClickHouse 架構參考；與現有 [`execution_intents.py`](../../execution_intents.py) jsonl 骨架漸進對照。
- **風險**：基建重；預設 **不**開 full stack，只取模式。

### 7. agent-next/polymarket-paper-trader

- **對接**：Phase 3 paper forward test；與 **無幻覺** 一致：模擬成交價仍須有可驗證 order book／fee 模型來源。
- **風險**：Polymarket API 變更與合規。

### 8. rtk-ai/rtk

- **對接**：Phase 1 LiteLLM／開發 CLI 流量走代理；與 **LG-1** 觀測（cache 命中率）可一併設計。
- **風險**：本機二進位信任鏈；僅內網／CI 可選用。

### 9. block/goose

- **對接**：Phase 1 本機替代付費 CLI 之**開發者體驗**；**不**取代 `main.py` 日報四模型管線。
- **風險**：任意 LLM 後端須與金鑰管理一致。

### 10. Kreo（Telegram，付費）

- **定位**：第三方跟單／錢包追蹤；**非** GitHub OSS。
- **紅線**：**不可**作為 `validate_report` 或儀表板 `<code>` 數字來源；若產品整合須獨立 ToS、資安審查與使用者明示同意。

---

## 建議 spike 順序（與維護者排序一致）

1. **fredapi** 或強化既有 FRED 路徑（Phase 1，低 UI 風險）。  
2. **lightweight-charts** 戰情室 PoC（Phase 2，與 PWA 現有技術棧一致）。  
3. **rtk** 小範圍 dev-only 實驗（Phase 1，成本敏感時）。  
4. **paper-trader / prediction-market-backtesting** 僅在 OMS 敘事定稿後（Phase 3–4）。

---

## 維護者勾選（可複製到 issue）

- [ ] `tradingview/lightweight-charts`
- [ ] `mortada/fredapi`
- [ ] `evan-kolberg/prediction-market-backtesting`
- [ ] `txbabaxyz/polyrec`
- [ ] `dylanpersonguy/Polymarket-Trading-Bot`
- [ ] `ent0n29/polybot`
- [ ] `agent-next/polymarket-paper-trader`
- [ ] `rtk-ai/rtk`
- [ ] `block/goose`
- [ ] Kreo（非 repo — 產品／法遵單獨項）

---

## 附錄：機讀 JSON（請另存為檔）

與 [`README`](README.md) 慣例一致：可將下列區塊分別存為 `docs/oss_candidates/2026-04-22-candidates.json` 與 `docs/oss_candidates/2026-04-22-digest.json`（例如於 Agent 模式或本機 shell 寫入），供 `oss_repo_digest`／審閱流程對齊。

### `2026-04-22-candidates.json`

```json
{
  "query": "curated:subscription-stack-oss-replacement (manual, not GitHub Search)",
  "sort": "stars",
  "per_page": 9,
  "total_count": 9,
  "items": [
    {
      "full_name": "tradingview/lightweight-charts",
      "html_url": "https://github.com/tradingview/lightweight-charts",
      "description": "Financial lightweight charts built with HTML5 canvas.",
      "stargazers_count": 14000,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["charts", "trading", "canvas"]
    },
    {
      "full_name": "mortada/fredapi",
      "html_url": "https://github.com/mortada/fredapi",
      "description": "Python API for FRED (Federal Reserve Economic Data).",
      "stargazers_count": 800,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["fred", "macro", "python"]
    },
    {
      "full_name": "evan-kolberg/prediction-market-backtesting",
      "html_url": "https://github.com/evan-kolberg/prediction-market-backtesting",
      "description": "NautilusTrader fork with Polymarket/Kalshi adapters (verify upstream).",
      "stargazers_count": 500,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["backtesting", "nautilus", "polymarket"]
    },
    {
      "full_name": "txbabaxyz/polyrec",
      "html_url": "https://github.com/txbabaxyz/polyrec",
      "description": "Terminal UI: feeds, orderbook, indicators, CSV logging (verify license/activity).",
      "stargazers_count": 300,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["terminal", "polymarket", "monitoring"]
    },
    {
      "full_name": "dylanpersonguy/Polymarket-Trading-Bot",
      "html_url": "https://github.com/dylanpersonguy/Polymarket-Trading-Bot",
      "description": "TypeScript Polymarket strategies (arbitrage, MM, etc.) — document-only spike default.",
      "stargazers_count": 1200,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["polymarket", "typescript", "trading"]
    },
    {
      "full_name": "ent0n29/polybot",
      "html_url": "https://github.com/ent0n29/polybot",
      "description": "Execution + market data infra; Kafka/ClickHouse/Grafana (architecture reference).",
      "stargazers_count": 400,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["oms", "infrastructure"]
    },
    {
      "full_name": "agent-next/polymarket-paper-trader",
      "html_url": "https://github.com/agent-next/polymarket-paper-trader",
      "description": "Paper trading with fee/slippage model for agents (verify API ToS).",
      "stargazers_count": 200,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["paper-trading", "polymarket"]
    },
    {
      "full_name": "rtk-ai/rtk",
      "html_url": "https://github.com/rtk-ai/rtk",
      "description": "Rust CLI proxy for AI tool token savings (dev/CI optional).",
      "stargazers_count": 1500,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["proxy", "rust", "llm"]
    },
    {
      "full_name": "block/goose",
      "html_url": "https://github.com/block/goose",
      "description": "Local agent loop; multiple LLM backends (developer workflow, not daily pipeline).",
      "stargazers_count": 35000,
      "forks_count": 0,
      "updated_at": "2026-04-22T00:00:00Z",
      "pushed_at": "2026-04-22T00:00:00Z",
      "archived": false,
      "topics": ["agent", "llm", "cli"]
    }
  ]
}
```

### `2026-04-22-digest.json`

```json
{
  "source": "2026-04-22-candidates.json (manual curated)",
  "generated_at": "2026-04-22T00:00:00Z",
  "repos": [
    {
      "full_name": "tradingview/lightweight-charts",
      "html_url": "https://github.com/tradingview/lightweight-charts",
      "readme_excerpt": "See draft §1. Canvas charts; no server telemetry in lib itself.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "mortada/fredapi",
      "html_url": "https://github.com/mortada/fredapi",
      "readme_excerpt": "See draft §2. Python wrapper for FRED series; align with macro_context_tool.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "evan-kolberg/prediction-market-backtesting",
      "html_url": "https://github.com/evan-kolberg/prediction-market-backtesting",
      "readme_excerpt": "See draft §3. Nautilus adapters; spike only before requirements merge.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "txbabaxyz/polyrec",
      "html_url": "https://github.com/txbabaxyz/polyrec",
      "readme_excerpt": "See draft §4. TUI monitoring reference; not primary daily pipeline path.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "dylanpersonguy/Polymarket-Trading-Bot",
      "html_url": "https://github.com/dylanpersonguy/Polymarket-Trading-Bot",
      "readme_excerpt": "See draft §5. TS strategies; document-only default.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "ent0n29/polybot",
      "html_url": "https://github.com/ent0n29/polybot",
      "readme_excerpt": "See draft §6. OMS/Kafka/CH reference; do not vendor full stack blindly.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "agent-next/polymarket-paper-trader",
      "html_url": "https://github.com/agent-next/polymarket-paper-trader",
      "readme_excerpt": "See draft §7. Paper trading; verify fee/slippage model vs live API.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "rtk-ai/rtk",
      "html_url": "https://github.com/rtk-ai/rtk",
      "readme_excerpt": "See draft §8. Rust LLM proxy; dev/CI optional; supply-chain review.",
      "readme_note": "manual_curated"
    },
    {
      "full_name": "block/goose",
      "html_url": "https://github.com/block/goose",
      "readme_excerpt": "See draft §9. Local agent CLI; does not replace main.py crew.",
      "readme_note": "manual_curated"
    }
  ]
}
```

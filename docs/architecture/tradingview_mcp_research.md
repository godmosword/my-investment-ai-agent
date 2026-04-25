# TradingView MCP 整合研究

> 研究日期：2026-04-25  
> 來源：[tradesdontlie/tradingview-mcp](https://github.com/tradesdontlie/tradingview-mcp)  
> 狀態：評估中（未實作）

---

## 一、什麼是 TradingView MCP？

`tradesdontlie/tradingview-mcp` 是一個 Node.js MCP（Model Context Protocol）server，透過 **Chrome DevTools Protocol（CDP）** 連線到本機執行中的 TradingView 桌面 App（port 9222），將圖表數據暴露為 Claude Code 可呼叫的工具。

### 核心工具

| 工具 | 功能 |
|------|------|
| `tv_health_check` | 驗證 CDP 連線（`cdp_connected: true/false`）|
| `tv_launch` | 啟動 TradingView（可選；未提供時需手動加 `--remote-debugging-port=9222`）|
| 價格 / 指標查詢 | 即時報價、RSI、MACD、EMA、Volume Profile 等 |

### 啟動方式

```bash
# Mac
/Applications/TradingView.app/Contents/MacOS/TradingView --remote-debugging-port=9222

# 或由 tv_launch 工具自動偵測並啟動
```

---

## 二、與本專案現有架構的對應

### 2.1 現有市場數據工具（tools_legacy.py）

本專案已有豐富的指標計算能力：

| 現有工具 | 數據來源 | 計算指標 |
|----------|----------|---------|
| `multi_timeframe_tool` | yfinance | MA20/50/200、趨勢共識（1D/4H/1H）|
| `regime_scorecard_tool` | yfinance + Alternative.me | RSI(14)、VIX、Fear & Greed、多空偏向 |
| `historical_analog_tool` | yfinance | 30d 波動率、價格/MA200 對數比 |
| `valuation_anchor_tool` | CoinGecko + Blockchain.info | NVT、MVRV proxy |
| `onchain_metrics_tool` | CryptoQuant + Glassnode | SOPR、交易所淨流量、NUPL |

### 2.2 TradingView MCP 能補充的缺口

| 面向 | 現況缺口 | TradingView MCP 補充 |
|------|---------|---------------------|
| 即時報價 | yfinance 有 15 分鐘延遲 | TradingView 即時（本機 App 連線）|
| 圖表偏向判斷 | 需自行計算 50D EMA 多空 | TradingView 原生 bias summary |
| 週線時框 | `multi_timeframe_tool` 以日線為主 | 1W/1D/4H 三層共識 |
| 技術信號強度 | RSI 單點數值 | MACD 柱狀圖趨勢、信號線交叉 |
| Claude Code 開發輔助 | 無即時數據查詢 | 開發時可直接驗證報告數字 |

---

## 三、規劃的 rules.json（對應本專案資產設定）

對應 `assets_config.json` 及 `_CRYPTO_YF` 標的集合：

```json
{
  "watchlist": {
    "majors": ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"],
    "alts": ["BINANCE:LINKUSDT", "BINANCE:AVAXUSDT", "BINANCE:SUIUSDT"],
    "macro": ["CRYPTOCAP:TOTAL", "CRYPTOCAP:TOTAL3", "CRYPTOCAP:BTC.D"]
  },
  "timeframes_to_check": ["1W", "1D", "4H"],
  "bias_criteria": {
    "bullish": "Price above 50D EMA, RSI on daily between 45 and 70, higher highs and higher lows on 4H",
    "bearish": "Price below 50D EMA, RSI on daily below 45, lower highs and lower lows on 4H",
    "neutral": "Price chopping around 50D EMA, RSI between 40 and 60, no clear structure"
  },
  "risk_rules": {
    "max_risk_per_trade": "1% of portfolio",
    "min_rr_ratio": 2,
    "no_trades_during": ["major US CPI", "FOMC", "weekend thin liquidity"]
  },
  "indicators_i_care_about": ["RSI (14)", "MACD (12, 26, 9)", "50 EMA", "200 EMA", "Volume"]
}
```

**對應關係：**
- `bias_criteria` → `regime_scorecard_tool` 多空判斷邏輯
- `risk_rules.min_rr_ratio: 2` → `QSREC` 的 `trade_legs` 風險報酬要求
- `no_trades_during` → `econ_calendar_tool` 高風險事件迴避邏輯
- `indicators_i_care_about` → `_calc_rsi()`、`_trend_by_ma()` 現有函式

---

## 四、整合架構（三層）

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Claude Code MCP (開發輔助)                        │
│  ~/.claude/.mcp.json → tradingview MCP server               │
│  用途：Claude 開發時直接驗證報告數字、查即時價格            │
└──────────────────────────┬──────────────────────────────────┘
                           │ 可選延伸
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 2: rules.json 對齊                                    │
│  ~/tradingview-mcp/rules.json                                │
│  watchlist / bias_criteria / risk_rules 對應專案資產設定     │
└──────────────────────────┬──────────────────────────────────┘
                           │ 可選延伸
┌──────────────────────────▼──────────────────────────────────┐
│  Layer 3: Python Bridge Tool (pipeline 整合)                 │
│  tools/tradingview.py — @tool 裝飾器                         │
│  CDP 可達 → TradingView 即時數據                             │
│  CDP 不可達（Cloud Run）→ yfinance fallback                  │
│  ↓ 加入 crew.py _crypto_researcher_tools() tail              │
│  ↓ 加入 graph/graph_tools.py RESEARCH_TOOLS                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、Layer 3 Python Bridge 實作要點

若選擇實作 `tools/tradingview.py`：

### 需遵循的現有模式

| 模式 | 來源檔案 | 說明 |
|------|----------|------|
| `_get_cache()` / `_set_cache()` | `tools_cache_http.py:77–93` | TTL 10 分鐘，LRU 256 entries |
| `_yf_download_with_timeout()` | `tools_legacy.py:47–64` | fallback 用；45s timeout |
| `_calc_rsi(series, period=14)` | `tools_legacy.py:4156–4163` | fallback 指標計算 |
| `mock_apis_enabled()` / `load_mock_json()` | `tools/base.py` | MOCK_APIS=1 測試 |
| `[DATA_MISSING:...]` 錯誤格式 | `tools_legacy.py:1612` 附近 | 失敗時回傳，不拋例外 |
| `traced_tool_execution()` | `tools_legacy.py:918` 模式 | 統一 tracing |
| `_run_legacy_tool()` | `graph/graph_tools.py:25–36` | LangGraph bridge |

### 需新增的檔案

```
tools/tradingview.py                     # 主實作
tests/fixtures/mock_data/tradingview.json  # MOCK_APIS=1 fixture
```

### 需修改的檔案

```
tools/__init__.py                  # 加 export
crew.py (lines 18–44, 77–101)     # import + _crypto_researcher_tools() tail
graph/graph_tools.py               # @tool wrapper + RESEARCH_TOOLS list
```

---

## 六、關鍵限制與風險

### 6.1 生產環境限制

TradingView MCP **需要桌面 App 在本機執行**，並開啟 CDP port 9222。

| 環境 | 狀態 | 處理方式 |
|------|------|---------|
| 本機開發 | 可用 | 正常呼叫 TradingView MCP |
| Cloud Run（自動化 pipeline）| **不可用** | Layer 3 fallback to yfinance |
| CI/GitHub Actions | 不可用 | `MOCK_APIS=1` fixture 模式 |

Layer 3 fallback 必須完全靜默（不拋例外、不阻斷 pipeline），只在 `logger.warning` 留下紀錄。

### 6.2 數據紅線（PROJECT RED LINE）

> CLAUDE.md §2：Objective prices and indicators must come from Python tools/APIs — not LLM invention.

TradingView MCP 提供的數據符合此要求（來自桌面 App 的真實圖表數據），但：
- Layer 1（Claude Code 工具）：僅用於輔助開發分析，**不能**作為日報數字的來源
- Layer 3（Python 工具）：可進入 pipeline，但須附 `[data_as_of: timestamp]` 標記

### 6.3 依賴風險

- TradingView 桌面 App 版本更新可能破壞 CDP 介面
- CDP 協議未被 TradingView 官方支援，屬灰色利用
- 建議 Layer 3 始終保有 yfinance fallback，不以 TradingView 為唯一數據源

---

## 七、安裝步驟（Layer 1 快速開始）

```bash
# 1. 克隆 MCP server
git clone https://github.com/tradesdontlie/tradingview-mcp.git ~/tradingview-mcp
cd ~/tradingview-mcp && npm install

# 2. 確認 ~/.claude/.mcp.json 存在（若不存在則建立）
# 合併加入，勿覆蓋其他 server

# 3. 建立 rules.json
# 使用上方 Section 三的內容

# 4. 啟動 TradingView
open -a TradingView --args --remote-debugging-port=9222
# 或等待 tv_launch 工具自動處理

# 5. 在 Claude Code session 中驗證
# tv_health_check → cdp_connected: true
```

---

## 八、決策矩陣

| 層次 | 工作量 | 生產影響 | 推薦優先級 |
|------|--------|---------|-----------|
| Layer 1（MCP 安裝）| 低（30 分鐘）| 無 | **立即執行** |
| Layer 2（rules.json 對齊）| 低（15 分鐘）| 無 | **立即執行** |
| Layer 3（Python Bridge）| 中（2–4 小時）| 低（有 fallback）| 下一個迭代 |

Layer 1 + 2 可立即提升開發體驗，Layer 3 等驗證 CDP 穩定性後再考慮接入 pipeline。

---

## 相關文件

- [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](../ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) — tools 套件 ADR
- [`docs/TOOLS_MODULARIZATION_PLAN.md`](../TOOLS_MODULARIZATION_PLAN.md) — tools 模組化計畫
- [`docs/architecture/AI_CONTEXT.md`](AI_CONTEXT.md) — AI 協作紅線
- [`assets_config.json`](../../assets_config.json) — 資產標的設定

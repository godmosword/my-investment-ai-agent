# Q-Silicon Token & API Optimization — Cursor Prompt

Paste this entire prompt into Cursor to apply all optimizations.

---

## Context

This is a CrewAI-based investment AI agent (Python) that generates daily crypto & AI market reports. The pipeline uses 4 LLMs (Grok, GPT, Claude, Gemini) across 2 parallel crews (CryptoResearchCrew + AIResearchCrew), each with 3 sequential tasks.

**Current problems:**
- `crew.py` has ~13,750 chars of task descriptions (~5,000-7,000 LLM tokens) with massive duplication
- Telegram HTML formatting rules are duplicated 2x (~1,500 chars each)
- IMPACT tag format string is repeated 6x across task descriptions
- "嚴禁" (forbidden) warnings appear 13 times — LLMs don't need repeated scolding
- `_make_llms()` creates 4 LLM instances per Crew but each Crew only uses 3
- Redundant API calls: VIX is fetched by both the researcher (yfinance_macro_tool) and critic (yfinance_tool) tasks
- CoinGlass metrics are requested in both Task 1 (researcher) and Task 3 (editor) with overlapping calls
- market_search_tool uses `max_results=5` for basic searches where 3 would suffice
- Tavily fallback functions are 4 near-identical copy-paste blocks

**Goal:** Reduce token usage by ~40-50% and reduce redundant API calls, while preserving report quality and structure. Keep current model assignments unchanged.

---

## Changes to Apply

### 1. `crew.py` — Extract shared constants (HIGH IMPACT)

At the top of `crew.py` (after imports), add these shared constant strings:

```python
# ── Shared prompt fragments (extracted to reduce token duplication) ──────────
_TELEGRAM_FORMAT_RULES = dedent("""\
    ════ Telegram HTML 格式 ════
    僅允許：<b>、<i>、<u>、<s>、<code>、<blockquote>
    禁止：Markdown（#、**、*、_、`）、<h1~h2>、<div>、<p>、<br>、<hr>、<span>、<table>
    分隔線用 ────────────，標題用 <b>【標題】</b>，條列用「· 」，數值用 <code>，推文用 <blockquote>""")

_IMPACT_TAG = "IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）｜NARRATIVE：FOMO/FUD/Infra/Regulation/Other"

_EDITOR_CONSENSUS_RULE = dedent("""\
    【主編共識原則】
    將 Grok/GPT 與 Claude 的辯論濃縮為一句話共識填入 💎 <b>主編共識</b>。
    戰報正文中每則新聞/推文僅保留 💎 主編共識一行，禁止呈現個別 Agent 觀點。""")

_NEWS_FORMAT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] 新聞標題
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1~2 句）""")

_PRICE_CHECK_RULE = "進場/目標/停損前必須呼叫 yfinance_tool 查詢最新報價，禁止憑空捏造價格。"
```

### 2. `crew.py` — Optimize `_make_llms()` to accept a filter

Replace `_make_llms()` with a version that only creates needed LLMs:

```python
def _make_llms(*names: str):
    """建立並回傳指定的 LLM 實例。names: 'grok','gpt','claude','gemini'"""
    factories = {
        "grok": lambda: LLM(model=MODEL_GROK, api_key=os.getenv("XAI_API_KEY"), max_retries=3, timeout=120),
        "gpt": lambda: LLM(model=MODEL_GPT, api_key=os.getenv("OPENAI_API_KEY"), max_retries=3, timeout=120),
        "claude": lambda: LLM(model=MODEL_CLAUDE, api_key=os.getenv("OPENROUTER_API_KEY"), max_retries=3, timeout=120),
        "gemini": lambda: LLM(model=MODEL_GEMINI, api_key=os.getenv("GEMINI_API_KEY"), max_retries=5, timeout=180),
    }
    return tuple(factories[n]() for n in names)
```

Update callers:
- `CryptoResearchCrew.__init__`: `grok, claude, gemini = _make_llms("grok", "claude", "gemini")`
- `AIResearchCrew.__init__`: `gpt, claude, gemini = _make_llms("gpt", "claude", "gemini")`

### 3. `crew.py` — Compress CryptoResearchCrew Task 1 (researcher) (~40% reduction)

Replace the crypto_task description with this compressed version. Key changes:
- Consolidate tool call instructions into a numbered checklist (not paragraphs)
- Remove repeated IMPACT_TAG inline — reference the constant
- Remove verbose formatting examples that duplicate the expected_output
- Combine 背離/衍生品 analysis into 2 concise bullet points

```python
crypto_task = Task(
    description=dedent(f"""
        【加密市場情報收集 — Grok】
        {_excl}
        === 數據收集（全部必須執行）===
        ① macro_liquidity_tool×2：DXY 與 M2
        ② mvrv_tool('latest')：BTC MVRV Z-Score
        ③ coinglass_data_tool×3：funding_rate / liquidations / long_short_ratio
        ④ yfinance_macro_tool('vix')：VIX 指數
        ⑤ yfinance_macro_tool('etf_flow')：SPY/QQQ 成交額 proxy
        ⑥ cryptopanic_tool('bitcoin')：幣圈原生快訊
        ⑦ rumor_scanner_tool：'BTC ETF flow OR crypto manipulation OR whale alert'
        ⑧ x_search_tool：'BTC whale OR bitcoin ETF OR crypto rumor'

        === 幣圈新聞（3 則）===
        優先：ETF 資金流、槓桿清算、鏈上流向、做市商操作。至少一則來自 CryptoPanic。
        每則格式（標註發布時間，無精確時間則 [近24h]/[近72h]）：
        {_NEWS_FORMAT}
        🛸 Grok 利多 / 🛸 Grok 利空（各 1~2 句）
        {_IMPACT_TAG}

        === 背離與衍生品 ===
        · FOMO + MVRV>7 + 巨鯨轉帳 → 標示「聰明錢出貨警告」
        · 全網悲觀 + MVRV<0 + 巨鯨平靜 → 標示「散戶盲目恐慌」
        · 資金費率極正 + 多頭過熱 → 標示「多頭清算風險」
        · 剛發生巨額多頭爆倉 → 標示「流動性洗盤，左側建倉條件」

        === 幣圈推文（5 則）===
        每則：〔推文 N〕推文原文 / 簡述 / 🛸 Grok 利多+利空 / {_IMPACT_TAG}

        禁止捏造來源或未出現於搜尋結果中的事實。
    """),
    expected_output="加密市場數據 + 3 則幣圈新聞 + 5 則推文的結構化初稿。",
    agent=self.crypto_researcher
)
```

### 4. `crew.py` — Compress CryptoResearchCrew Task 2 (critic) (~35% reduction)

```python
review_task = Task(
    description=dedent("""
        【幣圈辯論與風險審計 — Claude】

        === Fact-Check ===
        檢視所有數據（DXY/M2/MVRV/資金費率/爆倉/多空比/VIX/IBIT/ETF flow）。
        數據滯後 >12h 或極端異常 → 標記「數據失真警告：[指標]」。

        === Risk Off 訊號 ===
        呼叫 yfinance_tool('^VIX') 與 yfinance_tool('IBIT')。
        VIX 暴漲 + IBIT 下跌 → 「Risk Off 信號」；反之 → 風險偏好未退潮。

        === 幣圈新聞辯論（3 則）===
        每則：🛡️ Claude（幣圈新聞 N）：2~3 句辯論觀點。

        === 幣圈推文辯論（5 則）===
        每則：🛡️ Claude（幣圈推文 N）：1 句反向/補充觀點。

        === market_regime（risk_on / risk_off / neutral 三選一）===
        提供 3 個驅動因子（各一句話）。
        · FUD + ETF 巨大淨流出 → 「情緒感染流動性」高風險
        · 全網恐慌 + 巨鯨平靜 + MVRV<3 → 「黃金坑/洗盤」
        · 散戶過度槓桿做多 → 即使無 FUD 也判定 risk_off
    """),
    expected_output="Fact-Check 備忘 + VIX/IBIT 判定 + 3 新聞 5 推文辯論 + market_regime。",
    agent=self.risk_critic,
    context=[crypto_task]
)
```

### 5. `crew.py` — Compress CryptoResearchCrew Task 3 (editor) (~45% reduction)

Key: Extract formatting rules to constants, remove the full template (LLM already knows from context).

```python
final_report_task = Task(
    description=dedent(f"""
        【加密市場戰報排版 — Gemini 主編】

        排版前數據獲取：coinglass_data_tool('open_interest'/'funding_rate'/'liquidations'/'long_short_ratio')、cryptoquant_tool('inflow' 或 'outflow')、ml_quant_tool。

        {_EDITOR_CONSENSUS_RULE}

        {_TELEGRAM_FORMAT_RULES}

        === 投資標的 ===
        在【資金流向與精準操作 (Crypto)】提供 1 單邊標的（非 BTC）+ 1 配對交易。
        {_PRICE_CHECK_RULE}
        每標的含：信心水準⭐️1~5、資金佔比、進場/目標/停損、敘事邏輯。

        === 排版結構（嚴格依序）===
        <b>🛡️ Q-Silicon Institutional Research</b> / <i>Daily Brief · {today_str}</i>
        ────────────
        【今日市場模式】risk_on/risk_off/neutral + 3 驅動因子
        ══════ <b>📊 加密市場</b> ══════
        【加密市場數據儀表板】宏觀(M2/DXY/VIX) + 量化模型(ML權重/部位建議) + 幣圈指標(MVRV/OI/IBIT/資金費率/爆倉/多空比/交易所淨流入)
        【幣圈新聞】3 則：標題/來源/摘要/IMPACT/💎主編共識
        【幣圈推文討論】5 則：<blockquote>原文</blockquote>/簡述/IMPACT/💎主編共識
        【資金流向與精準操作 (Crypto)】1 單邊 + 1 配對

        所有標題用 <b>，數值用 <code>，推文用 <blockquote>。禁止 Markdown 與 HORIZON 標籤。
    """),
    expected_output="戰報上半部 Telegram HTML 格式完整輸出。",
    agent=self.quant_strategist,
    context=[crypto_task, review_task]
)
```

### 6. `crew.py` — Compress AIResearchCrew Task 1 (researcher) (~40% reduction)

```python
ai_task = Task(
    description=dedent(f"""
        【AI 市場情報收集 — GPT】
        {_excl}
        === 數據 ===
        呼叫 ai_momentum_tool('openrouter_rankings') 取得模型熱度排名。

        === 第一部分：AI 基建現況（3 則）===
        聚焦：資料中心/GPU/TPU/算力/電力/散熱/能源基建。
        必須搜尋（各至少一次）：
        · market_search_tool: 'AI data center GPU NVIDIA infrastructure 2025'
        · market_search_tool: 'data center power supply nuclear energy AI 2025'
        · market_search_tool: 'AI data center cooling thermal technology 2025'
        · rumor_scanner_tool: 'data center materials semiconductor supply chain'
        3 則中至少一則涵蓋電力/散熱/材料/能源基建。
        每則：{_NEWS_FORMAT} + 🤖 GPT 利多/利空 + {_IMPACT_TAG}

        === 第二部分：AI 投資案（3 則）===
        聚焦：AI 新創融資、科技收購、風投、IPO。
        搜尋：market_search_tool + rumor_scanner_tool。
        格式同上。

        === 第三部分：最新 AI 模型（3 則）===
        聚焦：LLM/多模態/Agent 框架新發布，摘要含模型特色。
        格式同上。

        === AI 推文（5 則）===
        x_search_tool: 'MCP Model Context Protocol OR AI agent app 2025'
        聚焦：AI 應用落地、MCP 發展、Agent 框架。
        每則：〔推文 N〕原文/簡述/🤖 GPT 利多+利空/{_IMPACT_TAG}

        · 訓練成本攀升但 Big Tech capex 增速放緩 → 標示「算力通縮研發通膨矛盾」
        禁止捏造事實。
    """),
    expected_output="OpenRouter 排名 + 三部分各 3 則 AI 新聞 + 5 則推文結構化初稿。",
    agent=self.ai_researcher
)
```

### 7. `crew.py` — Compress AIResearchCrew Task 2 & 3 (same pattern as crypto)

Apply identical compression patterns to `AIResearchCrew` review_task and final_report_task.

For **review_task** (~35% reduction):
```python
review_task = Task(
    description=dedent("""
        【AI 市場辯論審計 — Claude】

        === AI 基建辯論（3 則）===
        每則：🛡️ Claude（AI基建 N）：2~3 句辯論。

        === AI 投資案辯論（3 則）===
        每則：🛡️ Claude（AI投資 N）：2~3 句辯論。

        === 最新 AI 模型辯論（3 則）===
        每則：🛡️ Claude（AI模型 N）：2~3 句辯論。

        === AI 推文辯論（5 則）===
        每則：🛡️ Claude（AI推文 N）：1 句反向/補充觀點。
    """),
    expected_output="9 新聞 + 5 推文 Claude 辯論觀點。",
    agent=self.risk_critic,
    context=[ai_task]
)
```

For **final_report_task** (~45% reduction):
```python
final_report_task = Task(
    description=dedent("""
        【AI 市場戰報排版 — Gemini 主編】

        {_EDITOR_CONSENSUS_RULE}
        {_TELEGRAM_FORMAT_RULES}

        === 投資標的 ===
        在【AI 產業鏈精準操作 (US Equities)】提供 2 個美股標的。
        {_PRICE_CHECK_RULE}
        每標的含：信心水準⭐️1~5、資金佔比、進場/目標/停損、敘事邏輯。

        === 排版結構 ===
        ══════ <b>🤖 AI 市場</b> ══════
        【AI 數據參考】OpenRouter 模型熱度排名
        【AI 基建現況】3 則：標題/來源/摘要/IMPACT/💎主編共識
        【AI 投資案】3 則（同上格式）
        【最新 AI 模型】3 則（摘要含模型特色）
        【AI 推文討論】5 則：<blockquote>原文</blockquote>/簡述/IMPACT/💎主編共識
        【AI 產業鏈精準操作 (US Equities)】2 支

        所有標題用 <b>，數值用 <code>，推文用 <blockquote>。禁止 Markdown 與 HORIZON 標籤。
    """),
    expected_output="戰報下半部 Telegram HTML 格式完整輸出。",
    agent=self.quant_strategist,
    context=[ai_task, review_task]
)
```

### 8. `tools.py` — Consolidate Tavily fallback functions (DRY)

Replace the 4 near-identical `_tavily_fallback_*` functions with one generic:

```python
def _tavily_fallback(query: str, label: str) -> str:
    """通用 Tavily 備援搜尋。"""
    try:
        client = _get_tavily_client()
        res = client.search(query=query, search_depth="basic", max_results=3, topic="finance")
        return f"[Tavily 備援] {str(res.get('results', []))}"
    except Exception:
        return f"API 暫時無回應：CoinGlass（{label}）與 Tavily 備援均失敗。"

# Usage in coinglass_data_tool fallback section:
_TAVILY_FALLBACK_QUERIES = {
    "open_interest": "Bitcoin BTC open interest aggregated futures today billions",
    "funding_rate": "Bitcoin BTC current funding rate binance today",
    "liquidations": "Bitcoin BTC total liquidations past 24 hours crypto market",
    "long_short_ratio": "Bitcoin BTC top trader long short ratio binance today",
}

# Replace the fallbacks dict in coinglass_data_tool:
result = _tavily_fallback(_TAVILY_FALLBACK_QUERIES[metric_lower], metric_lower)
```

Also replace `_tavily_fallback_exchange_flow` with:
```python
result = _tavily_fallback(
    f"Bitcoin BTC exchange {indicator_lower} today on-chain",
    f"CryptoQuant-{indicator_lower}"
)
```

### 9. `tools.py` — Reduce Tavily max_results for non-critical searches

In `market_search_tool` and `rumor_scanner_tool`, change `max_results=5` → `max_results=3`. These tools already have caching and return more data than agents typically use. The news search with `days=1` already constrains freshness.

```python
# market_search_tool
response = client.search(query=query, search_depth="basic", max_results=3, topic="news", days=1)

# rumor_scanner_tool — already uses max_results=3, no change needed
```

### 10. `tools.py` — Batch yfinance downloads where possible

Add a batched VIX+IBIT fetcher to avoid the critic calling yfinance_tool twice:

```python
@tool("YFinance Multi-Quote")
def yfinance_multi_tool(symbols: str) -> str:
    """批量取得多標的報價，symbols 以逗號分隔（如 '^VIX,IBIT'）。"""
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    results = []
    for sym in symbol_list:
        results.append(yfinance_tool(sym))  # Reuses cache
    return "\n".join(results)
```

Then update the critic agent's tool list to include `yfinance_multi_tool` and update the task description to call it once with `'^VIX,IBIT'` instead of two separate calls.

### 11. `crew.py` — Trim Agent backstories

The backstories are already reasonably sized but can be tightened:

```python
# crypto_researcher backstory (was 65 chars → same, it's fine)
# risk_critic: trim to core personality
backstory="索羅斯反射性理論信徒。深知假新聞能創造真實踩踏，真正轉折在共識反面。"
```

### 12. `crew.py` — Eliminate redundant CoinGlass refetch in Task 3

In CryptoResearchCrew, Task 1 (researcher) already calls `coinglass_data_tool` for `funding_rate`, `liquidations`, and `long_short_ratio`. Task 3 (editor) re-calls the same 3 metrics plus `open_interest`. Since Task 3 receives Task 1's output via `context=[crypto_task, review_task]`, the data is already available.

**Fix:** In Task 3's description, change the data fetching instruction to only call `coinglass_data_tool('open_interest')` (the one metric NOT fetched in Task 1). Remove the redundant 3 calls. The editor should reuse funding_rate/liquidations/long_short_ratio from Task 1's context.

### 13. `tools.py` — Reduce `ai_momentum_tool` max_results

Change `max_results=5` → `max_results=3` in `ai_momentum_tool` for consistency with other tools:

```python
response = client.search(query=query, search_depth="basic", max_results=3)
```

### 14. Summary of Expected Savings

| Area | Before (est. tokens) | After (est. tokens) | Savings |
|---|---|---|---|
| Task descriptions (6 tasks) | ~6,875 | ~3,800 | ~45% |
| Shared constants (extracted) | 0 | ~400 (one-time) | — |
| Tavily fallback code | ~200 lines | ~50 lines | 75% code |
| API calls per run | ~25+ Tavily/tool calls | ~18-20 | ~25% |
| LLM instances created | 8 (4×2 crews) | 6 (3×2) | 25% |
| **Net token reduction per pipeline run** | | | **~40-45%** |

The biggest win is compressing the 6 task descriptions, which are sent as LLM prompts on every single pipeline run. At ~3,000 tokens saved × 4 LLM models × daily runs, this adds up fast.

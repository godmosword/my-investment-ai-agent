# Bug Fix Cursor Prompt
# Targets: VIX/IBIT 工具失效, MVRV 無數據, ML 無數據, 重複/過時新聞

---

## Root Cause Summary

| Bug shown in screenshot | Root cause |
|---|---|
| VIX 工具失效 | yfinance ≥ 0.2.38 returns MultiIndex DataFrame; `df["Close"].iloc[-1]` crashes |
| IBIT 工具失效 | Same MultiIndex issue in `_yf_quote` |
| MVRV 無數據 | CryptoQuant 403 error has no Tavily fallback |
| ML 權重 無數據 | BigQuery has <30 rows; tool fails but agents write "無數據" literally |
| 重複/過時新聞 | exclusion context only 1200 chars; AI searches hardcoded `2025` |

---

## Fix 1 — `tools.py`: yfinance MultiIndex crash (VIX + IBIT)

**Problem:** yfinance ≥ 0.2.38 changed the default for `auto_adjust`.
When downloading a single ticker, `df["Close"]` can now be a 2-column
DataFrame with a MultiIndex instead of a Series, causing
`float(df["Close"].iloc[-1])` to throw a ValueError.

**In `yfinance_macro_tool`, replace the entire `if key == "vix":` block:**

```python
if key == "vix":
    import pandas as pd
    df = yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return "YFinance：無法取得 VIX 資料。"
    # Fix: yfinance >= 0.2.38 may return MultiIndex columns for single ticker
    close_col = df["Close"]
    if isinstance(close_col, pd.DataFrame):
        close_col = close_col.iloc[:, 0]
    close_col = close_col.dropna()
    if close_col.empty:
        return "YFinance：VIX 資料欄位為空。"
    latest = float(close_col.iloc[-1])
    prev = float(close_col.iloc[-2]) if len(close_col) > 1 else latest
    change = latest - prev
    pct = (change / prev * 100) if prev else 0.0
    vix_level = "🔴 恐慌" if latest >= 30 else ("🟡 警戒" if latest >= 20 else "🟢 平靜")
    result = f"VIX {latest:.2f} {vix_level}，日變化 {change:+.2f}（{pct:+.2f}%）"
    _set_cache(cache_key, result)
    return result
```

**Replace the entire `elif key == "etf_flow":` block:**

```python
elif key == "etf_flow":
    import pandas as pd
    tickers = ["SPY", "QQQ"]
    df = yf.download(
        " ".join(tickers), period="6d", interval="1d",
        progress=False, auto_adjust=True, group_by="ticker"
    )
    if df.empty:
        return "YFinance：無法取得 SPY / QQQ 資料。"

    lines: list[str] = []
    for t in tickers:
        try:
            # Handle both MultiIndex (multi-ticker) and flat (single) cases
            if isinstance(df.columns, pd.MultiIndex):
                sub = df[t].dropna(how="all")
            else:
                sub = df.dropna(how="all")
            if sub.empty or len(sub) < 3:
                continue
            latest_close = float(sub["Close"].squeeze().iloc[-1])
            latest_vol   = float(sub["Volume"].squeeze().iloc[-1])
            prev5_close  = sub["Close"].squeeze().iloc[:-1].tail(5).astype(float)
            prev5_vol    = sub["Volume"].squeeze().iloc[:-1].tail(5).astype(float)
            dollar_vol_today = latest_close * latest_vol
            dollar_vol_avg5  = float((prev5_close * prev5_vol).mean())
            if dollar_vol_avg5 <= 0:
                continue
            ratio = dollar_vol_today / dollar_vol_avg5
            if ratio > 1.2:
                direction = "放量（資金關注升高）"
            elif ratio < 0.8:
                direction = "縮量（資金關注降溫）"
            else:
                direction = "量能中性"
            lines.append(
                f"{t} 成交額 ${dollar_vol_today/1e9:.2f}B，約 5日均額 {ratio:.2f}x，{direction}"
            )
        except Exception:
            continue

    if not lines:
        return "YFinance：ETF 成交額 proxy 計算失敗或資料不足。"
    result = "；".join(lines)
    _set_cache(cache_key, result)
    return result
```

**Replace the entire `_yf_quote` function:**

```python
def _yf_quote(symbol: str) -> str:
    """內部共用：取得單一標的報價，帶 cache。修正 yfinance MultiIndex 問題。"""
    import pandas as pd
    sym = (symbol or "").strip()
    if not sym:
        return "YFinance Tool Failed：symbol 不可為空。"
    cache_key = ("yfinance_quote", sym.upper())
    cached = _get_cache(cache_key)
    if cached:
        return cached
    try:
        df = yf.download(sym, period="5d", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return f"YFinance：無法取得 {sym} 資料。"
        close_col = df["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()
        if close_col.empty:
            return f"YFinance：{sym} 資料欄位為空。"
        latest = float(close_col.iloc[-1])
        prev   = float(close_col.iloc[-2]) if len(close_col) > 1 else latest
        change = latest - prev
        pct    = (change / prev * 100) if prev else 0.0
        result = f"{sym} 最新價 {latest:.2f}，日變化 {change:+.2f}（{pct:+.2f}%）"
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"YFinance Tool Failed：取得 {sym} 報價時發生錯誤（{e}）。"
```

---

## Fix 2 — `tools.py`: MVRV 403 → Tavily fallback

**Problem:** `mvrv_tool` catches `HTTPError 403` and returns a long error string.
Agents then write "無數據" in the dashboard.

**In `mvrv_tool`, replace the `if status == 403:` branch:**

```python
    if status == 403:
        # CryptoQuant 403: fallback to Tavily public data search
        try:
            client = _get_tavily_client()
            res = client.search(
                query="Bitcoin BTC MVRV Z-Score latest value today",
                search_depth="basic",
                max_results=3,
                topic="finance",
                days=2,
            )
            results = res.get("results", [])
            if results:
                raw = " | ".join(
                    r.get("content", "")[:200] for r in results[:3]
                )
                result = f"[Tavily備援-MVRV] {raw[:600]}"
                _set_cache(cache_key, result)
                return result
        except Exception:
            pass
        # Both failed: return a short, parseable marker
        return "MVRV：暫缺（CryptoQuant 403，需 Advanced 方案）"
```

---

## Fix 3 — `tools.py`: ML Quant graceful fallback message

**Problem:** `ml_quant_tool` returns "ML Quant Tool Failed：daily_metrics 數據不足（需至少 30 筆）"
Agents then write "ML 權重 無數據" literally in the dashboard.

**Find the two lines in `ml_quant_tool` that say `return "ML Quant Tool Failed：daily_metrics 數據不足..."` and replace with:**

```python
        if df_ind.empty or len(df_ind) < 30:
            available = len(df_ind)
            return (
                f"ML 模型建置中（已累積 {available}/30 天數據）。"
                f"請在儀表板中寫：ML 模型建置中（{available}/30天）｜部位建議：暫不適用"
            )
```

Also replace the BigQuery query failure return:
```python
        except Exception as e:
            return (
                f"ML 模型建置中（BigQuery 無歷史數據，請先執行 backfill_data.py）。"
                f"請在儀表板中寫：ML 模型建置中（需積累歷史數據）｜部位建議：暫不適用"
            )
```

---

## Fix 4 — `crew.py`: Dashboard template — graceful handling of failures

**Problem:** Task 3 for `CryptoResearchCrew` doesn't instruct Gemini how to handle tool failures.
Agents copy the raw error string directly into the dashboard.

**In `crew.py`, add this constant after `_PRICE_CHECK_RULE`:**

```python
_DASHBOARD_FALLBACK_RULES = dedent("""\
    【儀表板數據缺失處理規則（嚴格執行）】
    · 若工具回傳含 "Tool Failed" / "工具失敗" / "失效" → 改寫為「[指標] 暫缺」，禁止複製錯誤訊息
    · 若工具回傳含 "無法取得" / "資料為空" → 改寫為「[指標] 查詢中」
    · 若 VIX 工具失效 → 改用 yfinance_tool('^VIX') 重試一次
    · 若 IBIT 工具失效 → 改用 yfinance_tool('IBIT') 重試一次
    · 若 MVRV 含 "[Tavily備援-MVRV]" → 嘗試從回傳文字中解讀 Z-Score 數值
    · 若 ML 含 "建置中" → 儀表板寫：ML 建置中（XX/30天）｜部位建議 暫不適用
    · 禁止在儀表板出現 "無數據"、"工具失效"、"N/A"、"Failed" 等字樣""")
```

**In `CryptoResearchCrew.run()`, inside `final_report_task`, replace the start of description `dedent(f"""` with:**

```python
        final_report_task = Task(
            description=dedent(f"""
                【加密市場戰報排版 — Gemini 主編】

                {_DASHBOARD_FALLBACK_RULES}

                排版前數據獲取：coinglass_data_tool('open_interest')、cryptoquant_tool('inflow' 或 'outflow')、ml_quant_tool。
                若 VIX 或 IBIT 失效，立即重試：yfinance_tool('^VIX') 和 yfinance_tool('IBIT')。
                若回傳含 [Tavily 備援] 直接萃取數值，嚴禁 N/A 或工具失效字樣出現在報告。

                {_EDITOR_CONSENSUS_RULE}

                {_TELEGRAM_FORMAT_RULES}
                ... (rest unchanged)
            """),
```

---

## Fix 5 — `crew.py`: Remove hardcoded `2025` from AI search queries

**Problem:** AI researcher searches for `2025` articles but it is now 2026.

**In `AIResearchCrew.run()`, change:**

```python
# Find these lines in ai_task description and replace _YEAR_ with dynamic year:
_YEAR_ = datetime.now(timezone(timedelta(hours=8))).strftime("%Y")
```

Then update the task description's search queries by changing f-string and replacing:
- `'AI data center GPU NVIDIA infrastructure 2025'` → `f'AI data center GPU NVIDIA infrastructure {_YEAR_}'`
- `'data center power supply nuclear energy AI 2025'` → `f'data center power supply nuclear energy AI {_YEAR_}'`
- `'AI data center cooling thermal technology 2025'` → `f'AI data center cooling thermal technology {_YEAR_}'`
- `'MCP Model Context Protocol OR AI agent app 2025'` → `f'MCP Model Context Protocol OR AI agent app {_YEAR_}'`

**Full fix — in `AIResearchCrew.run()`, add before the Task:**

```python
    def run(self, exclude_context: str | None = None):
        _excl = (
            f"\n【避免重複】昨日戰報已涵蓋以下內容，請勿選用相同或高度相似的新聞，優先選取過去 24 小時內的最新資訊：\n{exclude_context}\n\n"
            if exclude_context else ""
        )
        _YEAR_ = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m")  # ← ADD THIS LINE
```

Then update all 4 hardcoded search strings in `ai_task` description to use `{_YEAR_}`.

---

## Fix 6 — `main.py`: Stronger news deduplication via title extraction

**Problem:** `fetch_exclusion_context` only stores 500-char summaries of news sections,
not the actual news titles. Articles repeat because the model sees only a vague summary.

**Add this function to `main.py` (after `_extract_section`):**

```python
def _extract_news_titles(text: str, max_titles: int = 20) -> list[str]:
    """從戰報中萃取所有新聞與推文標題，供次日排除重複使用。"""
    clean = strip_html(text)
    titles: list[str] = []
    # News: 〔新聞 N〕[date] 標題\n → grab the title line
    for m in re.finditer(r'〔新聞\s*\d+〕[^\n]*\n([^\n]{10,120})', clean):
        titles.append(m.group(1).strip())
    # Also grab lines after 〔新聞 N〕that look like titles (fallback)
    for m in re.finditer(r'〔新聞\s*\d+〕\s*([^\n]{10,120})', clean):
        candidate = m.group(1).strip()
        if candidate not in titles:
            titles.append(candidate)
    # Tweets: 〔推文 N〕 content
    for m in re.finditer(r'〔推文\s*\d+〕\s*([^\n]{10,100})', clean):
        titles.append("推文：" + m.group(1).strip())
    return titles[:max_titles]
```

**Replace `fetch_exclusion_context` with a version that uses stored titles + live extraction:**

```python
def fetch_exclusion_context(project_id: str = PROJECT_ID, metrics_table: str = METRICS_TABLE) -> str | None:
    """從 BigQuery 讀取前一日的新聞標題列表，供研究流程排除重複新聞。"""
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT grok_summary, gpt_summary, news_titles
            FROM `{metrics_table}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 36 HOUR)
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return None
        row = rows[0]

        parts: list[str] = []

        # Prefer structured news_titles column if available
        news_titles_raw = row.get("news_titles") if hasattr(row, "get") else None
        if news_titles_raw:
            parts.append("昨日已報導的新聞標題（禁止重複選用）：\n" + news_titles_raw)
        else:
            # Fallback: use summary sections
            for field in ("grok_summary", "gpt_summary"):
                val = row.get(field) if hasattr(row, "get") else None
                if val:
                    parts.append(val)

        s = "\n\n".join(parts) if parts else None
        if s and len(s) > 2000:
            s = s[:2000] + "\n…[truncated]"
        return s
    except Exception as e:
        logger.warning("Could not fetch exclusion context from BigQuery: %s", e)
        return None
```

**In `extract_and_save_metrics`, add `news_titles` extraction and storage:**

```python
def extract_and_save_metrics(report_text: str, project_id: str = PROJECT_ID) -> None:
    """從戰報文字萃取關鍵指標並寫入 BigQuery daily_metrics 資料表。"""
    metrics_table = f"{project_id}.market_data.daily_metrics"
    clean_text = strip_html(report_text)

    # ... (existing DXY, ETF, risk, MVRV extraction unchanged) ...

    # ── NEW: Extract news titles for deduplication ──────────────────
    all_titles = _extract_news_titles(report_text, max_titles=25)
    news_titles_str = "\n".join(f"· {t}" for t in all_titles) if all_titles else None
    logger.info("Extracted %d news/tweet titles for deduplication.", len(all_titles))

    # ── BigQuery schema — add news_titles column ─────────────────────
    schema = [
        bigquery.SchemaField("timestamp",          "TIMESTAMP"),
        bigquery.SchemaField("dxy",                "FLOAT"),
        bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
        bigquery.SchemaField("avg_risk_score",     "FLOAT"),
        bigquery.SchemaField("gpu_b200_price",     "FLOAT"),
        bigquery.SchemaField("grok_summary",       "STRING"),
        bigquery.SchemaField("gpt_summary",        "STRING"),
        bigquery.SchemaField("mvrv_z_score",       "FLOAT"),
        bigquery.SchemaField("news_titles",        "STRING"),   # ← NEW
    ]

    # ... (existing create_table + schema migration logic unchanged) ...

    row = {
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "dxy":               dxy,
        "etf_flow_millions": etf_flow,
        "avg_risk_score":    avg_risk,
        "gpu_b200_price":    gpu_b200,
        "grok_summary":      grok_summary,
        "gpt_summary":       gpt_summary,
        "mvrv_z_score":      mvrv_z,
        "news_titles":       news_titles_str,   # ← NEW
    }
    # ... (existing insert_rows_json unchanged) ...
```

---

## Fix 7 — `crew.py`: Stricter freshness filter for all news searches

**Add this constant to `crew.py` after `_PRICE_CHECK_RULE`:**

```python
_FRESHNESS_RULE = (
    "【新聞新鮮度規則】所有新聞必須為過去 48 小時內發布。"
    "若搜尋結果中無法確認發布時間，或時間明顯超過 48h，強制跳過並重新搜尋。"
    "禁止使用 3 天前的舊新聞填充報告。"
)
```

**In `CryptoResearchCrew.run()`, inject `{_FRESHNESS_RULE}` as first line of `crypto_task` description, right after `{_excl}`.**

**In `AIResearchCrew.run()`, inject `{_FRESHNESS_RULE}` as first line of `ai_task` description, right after `{_excl}`.**

---

## Apply order

1. `tools.py` — Fix 1 (yfinance), Fix 2 (MVRV), Fix 3 (ML message)
2. `main.py` — Fix 6 (news titles extraction + BigQuery storage + exclusion context)
3. `crew.py` — Fix 4 (dashboard fallback rules), Fix 5 (year), Fix 7 (freshness rule)

After applying, run with `SKIP_TELEGRAM=1 SKIP_BIGQUERY=1` once to verify no tool crashes appear in stdout.

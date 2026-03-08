# Fix: Stock Price N/A + News Investment Signal Redesign

---

## Issue 1 — 現價 N/A (API 取價異常) in Trade Recommendations

### Root Cause
`yfinance_tool('AMD')` and `yfinance_tool('BE')` are failing due to the MultiIndex crash
(same as VIX/IBIT in FIX_BUGS.md Fix 1). The Gemini agent then writes:
- 現價：N/A（API 取價異常）
- 進場：當前價位  ← completely useless

### Fix A — `tools.py`: Hardened `_yf_quote` with retry logic

Replace the entire `_yf_quote` function with this version that:
1. Fixes the MultiIndex crash
2. Retries with a different period if the first download is empty
3. Returns a clear marker (not "Failed") so the agent knows to retry with another symbol format

```python
def _yf_quote(symbol: str) -> str:
    """
    取得單一標的最新報價。
    修正：yfinance >= 0.2.38 MultiIndex crash；加入重試與備援。
    """
    import pandas as pd

    sym = (symbol or "").strip()
    if not sym:
        return "YFinance Tool Failed：symbol 不可為空。"

    cache_key = ("yfinance_quote", sym.upper())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    def _download_close(ticker: str, period: str = "5d") -> float | None:
        """Download and safely extract the latest close price."""
        try:
            df = yf.download(ticker, period=period, interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None
            close_col = df["Close"]
            # Fix: yfinance >= 0.2.38 MultiIndex case
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            close_col = close_col.dropna()
            if close_col.empty:
                return None
            return float(close_col.iloc[-1])
        except Exception:
            return None

    def _download_prev(ticker: str, period: str = "5d") -> float | None:
        """Download and safely extract the previous close price."""
        try:
            df = yf.download(ticker, period=period, interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty:
                return None
            close_col = df["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            close_col = close_col.dropna()
            if len(close_col) < 2:
                return None
            return float(close_col.iloc[-2])
        except Exception:
            return None

    # Attempt 1: direct symbol
    latest = _download_close(sym)

    # Attempt 2: if crypto-style (no dash), try adding -USD
    if latest is None and "-" not in sym and sym.upper() not in ("SPY", "QQQ", "IBIT", "AMD", "NVDA", "TSLA"):
        latest = _download_close(f"{sym}-USD")
        if latest is not None:
            sym = f"{sym}-USD"

    # Attempt 3: extend period to 10d (handles long weekends / holidays)
    if latest is None:
        latest = _download_close(sym, period="10d")

    if latest is None:
        return f"YFinance Tool Failed：{sym} 無法取得報價（市場可能休市或代碼錯誤）。"

    prev = _download_prev(sym) or latest
    change = latest - prev
    pct = (change / prev * 100) if prev else 0.0
    result = f"{sym} 現價 {latest:.2f} USD，日變化 {change:+.2f}（{pct:+.2f}%）"
    _set_cache(cache_key, result)
    return result
```

### Fix B — `crew.py`: Hard rule against N/A prices in trade recommendations

**Add this constant after `_PRICE_CHECK_RULE`:**

```python
_TRADE_PRICE_RULE = dedent("""\
    【交易建議價格規則（嚴格執行）】
    ① 必須先呼叫 yfinance_tool('SYMBOL') 取得現價，再填入進場/目標/停損
    ② 若 yfinance_tool 回傳含 "Failed" 或空值：
       - 立刻用 yfinance_multi_tool('SYMBOL1,SYMBOL2') 重試
       - 仍失敗則換一個可取得報價的標的，禁止使用無法取價的標的
    ③ 禁止填入 "N/A"、"API 取價異常"、"當前價位"、"市場價" 等模糊字樣
    ④ 進場價 = yfinance 回傳現價 ± 合理滑點（≤ 0.5%）
    ⑤ 目標價 = 現價 × (1 + 目標%)，停損價 = 現價 × (1 - 停損%)，全部計算出具體數字
    ⑥ 格式：現價 <code>$XXX.XX</code>，進場 <code>$XXX.XX</code>，目標 <code>$XXX.XX (+Y%)</code>，停損 <code>$XXX.XX (-Z%)</code>""")
```

**In `AIResearchCrew`, replace `_PRICE_CHECK_RULE` with `{_TRADE_PRICE_RULE}` inside `final_report_task` description:**

```python
                === 投資標的 ===
                在【AI 產業鏈精準操作 (US Equities)】提供 2 個美股標的。
                {_TRADE_PRICE_RULE}
                每標的含：信心水準⭐️1~5、資金佔比、進場/目標/停損（具體數字）、敘事邏輯。
```

**In `CryptoResearchCrew`, same replacement inside `final_report_task`:**

```python
                === 投資標的 ===
                在【資金流向與精準操作 (Crypto)】提供 1 單邊標的（非 BTC）+ 1 配對交易。
                {_TRADE_PRICE_RULE}
                加密貨幣 symbol 必須加 '-USD'（如 SOL-USD, ETH-USD）。
```

---

## Issue 2 — Redesign News Investment Signal Format

### Problem
Current format:
```
🛸 Grok 利多：[generic analysis]
🛸 Grok 利空：[generic analysis]
IMPACT：弱利多｜NARRATIVE：Infra
```
- Does not name specific tradeable assets
- No time horizon
- "利多/利空" without a subject is meaningless (利多 for WHO? which asset?)
- Investors cannot quickly act on it

### New Design: 投資解讀框架 (Investment Reading Framework)

Each news item should end with a structured **投資解讀** block that answers:
- **哪個資產受影響** (which specific ticker)
- **方向** (long/short/watch)
- **時效** (1-7d / 1月 / 季度)
- **IMPACT** (signal strength)
- **主編共識** (one actionable sentence)

### Fix C — `crew.py`: Replace `_NEWS_FORMAT` and `_IMPACT_TAG`

**Replace the existing constants:**

```python
# BEFORE (delete these):
_NEWS_FORMAT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM] 新聞標題
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1~2 句）""")

_IMPACT_TAG = "IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）｜NARRATIVE：FOMO/FUD/Infra/Regulation/Other"

# AFTER (replace with):
_NEWS_FORMAT = dedent("""\
    〔新聞 N〕[MM/DD HH:MM UTC+8] 新聞標題（若時間不明確標 [近24h] 或 [近48h]）
    來源：xxx｜性質：confirmed / likely / unverified rumor
    摘要：（1 句，聚焦事件本身）""")

_IMPACT_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker 或幣種，如 BTC / ETH / AMD / NVDA / IBIT，可多個]
    📈 做多機會：[標的] — [1句，說明受益原因與觸發條件]
    📉 做空風險：[標的] — [1句，說明受害原因與風險情境]
    ⏱️ 時效：短期(1-7天) / 中期(2-4週) / 長期(1季+)（三選一）
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）""")
```

**Update the tweet format constant (add after `_IMPACT_TAG`):**

```python
_TWEET_IMPACT_TAG = dedent("""\
    📍 受影響資產：[具體 Ticker]
    🎯 IMPACT：強利空/弱利空/中性/弱利多/強利多（五選一）
    ⏱️ 時效：短期 / 中期 / 長期""")
```

### Fix D — `crew.py`: Update CryptoResearchCrew Task 1 news format

**In `crypto_task` description, replace the news section format:**

```python
                === 幣圈新聞（3 則）===
                優先：ETF 資金流、槓桿清算、鏈上流向、做市商操作。至少一則來自 CryptoPanic。
                每則格式（標註發布時間，無精確時間則 [近24h]/[近48h]）：
                {_NEWS_FORMAT}
                🛸 Grok 研判：2~3 句，必須明確說明「哪個標的」受影響及「為何」
                {_IMPACT_TAG}

                === 背離與衍生品 ===
                · FOMO + MVRV>7 + 巨鯨轉帳 → 標示「聰明錢出貨警告」
                · 全網悲觀 + MVRV<0 + 巨鯨平靜 → 標示「散戶盲目恐慌」
                · 資金費率極正 + 多頭過熱 → 標示「多頭清算風險」
                · 剛發生巨額多頭爆倉 → 標示「流動性洗盤，左側建倉條件」

                === 幣圈推文（5 則）===
                每則：
                〔推文 N〕[MM/DD] <blockquote>推文原文（中文或英文原文）</blockquote>
                簡述：（1句）
                🛸 Grok 研判：指出具體受益/受害幣種 + 1句理由
                {_TWEET_IMPACT_TAG}
```

### Fix E — `crew.py`: Update AIResearchCrew Task 1 news format

**In `ai_task` description, replace each section's format:**

```python
                每則格式（搜尋結果需確認發布時間 <48h）：
                {_NEWS_FORMAT}
                🤖 GPT 研判：2~3 句，必須明確說明「哪個美股標的或 ETF」受影響及投資含義
                {_IMPACT_TAG}
```

**And for tweets:**

```python
                === AI 推文（5 則）===
                x_search_tool: f'MCP Model Context Protocol OR AI agent app {_YEAR_}'
                聚焦：AI 應用落地、MCP 發展、Agent 框架。
                每則：
                〔推文 N〕[MM/DD] <blockquote>推文原文</blockquote>
                簡述：（1句）
                🤖 GPT 研判：指出具體受益美股（如 MSFT/PLTR/AI/SMCI）+ 1句理由
                {_TWEET_IMPACT_TAG}
```

### Fix F — `crew.py`: Update Task 3 (Gemini editor) to enforce the new format

**In both `CryptoResearchCrew.final_report_task` and `AIResearchCrew.final_report_task`,
update the section format description:**

For Crypto Task 3, replace:
```python
                【幣圈新聞】3 則：標題/來源/摘要/IMPACT/💎主編共識
```
With:
```python
                【幣圈新聞】3 則，每則嚴格按以下格式：
                  標題/來源/摘要
                  📍 受影響資產：[具體幣種 Ticker]
                  📈 做多機會：[幣種] — [原因]
                  📉 做空風險：[幣種] — [原因]
                  ⏱️ 時效：短期/中期/長期
                  🎯 IMPACT：[五選一]
                  💎 <b>主編共識</b>：[1句最終操作判斷，必須點名具體標的]
```

For Crypto Task 3 tweets, replace:
```python
                【幣圈推文討論】5 則：<blockquote>原文</blockquote>/簡述/IMPACT/💎主編共識
```
With:
```python
                【幣圈推文討論】5 則，每則：
                  <blockquote>原文</blockquote>
                  簡述（1句）｜📍 受影響資產：[Ticker]｜⏱️ 時效｜🎯 IMPACT
                  💎 <b>主編共識</b>：[1句操作判斷]
```

For AI Task 3, replace:
```python
                【AI 基建現況】3 則：標題/來源/摘要/IMPACT/💎主編共識
                【AI 投資案】3 則（同上格式）
                【最新 AI 模型】3 則（摘要含模型特色）
```
With:
```python
                【AI 基建現況】3 則，每則嚴格按格式：
                  標題/來源/摘要
                  📍 受影響資產：[具體美股如 NVDA/AMD/VST/CEG/GEV]
                  📈 做多機會：[標的] — [原因]
                  📉 做空風險：[標的] — [原因]
                  ⏱️ 時效：短期/中期/長期
                  🎯 IMPACT：[五選一]
                  💎 <b>主編共識</b>：[1句最終判斷，點名可操作標的]
                【AI 投資案】3 則（同上格式）
                【最新 AI 模型】3 則（同上格式，摘要含模型特色與對算力/應用的影響）
```

---

## Expected Output After Fixes

### Before (current — broken):
```
現價：N/A（API 取價異常）
進場：當前價位
目標：+15%

🛸 Grok 利多：算力需求提升
🛸 Grok 利空：競爭壓力
IMPACT：弱利多｜NARRATIVE：Infra
```

### After (target — actionable):
```
· 標的：AMD
現價：$102.45，日變化 +1.23（+1.22%）
信心水準：⭐️⭐️⭐️
資金估比：10%
進場：$102.00  目標：$117.30（+15%）  停損：$94.00（-8%）
敘事邏輯：Riot 礦場轉型 AI 資料中心並簽署 10 年租約...
```

```
〔新聞 1〕[03/08 09:30] Oracle-OpenAI $40B 資料中心計畫傳出延宕
來源：WSJ｜性質：likely
摘要：Oracle 內部文件顯示原定 Q2 上線的 5 個資料中心因電力許可問題延後 6 個月。
📍 受影響資產：ORCL / BE / VST / GEV
📈 做多機會：VST — 電力短缺加速替代電源採購，VST 電力合約議價能力提升
📉 做空風險：BE（Bloom Energy）— 高度依賴大型資料中心訂單，延宕直接衝擊 backlog
⏱️ 時效：中期（2-4 週）
🎯 IMPACT：弱利空
💎 主編共識：短中期建議減持 BE，觀察 Oracle 下一份合約修訂公告再決定重新建倉時機
```

---

## Apply Order

1. `tools.py` → Fix A (`_yf_quote` hardened)
2. `crew.py` → Fix B (`_TRADE_PRICE_RULE` constant + inject into both Task 3)
3. `crew.py` → Fix C (replace `_NEWS_FORMAT`, `_IMPACT_TAG`, add `_TWEET_IMPACT_TAG`)
4. `crew.py` → Fix D (CryptoResearchCrew Task 1 news + tweet format)
5. `crew.py` → Fix E (AIResearchCrew Task 1 news + tweet format)
6. `crew.py` → Fix F (both Task 3 section format strings)

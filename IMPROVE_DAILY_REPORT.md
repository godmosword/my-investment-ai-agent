# Q-Silicon Daily Report — Improvement Cursor Prompt

Paste this entire prompt into Cursor to apply all improvements.

---

## Context

This is a CrewAI investment AI agent that generates daily crypto & AI market reports via Telegram.
The pipeline: `main.py` → `crew.py` (CryptoResearchCrew + AIResearchCrew) → `tools.py` → `visualizer.py`.

**Problems to fix across 5 areas:**
1. **Data correctness** — tools sometimes return empty/N/A, agents accept them without retry
2. **Report completeness** — validation is too loose, some sections regularly go missing
3. **Telegram formatting** — chunks can split in the middle of sections; blockquote tags leak
4. **Chart quality** — single BTC+VIX dual-axis chart lacks context (no signal overlay)
5. **Report content quality** — trade recommendations lack real-time price validation; market regime reasoning is shallow

---

## Area 1: Data Correctness & Stable Output (`tools.py`)

### 1-A. Make tool failures explicit and parseable by agents

When any tool fails, agents currently receive vague error strings and silently skip the data.
Add a consistent structured failure prefix so agents can detect and report missing data:

```python
# In all tool failure returns, prefix with [DATA_MISSING] so agents can flag it:
# Change:
return f"CoinGlass Tool Failed：{metric} API 暫無回應。"
# To:
return f"[DATA_MISSING:{metric}] CoinGlass API 暫無回應，請在報告中標記此數據缺失。"
```

Apply this pattern to ALL tool failure return strings in `tools.py`:
- `coinglass_data_tool` all failure branches → prefix `[DATA_MISSING:coinglass_{metric}]`
- `cryptoquant_tool` failure → `[DATA_MISSING:cryptoquant_{indicator}]`
- `mvrv_tool` failure → `[DATA_MISSING:mvrv_z_score]`
- `macro_liquidity_tool` failure → `[DATA_MISSING:macro_{indicator}]`
- `yfinance_macro_tool` failure → `[DATA_MISSING:vix]` or `[DATA_MISSING:etf_flow]`
- `cryptopanic_tool` failure → `[DATA_MISSING:cryptopanic]`
- `x_search_tool` failure → `[DATA_MISSING:x_tweets]`

### 1-B. Strengthen `_parse_coinglass_funding_rate` and related parsers

The current parsers return generic failure messages when `close_raw` is None, but don't try fallback field names. Update each parser to try multiple field name variants before failing:

```python
def _parse_coinglass_funding_rate(data: list) -> str:
    if not data or not isinstance(data, list):
        return "[DATA_MISSING:funding_rate] CoinGlass 無資金費率數據。"
    latest = data[-1] if data else {}
    # Try multiple known field names from different API versions
    close_raw = (
        latest.get("close") or latest.get("open") or
        latest.get("fundingRate") or latest.get("funding_rate") or
        latest.get("value")
    )
    if close_raw is None:
        return "[DATA_MISSING:funding_rate] CoinGlass 無法解析資金費率（欄位不存在）。"
    try:
        rate_pct = float(close_raw) * 100
    except (TypeError, ValueError):
        return "[DATA_MISSING:funding_rate] CoinGlass 資金費率格式異常。"
    hint = "多頭付費給空頭，情緒偏熱" if rate_pct > 0 else "空頭付費給多頭，情緒偏冷"
    level = "🔴 極度過熱" if rate_pct > 0.05 else ("🟡 偏熱" if rate_pct > 0.01 else ("🟢 中性" if rate_pct >= -0.01 else "🔵 偏冷"))
    return f"BTC 資金費率 {rate_pct:.4f}% {level}，{hint}"
```

Apply the same multi-field fallback pattern to `_parse_coinglass_long_short_ratio`:
```python
ratio_raw = (
    latest.get("top_account_long_short_ratio") or
    latest.get("topAccountLongShortRatio") or
    latest.get("longShortRatio") or
    latest.get("ratio")
)
```

### 1-C. Add data freshness check to `extract_and_save_metrics`

Before writing to BigQuery, check that key fields are not all None (empty row):

```python
# In extract_and_save_metrics(), after building `row`, add:
non_null_count = sum(1 for v in [dxy, etf_flow, avg_risk, mvrv_z] if v is not None)
if non_null_count == 0:
    logger.warning("All key metrics are None — skipping BigQuery write to avoid empty row.")
    return
logger.info("Writing %d/4 key metrics to BigQuery.", non_null_count)
```

### 1-D. Improve DXY extraction regex in `extract_and_save_metrics`

The current pattern `r'ICE\s+DXY\s*[→\->\s→]+\s*(\d{2,3}\.\d{1,4})'` only matches "ICE DXY →".
Add broader patterns that match how agents actually write DXY values:

```python
dxy_patterns = [
    r'ICE\s+DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',        # ICE DXY → 104.5
    r'DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',               # DXY: 104.5
    r'美元指數[（(]DXY[）)]?\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',  # 美元指數(DXY) → 104.5
    r'<code>DXY[^<]*?(\d{2,3}\.\d{1,4})</code>',             # <code>DXY 104.5</code>
]
dxy = None
for pattern in dxy_patterns:
    m = re.search(pattern, clean_text, re.IGNORECASE)
    dxy = _safe_float(m)
    if dxy is not None:
        break
```

Apply the same multi-pattern approach to MVRV Z-Score extraction:
```python
mvrv_patterns = [
    r'MVRV\s*Z[-\s]?Score\s*[→\->:：]+\s*(-?\d+(?:\.\d+)?)',
    r'MVRV[：:]\s*(-?\d+(?:\.\d+)?)',
    r'<code>MVRV[^<]*?(-?\d+(?:\.\d+)?)</code>',
]
```

---

## Area 2: Validation & Reliability (`main.py`)

### 2-A. Add section-level validation to `validate_report`

The current `validate_report` only counts news/tweet markers and checks for 2 regex patterns.
Replace with a more comprehensive validation that checks each required section:

```python
def validate_report(text: str) -> dict:
    """驗證戰報是否包含足夠的新聞、推文與所有必要區塊。"""
    news_count  = len(re.findall(r'〔新聞', text))
    tweet_count = len(re.findall(r'〔推文', text))

    # Section presence checks
    has_regime    = bool(re.search(r'risk_on|risk_off|neutral', text, re.IGNORECASE))
    has_dashboard = bool(re.search(r'ICE\s*DXY|BTC\s*OI|MVRV|資金費率|模型排名|ML.*權重', text, re.IGNORECASE))
    has_crypto_trade = bool(re.search(r'資金流向與精準操作\s*\(Crypto\)|精準操作.*Crypto', text, re.IGNORECASE))
    has_ai_trade  = bool(re.search(r'AI\s*產業鏈精準操作|精準操作.*Equit', text, re.IGNORECASE))
    has_ai_section = bool(re.search(r'AI\s*市場|AI\s*基建現況|AI\s*投資案', text, re.IGNORECASE))
    has_crypto_section = bool(re.search(r'加密市場|幣圈新聞|幣圈推文', text, re.IGNORECASE))
    has_data_missing = bool(re.search(r'\[DATA_MISSING:', text))

    issues = []
    if news_count < 12:
        issues.append(f"新聞數不足（{news_count}/12）")
    if tweet_count < 10:
        issues.append(f"推文數不足（{tweet_count}/10）")
    if not has_regime:
        issues.append("缺少 market_regime 標籤（risk_on/risk_off/neutral）")
    if not has_dashboard:
        issues.append("缺少數據儀表板（DXY/MVRV/資金費率）")
    if not has_crypto_trade:
        issues.append("缺少加密市場操作建議（精準操作 Crypto）")
    if not has_ai_trade:
        issues.append("缺少 AI 美股操作建議（精準操作 US Equities）")
    if not has_ai_section:
        issues.append("缺少 AI 市場段落")
    if not has_crypto_section:
        issues.append("缺少加密市場段落")
    if has_data_missing:
        # Count missing data markers
        missing_fields = re.findall(r'\[DATA_MISSING:([^\]]+)\]', text)
        issues.append(f"資料缺失欄位：{', '.join(set(missing_fields))}")

    return {
        "valid": len([i for i in issues if "資料缺失" not in i]) == 0,  # Allow data missing but require structure
        "issues": issues,
        "news_count": news_count,
        "tweet_count": tweet_count,
        "has_data_missing": has_data_missing,
    }
```

### 2-B. Improve `_safe_chunks` to avoid breaking sections mid-way

The current chunker splits at newlines but can cut between a news item's header and its body.
Update to prefer splitting at section dividers (`────────────`) first:

```python
def _safe_chunks(text: str, max_len: int = 4000) -> list[str]:
    """切分訊息，優先在區段分隔線處切割，避免切斷新聞/推文條目。"""
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        # Priority 1: cut at section divider
        cut = remaining.rfind("────────────", 0, max_len + 1)
        if cut > max_len // 2:  # Only use if in the latter half (meaningful cut)
            cut += len("────────────")
        else:
            # Priority 2: cut at 【...】 section header
            section_matches = list(re.finditer(r'\n【', remaining[:max_len + 1]))
            if section_matches:
                cut = section_matches[-1].start()
            else:
                # Priority 3: cut at newline
                cut = remaining.rfind("\n", 0, max_len + 1)
                if cut == -1:
                    cut = max_len

        # Safety: don't leave unclosed HTML tags
        candidate = remaining[:cut]
        if candidate.count("<") > candidate.count(">"):
            last_open = candidate.rfind("<")
            if last_open > 0:
                cut = last_open

        if cut <= 0:
            cut = max_len
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")

    if remaining:
        chunks.append(remaining)
    return chunks
```

### 2-C. Add a report length sanity check

A valid report should be at least 3000 characters. Add to `validate_report`:

```python
    if len(text) < 3000:
        issues.append(f"報告過短（{len(text)} chars，預期 >3000）")
```

---

## Area 3: Telegram Formatting (`main.py` + `crew.py`)

### 3-A. Fix `sanitize_telegram_html` to handle `<a href>` links

Agents sometimes output `<a href="...">text</a>` links which Telegram supports in HTML mode.
Update the allowed tags set and handle `<a>` specially:

```python
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "blockquote", "a"}

def sanitize_telegram_html(text: str) -> str:
    """清洗 LLM 輸出的 HTML，保留 Telegram 支援的標籤。"""
    # Fix bare & not already escaped
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)

    def _fix_tag(m: re.Match) -> str:
        inner = m.group(1)
        tag_name = inner.lstrip('/').split()[0].lower()
        if tag_name == 'a':
            # Allow <a href="..."> but strip all other attributes
            if inner.startswith('/'):
                return '</a>'
            href_m = re.search(r'href=["\']([^"\']+)["\']', inner)
            if href_m:
                return f'<a href="{href_m.group(1)}">'
            return ''  # <a> without href is stripped
        return m.group(0) if tag_name in _ALLOWED_TAGS else ''

    return re.sub(r'<(/?\w+(?:\s[^>]*)?)>', _fix_tag, text)
```

### 3-B. Add Telegram formatting rules to `crew.py` prompts: require section dividers

In `_TELEGRAM_FORMAT_RULES` in `crew.py`, add explicit instruction to always include the `────────────` divider before each major section:

```python
_TELEGRAM_FORMAT_RULES = dedent("""\
    ════ Telegram HTML 格式 ════
    僅允許：<b>、<i>、<u>、<s>、<code>、<blockquote>、<a href>
    禁止：Markdown（#、**、*、_、`）、<h1~h2>、<div>、<p>、<br>、<hr>、<span>、<table>
    分隔線用 ────────────（每個大區塊前必須加）
    標題用 <b>【標題】</b>，條列用「· 」，數值用 <code>，推文用 <blockquote>
    每則新聞必須在同一區塊內完整輸出（標題/來源/摘要/IMPACT/💎 在一起，勿換段）
    禁止在新聞條目中間插入分隔線""")
```

### 3-C. Add send retry with exponential backoff for rate limits

In `_send_telegram_report`, increase retry attempts for rate limit errors (HTTP 429):

```python
def _send_telegram_report(text: str, token: str, chat_id: str, image_path: str = "daily_chart.png") -> None:
    from telebot import apihelper
    apihelper.SESSION_TIME_TO_LIVE = 5 * 60
    bot = telebot.TeleBot(token)

    # Send chart
    if os.path.exists(image_path):
        for attempt in range(3):
            try:
                with open(image_path, "rb") as f:
                    bot.send_photo(chat_id, photo=f, timeout=60)
                break
            except Exception as e:
                logger.warning("send_photo attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

    # Send text chunks with smarter retry
    cleaned = sanitize_telegram_html(text)
    for i, chunk in enumerate(_safe_chunks(cleaned)):
        sent = False
        for attempt in range(4):
            try:
                bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                sent = True
                time.sleep(0.5)  # Avoid Telegram flood limits between chunks
                break
            except Exception as e:
                err_str = str(e).lower()
                wait = 5 if "429" not in err_str else 30 * (attempt + 1)
                logger.warning("Chunk %d send attempt %d failed (wait=%ds): %s", i, attempt + 1, wait, e)
                if attempt < 3:
                    time.sleep(wait)
        if not sent:
            try:
                bot.send_message(chat_id, strip_html(chunk), timeout=60)
            except Exception as final_e:
                logger.error("Chunk %d all retries failed: %s", i, final_e)
```

---

## Area 4: Chart / Visualization (`visualizer.py`)

### 4-A. Upgrade to a 3-panel chart: BTC price, VIX + MVRV signal zone, ETF flow

Replace `generate_quant_chart` with a 3-panel chart that gives more actionable context.
The new chart shows: top panel = BTC price with 20-day MA, middle panel = VIX, bottom panel = BTC ETF flow proxy (SPY volume vs average as a bar chart).

```python
"""圖表生成模組：3 Panel BTC 量化儀表板，供戰報 Telegram 發送使用。"""
import logging
from datetime import datetime

import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)


def generate_quant_chart(filename: str = "daily_chart.png") -> None:
    """
    3 Panel 量化圖表：
    Panel 1 (上): BTC-USD 收盤價 + 20日均線
    Panel 2 (中): VIX 恐慌指數（帶危險區上色）
    Panel 3 (下): SPY 成交額 vs 5日均值比率（ETF 資金流代理）
    """
    try:
        btc = yf.download("BTC-USD", period="60d", interval="1d", progress=False, auto_adjust=True)
        vix = yf.download("^VIX",    period="60d", interval="1d", progress=False, auto_adjust=True)
        spy = yf.download("SPY",     period="65d", interval="1d", progress=False, auto_adjust=True)

        if btc.empty or vix.empty or spy.empty:
            logger.warning("visualizer: 資料不足，跳過圖表生成。")
            _fallback_chart(btc, vix, filename)
            return

        btc_close = btc["Close"].squeeze()
        vix_close = vix["Close"].squeeze()

        # SPY dollar volume and 5-day rolling average
        spy_close  = spy["Close"].squeeze()
        spy_vol    = spy["Volume"].squeeze()
        spy_dollar = (spy_close * spy_vol).dropna()
        spy_avg5   = spy_dollar.rolling(5).mean()
        spy_ratio  = (spy_dollar / spy_avg5).dropna()

        # Align on common dates
        common = btc_close.index.intersection(vix_close.index).sort_values()
        if len(common) < 10:
            logger.warning("visualizer: 共同日期不足，退回雙軸圖。")
            _fallback_chart(btc, vix, filename)
            return

        btc_aligned = btc_close.reindex(common).ffill().bfill()
        vix_aligned = vix_close.reindex(common).ffill().bfill()
        btc_ma20    = btc_aligned.rolling(20).mean()

        # SPY ratio — align to common dates (may be shorter)
        spy_common  = spy_ratio.index.intersection(common)
        spy_aligned = spy_ratio.reindex(spy_common)

        plt.style.use("dark_background")
        fig = plt.figure(figsize=(11, 8))
        gs  = gridspec.GridSpec(3, 1, height_ratios=[3, 1.5, 1.5], hspace=0.08)

        # ── Panel 1: BTC + MA20 ───────────────────────────────
        ax1 = fig.add_subplot(gs[0])
        ax1.plot(common, btc_aligned, color="#00FF88", linewidth=1.8, label="BTC-USD", zorder=3)
        ax1.plot(common, btc_ma20,    color="#FFD700", linewidth=1.0, linestyle="--", alpha=0.8, label="MA20", zorder=2)
        ax1.fill_between(common, btc_aligned, btc_aligned.min(), alpha=0.08, color="#00FF88")
        ax1.set_ylabel("BTC-USD", color="#00FF88", fontsize=9)
        ax1.tick_params(axis="y", colors="#00FF88", labelsize=8)
        ax1.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax1.legend(loc="upper left", fontsize=8, framealpha=0.3)
        ax1.set_title(
            f"Q-Silicon Daily Brief  ·  {datetime.now().strftime('%Y-%m-%d')}",
            color="white", fontsize=10, pad=6
        )
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)

        # ── Panel 2: VIX with danger zones ───────────────────
        ax2 = fig.add_subplot(gs[1], sharex=ax1)
        vix_vals = vix_aligned.values
        ax2.plot(common, vix_vals, color="#FF4444", linewidth=1.5, label="VIX")
        ax2.axhspan(30, vix_vals.max() * 1.1, alpha=0.15, color="red",    label="恐慌 >30")
        ax2.axhspan(20, 30,                    alpha=0.08, color="orange", label="警戒 20-30")
        ax2.axhline(20, color="orange", linewidth=0.5, linestyle=":")
        ax2.axhline(30, color="red",    linewidth=0.5, linestyle=":")
        ax2.set_ylabel("VIX", color="#FF4444", fontsize=9)
        ax2.tick_params(axis="y", colors="#FF4444", labelsize=8)
        ax2.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax2.legend(loc="upper left", fontsize=7, framealpha=0.3)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

        # ── Panel 3: SPY volume ratio (ETF flow proxy) ───────
        ax3 = fig.add_subplot(gs[2], sharex=ax1)
        if len(spy_aligned) > 0:
            colors_bar = ["#00BFFF" if r >= 1.0 else "#FF6666" for r in spy_aligned.values]
            ax3.bar(spy_common, spy_aligned.values, color=colors_bar, alpha=0.8, width=0.8)
            ax3.axhline(1.0, color="white", linewidth=0.5, linestyle="--", alpha=0.5)
            ax3.set_ylabel("SPY 量比", color="#00BFFF", fontsize=9)
            ax3.tick_params(axis="y", colors="#00BFFF", labelsize=8)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax3.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        ax3.tick_params(axis="x", colors="gray", labelsize=7, rotation=30)
        ax3.legend(["SPY 量比 (藍>1=放量，紅<1=縮量)"], loc="upper left", fontsize=7, framealpha=0.3)
        ax3.spines["top"].set_visible(False)
        ax3.spines["right"].set_visible(False)

        # Watermark
        fig.text(0.5, 0.5, "Q-Silicon Institutional Research",
                 fontsize=13, ha="center", va="center", alpha=0.06, rotation=20)

        fig.savefig(filename, dpi=130, bbox_inches="tight", facecolor="#0E0E0E")
        plt.close(fig)
        logger.info("3-panel quant chart saved: %s", filename)

    except Exception as e:
        logger.warning("visualizer: generate_quant_chart failed — %s", e)


def _fallback_chart(btc, vix, filename: str) -> None:
    """後備：若 SPY 資料缺失，退回原始雙軸圖。"""
    try:
        btc_close = btc["Close"].squeeze() if not btc.empty else None
        vix_close = vix["Close"].squeeze() if not vix.empty else None
        if btc_close is None or vix_close is None:
            return
        common = btc_close.index.intersection(vix_close.index).sort_values()
        if len(common) < 2:
            return
        plt.style.use("dark_background")
        fig, ax1 = plt.subplots(figsize=(10, 5))
        ax1.plot(common, btc_close.reindex(common).ffill(), color="lime", linewidth=1.5, label="BTC-USD")
        ax1.set_ylabel("BTC-USD", color="lime")
        ax1.tick_params(axis="y", colors="lime")
        ax1.legend(loc="upper left")
        ax2 = ax1.twinx()
        ax2.plot(common, vix_close.reindex(common).ffill(), color="red", linewidth=1.2, alpha=0.9, label="VIX")
        ax2.set_ylabel("VIX", color="red")
        ax2.tick_params(axis="y", colors="red")
        ax2.legend(loc="upper right")
        fig.text(0.5, 0.5, "Q-Silicon Institutional Research", fontsize=14, ha="center", va="center", alpha=0.15)
        plt.tight_layout()
        fig.savefig(filename, dpi=120, bbox_inches="tight")
        plt.close(fig)
        logger.info("Fallback chart saved: %s", filename)
    except Exception as e:
        logger.warning("_fallback_chart failed — %s", e)
```

---

## Area 5: Report Content Quality (`crew.py`)

### 5-A. Add explicit "no N/A" rule to all agent task descriptions

In the CryptoResearchCrew and AIResearchCrew, add a global data quality rule at the top of every `Task.description`:

Add this constant to the top of `crew.py` (after other shared constants):
```python
_NO_NA_RULE = "⚠️ 若任何工具回傳 [DATA_MISSING:xxx]，請在報告中明確標示「⚠️ [xxx] 數據暫缺」，禁止填入 N/A 或省略該欄位。"
```

Then inject `{_NO_NA_RULE}` as the first line inside each Task `description` block (after `{_excl}` if present).

### 5-B. Strengthen trade recommendation prompt to require real-time price validation

In `CryptoResearchCrew` Task 3 and `AIResearchCrew` Task 3, replace the current investment targets section with:

```python
# For CryptoResearchCrew Task 3 final_report_task:
_CRYPTO_TRADE_SECTION = dedent(f"""
    === 交易建議（強制執行）===
    {_PRICE_CHECK_RULE}
    必須：先呼叫 yfinance_tool('TARGET-USD') 確認現價，再填入進場/目標/停損。
    提供 1 單邊標的（非 BTC）+ 1 配對交易（多 A 空 B）。
    每標的格式：
    · 標的：[代碼]（[名稱]）
    · 現價：<code>[yfinance 查詢結果]</code>
    · 信心水準：⭐️[1-5]  資金佔比：[%]
    · 進場：[價位]  目標：[價位]（+[%]）  停損：[價位]（-[%]）
    · 敘事邏輯：[1-2 句，引用本日新聞或鏈上信號]
""")

# For AIResearchCrew Task 3:
_AI_TRADE_SECTION = dedent(f"""
    === 交易建議（強制執行）===
    {_PRICE_CHECK_RULE}
    必須：先呼叫 yfinance_tool('SYMBOL') 確認現價，再填入進場/目標/停損。
    提供 2 個美股標的（AI 產業鏈相關）。
    每標的格式：
    · 標的：[代碼]（[公司名]）
    · 現價：<code>[yfinance 查詢結果]</code>
    · 信心水準：⭐️[1-5]  資金佔比：[%]
    · 進場：[價位]  目標：[價位]（+[%]）  停損：[價位]（-[%]）
    · 敘事邏輯：[1-2 句，引用本日 AI 新聞]
""")
```

Add `_CRYPTO_TRADE_SECTION` and `_AI_TRADE_SECTION` as constants after the existing shared constants.
In each crew's Task 3, replace the `=== 投資標的 ===` section content with `{_CRYPTO_TRADE_SECTION}` or `{_AI_TRADE_SECTION}`.

### 5-C. Strengthen `market_regime` reasoning in the crypto risk critic task

In `CryptoResearchCrew` Task 2 (`review_task`), update the `market_regime` section to require quantitative justification:

```python
# Replace the market_regime section with:
"""
=== market_regime（risk_on / risk_off / neutral 三選一）===
必須量化判定：列出 VIX 數值、IBIT 日漲跌、BTC 資金費率、MVRV Z-Score 各自的信號方向。
綜合 4 項信號給出最終判定，並說明主要驅動因子（各一句話）：
· 因子 1：[VIX 信號]
· 因子 2：[IBIT/ETF 信號]
· 因子 3：[鏈上/衍生品信號（MVRV/資金費率/爆倉）]
判定規則：3/4 信號 risk_off → risk_off；3/4 risk_on → risk_on；其餘 → neutral
"""
```

### 5-D. Add OpenRouter AI model rankings freshness instruction

In `AIResearchCrew` Task 1, the `ai_momentum_tool` call currently fetches general search results that may be stale. Add date filtering:

```python
# In ai_momentum_tool in tools.py, update the search query:
query = f"OpenRouter model usage rankings top AI models {datetime.now().strftime('%Y-%m')}"
# Also add days=3 to the search:
response = client.search(query=query, search_depth="basic", max_results=3, days=3)
```

---

## Summary of All Changes

| File | Changes | Impact |
|------|---------|--------|
| `tools.py` | `[DATA_MISSING:]` prefixes, multi-field parsers, freshness in ai_momentum | Data correctness |
| `main.py` | Enhanced `validate_report`, better `_safe_chunks`, multi-pattern regex, BigQuery guard | Reliability |
| `main.py` | `sanitize_telegram_html` with `<a>` support, retry backoff | Formatting |
| `visualizer.py` | Full replacement with 3-panel chart (BTC+MA20 / VIX zones / SPY ratio) | Chart quality |
| `crew.py` | `_NO_NA_RULE`, `_CRYPTO_TRADE_SECTION`, `_AI_TRADE_SECTION`, quantified market_regime | Content quality |

**Apply in this order:** `tools.py` → `main.py` → `crew.py` → `visualizer.py`

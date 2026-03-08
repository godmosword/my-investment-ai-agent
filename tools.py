import logging
import os
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

import requests
import yfinance as yf
from crewai.tools import tool
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE

# ── 模組級 in-memory cache（同一次執行內避免重複打外部 API）────────────
# key: (tool_name, query_string)  value: (result_str, expire_timestamp)
_CACHE: dict[tuple, tuple] = {}
_CACHE_TTL = 600  # 10 分鐘內相同 query 直接回傳 cache


def _get_cache(key: tuple) -> str | None:
    if key in _CACHE:
        result, expire = _CACHE[key]
        if time.time() < expire:
            return result
        del _CACHE[key]
    return None


def _set_cache(key: tuple, value: str) -> None:
    _CACHE[key] = (value, time.time() + _CACHE_TTL)


# ═══════════════════════════════════════════════════════════════════
# BigQuery Tool（Client 只初始化一次）
# ═══════════════════════════════════════════════════════════════════

_BQ_CLIENT: bigquery.Client | None = None
_TAVILY_CLIENT = None


def _get_bq_client() -> bigquery.Client:
    global _BQ_CLIENT
    if _BQ_CLIENT is None:
        _BQ_CLIENT = bigquery.Client(project=PROJECT_ID)
    return _BQ_CLIENT


def _get_tavily_client():
    """TavilyClient singleton：同一次執行只初始化一次，統一驗證 API key。"""
    global _TAVILY_CLIENT
    if _TAVILY_CLIENT is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY 未設定。")
        from tavily import TavilyClient
        _TAVILY_CLIENT = TavilyClient(api_key=api_key)
    return _TAVILY_CLIENT


# ═══════════════════════════════════════════════════════════════════
# AI Momentum Analyzer（OpenRouter 模型熱度排名）
# ═══════════════════════════════════════════════════════════════════

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str = "openrouter_rankings") -> str:
    """獲取 OpenRouter 平台最新的模型使用量或熱門排名。metric 可省略或輸入 'openrouter_rankings'。"""
    cache_key = ("ai_momentum", "openrouter_rankings")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    query = f"OpenRouter model usage rankings top AI models {datetime.now().strftime('%Y-%m')}"
    try:
        client = _get_tavily_client()
        response = client.search(query=query, search_depth="basic", max_results=3, days=3)
        result = str(response.get("results", "No data found."))
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:openrouter_rankings] AI Momentum Tool Failed：{e}"
    except Exception as e:
        return f"[DATA_MISSING:openrouter_rankings] AI Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# Macro Liquidity Tracker（FRED）
# ═══════════════════════════════════════════════════════════════════

@tool("Macro Liquidity Tracker")
def macro_liquidity_tool(indicator: str) -> str:
    """獲取全球宏觀指標。indicator 請輸入 'M2' (貨幣供應), 'CPI' (通膨) 或 'DXY' (ICE 美指)。"""
    indicator_upper = indicator.upper()

    cache_key = ("macro", indicator_upper)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # DXY：改用 Tavily 搜尋即時 ICE DXY（避免 FRED DTWEXBGS 廣義美元指數數值異常）
    if indicator_upper == "DXY":
        try:
            client = _get_tavily_client()
            response = client.search(
                query="current ICE US Dollar Index (DXY) real-time quote today",
                search_depth="basic",
                max_results=2,
            )
            result = str(response.get("results", []))
            _set_cache(cache_key, result)
            return result
        except ValueError as e:
            return f"[DATA_MISSING:macro_DXY] Macro Tracker Failed (Tavily ICE DXY)：{e}"
        except Exception:
            return "[DATA_MISSING:macro_DXY] Macro Tracker Failed (Tavily ICE DXY)：無法取得即時 DXY 報價。"

    # M2 / CPI：使用 FRED API
    series_map = {"M2": "M2SL", "CPI": "CPIAUCSL"}
    series_id = series_map.get(indicator_upper)
    if not series_id:
        return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed。不支援的指標：{indicator}，僅支援 DXY / M2 / CPI。"

    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED)。FRED_API_KEY 未設定，無法查詢 M2 / CPI。"

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": fred_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 1,
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 403:
            return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED 403)。FRED_API_KEY 無效或權限不足。"
        if response.status_code == 429:
            return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED 429)。FRED API 流量超限，請稍後再試。"
        response.raise_for_status()
        obs = response.json().get("observations", [])
        if not obs:
            return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED)。{indicator_upper} 無歷史資料。"
        latest = obs[0]
        result = f"{indicator_upper}: {latest.get('value')} (Date: {latest.get('date')})"
        _set_cache(cache_key, result)
        return result
    except requests.Timeout:
        return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED)。連線逾時，請稍後重試。"
    except requests.RequestException:
        return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED)。網路或服務異常。"
    except Exception:
        return f"[DATA_MISSING:macro_{indicator_upper}] Macro Tracker Failed (FRED)。發生未預期錯誤。"


# ═══════════════════════════════════════════════════════════════════
# YFinance Macro & ETF Data（VIX / 美股 ETF 成交額 proxy）
# ═══════════════════════════════════════════════════════════════════

@tool("YFinance Macro & ETF Data")
def yfinance_macro_tool(metric: str = "vix") -> str:
    """
    使用 yfinance 取得 VIX 與美股 ETF 成交額 proxy：
    - metric='vix'      → 回傳最新 VIX 指數與日變化。
    - metric='etf_flow' → 使用 SPY / QQQ 的「成交額 vs 5 日均值」作為資金流向近似指標。
    """
    key = metric.lower()
    cache_key = ("yfinance", key)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        import pandas as pd

        if key == "vix":
            df = yf.download("^VIX", period="5d", interval="1d", progress=False, auto_adjust=True)
            if df.empty:
                return "[DATA_MISSING:vix] YFinance：無法取得 VIX 資料。"
            close_col = df["Close"]
            if isinstance(close_col, pd.DataFrame):
                close_col = close_col.iloc[:, 0]
            close_col = close_col.dropna()
            if close_col.empty:
                return "[DATA_MISSING:vix] YFinance：VIX 資料欄位為空。"
            latest = float(close_col.iloc[-1])
            prev = float(close_col.iloc[-2]) if len(close_col) > 1 else latest
            change = latest - prev
            pct = (change / prev * 100) if prev else 0.0
            vix_level = "🔴 恐慌" if latest >= 30 else ("🟡 警戒" if latest >= 20 else "🟢 平靜")
            result = f"VIX {latest:.2f} {vix_level}，日變化 {change:+.2f}（{pct:+.2f}%）"
        elif key == "etf_flow":
            tickers = ["SPY", "QQQ"]
            df = yf.download(
                " ".join(tickers), period="6d", interval="1d",
                progress=False, auto_adjust=True, group_by="ticker"
            )
            if df.empty:
                return "[DATA_MISSING:etf_flow] YFinance：無法取得 SPY / QQQ 資料。"

            lines: list[str] = []
            for t in tickers:
                try:
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
                return "[DATA_MISSING:etf_flow] YFinance：ETF 成交額 proxy 計算失敗或資料不足。"
            result = "；".join(lines)
        else:
            return "YFinance Tool Failed：metric 僅支援 'vix' 或 'etf_flow'。"

        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"[DATA_MISSING:{key}] YFinance Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# YFinance Quote Fetcher（單一標的報價）
# ═══════════════════════════════════════════════════════════════════

def _yf_close(ticker: str, period: str = "5d") -> float | None:
    """安全取得最新收盤價，處理 yfinance >= 0.2.38 MultiIndex。"""
    import pandas as pd
    try:
        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close_col = df["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()
        return float(close_col.iloc[-1]) if not close_col.empty else None
    except Exception:
        return None


def _yf_prev(ticker: str, period: str = "5d") -> float | None:
    """安全取得前一日收盤價。"""
    import pandas as pd
    try:
        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close_col = df["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()
        return float(close_col.iloc[-2]) if len(close_col) >= 2 else None
    except Exception:
        return None


def _yf_quote(symbol: str) -> str:
    """取得單一標的最新報價，帶 cache、MultiIndex 防護與重試。"""
    sym = (symbol or "").strip()
    if not sym:
        return "YFinance Tool Failed：symbol 不可為空。"
    cache_key = ("yfinance_quote", sym.upper())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    latest = _yf_close(sym)

    if latest is None and "-" not in sym and sym.upper() not in (
        "SPY", "QQQ", "IBIT", "AMD", "NVDA", "TSLA", "MSFT", "GOOGL", "META",
        "SMCI", "PLTR", "VST", "CEG", "GEV", "BE",
    ):
        latest = _yf_close(f"{sym}-USD")
        if latest is not None:
            sym = f"{sym}-USD"

    if latest is None:
        latest = _yf_close(sym, period="10d")

    if latest is None:
        return f"YFinance Tool Failed：{sym} 無法取得報價（市場可能休市或代碼錯誤）。"

    prev = _yf_prev(sym) or latest
    change = latest - prev
    pct = (change / prev * 100) if prev else 0.0
    result = f"{sym} 現價 {latest:.2f} USD，日變化 {change:+.2f}（{pct:+.2f}%）"
    _set_cache(cache_key, result)
    return result


@tool("YFinance Quote Fetcher")
def yfinance_tool(symbol: str) -> str:
    """
    使用 yfinance 取得單一標的的最新收盤價與日內漲跌幅。
    例如 symbol='^VIX'（恐慌指數）、'IBIT'（比特幣現貨 ETF）、'SPY' 等。
    """
    return _yf_quote(symbol)


@tool("YFinance Multi-Quote")
def yfinance_multi_tool(symbols: str) -> str:
    """批量取得多標的報價，symbols 以逗號分隔（如 '^VIX,IBIT'）。"""
    symbol_list = [s.strip() for s in (symbols or "").split(",") if s.strip()]
    if not symbol_list:
        return "YFinance Multi Tool Failed：symbols 不可為空。"
    return "\n".join(_yf_quote(s) for s in symbol_list)


# ═══════════════════════════════════════════════════════════════════
# Tavily Market Search（帶 cache，basic depth 節省費用）
# ═══════════════════════════════════════════════════════════════════

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球即時新聞，強制過濾 48 小時以上舊聞並輸出明確時間戳記。"""
    cache_key = ("market_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        client = _get_tavily_client()
        response = client.search(query=query, search_depth="basic", max_results=5, topic="news", days=2)
        results = response.get("results", [])
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=48)

        lines = [f"(系統時間：{now.strftime('%Y-%m-%d %H:%M UTC')} | 僅顯示 48 小時內新聞)"]
        kept = 0
        for r in results:
            published = r.get("published_date") or ""
            title = r.get("title") or "(無標題)"
            url = r.get("url") or ""
            snippet = (r.get("content") or "")[:300]

            try:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    continue  # Python-level filter — AI cannot override this
                age_h = int((now - pub_dt).total_seconds() / 3600)
                age_str = f"{age_h}小時前" if age_h < 24 else f"{int(age_h / 24)}天前"
            except Exception:
                age_str = published or "時間不明"

            lines.append(f"\n【{age_str} | {published[:10]}】{title}\n{url}\n{snippet}")
            kept += 1

        if kept == 0:
            return f"[NO_RECENT_NEWS: 過去 48 小時內無符合條件的新聞 | query={query}]"
        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"Market Search Failed：{e}"
    except Exception as e:
        return f"Market Search Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# X Real-time Trend Search
# ═══════════════════════════════════════════════════════════════════

def _x_rapidapi_search(query: str) -> str:
    """RapidAPI Twitter 備援搜尋 (twitter154 endpoint)。"""
    key = os.getenv("RAPIDAPI_KEY", "")
    if not key:
        return "[TWEETS_UNAVAILABLE: 官方 API 失敗且 RAPIDAPI_KEY 未設定]"
    try:
        resp = requests.get(
            "https://twitter154.p.rapidapi.com/search/search",
            headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "twitter154.p.rapidapi.com"},
            params={"query": query, "section": "latest", "limit": 10, "language": "en"},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return "[NO_TWEETS_FOUND via RapidAPI]"
        return "\n".join(
            f"[{t.get('creation_date', '')[:16]}] {t.get('text', '').replace(chr(10), ' ')}"
            for t in results
        )
    except Exception as e:
        logging.getLogger(__name__).warning("RapidAPI Twitter fallback failed: %s", e)
        return "[TWEETS_UNAVAILABLE: 官方 API + RapidAPI 均失敗]"


@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X/Twitter 即時推文情緒，官方 API + RapidAPI 雙重備援，並附帶時間戳記。"""
    bearer = os.getenv("X_BEARER_TOKEN", "")
    if not bearer:
        return "[TWEETS_UNAVAILABLE: X_BEARER_TOKEN 未設定]"

    cache_key = ("x_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    _logger = logging.getLogger(__name__)
    try:
        url = "https://api.twitter.com/2/tweets/search/recent"
        params = {
            "query": f"{query} lang:en -is:retweet",
            "max_results": 10,
            "tweet.fields": "created_at,public_metrics",
        }
        resp = requests.get(
            url, headers={"Authorization": f"Bearer {bearer}"}, params=params, timeout=15
        )
        if resp.status_code == 403:
            _logger.warning("X official API: 403 (plan not authorized) — falling back to RapidAPI")
            result = _x_rapidapi_search(query)
        elif resp.status_code == 401:
            result = "[TWEETS_UNAVAILABLE: X Bearer Token 無效或已過期]"
        elif resp.status_code == 429:
            result = "[TWEETS_UNAVAILABLE: X API 速率限制，請稍後再試]"
        else:
            resp.raise_for_status()
            tweets = resp.json().get("data", [])
            if not tweets:
                result = "[NO_TWEETS_FOUND]"
            else:
                result = "\n".join(
                    f"[{t.get('created_at', '')[:16]}] {t['text'].replace(chr(10), ' ')}"
                    for t in tweets
                )
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        _logger.warning("x_search_tool official API failed: %s — falling back to RapidAPI", e)
        result = _x_rapidapi_search(query)
        _set_cache(cache_key, result)
        return result


# ═══════════════════════════════════════════════════════════════════
# CoinGlass On-chain Data
# ═══════════════════════════════════════════════════════════════════

def _tavily_fallback(query: str, label: str) -> str:
    """通用 Tavily 備援搜尋。"""
    try:
        client = _get_tavily_client()
        res = client.search(query=query, search_depth="basic", max_results=3, topic="finance")
        return f"[Tavily 備援] {str(res.get('results', []))}"
    except Exception:
        return f"[DATA_MISSING:coinglass_{label}] API 暫時無回應：CoinGlass（{label}）與 Tavily 備援均失敗。"


_TAVILY_FALLBACK_QUERIES = {
    "open_interest": "Bitcoin BTC open interest aggregated futures today billions",
    "funding_rate": "Bitcoin BTC current funding rate binance today",
    "liquidations": "Bitcoin BTC total liquidations past 24 hours crypto market",
    "long_short_ratio": "Bitcoin BTC top trader long short ratio binance today",
}

# CoinGlass API V4 endpoints（針對 BTC）
_COINGLASS_BASE = "https://open-api-v4.coinglass.com"
_COINGLASS_ENDPOINTS = {
    "open_interest": f"{_COINGLASS_BASE}/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
    "funding_rate": f"{_COINGLASS_BASE}/api/futures/funding-rate/history?exchange=Binance&symbol=BTCUSDT&interval=8h&limit=1",
    "liquidations": f"{_COINGLASS_BASE}/api/futures/liquidation/history?exchange=Binance&symbol=BTCUSDT&interval=1h&limit=24",
    "long_short_ratio": f"{_COINGLASS_BASE}/api/futures/top-long-short-account-ratio/history?exchange=Binance&symbol=BTCUSDT&interval=1d&limit=1",
}


def _parse_coinglass_funding_rate(data: list) -> str:
    """將資金費率 API 回傳解析為 Agent 友善文字。"""
    if not data or not isinstance(data, list):
        return "[DATA_MISSING:funding_rate] CoinGlass 無資金費率數據。"
    latest = data[-1] if data else {}
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


def _parse_coinglass_liquidations(data: list) -> str:
    """將清算 API 回傳解析為 Agent 友善文字（過去 24h 彙總）。"""
    if not data or not isinstance(data, list):
        return "[DATA_MISSING:liquidations] CoinGlass 無清算數據。"
    total_long = total_short = 0.0
    for item in data:
        try:
            total_long += float(item.get("long_liquidation_usd") or 0)
            total_short += float(item.get("short_liquidation_usd") or 0)
        except (TypeError, ValueError):
            continue
    total = total_long + total_short
    return f"過去 24h 總爆倉 ${total/1e6:.2f}M，其中多頭爆倉 ${total_long/1e6:.2f}M，空頭爆倉 ${total_short/1e6:.2f}M"


def _parse_coinglass_long_short_ratio(data: list) -> str:
    """將大戶多空比 API 回傳解析為 Agent 友善文字。"""
    if not data or not isinstance(data, list):
        return "[DATA_MISSING:long_short_ratio] CoinGlass 無多空比數據。"
    latest = data[-1] if data else {}
    ratio_raw = (
        latest.get("top_account_long_short_ratio") or
        latest.get("topAccountLongShortRatio") or
        latest.get("longShortRatio") or
        latest.get("ratio")
    )
    if ratio_raw is None:
        return "[DATA_MISSING:long_short_ratio] CoinGlass 無法解析大戶多空比（欄位不存在）。"
    try:
        ratio = float(ratio_raw)
    except (TypeError, ValueError):
        return "[DATA_MISSING:long_short_ratio] CoinGlass 多空比格式異常。"
    hint = "數值 > 1 代表大戶偏多" if ratio > 1 else "數值 < 1 代表大戶偏空"
    return f"最新大戶多空比為 {ratio:.2f}，{hint}"


@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。metric 請輸入 'open_interest'（未平倉）、'funding_rate'（資金費率）、'liquidations'（24h 爆倉）、'long_short_ratio'（大戶多空比）。"""
    metric_lower = metric.lower()
    supported = {"open_interest", "funding_rate", "liquidations", "long_short_ratio"}
    if metric_lower not in supported:
        return f"CoinGlass Tool Failed：不支援的 metric '{metric}'，僅支援 {', '.join(sorted(supported))}。"

    cache_key = ("coinglass", metric_lower)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    api_key = os.getenv("COINGLASS_API_KEY")
    url = _COINGLASS_ENDPOINTS.get(metric_lower)

    if api_key and url:
        try:
            headers = {"accept": "application/json", "CG-API-KEY": api_key}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                body = response.json()
                if body.get("code") == "0":
                    data = body.get("data") or []
                    if metric_lower == "open_interest":
                        result = str(data)[:2000] if data and str(data) != "[]" else ""
                    elif metric_lower == "funding_rate":
                        result = _parse_coinglass_funding_rate(data)
                    elif metric_lower == "liquidations":
                        result = _parse_coinglass_liquidations(data)
                    else:
                        result = _parse_coinglass_long_short_ratio(data)
                    if result:
                        _set_cache(cache_key, result)
                        return result
        except Exception:
            # 若 CoinGlass API 本身失敗，改走 Tavily 備援路徑。
            pass

    # CoinGlass 失敗或無 API key：依 metric 呼叫對應 Tavily 備援
    if metric_lower in _TAVILY_FALLBACK_QUERIES:
        result = _tavily_fallback(_TAVILY_FALLBACK_QUERIES[metric_lower], metric_lower)
    else:
        result = f"[DATA_MISSING:coinglass_{metric}] CoinGlass API 暫無回應，請在報告中標記此數據缺失。"
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# CryptoQuant On-chain Data
# ═══════════════════════════════════════════════════════════════════

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """獲取 BTC 交易所資金流數據。indicator 請輸入 'inflow'（流入）或 'outflow'（流出）。"""
    indicator_lower = indicator.lower()
    if indicator_lower not in ("inflow", "outflow"):
        return f"CryptoQuant Tool Failed：不支援的 indicator '{indicator}'，僅支援 inflow / outflow。"

    cache_key = ("cryptoquant", indicator_lower)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    url = f"https://api.cryptoquant.com/v1/btc/exchange-flows/{indicator_lower}?limit=1"

    if api_key:
        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json().get("result", {}).get("data", [])
                if data:
                    value = data[0].get(indicator_lower, None)
                    if value is not None:
                        result = f"BTC {indicator_lower.capitalize()}: {value} BTC"
                        _set_cache(cache_key, result)
                        return result
        except Exception:
            pass

    result = _tavily_fallback(
        f"Bitcoin BTC exchange {indicator_lower} today on-chain",
        f"CryptoQuant-{indicator_lower}",
    )
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# MVRV Z-Score（CryptoQuant On-chain Valuation）
# ═══════════════════════════════════════════════════════════════════

@tool("MVRV Z-Score Fetcher")
def mvrv_tool(window: str = "latest") -> str:
    """
    獲取 BTC MVRV Z-Score 鏈上估值指標。
    window 目前只支援 'latest'（最新一筆）。
    MVRV Z-Score 解讀：
      > 7   → 市場嚴重高估，歷史頂部區域
      3~7   → 看漲但需留意過熱風險
      0~3   → 健康多頭區間
      < 0   → 市場低估，歷史底部積累區
    """
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key:
        return "[DATA_MISSING:mvrv_z_score] MVRV Tool Failed：CRYPTOQUANT_API_KEY 未設定。"

    cache_key = ("mvrv", window)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    url = "https://api.cryptoquant.com/v1/btc/market-data/mvrv-z-score?limit=1&window=day"
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("result", {}).get("data", [])
        if not data:
            return "[DATA_MISSING:mvrv_z_score] MVRV Tool：API 回應無資料。"
        row = data[0]
        mvrv_z = row.get("mvrv_z_score", "N/A")
        date_str = row.get("date", "")
        if mvrv_z != "N/A":
            try:
                z = float(mvrv_z)
                if z > 7:
                    signal = "🔴 嚴重高估（歷史頂部區域）"
                elif z > 3:
                    signal = "🟡 看漲但注意過熱"
                elif z >= 0:
                    signal = "🟢 健康多頭區間"
                else:
                    signal = "🔵 低估積累區（歷史底部）"
            except ValueError:
                signal = "N/A"
            result = f"BTC MVRV Z-Score: {mvrv_z} ({date_str}) — {signal}"
        else:
            result = f"[DATA_MISSING:mvrv_z_score] BTC MVRV Z-Score 數據暫缺 ({date_str})"
        _set_cache(cache_key, result)
        return result
    except requests.HTTPError as e:
        status = e.response.status_code
        if status == 403:
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
            return "MVRV：暫缺（CryptoQuant 403，需 Advanced 方案）"
        if status == 429:
            return "[DATA_MISSING:mvrv_z_score] MVRV Tool Failed（HTTP 429）：CryptoQuant API 流量超限，請稍後重試。"
        return f"[DATA_MISSING:mvrv_z_score] MVRV Tool Failed（HTTP {status}）：{e}"
    except Exception as e:
        return f"[DATA_MISSING:mvrv_z_score] MVRV Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# CryptoPanic News Aggregator（幣圈原生新聞）
# ═══════════════════════════════════════════════════════════════════

@tool("CryptoPanic News Aggregator")
def cryptopanic_tool(topic: str = "bitcoin") -> str:
    """
    從 CryptoPanic 取得最新幣圈新聞（偏向原生加密媒體），強化日報新聞來源。
    topic 可輸入 'bitcoin'、'ethereum' 或任意關鍵字。
    若 CRYPTOPANIC_API_KEY 未設定，將回傳簡短錯誤訊息。
    """
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key:
        return "[DATA_MISSING:cryptopanic] CryptoPanic Tool Failed：CRYPTOPANIC_API_KEY 未設定。"

    cache_key = ("cryptopanic", topic.lower())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    params = {
        "auth_token": api_key,
        "currencies": "BTC",
        "kind": "news",
        "filter": "important",
    }
    if topic and topic.lower() not in ("bitcoin", "btc"):
        params["q"] = topic

    try:
        resp = requests.get("https://cryptopanic.com/api/v1/posts/", params=params, timeout=10)
        resp.raise_for_status()
        posts = resp.json().get("results", [])[:5]
        if not posts:
            return "CryptoPanic：目前沒有符合條件的重點新聞。"

        lines: list[str] = []
        for p in posts:
            title = p.get("title") or ""
            url = p.get("url") or ""
            created_at = p.get("created_at") or ""
            source = (p.get("source") or {}).get("title") or "unknown"
            sentiment = p.get("vote") or "neutral"
            lines.append(
                f"〔時間：{created_at}｜來源：{source}｜情緒：{sentiment}〕\n"
                f"{title}\nURL: {url}"
            )

        result = "\n\n".join(lines)
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"[DATA_MISSING:cryptopanic] CryptoPanic Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# ML Quant Signal Analyzer
# ═══════════════════════════════════════════════════════════════════

@tool("ML Quant Signal Analyzer")
def ml_quant_tool() -> str:
    """
    從 BigQuery daily_metrics 撈取過去 365 天指標，執行 ML 權重最佳化與動能訊號分析。
    回傳最佳權重配比與今日建議（做多 / 避險）。
    """
    cache_key = ("ml_quant", "v1")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        import pandas as pd
        from datetime import date, timedelta

        from backtest import optimize_ml_weights, get_latest_ml_signal
    except ImportError as e:
        return f"ML Quant Tool Failed：無法匯入 backtest 模組（{e}）。請確認 scipy 已安裝。"

    try:
        days = 365
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # 1. BigQuery daily_metrics
        query = f"""
            SELECT
                DATE(timestamp) AS date,
                AVG(dxy) AS dxy,
                AVG(etf_flow_millions) AS etf_flow_millions,
                AVG(avg_risk_score) AS avg_risk_score,
                AVG(mvrv_z_score) AS mvrv_z_score
            FROM `{METRICS_TABLE}`
            WHERE timestamp >= @cutoff
            GROUP BY date
            ORDER BY date ASC
        """
        try:
            client = _get_bq_client()
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("cutoff", "DATE", cutoff)]
            )
            df_ind = client.query(query, job_config=job_config).to_dataframe()
        except Exception as e:
            return (
                "ML 模型建置中（BigQuery 無歷史數據，請先執行 backfill_data.py）。"
                "請在儀表板中寫：ML 模型建置中（需積累歷史數據）｜部位建議：暫不適用"
            )

        if df_ind.empty or len(df_ind) < 30:
            available = len(df_ind)
            return (
                f"ML 模型建置中（已累積 {available}/30 天數據）。"
                f"請在儀表板中寫：ML 模型建置中（{available}/30天）｜部位建議：暫不適用"
            )

        df_ind["date"] = pd.to_datetime(df_ind["date"]).dt.date
        df_ind = df_ind.set_index("date").sort_index()

        # 2. CoinGecko BTC 價格
        url = (
            f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
            f"?vs_currency=usd&days={days}&interval=daily"
        )
        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            prices = resp.json().get("prices", [])
            df_btc = pd.DataFrame(prices, columns=["ts_ms", "close"])
            df_btc["date"] = pd.to_datetime(df_btc["ts_ms"], unit="ms").dt.date
            df_btc = df_btc.drop_duplicates("date").set_index("date")[["close"]].sort_index()
        except Exception as e:
            return f"ML Quant Tool Failed：CoinGecko 取得 BTC 價格失敗（{e}）。"

        # 3. 合併
        merged = df_ind.join(df_btc, how="inner")
        if merged.empty or len(merged) < 30:
            return "ML Quant Tool Failed：指標與 BTC 價格無法對齊，數據不足。"

        merged = merged.rename(columns={
            "etf_flow_millions": "etf_flow",
            "avg_risk_score": "risk_score",
            "mvrv_z_score": "mvrv_z",
        })

        # 4. 最佳化權重
        opt = optimize_ml_weights(merged)
        weights = opt.get("weights", {})
        sharpe = opt.get("sharpe", 0.0)

        # 5. 最新訊號
        signal_dict = get_latest_ml_signal(merged, weights)
        momentum = signal_dict.get("momentum_score", 0.0)
        sig = signal_dict.get("signal", "建議避險")

        w_dxy = weights.get("dxy", 0.25) * 100
        w_etf = weights.get("etf_flow", 0.25) * 100
        w_risk = weights.get("risk", 0.25) * 100
        w_mvrv = weights.get("mvrv", 0.25) * 100

        result = (
            f"ML 模型已完成過去 365 天回測最佳化。"
            f"當前最佳權重配比為 DXY: {w_dxy:.1f}%, ETF: {w_etf:.1f}%, RISK: {w_risk:.1f}%, MVRV: {w_mvrv:.1f}%。"
            f"歷史 Sharpe Ratio：{sharpe}。"
            f"今日系統綜合動能分數為 {momentum}，"
            f"量化模型強烈建議：【{sig}】。"
        )
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"ML Quant Tool Failed：BigQuery 查詢失敗（{e}）。請先執行 backfill_data.py 補入歷史數據。"


# ═══════════════════════════════════════════════════════════════════
# Rumor & Controversy Scanner（降低強度：days=7, max_results=5）
# ═══════════════════════════════════════════════════════════════════

@tool("Rumor & Controversy Scanner")
def rumor_scanner_tool(topic: str) -> str:
    """
    掃描圍繞指定主題的爭議、調查報導與未證實傳聞，只使用公開資訊來源。
    嚴格標註「傳聞性質 / 可信度」，僅供風險研究與情緒監控使用，不構成投資建議或事實認定。
    """
    cache_key = ("rumor_scanner", topic)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    query = (
        f"recent controversies, investigations, lawsuits, market manipulation accusations, "
        f"security incidents, model leaks, whistleblower reports related to {topic}. "
        "Return only publicly reported information from credible sources. "
        "For each item, clearly state if it is: confirmed, likely, or unverified rumor."
    )

    try:
        client = _get_tavily_client()
        result_data = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            topic="news",
            days=7,
        )
        raw = str(result_data.get("results", []))
        prefix = f"(當前系統時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，請過濾掉超過 48 小時的舊資訊)\n"
        result = prefix + raw
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"Rumor Scanner Failed：{e}"
    except Exception as e:
        return f"Rumor Scanner Failed: {str(e)}"

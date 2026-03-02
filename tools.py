import os
import time
import requests
from urllib.parse import quote
from crewai.tools import tool
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE, WHALE_TABLE

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
# AI Momentum Analyzer
# ═══════════════════════════════════════════════════════════════════

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str = "model_benchmarks") -> str:
    """獲取 AI 產業數據。metric 請輸入 'model_benchmarks'（LMSYS 排名）或 'big_tech_capex'（Big Tech AI 資本支出）。"""
    cache_key = ("ai_momentum", metric.lower())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    queries = {
        "model_benchmarks": "latest LMSYS Chatbot Arena ELO rankings for GPT-5, Claude 4, Gemini 3, Llama, Mistral",
        "big_tech_capex": "Amazon Microsoft Alphabet Google Meta AI capital expenditure 2025 data center spending billions",
    }
    query = queries.get(metric.lower(), queries["model_benchmarks"])
    try:
        client = _get_tavily_client()
        response = client.search(query=query, search_depth="basic", max_results=3)
        result = str(response.get("results", "No data found."))
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"AI Momentum Tool Failed：{e}"
    except Exception as e:
        return f"AI Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# Macro Liquidity Tracker
# ═══════════════════════════════════════════════════════════════════

@tool("Macro Liquidity Tracker")
def macro_liquidity_tool(indicator: str) -> str:
    """獲取全球宏觀指標。indicator 請輸入 'M2' (貨幣供應), 'CPI' (通膨) 或 'DXY' (ICE 美指)。"""
    indicator_upper = indicator.upper()

    cache_key = ("macro", indicator_upper)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        return "Macro Tracker Failed (FRED)。FRED_API_KEY 未設定，無法查詢 DXY / M2 / CPI。"

    series_map = {"DXY": "DTWEXBGS", "M2": "M2SL", "CPI": "CPIAUCSL"}
    series_id = series_map.get(indicator_upper)
    if not series_id:
        return f"Macro Tracker Failed (FRED)。不支援的指標：{indicator}，僅支援 DXY / M2 / CPI。"

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
            return "Macro Tracker Failed (FRED 403)。FRED_API_KEY 無效或權限不足。"
        if response.status_code == 429:
            return "Macro Tracker Failed (FRED 429)。FRED API 流量超限，請稍後再試。"
        response.raise_for_status()
        obs = response.json().get("observations", [])
        if not obs:
            return f"Macro Tracker Failed (FRED)。{indicator_upper} 無歷史資料。"
        latest = obs[0]
        result = f"{indicator_upper}: {latest.get('value')} (Date: {latest.get('date')})"
        _set_cache(cache_key, result)
        return result
    except requests.Timeout:
        return "Macro Tracker Failed (FRED)。連線逾時，請稍後重試。"
    except requests.RequestException:
        # 避免把可能包含 query string 的例外原文（含金鑰）回傳到上游 Agent。
        return "Macro Tracker Failed (FRED)。網路或服務異常。"
    except Exception:
        return "Macro Tracker Failed (FRED)。發生未預期錯誤。"


# ═══════════════════════════════════════════════════════════════════
# Tavily Market Search（帶 cache，basic depth 節省費用）
# ═══════════════════════════════════════════════════════════════════

@tool("Tavily Market Search")
def market_search_tool(query: str) -> str:
    """搜尋全球即時新聞。"""
    cache_key = ("market_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        client = _get_tavily_client()
        response = client.search(query=query, search_depth="basic", max_results=5, topic="news", days=1)
        result = str(response.get("results", []))
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"Market Search Failed：{e}"
    except Exception as e:
        return f"Market Search Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# X Real-time Trend Search
# ═══════════════════════════════════════════════════════════════════

@tool("X Real-time Trend Search")
def x_search_tool(query: str) -> str:
    """搜尋 X 情緒。"""
    bearer_token = os.getenv("X_BEARER_TOKEN")
    if not bearer_token:
        return "X Search Failed：X_BEARER_TOKEN 未設定。"

    cache_key = ("x_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        url = f"https://api.twitter.com/2/tweets/search/recent?query={quote(query)}&max_results=6"
        headers = {"Authorization": f"Bearer {bearer_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        tweets = response.json().get("data", [])
        result = "\n".join([f"- {t['text']}" for t in tweets]) if tweets else "No tweets found."
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"X Search Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# CoinGlass On-chain Data
# ═══════════════════════════════════════════════════════════════════

def _tavily_fallback_oi() -> str:
    """CoinGlass 失敗時以 Tavily 搜尋 BTC OI 作為備援。"""
    try:
        client = _get_tavily_client()
        res = client.search(
            query="Bitcoin BTC open interest aggregated futures today billions",
            search_depth="basic",
            max_results=3,
            topic="finance",
        )
        return f"[Tavily 備援] {str(res.get('results', []))}"
    except Exception:
        return "API 暫時無回應：CoinGlass 與 Tavily 備援均失敗。"


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
        return "CoinGlass：無資金費率數據。"
    latest = data[-1] if data else {}
    close_raw = latest.get("close") or latest.get("open")
    if close_raw is None:
        return "CoinGlass：無法解析資金費率。"
    try:
        rate_pct = float(close_raw) * 100
    except (TypeError, ValueError):
        return "CoinGlass：資金費率格式異常。"
    hint = "（若為正代表多頭付費給空頭，情緒偏熱）" if rate_pct > 0 else "（若為負代表空頭付費給多頭，情緒偏冷）"
    return f"BTC 最新資金費率為 {rate_pct:.4f}%，{hint}"


def _parse_coinglass_liquidations(data: list) -> str:
    """將清算 API 回傳解析為 Agent 友善文字（過去 24h 彙總）。"""
    if not data or not isinstance(data, list):
        return "CoinGlass：無清算數據。"
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
        return "CoinGlass：無多空比數據。"
    latest = data[-1] if data else {}
    ratio_raw = latest.get("top_account_long_short_ratio")
    if ratio_raw is None:
        ratio_raw = latest.get("topAccountLongShortRatio")
    if ratio_raw is None:
        return "CoinGlass：無法解析大戶多空比。"
    try:
        ratio = float(ratio_raw)
    except (TypeError, ValueError):
        return "CoinGlass：多空比格式異常。"
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
            pass

    if metric_lower == "open_interest":
        result = _tavily_fallback_oi()
    else:
        result = f"CoinGlass Tool Failed：{metric} API 暫無回應或 COINGLASS_API_KEY 未設定。"
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# CryptoQuant On-chain Data
# ═══════════════════════════════════════════════════════════════════

def _tavily_fallback_exchange_flow(indicator_lower: str) -> str:
    """CryptoQuant 失敗時以 Tavily 搜尋 BTC 交易所資金流作為備援。"""
    try:
        client = _get_tavily_client()
        q = "Bitcoin BTC exchange inflow" if indicator_lower == "inflow" else "Bitcoin BTC exchange outflow"
        res = client.search(
            query=f"{q} today on-chain",
            search_depth="basic",
            max_results=3,
            topic="finance",
        )
        return f"[Tavily 備援] {str(res.get('results', []))}"
    except Exception:
        return "API 暫時無回應：CryptoQuant 與 Tavily 備援均失敗。"


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
                    value = data[0].get(indicator_lower, "N/A")
                    result = f"BTC {indicator_lower.capitalize()}: {value} BTC"
                    _set_cache(cache_key, result)
                    return result
        except Exception:
            pass

    result = _tavily_fallback_exchange_flow(indicator_lower)
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
        return "MVRV Tool Failed：CRYPTOQUANT_API_KEY 未設定。"

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
            return "MVRV Tool：API 回應無資料。"
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
            result = f"BTC MVRV Z-Score: N/A ({date_str})"
        _set_cache(cache_key, result)
        return result
    except requests.HTTPError as e:
        status = e.response.status_code
        if status == 403:
            return (
                "MVRV Tool Failed（HTTP 403 Forbidden）：CryptoQuant MVRV Z-Score 端點需要 "
                "Advanced 或 Professional 方案。請至 https://cryptoquant.com/pricing 確認訂閱等級。"
            )
        if status == 429:
            return "MVRV Tool Failed（HTTP 429）：CryptoQuant API 流量超限，請稍後重試。"
        return f"MVRV Tool Failed（HTTP {status}）：{e}"
    except Exception as e:
        return f"MVRV Tool Failed: {str(e)}"


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
        return f"ML Quant Tool Failed：BigQuery 查詢失敗（{e}）。請先執行 backfill_data.py 補入歷史數據。"

    if df_ind.empty or len(df_ind) < 30:
        return "ML Quant Tool Failed：daily_metrics 數據不足（需至少 30 筆）。請先執行 backfill_data.py。"

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
            max_results=5,
            topic="news",
            days=7,
        )
        result = str(result_data.get("results", []))
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"Rumor Scanner Failed：{e}"
    except Exception as e:
        return f"Rumor Scanner Failed: {str(e)}"

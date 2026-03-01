import os
import json
import time
import requests
from urllib.parse import quote
from crewai.tools import tool, BaseTool
from google.cloud import bigquery

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
        _BQ_CLIENT = bigquery.Client(project="my-investment-ai-agent")
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


class BigQueryAnalyticsTool(BaseTool):
    name: str = "BigQuery_Market_Data_Analyzer"
    description: str = "A tool to query Bitcoin whale transactions from BigQuery."

    def _run(self, query_type: str) -> str:
        cache_key = ("bigquery", query_type)
        cached = _get_cache(cache_key)
        if cached:
            return cached

        try:
            client = _get_bq_client()

            match query_type:
                case "crypto_whale_alert":
                    query = """
                        SELECT
                            COUNT(*) as alert_count,
                            MAX(amount) as max_transfer
                        FROM `my-investment-ai-agent.market_data.btc_whale_transactions`
                        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
                        AND amount > 100
                    """
                    results = client.query(query).result()
                    for row in results:
                        result = json.dumps({
                            "status": "ok",
                            "type": "crypto_whale_alert",
                            "alert_count": row.alert_count,
                            "max_transfer_btc": row.max_transfer,
                        })
                        _set_cache(cache_key, result)
                        return result
                    result = '{"status": "ok", "message": "No whale alerts in 24h"}'
                    _set_cache(cache_key, result)
                    return result

                case _:
                    return '{"status": "error", "message": "Unknown query type."}'

        except Exception as e:
            return json.dumps({"status": "error", "message": f"BigQuery Connection Failed: {str(e)}"})


# ═══════════════════════════════════════════════════════════════════
# AI Momentum Analyzer
# ═══════════════════════════════════════════════════════════════════

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str) -> str:
    """獲取 AI 產業核心數據。metric 請輸入 'gpu_pricing' (H100/B200 租賃價) 或 'model_benchmarks' (排名)。"""
    cache_key = ("ai_momentum", metric.lower())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    queries = {
        "gpu_pricing":      "current hourly rental price for NVIDIA H100 and B200 GPUs today",
        "model_benchmarks": "latest LMSYS Chatbot Arena ELO rankings for GPT-5, Claude 4, Gemini 3"
    }
    query = queries.get(metric.lower(), "latest AI compute economy")
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

    if indicator_upper == "DXY":
        try:
            client = _get_tavily_client()
            res = client.search(
                query="current ICE US Dollar Index (DXY) real-time quote today",
                search_depth="basic",
                max_results=2,
            )
            result = str(res.get("results", "ICE DXY data not found."))
            _set_cache(cache_key, result)
            return result
        except ValueError as e:
            return f"Macro Tracker Failed (Tavily)。{e}"
        except Exception as e:
            return f"Macro Tracker Failed (Tavily ICE DXY)。詳細錯誤：{str(e)}"

    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        return "Macro Tracker Failed (FRED)。FRED_API_KEY 未設定，無法查詢 M2 / CPI。"

    series_map = {"M2": "M2SL", "CPI": "CPIAUCSL"}
    series_id = series_map.get(indicator_upper)
    if not series_id:
        return f"Macro Tracker Failed (FRED)。不支援的指標：{indicator}，僅支援 M2 與 CPI。"

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
        latest = response.json().get("observations", [{}])[0]
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
        url = f"https://api.twitter.com/2/tweets/search/recent?query={quote(query)}&max_results=10"
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

@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。metric 請輸入 'open_interest'（BTC 未平倉合約歷史）。"""
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key:
        return "CoinGlass Tool Failed：COINGLASS_API_KEY 未設定。"

    metric_lower = metric.lower()
    cache_key = ("coinglass", metric_lower)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    endpoint_map = {
        "open_interest": "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
    }
    url = endpoint_map.get(metric_lower)
    if not url:
        return f"CoinGlass Tool Failed：不支援的 metric '{metric}'，目前僅支援 'open_interest'。"

    try:
        headers = {"accept": "application/json", "coinglassSecret": api_key}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        result = str(response.json().get("data", []))[:2000]
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"CoinGlass Tool Failed: {str(e)}"


# ═══════════════════════════════════════════════════════════════════
# CryptoQuant On-chain Data
# ═══════════════════════════════════════════════════════════════════

@tool("CryptoQuant On-chain Data")
def cryptoquant_tool(indicator: str) -> str:
    """獲取 BTC 交易所資金流數據。indicator 請輸入 'inflow'（流入）或 'outflow'（流出）。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key:
        return "CryptoQuant Tool Failed：CRYPTOQUANT_API_KEY 未設定。"

    indicator_lower = indicator.lower()
    endpoint_map = {
        "inflow":  "https://api.cryptoquant.com/v1/btc/exchange-flows/inflow?limit=1",
        "outflow": "https://api.cryptoquant.com/v1/btc/exchange-flows/outflow?limit=1",
    }
    url = endpoint_map.get(indicator_lower)
    if not url:
        return f"CryptoQuant Tool Failed：不支援的 indicator '{indicator}'，僅支援 inflow / outflow。"

    cache_key = ("cryptoquant", indicator_lower)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json().get("result", {}).get("data", [])
        if data:
            value = data[0].get(indicator_lower, "N/A")
            result = f"BTC {indicator_lower.capitalize()}: {value} BTC"
        else:
            result = "No data."
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"CryptoQuant Tool Failed: {str(e)}"


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
            search_depth="advanced",
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

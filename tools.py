import logging
import os
import time
from datetime import datetime

import requests
from apify_client import ApifyClient
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
_APIFY_CLIENT: ApifyClient | None = None


def _get_bq_client() -> bigquery.Client:
    global _BQ_CLIENT
    if _BQ_CLIENT is None:
        _BQ_CLIENT = bigquery.Client(project=PROJECT_ID)
    return _BQ_CLIENT


def _get_apify_client() -> ApifyClient:
    """ApifyClient singleton：同一次執行只初始化一次。"""
    global _APIFY_CLIENT
    if _APIFY_CLIENT is None:
        token = os.getenv("APIFY_API_TOKEN")
        if not token:
            raise ValueError("APIFY_API_TOKEN 未設定。")
        _APIFY_CLIENT = ApifyClient(token)
    return _APIFY_CLIENT


def _search_with_apify(query: str, max_items: int = 8) -> str:
    """以 Apify Google Search Scraper 回傳結構化搜尋結果。"""
    client = _get_apify_client()
    actor_id = os.getenv("APIFY_SEARCH_ACTOR", "apify/google-search-scraper")
    run = client.actor(actor_id).call(run_input={
        "queries": query,
        "maxPagesPerQuery": 1,
        "resultsPerPage": max_items,
        "languageCode": "zh-TW",
    })
    dataset = client.dataset(run["defaultDatasetId"])
    items = list(dataset.iterate_items())[:max_items]
    prefix = f"(當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，請嚴格過濾超過 48 小時的舊資訊)\n"
    if not items:
        return prefix + "[DATA_MISSING:apify_search] Apify 無搜尋結果。"

    lines: list[str] = []
    for i, item in enumerate(items, 1):
        title = str(item.get("title") or item.get("headline") or item.get("name") or "(無標題)")
        source = str(item.get("source") or item.get("siteName") or item.get("domain") or "unknown")
        url = str(item.get("url") or item.get("link") or "")
        published_at = str(
            item.get("publishedAt")
            or item.get("published_at")
            or item.get("publishedTime")
            or item.get("date")
            or item.get("time")
            or "未知"
        )
        lines.append(
            f"〔{i}〕{title}\n"
            f"來源：{source}｜發布：{published_at}\n"
            f"URL: {url}"
        )
    return prefix + "\n\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# AI Momentum Analyzer（OpenRouter 模型熱度排名）
# ═══════════════════════════════════════════════════════════════════

@tool("AI Momentum Analyzer")
def ai_momentum_tool(metric: str = "openrouter_rankings") -> str:
    """使用 Apify 搜尋 OpenRouter 模型熱度排名。"""
    cache_key = ("ai_momentum", "openrouter_rankings")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    query = f"OpenRouter model usage rankings top AI models {datetime.now().strftime('%Y-%m')}"
    try:
        result = _search_with_apify(query, max_items=5)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:openrouter_rankings] AI Momentum Tool Failed：{e}"
    except Exception:
        return "[DATA_MISSING:openrouter_rankings] AI Momentum Tool Failed：Apify API 暫無回應。"


# ═══════════════════════════════════════════════════════════════════
# 搜尋工具（Apify）
# ═══════════════════════════════════════════════════════════════════

@tool("Apify Market Search")
def market_search_tool(query: str) -> str:
    """以 Apify 搜尋全球即時新聞。"""
    cache_key = ("market_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        result = _search_with_apify(query, max_items=6)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:market_search] Market Search Failed：{e}"
    except Exception:
        return "[DATA_MISSING:market_search] Market Search Failed：Apify API 暫無回應。"


# ═══════════════════════════════════════════════════════════════════
# CoinGlass On-chain Data
# ═══════════════════════════════════════════════════════════════════

# CoinGlass API V4 endpoints（針對 BTC）
_COINGLASS_BASE = "https://open-api-v4.coinglass.com"
_COINGLASS_ENDPOINTS = {
    "open_interest": f"{_COINGLASS_BASE}/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d",
    "funding_rate": f"{_COINGLASS_BASE}/api/futures/funding-rate/history?exchange=Binance&symbol=BTCUSDT&interval=8h&limit=1",
    "liquidations": f"{_COINGLASS_BASE}/api/futures/liquidation/history?exchange=Binance&symbol=BTCUSDT&interval=1h&limit=24",
    "long_short_ratio": f"{_COINGLASS_BASE}/api/futures/top-long-short-account-ratio/history?exchange=Binance&symbol=BTCUSDT&interval=1d&limit=1",
    "options_info": f"{_COINGLASS_BASE}/api/option/info?symbol=BTC",
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


def _parse_coinglass_options_info(data) -> str:
    """將 BTC 選擇權概覽 API 回傳解析為 Agent 友善文字。"""
    if not data or not isinstance(data, dict):
        return "[DATA_MISSING:options_info] CoinGlass 無 BTC 選擇權數據。"
    try:
        put_call_ratio = data.get("putCallRatio")
        max_pain = data.get("maxPain")
        total_oi = data.get("openInterest") or data.get("totalOpenInterest")
        notional = data.get("notionalValue") or data.get("totalNotionalValue")

        parts: list[str] = []
        if put_call_ratio is not None:
            pcr = float(put_call_ratio)
            hint = "偏空避險" if pcr > 1.0 else ("中性" if pcr > 0.7 else "偏多投機")
            parts.append(f"Put/Call Ratio: {pcr:.2f}（{hint}）")
        if max_pain is not None:
            parts.append(f"Max Pain: ${float(max_pain):,.0f}")
        if total_oi is not None:
            parts.append(f"選擇權 OI: {float(total_oi):,.0f} 張")
        if notional is not None:
            parts.append(f"名目價值: ${float(notional)/1e9:.2f}B")
        return " ｜ ".join(parts) if parts else "[DATA_MISSING:options_info] CoinGlass 選擇權欄位不存在。"
    except (TypeError, ValueError):
        return "[DATA_MISSING:options_info] CoinGlass 選擇權格式異常。"


@tool("CoinGlass On-chain Data")
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。metric 請輸入 'open_interest'（未平倉）、'funding_rate'（資金費率）、'liquidations'（24h 爆倉）、'long_short_ratio'（大戶多空比）、'options_info'（BTC 選擇權 Put/Call Ratio + Max Pain）。"""
    metric_lower = metric.lower()
    supported = {"open_interest", "funding_rate", "liquidations", "long_short_ratio", "options_info"}
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
                    elif metric_lower == "options_info":
                        result = _parse_coinglass_options_info(data)
                    else:
                        result = _parse_coinglass_long_short_ratio(data)
                    if result:
                        _set_cache(cache_key, result)
                        return result
        except Exception:
            # CoinGlass API 失敗，直接回傳暫無回應標記。
            pass

    result = f"[DATA_MISSING:coinglass_{metric_lower}] CoinGlass API 暫無回應。"
    _set_cache(cache_key, result)
    return result


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
# Fear & Greed Index（Alternative.me 免費 API）
# ═══════════════════════════════════════════════════════════════════

@tool("Crypto Fear & Greed Index")
def fear_greed_tool() -> str:
    """取得加密市場恐懼與貪婪指數（0-100），含今日與昨日數值及變化方向。"""
    cache_key = ("fear_greed", "latest")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    try:
        resp = requests.get(
            "https://api.alternative.me/fng/?limit=2&format=json",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return "[DATA_MISSING:fear_greed] Alternative.me 無數據。"

        today = data[0]
        today_val = int(today.get("value", 0))
        today_label = today.get("value_classification", "")

        result_parts = [f"Fear & Greed Index: {today_val}/100（{today_label}）"]

        if len(data) > 1:
            yesterday = data[1]
            yest_val = int(yesterday.get("value", 0))
            delta = today_val - yest_val
            arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
            result_parts.append(f"昨日 {yest_val}，變化 {arrow}{abs(delta)}")

        # 情緒判讀
        if today_val <= 25:
            result_parts.append("💡 極度恐懼區間，歷史上常為中期反彈買點")
        elif today_val >= 75:
            result_parts.append("⚠️ 極度貪婪區間，歷史上常為過熱訊號")

        result = " ｜ ".join(result_parts)
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        return f"[DATA_MISSING:fear_greed] Fear & Greed Tool Failed: {e}"


# ═══════════════════════════════════════════════════════════════════
# BTC ETF Flow Analyzer（Farside / SoSoValue via Apify）
# ═══════════════════════════════════════════════════════════════════

@tool("BTC ETF Flow Analyzer")
def etf_flow_tool() -> str:
    """取得最新交易日 BTC Spot ETF 淨流入/流出數據（百萬美元），含各基金明細。"""
    cache_key = ("etf_flow", "latest")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # 策略：用 Apify 搜尋 Farside / SoSoValue / TheBlock 最新 ETF flow 結構化報導
    query = (
        "Bitcoin spot ETF daily flow IBIT GBTC net inflow outflow millions "
        "site:farside.co.uk OR site:sosovalue.com OR site:theblock.co OR site:coinglass.com"
    )
    try:
        result = _search_with_apify(query, max_items=5)
        if "[DATA_MISSING" in result:
            return "[DATA_MISSING:etf_flow] 無法取得 BTC ETF 資金流數據。"
        prefix = (
            "【BTC Spot ETF 資金流（以下為搜尋結果，請從中萃取最新一日的淨流入數據）】\n"
            "必須輸出：總淨流入金額、IBIT / FBTC / GBTC 等主要基金明細。\n"
            "若無法確認具體數字，標注（數據待確認）。\n"
        )
        result = prefix + result
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:etf_flow] ETF Flow Tool Failed：{e}"
    except Exception:
        return "[DATA_MISSING:etf_flow] ETF Flow Tool Failed：Apify API 暫無回應。"


# ═══════════════════════════════════════════════════════════════════
# Macro Economic Calendar（FMP API + Apify fallback）
# ═══════════════════════════════════════════════════════════════════

@tool("Macro Economic Calendar")
def econ_calendar_tool() -> str:
    """取得未來 7 天內高重要性的美國宏觀數據公布時間（FOMC、CPI、NFP、PPI 等）。"""
    cache_key = ("econ_calendar", "weekly")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # ── 策略 A：Financial Modeling Prep 免費 API ──
    fmp_key = os.getenv("FMP_API_KEY")
    if fmp_key:
        try:
            from datetime import timedelta
            today = datetime.now()
            from_date = today.strftime("%Y-%m-%d")
            to_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
            url = (
                f"https://financialmodelingprep.com/api/v3/economic_calendar"
                f"?from={from_date}&to={to_date}&apikey={fmp_key}"
            )
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            events = resp.json()

            # 篩選高重要性 + 美國
            high_impact = [
                e for e in events
                if (e.get("impact") or "").lower() == "high"
                and (e.get("country") or "").upper() in ("US", "USA", "UNITED STATES")
            ]

            if not high_impact:
                result = "本週無高風險美國宏觀數據公布。"
                _set_cache(cache_key, result)
                return result

            lines: list[str] = []
            for i, e in enumerate(high_impact[:8], 1):
                event_name = e.get("event") or "未知事件"
                event_date = e.get("date") or "未知日期"
                estimate = e.get("estimate")
                previous = e.get("previous")
                detail = f"預期 {estimate}" if estimate else ""
                if previous:
                    detail += f"，前值 {previous}" if detail else f"前值 {previous}"
                lines.append(f"{i}. {event_date} <b>{event_name}</b>（{detail}）" if detail else f"{i}. {event_date} <b>{event_name}</b>")

            result = "本週重大美國宏觀事件：\n" + "\n".join(lines)
            _set_cache(cache_key, result)
            return result
        except Exception as e:
            logging.getLogger(__name__).warning("FMP economic calendar failed, falling back to Apify: %s", e)

    # ── 策略 B：Apify fallback ──
    try:
        query = (
            f"US economic calendar this week high impact FOMC CPI NFP PPI "
            f"{datetime.now().strftime('%Y-%m')}"
        )
        result = _search_with_apify(query, max_items=5)
        if "[DATA_MISSING" in result:
            result = "本週宏觀日曆暫無法取得，請手動查閱 Trading Economics 或 Investing.com。"
        else:
            prefix = (
                "【本週美國宏觀經濟日曆（以下為搜尋結果，請萃取高重要性事件）】\n"
                "必須輸出：事件名稱、公布日期時間（台灣時間）、市場預期值。\n"
                "若本週無重大事件，明確寫出「本週無高風險宏觀數據公布」。\n"
            )
            result = prefix + result
        _set_cache(cache_key, result)
        return result
    except Exception:
        result = "[DATA_MISSING:econ_calendar] 宏觀日曆工具失敗。"
        _set_cache(cache_key, result)
        return result


# ═══════════════════════════════════════════════════════════════════
# Rumor & Controversy Scanner（降低強度：days=7, max_results=5）
# ═══════════════════════════════════════════════════════════════════

@tool("Rumor & Controversy Scanner")
def rumor_scanner_tool(topic: str) -> str:
    """掃描爭議與傳聞（Apify 版）。"""
    cache_key = ("rumor_scanner", topic)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    query = (
        f"recent controversies investigations lawsuits market manipulation accusations related to {topic} "
        "site:reuters.com OR site:bloomberg.com OR site:coindesk.com OR site:theblock.co"
    )

    try:
        result = _search_with_apify(query, max_items=6)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:rumor_scanner] Rumor Scanner Failed：{e}"
    except Exception:
        return "[DATA_MISSING:rumor_scanner] Rumor Scanner Failed：Apify API 暫無回應。"

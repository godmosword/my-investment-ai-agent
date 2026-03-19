import logging
import os
import re
import time
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from apify_client import ApifyClient
from crewai.tools import tool
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE

logger = logging.getLogger(__name__)

# ── 模組級 in-memory cache（同一次執行內避免重複打外部 API）────────────
# key: (tool_name, query_string)  value: (result_str, expire_timestamp)
_CACHE: dict[tuple, tuple] = {}
_CACHE_TTL = 600  # 10 分鐘內相同 query 直接回傳 cache
_SOURCE_HEALTH: dict[str, dict[str, float | str]] = {
    "newsapi": {"ok": 0, "fail": 0},
    "gnews": {"ok": 0, "fail": 0},
    "apify": {"ok": 0, "fail": 0},
}
_SOURCE_HEALTH_FILE = Path(__file__).resolve().parent / ".source_health.json"
_SOURCE_HEALTH_HALFLIFE_DAYS = 7.0
_LAST_SOURCE_BQ_SYNC_TS = 0.0
_SOURCE_BQ_SYNC_INTERVAL_SEC = 120.0
_SOURCE_DAILY_LIMIT_BASE = {
    "newsapi": int(os.getenv("NEWSAPI_DAILY_CALL_LIMIT", "120")),
    "gnews": int(os.getenv("GNEWS_DAILY_CALL_LIMIT", "120")),
    "apify": int(os.getenv("APIFY_DAILY_CALL_LIMIT", "30")),
}
_SOURCE_QUOTA_STATE: dict[str, dict[str, float | str]] = {
    "newsapi": {"day": "", "used": 0.0},
    "gnews": {"day": "", "used": 0.0},
    "apify": {"day": "", "used": 0.0},
}


def _get_cache(key: tuple) -> str | None:
    if key in _CACHE:
        result, expire = _CACHE[key]
        if time.time() < expire:
            return result
        del _CACHE[key]
    return None


def _set_cache(key: tuple, value: str) -> None:
    _CACHE[key] = (value, time.time() + _CACHE_TTL)


def _append_data_as_of(body: str, source_id: str) -> str:
    """在 tool 回傳字串末尾加上 data_as_of 供 main 做時效驗證（>2h 標記 STALE）。"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"{body}\n[data_as_of: {ts}] (source={source_id})"


def _save_source_health() -> None:
    try:
        payload = {
            "newsapi": _SOURCE_HEALTH.get("newsapi", {"ok": 0, "fail": 0}),
            "gnews": _SOURCE_HEALTH.get("gnews", {"ok": 0, "fail": 0}),
            "apify": _SOURCE_HEALTH.get("apify", {"ok": 0, "fail": 0}),
        }
        _SOURCE_HEALTH_FILE.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    except Exception as e:
        logger.warning("failed to persist source health: %s", e)
    _save_source_health_to_bigquery()


def _load_source_health() -> None:
    if not _SOURCE_HEALTH_FILE.exists():
        return
    try:
        raw = json.loads(_SOURCE_HEALTH_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        for source in ("newsapi", "gnews", "apify"):
            stats = raw.get(source, {})
            if isinstance(stats, dict):
                ok = float(stats.get("ok", 0))
                fail = float(stats.get("fail", 0))
                loaded = {"ok": max(ok, 0.0), "fail": max(fail, 0.0)}
                for err_key in ("e429", "e400", "etimeout", "e5xx", "eother"):
                    loaded[err_key] = max(float(stats.get(err_key, 0.0)), 0.0)
                if "updated_at" in stats:
                    loaded["updated_at"] = str(stats.get("updated_at"))
                _SOURCE_HEALTH[source] = loaded
    except Exception as e:
        logger.warning("failed to load source health: %s", e)
    _load_source_health_from_bigquery()


def _source_health_table_id() -> str:
    # 由現有 METRICS_TABLE 推導 dataset，避免新增額外設定。
    # 例：project.dataset.table -> project.dataset.source_health_stats
    parts = METRICS_TABLE.split(".")
    if len(parts) >= 3:
        return f"{parts[0]}.{parts[1]}.source_health_stats"
    return f"{PROJECT_ID}.q_silicon.source_health_stats"


def _merge_source_health_row(source: str, row: dict[str, float | str]) -> None:
    current = _SOURCE_HEALTH.get(source, {})
    current_updated_at_raw = str(current.get("updated_at", ""))
    row_updated_at_raw = str(row.get("updated_at", ""))
    if current_updated_at_raw and row_updated_at_raw:
        try:
            current_updated_at = datetime.fromisoformat(current_updated_at_raw.replace("Z", "+00:00"))
            row_updated_at = datetime.fromisoformat(row_updated_at_raw.replace("Z", "+00:00"))
            if row_updated_at <= current_updated_at:
                return
        except Exception:
            if row_updated_at_raw <= current_updated_at_raw:
                return
    _SOURCE_HEALTH[source] = row


def _load_source_health_from_bigquery() -> None:
    if os.getenv("DISABLE_SOURCE_HEALTH_BQ", "").lower() in ("1", "true", "yes"):
        return
    try:
        client = _get_bq_client()
        table_id = _source_health_table_id()
        query = f"""
            SELECT source, ok, fail, e429, e400, etimeout, e5xx, eother, updated_at
            FROM `{table_id}`
            QUALIFY ROW_NUMBER() OVER (PARTITION BY source ORDER BY updated_at DESC) = 1
        """
        rows = list(client.query(query).result())
        for r in rows:
            source = str(r.get("source", ""))
            if source not in ("newsapi", "gnews", "apify"):
                continue
            _merge_source_health_row(
                source,
                {
                    "ok": max(float(r.get("ok") or 0.0), 0.0),
                    "fail": max(float(r.get("fail") or 0.0), 0.0),
                    "e429": max(float(r.get("e429") or 0.0), 0.0),
                    "e400": max(float(r.get("e400") or 0.0), 0.0),
                    "etimeout": max(float(r.get("etimeout") or 0.0), 0.0),
                    "e5xx": max(float(r.get("e5xx") or 0.0), 0.0),
                    "eother": max(float(r.get("eother") or 0.0), 0.0),
                    "updated_at": str(r.get("updated_at") or ""),
                },
            )
    except Exception as e:
        logger.warning("failed to load source health from bigquery: %s", e)


def _save_source_health_to_bigquery() -> None:
    global _LAST_SOURCE_BQ_SYNC_TS
    if os.getenv("DISABLE_SOURCE_HEALTH_BQ", "").lower() in ("1", "true", "yes"):
        return
    now = time.time()
    if now - _LAST_SOURCE_BQ_SYNC_TS < _SOURCE_BQ_SYNC_INTERVAL_SEC:
        return
    _LAST_SOURCE_BQ_SYNC_TS = now
    try:
        client = _get_bq_client()
        table_id = _source_health_table_id()
        schema = [
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("ok", "FLOAT"),
            bigquery.SchemaField("fail", "FLOAT"),
            bigquery.SchemaField("e429", "FLOAT"),
            bigquery.SchemaField("e400", "FLOAT"),
            bigquery.SchemaField("etimeout", "FLOAT"),
            bigquery.SchemaField("e5xx", "FLOAT"),
            bigquery.SchemaField("eother", "FLOAT"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        try:
            client.get_table(table_id)
        except Exception:
            client.create_table(table, exists_ok=True)

        rows = []
        for source in ("newsapi", "gnews", "apify"):
            stats = _SOURCE_HEALTH.get(source, {})
            updated_at = stats.get("updated_at") or datetime.now(timezone.utc).isoformat()
            rows.append(
                {
                    "source": source,
                    "ok": float(stats.get("ok", 0.0)),
                    "fail": float(stats.get("fail", 0.0)),
                    "e429": float(stats.get("e429", 0.0)),
                    "e400": float(stats.get("e400", 0.0)),
                    "etimeout": float(stats.get("etimeout", 0.0)),
                    "e5xx": float(stats.get("e5xx", 0.0)),
                    "eother": float(stats.get("eother", 0.0)),
                    "updated_at": str(updated_at),
                }
            )
        if rows:
            errs = client.insert_rows_json(table_id, rows)
            if errs:
                logger.warning("insert source health rows errors: %s", errs)
    except Exception as e:
        logger.warning("failed to save source health to bigquery: %s", e)


def _decayed_source_counts(source: str) -> tuple[float, float]:
    stats = _SOURCE_HEALTH.get(source, {"ok": 0, "fail": 0})
    ok = float(stats.get("ok", 0.0))
    fail = float(stats.get("fail", 0.0))
    updated_at_raw = stats.get("updated_at")
    if not updated_at_raw:
        return ok, fail

    try:
        updated_at = datetime.fromisoformat(str(updated_at_raw))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
    except Exception:
        return ok, fail

    now_utc = datetime.now(timezone.utc)
    age_days = max((now_utc - updated_at).total_seconds() / 86400.0, 0.0)
    decay_factor = 0.5 ** (age_days / _SOURCE_HEALTH_HALFLIFE_DAYS)
    return ok * decay_factor, fail * decay_factor


def _normalize_error_key(reason: str | None) -> str:
    r = (reason or "").strip().lower()
    if r in ("429", "rate_limit"):
        return "e429"
    if r in ("400", "bad_request"):
        return "e400"
    if r in ("timeout", "read_timeout", "connect_timeout"):
        return "etimeout"
    if r in ("5xx", "server_error"):
        return "e5xx"
    return "eother"


def _record_source_outcome(source: str, ok: bool, reason: str | None = None) -> None:
    if source not in _SOURCE_HEALTH:
        _SOURCE_HEALTH[source] = {"ok": 0, "fail": 0}
    decayed_ok, decayed_fail = _decayed_source_counts(source)
    stats = _SOURCE_HEALTH.get(source, {})
    e429 = float(stats.get("e429", 0.0))
    e400 = float(stats.get("e400", 0.0))
    etimeout = float(stats.get("etimeout", 0.0))
    e5xx = float(stats.get("e5xx", 0.0))
    eother = float(stats.get("eother", 0.0))
    if ok:
        decayed_ok += 1.0
    else:
        decayed_fail += 1.0
        err_key = _normalize_error_key(reason)
        if err_key == "e429":
            e429 += 1.0
        elif err_key == "e400":
            e400 += 1.0
        elif err_key == "etimeout":
            etimeout += 1.0
        elif err_key == "e5xx":
            e5xx += 1.0
        else:
            eother += 1.0
    _SOURCE_HEALTH[source] = {
        "ok": decayed_ok,
        "fail": decayed_fail,
        "e429": e429,
        "e400": e400,
        "etimeout": etimeout,
        "e5xx": e5xx,
        "eother": eother,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_source_health()


def _source_score(source: str) -> float:
    """
    來源健康分數（0~1）：
    - 冷啟動給 0.5（中立）
    - 有樣本後用 ok / (ok+fail)
    """
    ok, fail = _decayed_source_counts(source)
    total = ok + fail
    if total <= 0:
        return 0.5
    # 輕量先驗，避免小樣本時分數過度極端。
    return (ok + 1.0) / (total + 2.0)


def _source_health_summary() -> str:
    parts = []
    for s in ("newsapi", "gnews", "apify"):
        score = _source_score(s)
        parts.append(f"{s}:{score:.2f}")
    return " | ".join(parts)


def _source_error_summary() -> str:
    parts = []
    for s in ("newsapi", "gnews", "apify"):
        stats = _SOURCE_HEALTH.get(s, {})
        e429 = int(float(stats.get("e429", 0.0)))
        e400 = int(float(stats.get("e400", 0.0)))
        etimeout = int(float(stats.get("etimeout", 0.0)))
        e5xx = int(float(stats.get("e5xx", 0.0)))
        eother = int(float(stats.get("eother", 0.0)))
        parts.append(f"{s}:429={e429},400={e400},timeout={etimeout},5xx={e5xx},other={eother}")
    return " | ".join(parts)


def source_observability_lines() -> str:
    return (
        f"【SourceHealth】{_source_health_summary()}\n"
        f"【SourceErrors】{_source_error_summary()}\n"
        f"【SourceQuota】{_source_quota_summary()}"
    )


def _reason_from_exception(err: Exception | None) -> str:
    if err is None:
        return "other"
    if isinstance(err, requests.Timeout):
        return "timeout"
    if isinstance(err, requests.HTTPError):
        status = err.response.status_code if err.response is not None else None
        if status == 429:
            return "429"
        if status == 400:
            return "400"
        if status and 500 <= status < 600:
            return "5xx"
    msg = str(err).lower()
    if "timeout" in msg:
        return "timeout"
    if "429" in msg:
        return "429"
    if "400" in msg:
        return "400"
    return "other"


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _effective_source_limit(source: str) -> int:
    base = int(_SOURCE_DAILY_LIMIT_BASE.get(source, 100))
    score = _source_score(source)
    if score < 0.35:
        return max(1, int(base * 0.4))
    if score < 0.50:
        return max(1, int(base * 0.7))
    return base


def _quota_used(source: str) -> int:
    state = _SOURCE_QUOTA_STATE.get(source)
    today = _today_utc()
    if state is None:
        _SOURCE_QUOTA_STATE[source] = {"day": today, "used": 0.0}
        return 0
    if str(state.get("day", "")) != today:
        state["day"] = today
        state["used"] = 0.0
        return 0
    return int(float(state.get("used", 0.0)))


def _consume_source_quota(source: str) -> bool:
    used = _quota_used(source)
    limit = _effective_source_limit(source)
    if used >= limit:
        return False
    _SOURCE_QUOTA_STATE[source]["used"] = float(used + 1)
    return True


def _source_quota_summary() -> str:
    parts = []
    for s in ("newsapi", "gnews", "apify"):
        used = _quota_used(s)
        limit = _effective_source_limit(s)
        parts.append(f"{s}:{used}/{limit}")
    return " | ".join(parts)


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


_load_source_health()


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
# AI Momentum Analyzer（AI 模型熱度排名：HuggingFace → OpenRouter → RSS → Apify）
# ═══════════════════════════════════════════════════════════════════

_HF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QSilicon-AIAgent/1.0)",
    "Accept": "application/json",
}


def _hf_fetch_models() -> str | None:
    """HuggingFace 官方 API 取 text-generation 模型下載量排名，失敗回傳 None。"""
    try:
        resp = requests.get(
            "https://huggingface.co/api/models",
            params={"sort": "downloads", "direction": -1, "limit": 10, "filter": "text-generation"},
            headers=_HF_HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("HuggingFace API HTTP %s", resp.status_code)
            return None
        models = resp.json()
        if not isinstance(models, list) or not models:
            logger.warning("HuggingFace API returned empty or non-list")
            return None
        lines: list[str] = []
        for i, m in enumerate(models[:5], 1):
            name = m.get("modelId") or m.get("id") or "unknown"
            downloads = m.get("downloads") or m.get("downloadsAllTime") or 0
            likes = m.get("likes") or 0
            # 過濾掉 downloads=0 的無效條目，改選下一個
            if downloads == 0 and len(models) > i + 4:
                continue
            lines.append(
                f"Top{i}: {name}"
                f"（下載 {int(downloads):,}｜按讚 {int(likes):,}）"
            )
        if not lines:
            return None
        return "【HuggingFace AI 模型熱度 Top5（按下載量）】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("HuggingFace API failed: %s", e)
        return None


def _openrouter_fetch_models() -> str | None:
    """OpenRouter API 取模型清單（需 OPENROUTER_API_KEY），失敗回傳 None。"""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        return None
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {openrouter_key}", **_HF_HEADERS},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("OpenRouter API HTTP %s", resp.status_code)
            return None
        models = resp.json().get("data", [])
        if not models:
            return None
        lines: list[str] = []
        for i, m in enumerate(models[:5], 1):
            name = m.get("name") or m.get("id") or "unknown"
            ctx = m.get("context_length") or 0
            pricing = m.get("pricing") or {}
            prompt_price = pricing.get("prompt", "N/A")
            lines.append(
                f"Top{i}: {name}"
                f"（上下文 {int(ctx):,} tokens｜提示 ${prompt_price}/token）"
            )
        return "【OpenRouter 支援模型 Top5（API 順序，非熱度排名）】\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("OpenRouter API failed: %s", e)
        return None


def _ai_momentum_rss_fallback() -> str | None:
    """從 AI RSS 取近期熱門模型/工具新聞作為儀表板備援，失敗回傳 None。"""
    try:
        import feedparser  # noqa: PLC0415
        ai_urls = _RSS_FEEDS.get("ai", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        entries: list[tuple] = []
        for url in ai_urls[:3]:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:3]:
                    published = e.get("published_parsed") or e.get("updated_parsed")
                    if published:
                        dt = datetime(*published[:6], tzinfo=timezone.utc)
                        if dt >= cutoff:
                            entries.append((dt, e.get("title", ""), feed.feed.get("title", "AI RSS")))
            except Exception as ex:
                logger.warning("_ai_momentum_rss_fallback feed error: %s", ex)
        if not entries:
            return None
        entries.sort(key=lambda x: x[0], reverse=True)
        lines = ["【AI 熱門話題 Top5（RSS 備援，非模型排名）】"]
        for i, (dt, title, src) in enumerate(entries[:5], 1):
            lines.append(f"Top{i}: {title}（{src}｜{dt.strftime('%m/%d %H:%M')}）")
        return "\n".join(lines)
    except Exception as e:
        logger.warning("_ai_momentum_rss_fallback failed: %s", e)
        return None


@tool
def ai_momentum_tool(metric: str = "openrouter_rankings") -> str:
    """
    取得 AI 模型熱度排名。
    策略 A：HuggingFace 官方 API（免費，按下載量排名的 text-generation 模型）。
    策略 B：OpenRouter API（需 OPENROUTER_API_KEY，模型清單）。
    策略 C：AI RSS 備援（近 48h 熱門 AI 新聞標題）。
    策略 D：Apify 搜尋備援（最後手段）。
    """
    cache_key = ("ai_momentum", "openrouter_rankings")
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # ── 策略 A：HuggingFace ──
    result = _hf_fetch_models()
    if result:
        _set_cache(cache_key, result)
        return result

    # ── 策略 B：OpenRouter ──
    result = _openrouter_fetch_models()
    if result:
        _set_cache(cache_key, result)
        return result

    # ── 策略 C：RSS 備援 ──
    result = _ai_momentum_rss_fallback()
    if result:
        _set_cache(cache_key, result)
        return result

    # ── 策略 D：Apify 搜尋備援 ──
    query = (
        f"most popular AI models usage rankings downloads "
        f"site:huggingface.co OR site:artificialanalysis.ai {datetime.now().strftime('%Y-%m')}"
    )
    try:
        result = _search_with_apify(query, max_items=5)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        return f"[DATA_MISSING:openrouter_rankings] AI Momentum Tool Failed：{e}"
    except Exception:
        return "[DATA_MISSING:openrouter_rankings] AI Momentum Tool Failed：所有來源均無回應。"


# ═══════════════════════════════════════════════════════════════════
# 新聞來源 helpers（NewsAPI / GNews / RSS）— 供多個工具共用
# ═══════════════════════════════════════════════════════════════════

_RSS_FEEDS: dict[str, list[str]] = {
    "crypto": [
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://www.theblock.co/rss.xml",
        "https://decrypt.co/feed",
        "https://cointelegraph.com/rss",
    ],
    "ai": [
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/ai/feed/",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "https://www.wired.com/feed/tag/ai/latest/rss",
        "https://feeds.feedburner.com/AIweekly",
        "https://www.artificialintelligence-news.com/feed/",
    ],
}


def _build_query_candidates(query: str, min_words: int = 4) -> list[str]:
    """
    建立查詢降級候選：
    1) 原始 query
    2) 去除日期/符號後的精簡 query
    3) 更短 query（避免部分 API 400）
    """
    q = (query or "").strip()
    if not q:
        return [""]

    cleaned = re.sub(r"\b\d{4}-\d{2}\b", " ", q)  # 移除 2026-03 類月份 token
    cleaned = re.sub(r"[^\w\s:/.-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    words = cleaned.split()

    cands = [q]
    if words:
        cands.append(" ".join(words[:8]))
        if len(words) >= min_words:
            cands.append(" ".join(words[:min_words]))

    # 去重且保序
    seen: set[str] = set()
    uniq: list[str] = []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq or [q]


def _get_with_retry(url: str, *, params: dict, headers: dict | None = None, timeout: int = 10,
                    retries: int = 2, base_sleep: float = 1.2) -> requests.Response:
    """針對 429/5xx 做指數退避重試，其他錯誤直接拋出。"""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(base_sleep * (2 ** attempt))
                continue
            resp.raise_for_status()
            return resp
        except requests.HTTPError as e:
            last_err = e
            status = e.response.status_code if e.response is not None else None
            # 非重試型錯誤（例如 400）交由呼叫端決定是否降級 query
            if status not in (429, 500, 502, 503, 504):
                raise
            if attempt < retries:
                time.sleep(base_sleep * (2 ** attempt))
            else:
                raise
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(base_sleep * (2 ** attempt))
            else:
                raise
    if last_err:
        raise last_err
    raise RuntimeError("unexpected retry state")


def _newsapi_fetch(query: str) -> str:
    """NewsAPI 主流財經新聞（48h）。無 key 或無結果回傳 [DATA_MISSING:newsapi]。
    降級策略：sources 限定主流媒體 → 失敗時改用 language=en 全域搜尋（无 sources 限制）。
    """
    key = os.getenv("NEWSAPI_KEY", "")
    if not key:
        return "[DATA_MISSING:newsapi] NEWSAPI_KEY 未設定"
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 建立兩組 param 模板：(1) 主流媒體 sources 限定 (2) 全域無 sources 限制
    param_templates = [
        {
            "sources": "bloomberg,reuters,cnbc,the-wall-street-journal,financial-times",
            "sortBy": "publishedAt",
            "pageSize": 3,
            "from": from_dt,
            "apiKey": key,
        },
        {
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "from": from_dt,
            "apiKey": key,
        },
    ]

    last_err: Exception | None = None
    for base_params in param_templates:
        for cand in _build_query_candidates(query):
            params = dict(base_params)
            params["q"] = cand
            try:
                r = _get_with_retry("https://newsapi.org/v2/everything", params=params, timeout=10, retries=2)
                data = r.json()
                # NewsAPI 有時回傳 status=error 但 HTTP 200
                if data.get("status") == "error":
                    logger.warning("_newsapi_fetch API error (query=%r): %s", cand, data.get("message"))
                    last_err = RuntimeError(data.get("message", "newsapi status=error"))
                    break  # 此模板組失敗，跳到下一組 param_template
                articles = data.get("articles", [])
                if not articles:
                    continue
                _record_source_outcome("newsapi", True)
                lines = [f"【NewsAPI｜{cand}】"]
                for a in articles:
                    lines.append(
                        f"〔{a.get('publishedAt', '')[:16]}｜{a.get('source', {}).get('name', '')}〕"
                        f"{a.get('title', '')}\n{a.get('url', '')}"
                    )
                return "\n".join(lines)
            except requests.HTTPError as e:
                last_err = e
                status = e.response.status_code if e.response is not None else None
                # 400 時嘗試更短 query；429/5xx 已由 _get_with_retry 內重試
                if status == 400:
                    logger.warning("_newsapi_fetch 400 with query=%r, trying degraded query", cand)
                    continue
                logger.warning("_newsapi_fetch http error (query=%r): %s", cand, e)
                break  # 非 400 HTTP 錯誤，跳出此模板組
            except Exception as e:
                last_err = e
                logger.warning("_newsapi_fetch error (query=%r): %s", cand, e)
                break  # 網路或解析錯誤，跳出此模板組

    _record_source_outcome("newsapi", False, _reason_from_exception(last_err))
    if last_err:
        return f"[DATA_MISSING:newsapi] {last_err}"
    return "[DATA_MISSING:newsapi] 無符合條件的新聞"


def _gnews_fetch(query: str) -> str:
    """GNews 多語言新聞搜尋（48h）。無 key 或無結果回傳 [DATA_MISSING:gnews]。"""
    key = os.getenv("GNEWS_API_KEY", "")
    if not key:
        return "[DATA_MISSING:gnews] GNEWS_API_KEY 未設定"
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")
    base_params = {"lang": "en", "max": 3, "from": from_dt, "token": key}
    last_err: Exception | None = None
    for i, cand in enumerate(_build_query_candidates(query)):
        params = dict(base_params)
        params["q"] = cand
        # 降級查詢時再降 max，降低 GNews 400 機率
        if i > 0:
            params["max"] = 2
        try:
            r = _get_with_retry("https://gnews.io/api/v4/search", params=params, timeout=10, retries=2)
            articles = r.json().get("articles", [])
            if not articles:
                continue
            _record_source_outcome("gnews", True)
            lines = [f"【GNews｜{cand}】"]
            for a in articles:
                lines.append(
                    f"〔{a.get('publishedAt', '')[:16]}｜{a.get('source', {}).get('name', '')}〕"
                    f"{a.get('title', '')}\n{a.get('url', '')}"
                )
            return "\n".join(lines)
        except requests.HTTPError as e:
            last_err = e
            status = e.response.status_code if e.response is not None else None
            if status == 400:
                logger.warning("_gnews_fetch 400 with query=%r, trying degraded query", cand)
                continue
            logger.warning("_gnews_fetch http error (query=%r): %s", cand, e)
            continue
        except Exception as e:
            last_err = e
            logger.warning("_gnews_fetch error (query=%r): %s", cand, e)
            continue
    _record_source_outcome("gnews", False, _reason_from_exception(last_err))
    if last_err:
        return f"[DATA_MISSING:gnews] {last_err}"
    return "[DATA_MISSING:gnews] 無符合條件的新聞"


def _rss_fetch(category: str = "crypto") -> str:
    """feedparser 免費 RSS 抓取（48h）。不需 API key。"""
    try:
        import feedparser  # noqa: PLC0415
    except ImportError:
        return "[DATA_MISSING:rss] feedparser 未安裝，請執行 pip install feedparser"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    entries: list[tuple] = []
    for url in _RSS_FEEDS.get(category, _RSS_FEEDS["crypto"]):
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                published = e.get("published_parsed") or e.get("updated_parsed")
                if published:
                    dt = datetime(*published[:6], tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                    entries.append((dt, e.get("title", ""), e.get("link", ""),
                                    feed.feed.get("title", "RSS")))
        except Exception as ex:
            logger.warning("_rss_fetch %s error: %s", url, ex)
    entries.sort(key=lambda x: x[0], reverse=True)
    if not entries:
        return "[DATA_MISSING:rss] 近 48h 內無新文章"
    lines = [f"【RSS｜{category}】"]
    for dt, title, link, src in entries[:6]:
        lines.append(f"〔{dt.strftime('%m/%d %H:%M')}｜{src}〕{title}\n{link}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# 搜尋工具（NewsAPI → GNews → Apify 三層 fallback）
# ═══════════════════════════════════════════════════════════════════

@tool
def market_search_tool(query: str) -> str:
    """搜尋全球即時新聞（NewsAPI → GNews → Apify 三層 fallback）。"""
    cache_key = ("market_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # 第一/二層：依來源健康分數動態排序（僅在有 API key 的來源間排序）
    source_funcs: list[tuple[str, Callable[[str], str]]] = []
    if os.getenv("NEWSAPI_KEY"):
        source_funcs.append(("newsapi", _newsapi_fetch))
    if os.getenv("GNEWS_API_KEY"):
        source_funcs.append(("gnews", _gnews_fetch))
    source_funcs.sort(key=lambda x: _source_score(x[0]), reverse=True)

    for _source_name, fn in source_funcs:
        if not _consume_source_quota(_source_name):
            logger.info("skip source %s due to quota limit", _source_name)
            continue
        result = fn(query)
        if not result.startswith("[DATA_MISSING"):
            _set_cache(cache_key, result)
            return result

    # 第三層：Apify（付費，最後手段）
    if not _consume_source_quota("apify"):
        return "[DATA_MISSING:market_search] Market Search Failed：免費來源失敗，且 Apify 當日配額已用盡。"

    try:
        result = _search_with_apify(query, max_items=4)
        _record_source_outcome("apify", True)
        _set_cache(cache_key, result)
        return result
    except ValueError as e:
        _record_source_outcome("apify", False, "other")
        return f"[DATA_MISSING:market_search] Market Search Failed：{e}"
    except Exception:
        _record_source_outcome("apify", False, "other")
        return "[DATA_MISSING:market_search] Market Search Failed：所有來源均無法取得資料。"


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


def _apify_liquidations_fallback() -> str:
    """CoinGlass 爆倉數據失敗時，以 Apify 搜尋最新 24h 清算總額作為備援。"""
    query = (
        f"crypto liquidations 24h total long short million "
        f"site:coinglass.com OR site:coinstats.app OR site:theblock.co "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )
    try:
        raw = _search_with_apify(query, max_items=3)
        if "[DATA_MISSING" not in raw:
            return "【爆倉數據（Apify 搜尋備援，請從中萃取最新 24h 清算金額）】\n" + raw
    except Exception as e:
        logger.warning("_apify_liquidations_fallback failed: %s", e)
    return "[DATA_MISSING:liquidations] CoinGlass 與備援來源均無爆倉數據，請以資金費率/OI 代替判讀。"


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


# ── Binance 公開 API 備援（不需 API key）──────────────────────────

def _binance_funding_rate() -> str:
    """從 Binance 公開 API 取得 BTC 最新資金費率（不需 API key）。"""
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list):
            rate = float(data[-1].get("fundingRate", 0))
            rate_pct = rate * 100
            hint = "多頭付費給空頭，情緒偏熱" if rate_pct > 0 else "空頭付費給多頭，情緒偏冷"
            level = (
                "🔴 極度過熱" if rate_pct > 0.05 else
                ("🟡 偏熱" if rate_pct > 0.01 else
                 ("🟢 中性" if rate_pct >= -0.01 else "🔵 偏冷"))
            )
            return f"BTC 資金費率 {rate_pct:.4f}% {level}，{hint}（來源：Binance）"
    except Exception as e:
        logger.warning("Binance funding rate fallback failed: %s", e)
    return "[DATA_MISSING:funding_rate] 資金費率暫無法取得（CoinGlass + Binance 均失敗）。"


def _binance_open_interest() -> str:
    """從 Binance 公開 API 取得 BTC 未平倉合約量（不需 API key）。"""
    try:
        oi_resp = requests.get(
            "https://fapi.binance.com/fapi/v1/openInterest",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        oi_resp.raise_for_status()
        oi = float(oi_resp.json().get("openInterest", 0))
        price_resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5,
        )
        btc_price = float(price_resp.json().get("price", 0)) if price_resp.ok else 0
        oi_usd = oi * btc_price / 1e9 if btc_price else 0
        return f"BTC 未平倉合約 OI: {oi:,.0f} BTC（約 ${oi_usd:.2f}B）（來源：Binance）"
    except Exception as e:
        logger.warning("Binance OI fallback failed: %s", e)
    return "[DATA_MISSING:open_interest] OI 暫無法取得（CoinGlass + Binance 均失敗）。"


def _binance_long_short_ratio() -> str:
    """從 Binance 公開 API 取得 BTC 全球大戶多空比（不需 API key）。"""
    try:
        resp = requests.get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data and isinstance(data, list):
            ratio = float(data[-1].get("longShortRatio", 1.0))
            hint = "多方佔優" if ratio > 1 else "空方佔優"
            return f"BTC 全球多空比 {ratio:.3f}（{hint}）（來源：Binance）"
    except Exception as e:
        logger.warning("Binance long/short ratio fallback failed: %s", e)
    return "[DATA_MISSING:long_short_ratio] 多空比暫無法取得（CoinGlass + Binance 均失敗）。"


@tool
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
                        return _append_data_as_of(result, "coinglass")
        except Exception:
            # CoinGlass API 失敗，直接回傳暫無回應標記。
            pass

    # ── CoinGlass 失敗，嘗試 Binance 公開 API 備援 ──
    if metric_lower == "funding_rate":
        result = _binance_funding_rate()
    elif metric_lower == "open_interest":
        result = _binance_open_interest()
    elif metric_lower == "long_short_ratio":
        result = _binance_long_short_ratio()
    elif metric_lower == "liquidations":
        result = _apify_liquidations_fallback()
    else:
        result = f"[DATA_MISSING:coinglass_{metric_lower}] CoinGlass API 暫無回應，此指標無備援來源。"
    _set_cache(cache_key, result)
    if result.startswith("[DATA_MISSING:"):
        return result
    return _append_data_as_of(result, "coinglass")


# ═══════════════════════════════════════════════════════════════════
# CryptoPanic News Aggregator（幣圈原生新聞）
# ═══════════════════════════════════════════════════════════════════

@tool
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
# X/Twitter Trending Posts（Twitter API v2 + RapidAPI 備援）
# ═══════════════════════════════════════════════════════════════════

@tool
def x_search_tool(query: str) -> str:
    """搜尋 X/Twitter 最新 24h 高互動推文。
    需設定 TWITTER_BEARER_TOKEN（Twitter API v2 官方）或 RAPIDAPI_KEY（twitter154 備援）。
    回傳含用戶名、時間、推文內容、互動數的結構化列表。
    """
    cache_key = ("x_search", query)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # ── 策略 A：Twitter API v2 Recent Search ──
    bearer = os.getenv("TWITTER_BEARER_TOKEN")
    if bearer:
        try:
            resp = requests.get(
                "https://api.twitter.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {bearer}"},
                params={
                    "query": f"({query}) -is:retweet lang:en",
                    "max_results": 10,
                    "tweet.fields": "created_at,public_metrics",
                    "sort_order": "recency",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                tweets = resp.json().get("data", [])
                if tweets:
                    lines: list[str] = []
                    for t in tweets[:5]:
                        created = str(t.get("created_at", ""))[:16].replace("T", " ")
                        text = t.get("text", "").replace("\n", " ")[:180]
                        m = t.get("public_metrics", {})
                        lines.append(
                            f"🐦 [{created}] {text}"
                            f"（❤️{m.get('like_count', 0)} 🔁{m.get('retweet_count', 0)}）"
                        )
                    result = f"【X 即時推文｜{query}】\n" + "\n".join(lines)
                    _set_cache(cache_key, result)
                    return result
            elif resp.status_code in (401, 403):
                logger.warning("Twitter API %s: 認證失敗或訂閱方案不支援 search/recent。", resp.status_code)
            elif resp.status_code == 429:
                logger.warning("Twitter API 429: 已達速率限制。")
        except Exception as e:
            logger.warning("Twitter API v2 failed: %s", e)

    # ── 策略 B：RapidAPI twitter154 備援 ──
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if rapidapi_key:
        try:
            resp = requests.get(
                "https://twitter154.p.rapidapi.com/search/search",
                headers={
                    "X-RapidAPI-Key": rapidapi_key,
                    "X-RapidAPI-Host": "twitter154.p.rapidapi.com",
                },
                params={
                    "query": query,
                    "section": "latest",
                    "min_retweets": "5",
                    "min_likes": "10",
                    "limit": "5",
                    "language": "en",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                tweets = resp.json().get("results", [])
                if tweets:
                    lines = []
                    for t in tweets[:5]:
                        user = (t.get("user") or {}).get("username", "unknown")
                        text = (t.get("text") or "").replace("\n", " ")[:180]
                        created = str(t.get("creation_date") or "")[:16]
                        lines.append(
                            f"🐦 @{user} [{created}] {text}"
                            f"（❤️{t.get('favorite_count', 0)} 🔁{t.get('retweet_count', 0)}）"
                        )
                    result = f"【X 即時推文｜{query}】\n" + "\n".join(lines)
                    _set_cache(cache_key, result)
                    return result
        except Exception as e:
            logger.warning("RapidAPI twitter154 failed: %s", e)

    result = (
        "[DATA_MISSING:x_search] X/Twitter 搜尋失敗："
        "請設定 TWITTER_BEARER_TOKEN（Twitter API v2）或 RAPIDAPI_KEY（RapidAPI twitter154）。"
    )
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# ML Quant Signal Analyzer
# ═══════════════════════════════════════════════════════════════════

@tool
def ml_quant_tool() -> str:
    """
    從 BigQuery daily_metrics 撈取過去 365 天指標，執行 ML 權重最佳化與動能訊號分析。
    回傳最佳權重配比與今日建議（做多 / 避險）。
    """
    cache_key = ("ml_quant", "v1")
    cached = _get_cache(cache_key)
    if cached:
        return _append_data_as_of(cached, "ml_quant")

    try:
        import pandas as pd
        from datetime import date, timedelta

        from backtest import optimize_ml_weights, get_latest_ml_signal
    except ImportError as e:
        return f"ML Quant Tool Failed：無法匯入 backtest 模組（{e}）。請確認 scipy 已安裝。"

    try:
        days = 365
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # 1. BigQuery daily_metrics（P2 新增欄位以 SAFE 方式查詢，向後相容）
        query = f"""
            SELECT
                DATE(timestamp) AS date,
                AVG(dxy)                AS dxy,
                AVG(etf_flow_millions)  AS etf_flow_millions,
                AVG(avg_risk_score)     AS avg_risk_score,
                AVG(mvrv_z_score)       AS mvrv_z_score,
                AVG(IF(sentiment_score IS NOT NULL, sentiment_score, NULL)) AS sentiment_score,
                AVG(IF(sopr            IS NOT NULL, sopr,             NULL)) AS sopr,
                AVG(IF(exchange_netflow IS NOT NULL, exchange_netflow, NULL)) AS exchange_netflow
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
        except Exception:
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

        # 4. 最佳化權重（P2：動態因子，含 sentiment / sopr / exchange_netflow）
        opt = optimize_ml_weights(merged)
        weights = opt.get("weights", {})
        sharpe = opt.get("sharpe", 0.0)

        # 5. 最新訊號
        signal_dict = get_latest_ml_signal(merged, weights)
        momentum = signal_dict.get("momentum_score", 0.0)
        sig = signal_dict.get("signal", "建議避險")

        # 格式化基礎四因子
        w_dxy  = weights.get("dxy",      0.25) * 100
        w_etf  = weights.get("etf_flow", 0.25) * 100
        w_risk = weights.get("risk",     0.25) * 100
        w_mvrv = weights.get("mvrv",     0.25) * 100
        base_weights = (
            f"DXY: {w_dxy:.1f}%, ETF: {w_etf:.1f}%, RISK: {w_risk:.1f}%, MVRV: {w_mvrv:.1f}%"
        )
        # P2 新增因子（若有）
        extra_parts: list[str] = []
        for key, label in [("sentiment", "情緒"), ("sopr", "SOPR"), ("exchange_netflow", "交易所流向")]:
            if key in weights:
                extra_parts.append(f"{label}: {weights[key] * 100:.1f}%")
        extra_weights = ("，" + "，".join(extra_parts)) if extra_parts else ""

        result = (
            f"ML 模型已完成過去 365 天回測最佳化（{len(weights)} 因子）。"
            f"當前最佳權重：{base_weights}{extra_weights}。"
            f"歷史 Sharpe Ratio：{sharpe}。"
            f"今日系統綜合動能分數為 {momentum}，"
            f"量化模型強烈建議：【{sig}】。"
        )
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "ml_quant")
    except Exception as e:
        return f"ML Quant Tool Failed：BigQuery 查詢失敗（{e}）。請先執行 backfill_data.py 補入歷史數據。"


# ═══════════════════════════════════════════════════════════════════
# Market Regime Scorecard（可審計的 risk_on/off 評分工具）
# ═══════════════════════════════════════════════════════════════════

# 每個指標的閾值與對應評分（+1=risk_on, 0=neutral, -1=risk_off）
_REGIME_RULES: dict[str, list[tuple]] = {
    "VIX":        [("<20", +1, lambda v: v < 20), ("20–25", 0, lambda v: 20 <= v <= 25), (">25", -1, lambda v: v > 25)],
    "ETF_flow_M": [(">200", +1, lambda v: v > 200), ("-200~200", 0, lambda v: -200 <= v <= 200), ("<-200", -1, lambda v: v < -200)],
    "funding_%":  [("<0.03", +1, lambda v: v < 0.03), ("0.03–0.07", 0, lambda v: 0.03 <= v <= 0.07), (">0.07 or <-0.01", -1, lambda v: v > 0.07 or v < -0.01)],
    "liq_24h_M":  [("<100", +1, lambda v: v < 100), ("100–300", 0, lambda v: 100 <= v <= 300), (">300", -1, lambda v: v > 300)],
    "fear_greed": [(">55", +1, lambda v: v > 55), ("40–55", 0, lambda v: 40 <= v <= 55), ("<40", -1, lambda v: v < 40)],
    "BTC_RSI":    [("45–65", +1, lambda v: 45 <= v <= 65), ("35–45 or 65–75", 0, lambda v: (35 <= v < 45) or (65 < v <= 75)), ("<35 or >75", -1, lambda v: v < 35 or v > 75)],
}


def _score_signal(key: str, value: float | None) -> tuple[int, str]:
    """對單一指標評分，回傳 (score, label)。value=None 時評為 0（neutral）。"""
    if value is None:
        return 0, "N/A"
    for label, score, check in _REGIME_RULES.get(key, []):
        if check(value):
            return score, f"{value:.2f}({label})"
    return 0, f"{value:.2f}(out-of-range)"


@tool
def regime_scorecard_tool(query: str = "") -> str:
    """
    以 6 個量化指標計算市場機制評分卡，輸出可審計的 risk_on/neutral/risk_off 判定。
    指標：VIX、BTC ETF 資金流（M$）、資金費率(%)、24h 爆倉量(M$)、恐懼貪婪指數、BTC RSI(14)。
    每項 +1=risk_on, 0=neutral, -1=risk_off；總分 ≥3 → risk_on，≤-3 → risk_off，其餘 → neutral。
    """
    cache_key = ("regime_scorecard", "latest")
    cached = _get_cache(cache_key)
    if cached:
        return _append_data_as_of(cached, "regime_scorecard")

    import yfinance as yf  # noqa: PLC0415

    # ── 1. 抓取各指標數值 ──────────────────────────────────────────────
    values: dict[str, float | None] = {
        "VIX": None, "ETF_flow_M": None, "funding_%": None,
        "liq_24h_M": None, "fear_greed": None, "BTC_RSI": None,
    }

    # VIX
    try:
        df_vix = yf.download("^VIX", period="2d", interval="1d", progress=False, auto_adjust=True)
        if df_vix is not None and not df_vix.empty:
            close = df_vix["Close"].dropna()
            if hasattr(close, "ndim") and close.ndim > 1:
                close = close.iloc[:, 0]
            values["VIX"] = float(close.iloc[-1]) if not close.empty else None
    except Exception:
        pass

    # BTC RSI(14) via yfinance
    try:
        df_btc = yf.download("BTC-USD", period="30d", interval="1d", progress=False, auto_adjust=True)
        if df_btc is not None and not df_btc.empty:
            close = df_btc["Close"].dropna()
            if hasattr(close, "ndim") and close.ndim > 1:
                close = close.iloc[:, 0]
            if len(close) >= 15:
                delta = close.diff().dropna()
                gain = delta.where(delta > 0, 0.0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
                rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
                values["BTC_RSI"] = round(float(100 - (100 / (1 + rs))), 1)
    except Exception:
        pass

    # Fear & Greed
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1&format=json", timeout=8)
        data = resp.json().get("data", [{}])
        if data:
            values["fear_greed"] = float(data[0].get("value", 0))
    except Exception:
        pass

    # CoinGlass fallback：從 Binance 抓資金費率
    try:
        resp = requests.get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=8,
        )
        items = resp.json()
        if items:
            values["funding_%"] = float(items[-1].get("fundingRate", 0)) * 100
    except Exception:
        pass

    # CoinGlass 爆倉數據（嘗試 CoinGlass API）
    try:
        cg_key = os.getenv("COINGLASS_API_KEY", "")
        if cg_key:
            resp = requests.get(
                "https://open-api.coinglass.com/public/v2/liquidation_ex",
                headers={"coinglassSecret": cg_key},
                params={"ex": "Binance", "pair": "BTCUSDT", "interval": "1d"},
                timeout=10,
            )
            liq_data = resp.json().get("data", {})
            if liq_data:
                long_liq = float(liq_data.get("longLiquidationUsd", 0))
                short_liq = float(liq_data.get("shortLiquidationUsd", 0))
                values["liq_24h_M"] = (long_liq + short_liq) / 1e6
    except Exception:
        pass

    # ETF 流量從 BigQuery daily_metrics 最近一筆
    try:
        bq = _get_bq_client()
        from config import METRICS_TABLE  # noqa: PLC0415
        rows = list(bq.query(
            f"SELECT etf_flow_millions FROM `{METRICS_TABLE}` "
            "ORDER BY timestamp DESC LIMIT 1"
        ).result())
        if rows and rows[0]["etf_flow_millions"] is not None:
            values["ETF_flow_M"] = float(rows[0]["etf_flow_millions"])
    except Exception:
        pass

    # ── 2. 計算評分 ────────────────────────────────────────────────────
    scores: dict[str, tuple[int, str]] = {}
    total = 0
    for key in _REGIME_RULES:
        s, label = _score_signal(key, values[key])
        scores[key] = (s, label)
        total += s

    if total >= 3:
        regime = "risk_on"
        regime_emoji = "🟢"
    elif total <= -3:
        regime = "risk_off"
        regime_emoji = "🔴"
    else:
        regime = "neutral"
        regime_emoji = "🟡"

    # ── 3. 格式化評分卡 ────────────────────────────────────────────────
    sign = f"+{total}" if total > 0 else str(total)
    header = f"{regime_emoji} 市場機制評分：<b>{regime}</b>（{sign}/6）"

    score_arrow = {+1: "✅", 0: "⬜", -1: "❌"}
    detail_lines = []
    label_map = {
        "VIX": "VIX", "ETF_flow_M": "ETF流", "funding_%": "資金費率",
        "liq_24h_M": "24h爆倉", "fear_greed": "恐懼貪婪", "BTC_RSI": "BTC RSI",
    }
    for key, (s, lbl) in scores.items():
        detail_lines.append(f"{score_arrow[s]} {label_map[key]} <code>{lbl}</code>→{s:+d}")

    scorecard = header + "\n" + " | ".join(detail_lines)
    _set_cache(cache_key, scorecard)
    return _append_data_as_of(scorecard, "regime_scorecard")


# ═══════════════════════════════════════════════════════════════════
# Fear & Greed Index（Alternative.me 免費 API）
# ═══════════════════════════════════════════════════════════════════

@tool
def fear_greed_tool() -> str:
    """取得加密市場恐懼與貪婪指數（0-100），含今日與昨日數值及變化方向。"""
    cache_key = ("fear_greed", "latest")
    cached = _get_cache(cache_key)
    if cached:
        return _append_data_as_of(cached, "fear_greed")

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
        return _append_data_as_of(result, "fear_greed")
    except Exception as e:
        return f"[DATA_MISSING:fear_greed] Fear & Greed Tool Failed: {e}"


# ═══════════════════════════════════════════════════════════════════
# BTC ETF Flow Analyzer（結構化 API：CoinGlass → SoSoValue → Apify 備援）
# ═══════════════════════════════════════════════════════════════════

# 主要基金代號對照表
_ETF_FUND_NAMES: dict[str, str] = {
    "IBIT": "BlackRock IBIT", "FBTC": "Fidelity FBTC", "GBTC": "Grayscale GBTC",
    "ARKB": "ARK/21Shares ARKB", "BITB": "Bitwise BITB", "BTCO": "Invesco BTCO",
    "HODL": "VanEck HODL", "BRRR": "Valkyrie BRRR", "EZBC": "Franklin EZBC",
    "BTCW": "WisdomTree BTCW",
}


def _yfinance_etf_flow_estimate() -> str | None:
    """
    免費備援：用 yfinance 批量下載 BTC Spot ETF 的近 7 日成交量與價格，
    以「成交量方向 × 價格方向」啟發式推估資金流向趨勢。
    無法取得精確淨流入金額，但可提供 IBIT/FBTC/GBTC 等主要 ETF 的方向性訊號。
    批量下載（一次請求）避免逐 ticker 串行造成 ~30s 阻塞。
    """
    import pandas as pd  # noqa: PLC0415
    import yfinance as yf  # noqa: PLC0415

    etfs = list(_ETF_FUND_NAMES.keys())  # IBIT, FBTC, GBTC, ARKB, BITB, BTCO, HODL, BRRR, EZBC, BTCW
    lines: list[str] = []
    available = 0

    try:
        # 批量下載：一次請求所有 ETF，columns 為 MultiIndex (field, ticker)
        df_all = yf.download(
            " ".join(etfs),
            period="7d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        logger.warning("yfinance batch ETF download failed: %s", e)
        return None

    for ticker in etfs:
        try:
            # MultiIndex columns: (ticker, field) when group_by="ticker"
            if isinstance(df_all.columns, pd.MultiIndex):
                close = df_all[ticker]["Close"].dropna()
                vol = df_all[ticker]["Volume"].dropna()
            else:
                # Single ticker fallback (shouldn't happen in batch mode)
                close = df_all["Close"].dropna()
                vol = df_all["Volume"].dropna()

            if len(close) < 2 or len(vol) < 2:
                continue

            price_chg = (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100
            vol_today = float(vol.iloc[-1])
            vol_avg = float(vol.iloc[-5:].mean()) if len(vol) >= 5 else float(vol.mean())
            vol_chg = (vol_today - vol_avg) / vol_avg * 100 if vol_avg > 0 else 0.0

            # 啟發式：成交量 ↑ + 價格 ↑ → 流入；成交量 ↑ + 價格 ↓ → 流出
            if vol_chg > 15 and price_chg > 0.5:
                signal = "↑ 流入跡象"
            elif vol_chg > 15 and price_chg < -0.5:
                signal = "↓ 流出跡象"
            else:
                signal = "→ 成交平緩"

            fund_name = _ETF_FUND_NAMES.get(ticker, ticker)
            lines.append(
                f"  · {fund_name}: {signal}"
                f"（成交量 {vol_chg:+.0f}% vs 5日均，價格 {price_chg:+.2f}%）"
            )
            available += 1
        except Exception:
            continue

    if available == 0:
        return None

    header = "【BTC Spot ETF 資金流向推估（yfinance 備援，成交量趨勢分析）】"
    note = "⚠️ 注意：此為方向性推估，非精確淨流入金額；精確數據需 COINGLASS_API_KEY。"
    return header + "\n" + "\n".join(lines) + "\n" + note


def _coinglass_etf_flow() -> str | None:
    """CoinGlass v4 ETF list API → 分基金淨流入摘要（需 COINGLASS_API_KEY）。"""
    api_key = os.getenv("COINGLASS_API_KEY", "")
    if not api_key:
        return None
    for endpoint in [
        "https://open-api-v4.coinglass.com/api/bitcoin/etf/list",
        "https://open-api-v4.coinglass.com/api/etf/bitcoin/fund-list",
    ]:
        try:
            resp = requests.get(endpoint, headers={"CG-API-KEY": api_key}, timeout=10)
            if resp.status_code != 200:
                continue
            payload = resp.json()
            data = payload.get("data") if isinstance(payload, dict) else payload
            if not isinstance(data, list) or len(data) < 2:
                continue
            lines: list[str] = []
            total = 0.0
            for fund in data:
                ticker = str(
                    fund.get("ticker") or fund.get("code") or fund.get("symbol") or ""
                ).upper()
                raw = (fund.get("netInflow") or fund.get("net_inflow")
                       or fund.get("dailyNetFlow") or fund.get("daily_flow") or 0)
                try:
                    net_m = float(raw)
                    if abs(net_m) > 1_000_000:  # raw in USD → convert to millions
                        net_m /= 1_000_000
                except (TypeError, ValueError):
                    continue
                total += net_m
                name = _ETF_FUND_NAMES.get(ticker, ticker or "Unknown")
                arrow = "↑" if net_m >= 0 else "↓"
                lines.append(f"  · {name}: {arrow}{abs(net_m):.1f}M USD")
            if lines:
                header = (
                    f"【BTC Spot ETF 資金流（CoinGlass 結構化）】\n"
                    f"· 總淨流入：{total:+.1f}M USD"
                )
                return header + "\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("CoinGlass ETF endpoint %s failed: %s", endpoint, e)
    return None


def _sosovalue_etf_flow() -> str | None:
    """SoSoValue 公開 API（免費，無需 API key）。"""
    for url in [
        "https://sosovalue.xyz/api/etf/us-btc-spot",
        "https://sosovalue.com/api/etf/us-btc-spot",
    ]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            raw_data = resp.json()
            items = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
            if not items:
                continue
            lines: list[str] = []
            total = 0.0
            for fund in items[:12]:
                ticker = str(
                    fund.get("ticker") or fund.get("symbol") or fund.get("etfTicker") or ""
                ).upper()
                raw = (fund.get("dailyNetInflow") or fund.get("daily_net_inflow")
                       or fund.get("netInflow") or fund.get("flowUsd") or 0)
                try:
                    net_m = float(raw)
                    if abs(net_m) > 1_000_000:
                        net_m /= 1_000_000
                except (TypeError, ValueError):
                    continue
                if not ticker:
                    continue
                total += net_m
                arrow = "↑" if net_m >= 0 else "↓"
                lines.append(f"  · {ticker}: {arrow}{abs(net_m):.1f}M USD")
            if lines:
                header = (
                    f"【BTC Spot ETF 資金流（SoSoValue 公開數據）】\n"
                    f"· 總淨流入：{total:+.1f}M USD"
                )
                return header + "\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("SoSoValue ETF endpoint %s failed: %s", url, e)
    return None


@tool
def etf_flow_tool() -> str:
    """
    取得最新交易日 BTC Spot ETF 淨流入/流出數據（百萬美元），含各基金明細。
    優先 CoinGlass 結構化 API → SoSoValue 公開 API → Apify 搜尋備援。
    """
    cache_key = ("etf_flow", "latest")
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "etf_flow")

    # 優先：CoinGlass 結構化 API
    result = _coinglass_etf_flow()
    if result:
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "etf_flow")

    # 備援 1：SoSoValue 公開 API
    result = _sosovalue_etf_flow()
    if result:
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "etf_flow")

    # 備援 2：Apify 搜尋
    query = (
        "Bitcoin spot ETF daily flow IBIT GBTC net inflow outflow millions "
        "site:farside.co.uk OR site:sosovalue.com OR site:theblock.co OR site:coinglass.com"
    )
    try:
        result = _search_with_apify(query, max_items=5)
        if "[DATA_MISSING" not in result:
            prefix = (
                "【BTC Spot ETF 資金流（Apify 搜尋備援，請從中萃取最新一日淨流入）】\n"
                "必須輸出：總淨流入金額、IBIT / FBTC / GBTC 等主要基金明細。\n"
                "若無法確認具體數字，標注（數據待確認）。\n"
            )
            result = prefix + result
            _set_cache(cache_key, result)
            return _append_data_as_of(result, "etf_flow")
    except Exception as e:
        logger.warning("Apify etf_flow search failed: %s", e)

    # 備援 3：yfinance 成交量趨勢推估（無需 API Key）
    result = _yfinance_etf_flow_estimate()
    if result:
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "etf_flow")

    return "[DATA_MISSING:etf_flow] ETF Flow Tool Failed：所有數據源均無回應。"


# ═══════════════════════════════════════════════════════════════════
# Macro Economic Calendar（FMP API + Apify fallback）
# ═══════════════════════════════════════════════════════════════════

@tool
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
# Multi-Timeframe Signal（D/4H/1H）
# ═══════════════════════════════════════════════════════════════════

_CRYPTO_YF = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "LINK", "DOT", "MATIC", "DOGE", "ADA",
}


def _trend_by_ma(close_val: float, ma20: float | None, ma50: float | None) -> str:
    if ma20 is None or ma50 is None:
        return "neutral"
    if close_val > ma20 > ma50:
        return "bullish"
    if close_val < ma20 < ma50:
        return "bearish"
    return "neutral"


@tool
def multi_timeframe_tool(symbol: str) -> str:
    """
    多時框信號整合：
    - D（日線）：趨勢方向
    - 4H：進場時機（以 1H 近 60d 聚合代理）
    - 1H：短線微結構
    """
    raw = (symbol or "").upper().strip().strip("$")
    if not raw:
        return "[DATA_MISSING:multi_timeframe] symbol 不可為空。"

    yf_symbol = f"{raw}-USD" if raw in _CRYPTO_YF else raw
    cache_key = ("multi_timeframe", yf_symbol)
    if cached := _get_cache(cache_key):
        return cached

    try:
        import yfinance as yf
    except Exception as e:
        return f"[DATA_MISSING:multi_timeframe] yfinance 載入失敗：{e}"

    def _fetch(interval: str, period: str) -> str:
        try:
            df = yf.download(yf_symbol, period=period, interval=interval, progress=False, auto_adjust=True)
            if df is None or df.empty:
                return "N/A"
            close = df["Close"]
            if hasattr(close, "ndim") and close.ndim > 1:
                close = close.iloc[:, 0]
            close = close.dropna()
            if close.empty:
                return "N/A"
            c = float(close.iloc[-1])
            ma20 = float(close.iloc[-20:].mean()) if len(close) >= 20 else None
            ma50 = float(close.iloc[-50:].mean()) if len(close) >= 50 else None
            return _trend_by_ma(c, ma20, ma50)
        except Exception:
            return "N/A"

    trend_d = _fetch("1d", "6mo")
    trend_4h = _fetch("1h", "60d")  # yfinance 無穩定 4h，使用 1h 長窗作 4h 代理
    trend_1h = _fetch("1h", "14d")

    known = [t for t in (trend_d, trend_4h, trend_1h) if t in ("bullish", "bearish", "neutral")]
    bull = sum(1 for t in known if t == "bullish")
    bear = sum(1 for t in known if t == "bearish")

    if len(known) == 3 and bull == 3:
        consensus = "三時框同向多頭（高信心）"
    elif len(known) == 3 and bear == 3:
        consensus = "三時框同向空頭（高信心）"
    elif bull >= 2:
        consensus = "偏多但分歧（中信心）"
    elif bear >= 2:
        consensus = "偏空但分歧（中信心）"
    else:
        consensus = "方向分歧（低信心）"

    result = (
        f"【多時框信號 {raw}】"
        f"D={trend_d} | 4H={trend_4h} | 1H={trend_1h} | 結論：{consensus}"
    )
    _set_cache(cache_key, result)
    return result


# ═══════════════════════════════════════════════════════════════════
# Rumor & Controversy Scanner（降低強度：days=7, max_results=5）
# ═══════════════════════════════════════════════════════════════════

@tool
def rumor_scanner_tool(topic: str) -> str:
    """掃描爭議與傳聞（RSS → NewsAPI → Apify 三層 fallback）。"""
    cache_key = ("rumor_scanner", topic)
    cached = _get_cache(cache_key)
    if cached:
        return cached

    # 第一層：RSS（CoinDesk/TheBlock，免費）
    rss_result = _rss_fetch("crypto")
    if not rss_result.startswith("[DATA_MISSING"):
        combined_lines = [f"【傳聞掃描｜{topic}】", rss_result]
        result = "\n".join(combined_lines)
        _set_cache(cache_key, result)
        return result

    # 第二層：NewsAPI（Reuters/Bloomberg）
    news_query = f"controversies manipulation accusations {topic}"
    newsapi_result = _newsapi_fetch(news_query)
    if not newsapi_result.startswith("[DATA_MISSING"):
        _set_cache(cache_key, newsapi_result)
        return newsapi_result

    # 第三層：Apify（付費，最後手段）
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
        return "[DATA_MISSING:rumor_scanner] Rumor Scanner Failed：所有來源均無法取得資料。"


# ═══════════════════════════════════════════════════════════════════
# BTC 鏈上數據深化（CryptoQuant → Glassnode → Blockchain.info 備援）
# ═══════════════════════════════════════════════════════════════════

def _cryptoquant_fetch(path: str) -> dict | None:
    """CryptoQuant API 通用請求（需 CRYPTOQUANT_API_KEY）。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = requests.get(
            f"https://api.cryptoquant.com/v1{path}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else None
    except Exception as e:
        logger.warning("CryptoQuant %s failed: %s", path, e)
        return None


def _cq_sopr() -> str | None:
    """SOPR：持有者是在獲利還是虧損出貨（>1 獲利，<1 虧損）。"""
    data = _cryptoquant_fetch("/btc/market-data/sopr?window=day&limit=2")
    if not data:
        return None
    items = data.get("data", {}).get("result", [])
    if not items:
        return None
    val = items[-1].get("sopr") or items[-1].get("v")
    if val is None:
        return None
    try:
        v = float(val)
        if v > 1.05:
            interp = "獲利者在出貨（賣壓偏強）"
        elif v < 0.97:
            interp = "虧損者在拋售（投降式清倉，潛在底部）"
        else:
            interp = "持有者成本接近持平（中性）"
        return f"· SOPR：{v:.4f} → {interp}"
    except (TypeError, ValueError):
        return None


def _cq_exchange_netflow() -> str | None:
    """交易所 BTC 淨流入/流出：正值 = 流入（潛在賣壓），負值 = 流出（囤幣）。"""
    data = _cryptoquant_fetch("/btc/exchange-flows/netflow?window=day&limit=2")
    if not data:
        return None
    items = data.get("data", {}).get("result", [])
    if not items:
        return None
    val = items[-1].get("netflow_total") or items[-1].get("v")
    if val is None:
        return None
    try:
        v = float(val)
        direction = "流入交易所（潛在賣壓）" if v > 0 else "流出交易所（聰明錢囤幣）"
        return f"· 交易所 BTC 淨流向：{v / 1000:+.2f}K BTC → {direction}"
    except (TypeError, ValueError):
        return None


def _blockchain_info_active_addresses() -> str | None:
    """Blockchain.info 免費 API：活躍地址數近 7 日趨勢。"""
    try:
        resp = requests.get(
            "https://api.blockchain.info/charts/n-unique-addresses"
            "?timespan=14days&format=json&cors=true",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        values = resp.json().get("values", [])
        if len(values) < 7:
            return None
        recent = [v["y"] for v in values[-7:]]
        latest, prev_wk = recent[-1], recent[0]
        chg_pct = (latest - prev_wk) / prev_wk * 100 if prev_wk else 0.0
        trend = (
            "↑ 網路使用量增加" if chg_pct > 5 else
            "↓ 網路使用量萎縮" if chg_pct < -5 else
            "→ 活躍度持平"
        )
        return f"· 活躍地址數（7日均）：{int(latest):,}（週變化 {chg_pct:+.1f}%）{trend}"
    except Exception as e:
        logger.warning("Blockchain.info active addresses failed: %s", e)
        return None


def _glassnode_nupl() -> str | None:
    """Glassnode NUPL（未實現損益比，需 GLASSNODE_API_KEY）。"""
    api_key = os.getenv("GLASSNODE_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = requests.get(
            "https://api.glassnode.com/v1/metrics/indicators/net_unrealized_profit_loss",
            params={"a": "BTC", "i": "24h", "limit": 2, "api_key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        val = data[-1].get("v") if data else None
        if val is None:
            return None
        v = float(val)
        if v > 0.75:
            zone = "Euphoria（極度高估，歷史性頂部風險）"
        elif v > 0.5:
            zone = "Greed（貪婪區間）"
        elif v > 0.25:
            zone = "Optimism（樂觀，健康多頭）"
        elif v > 0.0:
            zone = "Hope（中性偏多）"
        elif v > -0.25:
            zone = "Anxiety（焦慮，謹慎）"
        else:
            zone = "Capitulation（恐慌清倉，潛在底部）"
        return f"· NUPL（未實現損益比）：{v:.4f} → {zone}"
    except Exception as e:
        logger.warning("Glassnode NUPL failed: %s", e)
        return None


@tool
def onchain_metrics_tool() -> str:
    """
    取得 BTC 鏈上核心指標：SOPR（持有者損益比）、交易所淨流向、活躍地址數、NUPL（未實現損益比）。
    來源優先：CryptoQuant API（需 CRYPTOQUANT_API_KEY）→ Glassnode（需 GLASSNODE_API_KEY）
             → Blockchain.info（免費備援）。
    """
    cache_key = ("onchain_metrics", "btc")
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "onchain_metrics")

    parts: list[str] = []
    for fn in (_cq_sopr, _cq_exchange_netflow, _blockchain_info_active_addresses, _glassnode_nupl):
        val = fn()
        if val:
            parts.append(val)

    if not parts:
        result = (
            "[DATA_MISSING:onchain_metrics] 鏈上數據均無回應。"
            "請確認 CRYPTOQUANT_API_KEY 和 GLASSNODE_API_KEY 是否已設定。"
        )
    else:
        result = "【BTC 鏈上深度指標】\n" + "\n".join(parts)

    _set_cache(cache_key, result)
    if result.startswith("[DATA_MISSING:"):
        return result
    return _append_data_as_of(result, "onchain_metrics")


# ═══════════════════════════════════════════════════════════════════
# 社群情緒量化引擎（LLM NLP 評分 -1 到 +1）
# ═══════════════════════════════════════════════════════════════════

@tool
def sentiment_score_tool(news_and_tweets: str) -> str:
    """
    對 CryptoPanic 新聞標題 + X 推文做 LLM 情緒評分。
    輸入：換行分隔的新聞標題或推文文字。
    輸出：量化情緒分數 -1（極度恐慌）到 +1（極度貪婪），含逐條分析與極端值警示。
    極端分數可作反向指標（-0.7 以下 = 潛在底部，+0.7 以上 = 潛在頂部）。
    """
    text = (news_and_tweets or "").strip()
    if not text:
        return "[DATA_MISSING:sentiment_score] 未提供文本進行情緒分析。"

    cache_key = ("sentiment_score", text[:120])
    if cached := _get_cache(cache_key):
        return cached

    # 依可用金鑰建立候選模型，避免單一模型下線導致工具整體失效
    model_candidates: list[str] = []
    if os.getenv("GEMINI_API_KEY"):
        model_candidates.extend([
            "gemini/gemini-2.5-flash",
            "gemini/gemini-2.0-flash",
        ])
    if os.getenv("OPENAI_API_KEY"):
        model_candidates.append("openai/gpt-4o-mini")
    if os.getenv("OPENROUTER_API_KEY"):
        model_candidates.append("openrouter/anthropic/claude-haiku-4-5-20251001")

    if not model_candidates:
        return "[DATA_MISSING:sentiment_score] 無可用 LLM 金鑰進行情緒評分。"

    prompt = f"""你是加密貨幣市場情緒分析師。對以下新聞/推文評分：

{text[:2000]}

輸出純 JSON（禁止其他文字）：
{{"aggregate_score": 從-1.0到+1.0的數字, "label": "極度恐慌/恐慌/中性/貪婪/極度貪婪", "bullish_count": 正面條數, "bearish_count": 負面條數, "rationale": "2句中文總結"}}

評分基準：+1.0=所有消息極度看漲, 0.0=中性混合, -1.0=所有消息極度看跌"""

    try:
        from litellm import completion as _llm_completion

        raw = ""
        last_err: Exception | None = None
        for model in model_candidates:
            try:
                resp = _llm_completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0.1,
                )
                raw = (resp.choices[0].message.content or "").strip()
                if raw:
                    break
            except Exception as model_err:
                last_err = model_err
                msg = str(model_err).lower()
                # 模型下線/找不到時嘗試下一個候選
                if ("not_found" in msg) or ("no longer available" in msg) or ("404" in msg):
                    logger.warning("sentiment_score_tool model unavailable, fallback to next: %s", model)
                    continue
                raise

        if not raw:
            if last_err is not None:
                raise last_err
            return "[DATA_MISSING:sentiment_score] 情緒評分模型回傳空結果。"

        import json as _json

        json_m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
        if json_m:
            parsed = _json.loads(json_m.group())
            score = max(-1.0, min(1.0, float(parsed.get("aggregate_score", 0.0))))
            label = parsed.get("label", "中性")
            bullish = int(parsed.get("bullish_count", 0))
            bearish = int(parsed.get("bearish_count", 0))
            rationale = parsed.get("rationale", "")
            emoji = "🚀" if score > 0.5 else ("😰" if score < -0.5 else "😐")
            if score < -0.7:
                extreme_warn = "⚠️ 極端恐慌 → 歷史反向底部信號"
            elif score > 0.7:
                extreme_warn = "⚠️ 極端貪婪 → 歷史反向頂部風險"
            else:
                extreme_warn = "正常範圍"
            result = (
                f"【社群情緒量化】{emoji}\n"
                f"· 情緒分數：{score:+.2f}（{label}）\n"
                f"· 看漲 {bullish} 條 / 看跌 {bearish} 條\n"
                f"· 解讀：{rationale}\n"
                f"· 極端值警示：{extreme_warn}"
            )
        else:
            result = f"【社群情緒量化】\n· LLM 回傳：{raw[:300]}"

        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.warning("Sentiment score tool failed: %s", e)
        return f"[DATA_MISSING:sentiment_score] 情緒評分失敗：{e}"


# ═══════════════════════════════════════════════════════════════════
# Macro Context Tool（美債利率、殖利率曲線、Fed 期貨、本週財報）
# ═══════════════════════════════════════════════════════════════════

# 固定追蹤的大型科技/AI 相關財報標的
_EARNINGS_WATCHLIST = ["NVDA", "AMD", "MSFT", "GOOGL", "AAPL", "META", "AMZN", "TSM", "AVGO", "ARM"]


@tool
def macro_context_tool(query: str = "") -> str:
    """
    取得宏觀投資框架數據：美債 10Y/2Y 殖利率、殖利率曲線利差、Fed SOFR 期貨隱含升降息預期、本週重要科技財報。
    數據來源：yfinance（^TNX, 2YY=F, ZQ=F）+ FRED（DGS2 fallback）。
    """
    cache_key = ("macro_context", "latest")
    cached = _get_cache(cache_key)
    if cached:
        return _append_data_as_of(cached, "macro_context")

    import yfinance as yf  # noqa: PLC0415

    lines: list[str] = ["【宏觀框架】"]

    # ── 1. 美債殖利率 ──────────────────────────────────────────────────
    yield_10y: float | None = None
    yield_2y: float | None = None

    def _fetch_latest_fred_percent(series_id: str) -> float | None:
        fred_key = (os.getenv("FRED_API_KEY") or "").strip()
        if not fred_key:
            return None
        try:
            resp = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 10,
                },
                timeout=8,
            )
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            for obs in observations:
                raw = str(obs.get("value", "")).strip()
                if not raw or raw == ".":
                    continue
                try:
                    return round(float(raw), 3)
                except ValueError:
                    continue
        except Exception:
            return None
        return None
    try:
        df10 = yf.download("^TNX", period="3d", interval="1d", progress=False, auto_adjust=True)
        if df10 is not None and not df10.empty:
            c = df10["Close"].dropna()
            if hasattr(c, "ndim") and c.ndim > 1:
                c = c.iloc[:, 0]
            if not c.empty:
                yield_10y = round(float(c.iloc[-1]), 3)
    except Exception:
        pass

    try:
        df2 = yf.download("2YY=F", period="5d", interval="1d", progress=False, auto_adjust=True)
        if df2 is not None and not df2.empty:
            c = df2["Close"].dropna()
            if hasattr(c, "ndim") and c.ndim > 1:
                c = c.iloc[:, 0]
            if not c.empty:
                yield_2y = round(float(c.iloc[-1]), 3)
    except Exception:
        pass
    if yield_2y is None:
        yield_2y = _fetch_latest_fred_percent("DGS2")

    y10_str = f"{yield_10y:.3f}%" if yield_10y is not None else "N/A"
    y2_str = f"{yield_2y:.3f}%" if yield_2y is not None else "N/A"
    if yield_10y is not None and yield_2y is not None:
        spread_bp = round((yield_10y - yield_2y) * 100, 1)
        spread_str = f"{spread_bp:+.1f}bp"
        curve_signal = "利率倒掛（衰退預警）⚠️" if spread_bp < 0 else "正斜率（正常）"
    else:
        spread_str = "N/A"
        curve_signal = ""

    lines.append(f"🏛️ 美債 10Y: <code>{y10_str}</code> | 2Y: <code>{y2_str}</code> | 利差: <code>{spread_str}</code> {curve_signal}")

    # ── 2. Fed SOFR 期貨隱含預期 ─────────────────────────────────────
    try:
        df_fed = yf.download("ZQ=F", period="3d", interval="1d", progress=False, auto_adjust=True)
        if df_fed is not None and not df_fed.empty:
            c = df_fed["Close"].dropna()
            if hasattr(c, "ndim") and c.ndim > 1:
                c = c.iloc[:, 0]
            if not c.empty:
                implied_rate = round(100 - float(c.iloc[-1]), 3)
                lines.append(f"🎯 Fed SOFR 期貨隱含利率: <code>{implied_rate:.3f}%</code>")
    except Exception:
        lines.append("🎯 Fed SOFR 期貨: <code>N/A</code>")

    # ── 3. 本週重要財報（使用 yfinance 查詢財報日期）─────────────────
    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=7)
    upcoming_earnings: list[str] = []

    for ticker_sym in _EARNINGS_WATCHLIST:
        try:
            t = yf.Ticker(ticker_sym)
            cal = t.calendar
            if cal is None:
                continue
            # yfinance calendar 回傳格式多種，嘗試 'Earnings Date' 欄位
            if hasattr(cal, "get"):
                ed = cal.get("Earnings Date")
            elif hasattr(cal, "iloc"):
                # DataFrame 格式
                ed = cal.iloc[0].get("Earnings Date") if not cal.empty else None
            else:
                ed = None
            if ed is None:
                continue
            # 可能是 list 或單一值
            dates = ed if isinstance(ed, list) else [ed]
            for d in dates:
                try:
                    ed_date = d.date() if hasattr(d, "date") else None
                    if ed_date and today <= ed_date <= week_end:
                        upcoming_earnings.append(f"{ticker_sym}({ed_date.strftime('%m/%d')})")
                        break
                except Exception:
                    pass
        except Exception:
            continue

    if upcoming_earnings:
        lines.append(f"📅 本週財報: <code>{' · '.join(upcoming_earnings)}</code>")
    else:
        lines.append("📅 本週財報: <code>本週無主要科技財報</code>")

    result = "\n".join(lines)
    _set_cache(cache_key, result)
    return _append_data_as_of(result, "macro_context")


# ═══════════════════════════════════════════════════════════════════
# 新聞來源工具（NewsAPI / GNews / RSS）— Agent 可直接呼叫
# ═══════════════════════════════════════════════════════════════════

@tool
def newsapi_tool(query: str) -> str:
    """取得 Bloomberg/Reuters/CNBC 等主流財經媒體近 48h 新聞。"""
    cache_key = ("newsapi", query)
    if hit := _get_cache(cache_key):
        return hit
    result = _newsapi_fetch(query)
    if not result.startswith("[DATA_MISSING"):
        _set_cache(cache_key, result)
    return result


@tool
def gnews_tool(query: str) -> str:
    """用 GNews API 搜尋多語言財經新聞（近 48h）。"""
    cache_key = ("gnews", query)
    if hit := _get_cache(cache_key):
        return hit
    result = _gnews_fetch(query)
    if not result.startswith("[DATA_MISSING"):
        _set_cache(cache_key, result)
    return result


@tool
def rss_feed_tool(category: str = "crypto") -> str:
    """從 RSS 取得加密/AI 媒體近 48h 新聞，category 可為 'crypto' 或 'ai'（免費，不需 API key）。"""
    cache_key = ("rss", category)
    if hit := _get_cache(cache_key):
        return hit
    result = _rss_fetch(category)
    if not result.startswith("[DATA_MISSING"):
        _set_cache(cache_key, result)
    return result

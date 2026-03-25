import logging
import os
import re
import time
import json
import threading
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from apify_client import ApifyClient
from crewai.tools import tool
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from api_schema import require_json_dict, require_json_list, require_list
from config import PROJECT_ID, METRICS_TABLE
from scratchpad import traced_tool_execution

logger = logging.getLogger(__name__)


def _response_json_dict(resp: requests.Response, source: str) -> dict | None:
    try:
        raw = resp.json()
    except ValueError as e:
        logger.warning("%s JSON decode failed: %s", source, e)
        return None
    try:
        return require_json_dict(raw, source=source)
    except ValueError:
        return None


def _response_json_list(resp: requests.Response, source: str) -> list | None:
    try:
        raw = resp.json()
    except ValueError as e:
        logger.warning("%s JSON decode failed: %s", source, e)
        return None
    try:
        return require_json_list(raw, source=source)
    except ValueError:
        return None


def _http_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float | int | tuple = 10,
) -> requests.Response:
    """模組級 Session 的 GET，供連線重用與統一出口。"""
    return _get_http_session().get(url, params=params, headers=headers, timeout=timeout)

# ── 模組級 in-memory cache（同一次執行內避免重複打外部 API）────────────
# key: (tool_name, query_string)  value: (result_str, expire_timestamp)
_CACHE: dict[tuple, tuple] = {}
_CACHE_TTL = 600  # 10 分鐘內相同 query 直接回傳 cache
_CACHE_MAX_SIZE = 256
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

# Domains known to produce low-quality, tutorial-style, or non-investment-grade content.
# Articles whose URL or source name matches any of these are silently skipped.
# Review and extend quarterly; keep lowercase.
_LOW_QUALITY_DOMAINS: frozenset[str] = frozenset({
    "c-sharpcorner.com",
    "geeksforgeeks.org",
    "medium.com",        # too broad / unvetted; individual premium pubs are OK via NewsAPI sources
    "dev.to",
    "hackernoon.com",
    "towardsdatascience.com",
    "analyticsvidhya.com",
    "kdnuggets.com",
    "dzone.com",
    "simplilearn.com",
    "javatpoint.com",
    "tutorialspoint.com",
    "w3schools.com",
})

# Minimum source health score below which a source is treated as degraded and skipped
# entirely (rather than just having its quota reduced).  Configurable via env var.
_SOURCE_HEALTH_SKIP_THRESHOLD: float = float(
    os.getenv("SOURCE_HEALTH_SKIP_THRESHOLD", "0.20")
)

_HTTP_SESSION: requests.Session | None = None

_INIT_LOCK = threading.Lock()   # protects lazy-init singletons
_CACHE_LOCK = threading.Lock()  # protects _CACHE mutations


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        with _INIT_LOCK:
            if _HTTP_SESSION is None:  # double-check
                s = requests.Session()
                s.headers.update({"User-Agent": "Q-Silicon/1.0"})
                _HTTP_SESSION = s
    return _HTTP_SESSION


def _get_cache(key: tuple) -> str | None:
    if key in _CACHE:
        result, expire = _CACHE[key]
        if time.time() < expire:
            return result
        with _CACHE_LOCK:
            _CACHE.pop(key, None)
    return None


def _set_cache(key: tuple, value: str) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_SIZE:
            # Evict oldest entries (by expire timestamp)
            oldest_keys = sorted(_CACHE, key=lambda k: _CACHE[k][1])[:len(_CACHE) // 4]
            for k in oldest_keys:
                del _CACHE[k]
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
                for err_key in ("e429", "e400", "etimeout", "e5xx", "eauth", "eother"):
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
        except (TypeError, ValueError) as e:
            logger.warning("merge source health row datetime compare failed: %s", e)
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
            SELECT source, ok, fail, e429, e400, etimeout, e5xx, eauth, eother, updated_at
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
                    "eauth": max(float(r.get("eauth") or 0.0), 0.0),
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
    with _INIT_LOCK:
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
            bigquery.SchemaField("eauth", "FLOAT"),
            bigquery.SchemaField("eother", "FLOAT"),
            bigquery.SchemaField("updated_at", "TIMESTAMP"),
        ]
        table = bigquery.Table(table_id, schema=schema)
        try:
            client.get_table(table_id)
        except NotFound:
            client.create_table(table, exists_ok=True)
        except Exception as e:
            logger.warning("source_health BQ get_table unexpected (table_id=%s): %s", table_id, e)
            raise

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
                    "eauth": float(stats.get("eauth", 0.0)),
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
    except (TypeError, ValueError) as e:
        logger.warning("decayed_source_counts datetime parse failed: %s", e)
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
    if r in ("timeout", "read_timeout", "connect_timeout", "conn_err"):
        return "etimeout"
    if r in ("5xx", "server_error"):
        return "e5xx"
    if r in ("auth", "unauthorized", "forbidden"):
        return "eauth"
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
    eauth = float(stats.get("eauth", 0.0))
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
        elif err_key == "eauth":
            eauth += 1.0
        else:
            eother += 1.0
    _SOURCE_HEALTH[source] = {
        "ok": decayed_ok,
        "fail": decayed_fail,
        "e429": e429,
        "e400": e400,
        "etimeout": etimeout,
        "e5xx": e5xx,
        "eauth": eauth,
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
        eauth = int(float(stats.get("eauth", 0.0)))
        eother = int(float(stats.get("eother", 0.0)))
        parts.append(f"{s}:429={e429},400={e400},timeout={etimeout},5xx={e5xx},auth={eauth},other={eother}")
    return " | ".join(parts)


def source_observability_lines() -> str:
    return (
        f"【SourceHealth】{_source_health_summary()}\n"
        f"【SourceErrors】{_source_error_summary()}\n"
        f"【SourceQuota】{_source_quota_summary()}"
    )


def _reason_from_exception(err: Exception | None) -> str:
    if err is None:
        return "no_articles"
    if isinstance(err, requests.Timeout):
        return "timeout"
    if isinstance(err, requests.HTTPError):
        status = err.response.status_code if err.response is not None else None
        if status == 429:
            return "429"
        if status in (401, 403):
            return "auth"
        if status == 400:
            return "400"
        if status and 500 <= status < 600:
            return "5xx"
    msg = str(err).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "429" in msg or "rate limit" in msg:
        return "429"
    if "401" in msg or "403" in msg or "unauthorized" in msg or "forbidden" in msg:
        return "auth"
    if "400" in msg:
        return "400"
    if any(k in msg for k in ("500", "502", "503", "504", "server error")):
        return "5xx"
    if "connection" in msg or "dns" in msg or "resolve" in msg:
        return "conn_err"
    # 警告等級，讓生產環境看到未分類的例外類型
    logger.warning("_reason_from_exception unclassified: %s(%s)", type(err).__name__, msg[:120])
    return "other"


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _is_low_quality_source(url: str, source_name: str = "") -> bool:
    """Return True if the article URL or source name matches the low-quality domain blacklist."""
    haystack = (url + " " + source_name).lower()
    return any(domain in haystack for domain in _LOW_QUALITY_DOMAINS)


def _source_is_degraded(source: str) -> bool:
    """Return True when a source's health score is below the skip threshold.

    Sources at this level have a persistent error rate that makes their results
    unreliable.  Rather than filling the context with low-quality or empty results,
    we skip them entirely and let the fallback chain handle the query.
    """
    score = _source_score(source)
    if score < _SOURCE_HEALTH_SKIP_THRESHOLD:
        logger.warning(
            "Source '%s' is degraded (health=%.2f < threshold=%.2f) — skipping this call",
            source, score, _SOURCE_HEALTH_SKIP_THRESHOLD,
        )
        return True
    return False


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
        with _INIT_LOCK:
            if _BQ_CLIENT is None:  # double-check
                _BQ_CLIENT = bigquery.Client(project=PROJECT_ID)
    return _BQ_CLIENT


def _get_apify_client() -> ApifyClient:
    """ApifyClient singleton：同一次執行只初始化一次。"""
    global _APIFY_CLIENT
    if _APIFY_CLIENT is None:
        with _INIT_LOCK:
            if _APIFY_CLIENT is None:  # double-check
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
    prefix = f"(當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}，請嚴格過濾超過 48 小時的舊資訊)\n"

    run_obj = client.actor(actor_id).call(run_input={
        "queries": query,
        "maxPagesPerQuery": 1,
        "resultsPerPage": max_items,
        "languageCode": "zh-TW",
    })
    if isinstance(run_obj, dict):
        run_candidate: dict = run_obj
    elif isinstance(run_obj, Mapping):
        run_candidate = dict(run_obj)
    else:
        logger.warning("Apify run not mapping-like: %s", type(run_obj).__name__)
        return prefix + "[DATA_MISSING:apify_search] Apify run 回傳格式異常。"
    try:
        run_ok = require_json_dict(run_candidate, source="Apify-run")
    except ValueError:
        return prefix + "[DATA_MISSING:apify_search] Apify run 回傳格式異常。"

    ds_id = run_ok.get("defaultDatasetId")
    if not ds_id:
        logger.warning(
            "Apify run missing defaultDatasetId (keys=%s)",
            sorted(run_ok.keys())[:30],
        )
        return prefix + "[DATA_MISSING:apify_search] Apify run 缺少 dataset id。"

    dataset = client.dataset(ds_id)
    raw_items = list(dataset.iterate_items())[:max_items]
    items: list[dict] = []
    for it in raw_items:
        if isinstance(it, dict):
            cand = it
        elif isinstance(it, Mapping):
            cand = dict(it)
        else:
            logger.debug("apify: skip non-object dataset item type=%s", type(it).__name__)
            continue
        try:
            items.append(require_json_dict(cand, source="Apify-dataset-item"))
        except ValueError:
            continue

    if not items:
        return prefix + "[DATA_MISSING:apify_search] Apify 無搜尋結果。"

    lines: list[str] = []
    for i, item in enumerate(items, 1):
        title = str(item.get("title") or item.get("headline") or item.get("name") or "(無標題)")
        source = str(item.get("source") or item.get("siteName") or item.get("domain") or "unknown")
        url = str(item.get("url") or item.get("link") or "")
        if _is_low_quality_source(url, source):
            logger.debug("apify: skipping low-quality source %r (%s)", source, url)
            continue
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
    if not lines:
        return prefix + "[DATA_MISSING:apify_search] Apify 搜尋結果全部來自低品質來源，已過濾。"
    return prefix + "\n\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# AI Momentum Analyzer（AI 模型熱度排名：HuggingFace → OpenRouter → RSS → Apify）
# ═══════════════════════════════════════════════════════════════════

_HF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; QSilicon-AIAgent/1.0)",
    "Accept": "application/json",
}


def _hf_fetch_models() -> str | None:
    """HuggingFace 官方 API 取 text-generation 模型排名，失敗回傳 None。
    嘗試順序：trendingScore → likes → downloads，提高成功率。"""
    # downloads / likes 較穩定；trendingScore 偶爾因 API 參數或空榜失敗
    sort_strategies = [
        ("downloads", "下載量"),
        ("likes", "按讚"),
        ("trendingScore", "趨勢"),
    ]
    for sort_key, sort_label in sort_strategies:
        try:
            resp = _http_get(
                "https://huggingface.co/api/models",
                params={"sort": sort_key, "direction": -1, "limit": 10,
                        "filter": "text-generation"},
                headers=_HF_HEADERS,
                timeout=45,
            )
            if resp.status_code != 200:
                logger.warning("HuggingFace API HTTP %s (sort=%s)", resp.status_code, sort_key)
                continue
            try:
                models = require_json_list(resp.json(), source="HuggingFace")
            except ValueError as e:
                logger.warning("HuggingFace API schema (sort=%s): %s", sort_key, e)
                continue
            if not models:
                logger.warning("HuggingFace API empty (sort=%s)", sort_key)
                continue
            lines: list[str] = []
            rank = 0
            for m in models:
                if not isinstance(m, dict):
                    continue
                name = m.get("modelId") or m.get("id") or ""
                if not name:
                    continue
                try:
                    downloads = int(m.get("downloads") or m.get("downloadsAllTime") or 0)
                except (TypeError, ValueError):
                    downloads = 0
                try:
                    likes = int(m.get("likes") or 0)
                except (TypeError, ValueError):
                    likes = 0
                # 不再因 0/0 略過：趨勢榜常見新模型下載為 0，略過會導致整榜為空
                rank += 1
                lines.append(
                    f"Top{rank}: {name}"
                    f"（下載 {downloads:,}｜按讚 {likes:,}）"
                )
                if rank >= 5:
                    break
            if not lines:
                continue
            return f"【HuggingFace AI 模型熱度 Top5（按{sort_label}）】\n" + "\n".join(lines)
        except requests.Timeout:
            logger.warning("HuggingFace API timeout (sort=%s)", sort_key)
            continue
        except Exception as e:
            logger.warning("HuggingFace API failed (sort=%s): %s", sort_key, e)
            continue
    logger.warning("HuggingFace API: all sort strategies exhausted")
    return None


def _openrouter_fetch_models() -> str | None:
    """OpenRouter API 取模型清單（需 OPENROUTER_API_KEY），失敗回傳 None。"""
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        logger.warning("OPENROUTER_API_KEY 未設定，跳過 OpenRouter 資料取得")
        return None
    try:
        resp = _http_get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {openrouter_key}", **_HF_HEADERS},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("OpenRouter API HTTP %s", resp.status_code)
            return None
        try:
            raw = resp.json()
            payload = require_json_dict(raw, source="OpenRouter")
            models = require_list(payload, "data", source="OpenRouter")
        except ValueError as e:
            logger.warning("OpenRouter JSON/schema failed: %s", e)
            return None
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
    except Exception as e:
        logger.warning("ai_momentum apify fallback failed: %s", e)
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
            resp = _http_get(url, params=params, headers=headers, timeout=timeout)
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
                try:
                    data = r.json()
                    data = require_json_dict(data, source="NewsAPI")
                    articles = require_list(data, "articles", source="NewsAPI")
                except ValueError as e:
                    logger.warning("_newsapi_fetch JSON/schema (query=%r): %s", cand, e)
                    last_err = e
                    break
                # NewsAPI 有時回傳 status=error 但 HTTP 200
                if data.get("status") == "error":
                    logger.warning("_newsapi_fetch API error (query=%r): %s", cand, data.get("message"))
                    last_err = RuntimeError(data.get("message", "newsapi status=error"))
                    break  # 此模板組失敗，跳到下一組 param_template
                if not articles:
                    continue
                _record_source_outcome("newsapi", True)
                lines = [f"【NewsAPI｜{cand}】"]
                for a in articles:
                    src_name = a.get("source", {}).get("name", "")
                    url = a.get("url", "")
                    if _is_low_quality_source(url, src_name):
                        logger.debug("newsapi: skipping low-quality source %r (%s)", src_name, url)
                        continue
                    lines.append(
                        f"〔{a.get('publishedAt', '')[:16]}｜{src_name}〕"
                        f"{a.get('title', '')}\n{url}"
                    )
                if len(lines) > 1:  # has at least one article after filtering
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
            try:
                payload = r.json()
                payload = require_json_dict(payload, source="GNews")
                articles = require_list(payload, "articles", source="GNews")
            except ValueError as e:
                last_err = e
                logger.warning("_gnews_fetch JSON/schema (query=%r): %s", cand, e)
                continue
            if not articles:
                continue
            _record_source_outcome("gnews", True)
            lines = [f"【GNews｜{cand}】"]
            for a in articles:
                src_name = a.get("source", {}).get("name", "")
                url = a.get("url", "")
                if _is_low_quality_source(url, src_name):
                    logger.debug("gnews: skipping low-quality source %r (%s)", src_name, url)
                    continue
                lines.append(
                    f"〔{a.get('publishedAt', '')[:16]}｜{src_name}〕"
                    f"{a.get('title', '')}\n{url}"
                )
            if len(lines) > 1:  # has at least one article after filtering
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

    def _run() -> str:
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
            if _source_is_degraded(_source_name):
                continue
            if not _consume_source_quota(_source_name):
                logger.info("skip source %s due to quota limit", _source_name)
                continue
            result = fn(query)
            if not result.startswith("[DATA_MISSING"):
                _set_cache(cache_key, result)
                return result

        # 第三層：Apify（付費，最後手段）
        if _source_is_degraded("apify"):
            return "[DATA_MISSING:market_search] Market Search Failed：所有來源已降級或配額耗盡。"
        if not _consume_source_quota("apify"):
            return "[DATA_MISSING:market_search] Market Search Failed：免費來源失敗，且 Apify 當日配額已用盡。"

        try:
            result = _search_with_apify(query, max_items=4)
            _record_source_outcome("apify", True)
            _set_cache(cache_key, result)
            return result
        except ValueError as e:
            _record_source_outcome("apify", False, _reason_from_exception(e))
            return f"[DATA_MISSING:market_search] Market Search Failed：{e}"
        except Exception as e:
            logger.warning("market_search Apify failed: %s", e)
            _record_source_outcome("apify", False, _reason_from_exception(e))
            return "[DATA_MISSING:market_search] Market Search Failed：所有來源均無法取得資料。"

    return traced_tool_execution("market_search_tool", {"query": query}, _run)


# ═══════════════════════════════════════════════════════════════════
# CoinGlass On-chain Data
# ═══════════════════════════════════════════════════════════════════

# CoinGlass API V4 endpoints（支援多幣種，預設 BTC）
_COINGLASS_BASE = "https://open-api-v4.coinglass.com"


def _coinglass_endpoints(symbol: str = "BTC") -> dict[str, str]:
    """依 symbol 產生 CoinGlass API v4 endpoint URL（與官方 base + CG-API-KEY 一致）。"""
    pair = f"{symbol}USDT"
    return {
        # 官方文件：GET open-api-v4.coinglass.com，Header CG-API-KEY；部分端點需較高方案否則回 code=401 msg=Upgrade plan
        "open_interest": (
            f"{_COINGLASS_BASE}/api/futures/open-interest/aggregated-history"
            f"?symbol={symbol}&interval=1d&limit=30"
        ),
        "funding_rate": f"{_COINGLASS_BASE}/api/futures/funding-rate/history?exchange=Binance&symbol={pair}&interval=8h&limit=1",
        "liquidations": f"{_COINGLASS_BASE}/api/futures/liquidation/history?exchange=Binance&symbol={pair}&interval=1h&limit=24",
        "long_short_ratio": f"{_COINGLASS_BASE}/api/futures/top-long-short-account-ratio/history?exchange=Binance&symbol={pair}&interval=1d&limit=1",
        "options_info": f"{_COINGLASS_BASE}/api/option/info?symbol={symbol}",
    }


def _coinglass_success(body: object) -> bool:
    """CoinGlass v4 成功時 code 為字串 '0' 或整數 0（錯誤時常為字串如 '401'、msg=Upgrade plan）。"""
    if not isinstance(body, dict):
        return False
    c = body.get("code")
    return c == "0" or c == 0


def _parse_coinglass_funding_rate(data: list, symbol: str = "BTC") -> str:
    """將資金費率 API 回傳解析為 Agent 友善文字。"""
    if not data or not isinstance(data, list):
        return f"[DATA_MISSING:funding_rate] CoinGlass 無 {symbol} 資金費率數據。"
    latest = data[-1] if data else {}
    close_raw = (
        latest.get("close") or latest.get("open") or
        latest.get("fundingRate") or latest.get("funding_rate") or
        latest.get("value")
    )
    if close_raw is None:
        return f"[DATA_MISSING:funding_rate] CoinGlass 無法解析 {symbol} 資金費率（欄位不存在）。"
    try:
        rate_pct = float(close_raw) * 100
    except (TypeError, ValueError):
        return f"[DATA_MISSING:funding_rate] CoinGlass {symbol} 資金費率格式異常。"
    hint = "多頭付費給空頭，情緒偏熱" if rate_pct > 0 else "空頭付費給多頭，情緒偏冷"
    level = "🔴 極度過熱" if rate_pct > 0.05 else ("🟡 偏熱" if rate_pct > 0.01 else ("🟢 中性" if rate_pct >= -0.01 else "🔵 偏冷"))
    return f"{symbol} 資金費率 {rate_pct:.4f}% {level}，{hint}"


def _parse_coinglass_liquidations(data: list, symbol: str = "BTC") -> str:
    """將清算 API 回傳解析為 Agent 友善文字（過去 24h 彙總）。"""
    if not data or not isinstance(data, list):
        return f"[DATA_MISSING:liquidations] CoinGlass 無 {symbol} 清算數據。"
    total_long = total_short = 0.0
    for item in data:
        try:
            total_long += float(item.get("long_liquidation_usd") or 0)
            total_short += float(item.get("short_liquidation_usd") or 0)
        except (TypeError, ValueError):
            continue
    total = total_long + total_short
    return f"{symbol} 過去 24h 總爆倉 ${total/1e6:.2f}M，其中多頭爆倉 ${total_long/1e6:.2f}M，空頭爆倉 ${total_short/1e6:.2f}M"


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


def _parse_coinglass_long_short_ratio(data: list, symbol: str = "BTC") -> str:
    """將大戶多空比 API 回傳解析為 Agent 友善文字。"""
    if not data or not isinstance(data, list):
        return f"[DATA_MISSING:long_short_ratio] CoinGlass 無 {symbol} 多空比數據。"
    latest = data[-1] if data else {}
    ratio_raw = (
        latest.get("top_account_long_short_ratio") or
        latest.get("topAccountLongShortRatio") or
        latest.get("longShortRatio") or
        latest.get("ratio")
    )
    if ratio_raw is None:
        return f"[DATA_MISSING:long_short_ratio] CoinGlass 無法解析 {symbol} 大戶多空比（欄位不存在）。"
    try:
        ratio = float(ratio_raw)
    except (TypeError, ValueError):
        return f"[DATA_MISSING:long_short_ratio] CoinGlass {symbol} 多空比格式異常。"
    hint = "數值 > 1 代表大戶偏多" if ratio > 1 else "數值 < 1 代表大戶偏空"
    return f"{symbol} 最新大戶多空比為 {ratio:.2f}，{hint}"


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
        resp = _http_get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = _response_json_list(resp, "Binance-fundingRate")
        if data:
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
        oi_resp = _http_get(
            "https://fapi.binance.com/fapi/v1/openInterest",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        oi_resp.raise_for_status()
        oi_body = _response_json_dict(oi_resp, "Binance-openInterest") or {}
        oi = float(oi_body.get("openInterest", 0))
        price_resp = _http_get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5,
        )
        px_body = _response_json_dict(price_resp, "Binance-ticker") if price_resp.ok else None
        btc_price = float(px_body.get("price", 0)) if px_body else 0
        oi_usd = oi * btc_price / 1e9 if btc_price else 0
        return f"BTC 未平倉合約 OI: {oi:,.0f} BTC（約 ${oi_usd:.2f}B）（來源：Binance）"
    except Exception as e:
        logger.warning("Binance OI fallback failed: %s", e)
    return "[DATA_MISSING:open_interest] OI 暫無法取得（CoinGlass + Binance 均失敗）。"


def _binance_liquidations(symbol: str = "BTC") -> str:
    """從 Binance 公開 API 取得過去 24h 強平訂單並加總（不需 API key）。

    使用 GET /fapi/v1/allForceOrders（Security: NONE），
    SELL side = 多頭被爆，BUY side = 空頭被爆。
    """
    pair = f"{symbol}USDT"
    try:
        since_ms = int((datetime.now(timezone.utc).timestamp() - 86400) * 1000)
        resp = _http_get(
            "https://fapi.binance.com/fapi/v1/allForceOrders",
            params={"symbol": pair, "limit": 1000, "startTime": since_ms},
            timeout=12,
        )
        resp.raise_for_status()
        orders = _response_json_list(resp, "Binance-allForceOrders")
        if orders is None:
            raise ValueError("unexpected Binance force orders response")
        long_liq = short_liq = 0.0
        for o in orders:
            try:
                usd = float(o.get("origQty", 0)) * float(o.get("avgPrice", 0))
                if o.get("side") == "SELL":   # 多頭強平 → 賣出
                    long_liq += usd
                else:                          # 空頭強平 → 買入
                    short_liq += usd
            except (TypeError, ValueError):
                continue
        total = long_liq + short_liq
        if total == 0:
            return "[DATA_MISSING:liquidations] Binance 24h 爆倉數據為零或查無記錄。"
        return (
            f"{symbol} 過去 24h 總爆倉 ${total/1e6:.2f}M，"
            f"其中多頭爆倉 ${long_liq/1e6:.2f}M，空頭爆倉 ${short_liq/1e6:.2f}M"
            f"（來源：Binance allForceOrders）"
        )
    except Exception as e:
        logger.warning("_binance_liquidations fallback failed (symbol=%s): %s", symbol, e)
    return f"[DATA_MISSING:liquidations_{symbol}] Binance 爆倉備援失敗。"


def _binance_long_short_ratio() -> str:
    """從 Binance 公開 API 取得 BTC 全球大戶多空比（不需 API key）。"""
    try:
        resp = _http_get(
            "https://fapi.binance.com/futures/data/globalLongShortAccountRatio",
            params={"symbol": "BTCUSDT", "period": "1h", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = _response_json_list(resp, "Binance-longShortRatio")
        if data:
            ratio = float(data[-1].get("longShortRatio", 1.0))
            hint = "多方佔優" if ratio > 1 else "空方佔優"
            return f"BTC 全球多空比 {ratio:.3f}（{hint}）（來源：Binance）"
    except Exception as e:
        logger.warning("Binance long/short ratio fallback failed: %s", e)
    return "[DATA_MISSING:long_short_ratio] 多空比暫無法取得（CoinGlass + Binance 均失敗）。"


def _deribit_options_info(symbol: str = "BTC") -> str:
    """從 Deribit 公開 API 計算 Put/Call Ratio（不需 API key）。

    使用 GET /api/v2/public/get_book_summary_by_currency，
    加總 put/call OI 計算 PCR，附帶名目價值。
    """
    try:
        resp = _http_get(
            "https://www.deribit.com/api/v2/public/get_book_summary_by_currency",
            params={"currency": symbol, "kind": "option"},
            timeout=15,
        )
        resp.raise_for_status()
        root = _response_json_dict(resp, "Deribit")
        if root is None:
            return "[DATA_MISSING:options_info] Deribit API 回傳格式異常。"
        try:
            instruments = require_list(root, "result", source="Deribit")
        except ValueError:
            instruments = []
        if not instruments:
            return f"[DATA_MISSING:options_info] Deribit 無 {symbol} 選擇權數據。"

        put_oi = call_oi = 0.0
        put_usd = call_usd = 0.0
        for inst in instruments:
            name = str(inst.get("instrument_name", ""))
            oi = float(inst.get("open_interest") or 0)
            # 名目價值估算：OI 數量 × 標的價格（underlying_price）
            price = float(inst.get("underlying_price") or inst.get("mark_price") or 0)
            usd = oi * price
            if name.endswith("-P"):
                put_oi += oi
                put_usd += usd
            elif name.endswith("-C"):
                call_oi += oi
                call_usd += usd

        if call_oi == 0:
            return "[DATA_MISSING:options_info] Deribit call OI 為零，無法計算 PCR。"

        pcr = put_oi / call_oi
        hint = "偏空避險" if pcr > 1.0 else ("中性" if pcr > 0.7 else "偏多投機")
        total_usd = (put_usd + call_usd) / 1e9
        return (
            f"Put/Call Ratio: {pcr:.2f}（{hint}）"
            f" ｜ 名目價值: ${total_usd:.2f}B"
            f"（來源：Deribit，OI 統計）"
        )
    except Exception as e:
        logger.warning("_deribit_options_info fallback failed (symbol=%s): %s", symbol, e)
    return f"[DATA_MISSING:options_info] Deribit 備援失敗（{symbol}）。"


@tool
def coinglass_data_tool(metric: str) -> str:
    """獲取幣圈衍生品數據。格式：'metric' 或 'metric:SYMBOL'（預設 BTC）。

    metric 請輸入 'open_interest'（未平倉）、'funding_rate'（資金費率）、'liquidations'（24h 爆倉）、'long_short_ratio'（大戶多空比）、'options_info'（選擇權 Put/Call Ratio + Max Pain）。
    範例：'funding_rate'（預設 BTC）、'funding_rate:ETH'、'liquidations:SOL'。
    """

    def _run() -> str:
        # 解析 metric:SYMBOL 格式
        if ":" in metric:
            metric_part, symbol = metric.split(":", 1)
            symbol = symbol.strip().upper()
        else:
            metric_part = metric
            symbol = "BTC"
        metric_lower = metric_part.strip().lower()

        supported = {"open_interest", "funding_rate", "liquidations", "long_short_ratio", "options_info"}
        if metric_lower not in supported:
            return f"CoinGlass Tool Failed：不支援的 metric '{metric_part}'，僅支援 {', '.join(sorted(supported))}。"

        cache_key = ("coinglass", f"{metric_lower}_{symbol}")
        cached = _get_cache(cache_key)
        if cached:
            return cached

        api_key = os.getenv("COINGLASS_API_KEY")
        endpoints = _coinglass_endpoints(symbol)
        url = endpoints.get(metric_lower)

        if api_key and url:
            try:
                headers = {"accept": "application/json", "CG-API-KEY": api_key}
                response = _http_get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    body = _response_json_dict(response, "CoinGlass") or {}
                    if not _coinglass_success(body):
                        logger.warning(
                            "CoinGlass v4 non-success: code=%r msg=%r metric=%s symbol=%s",
                            body.get("code"),
                            body.get("msg"),
                            metric_lower,
                            symbol,
                        )
                    if _coinglass_success(body):
                        try:
                            data = require_list(body, "data", source="CoinGlass")
                        except ValueError:
                            data = []
                        if metric_lower == "open_interest":
                            if data:
                                # 解析最新 OI 數據為可讀格式，而非原始 JSON
                                try:
                                    latest = data[-1] if isinstance(data, list) else data
                                    oi_val = float(latest.get("openInterest", 0) if isinstance(latest, dict) else 0)
                                    if oi_val > 0:
                                        oi_usd_b = oi_val / 1e9 if oi_val > 1e6 else oi_val
                                        result = f"BTC 未平倉合約 OI: 約 ${oi_usd_b:.2f}B（來源：CoinGlass）"
                                    else:
                                        result = ""
                                except (TypeError, ValueError, IndexError):
                                    result = ""
                            else:
                                result = ""
                        elif metric_lower == "funding_rate":
                            result = _parse_coinglass_funding_rate(data, symbol)
                        elif metric_lower == "liquidations":
                            result = _parse_coinglass_liquidations(data, symbol)
                        elif metric_lower == "options_info":
                            result = _parse_coinglass_options_info(data)
                        else:
                            result = _parse_coinglass_long_short_ratio(data, symbol)
                        if result:
                            _set_cache(cache_key, result)
                            return _append_data_as_of(result, "coinglass")
            except Exception as e:
                logger.warning("CoinGlass primary path failed metric=%s symbol=%s: %s", metric_lower, symbol, e)

        # ── CoinGlass 失敗，嘗試 Binance 公開 API 備援 ──
        if metric_lower == "funding_rate" and symbol == "BTC":
            result = _binance_funding_rate()
        elif metric_lower == "open_interest" and symbol == "BTC":
            result = _binance_open_interest()
        elif metric_lower == "long_short_ratio" and symbol == "BTC":
            result = _binance_long_short_ratio()
        elif metric_lower == "liquidations":
            # 所有幣種都試 Binance（公開 API），失敗再試 Apify（BTC 限定）
            result = _binance_liquidations(symbol)
            if result.startswith("[DATA_MISSING") and symbol == "BTC":
                result = _apify_liquidations_fallback()
        elif metric_lower == "options_info":
            # Deribit 公開 API 作為 CoinGlass 備援
            result = _deribit_options_info(symbol)
        else:
            result = f"[DATA_MISSING:coinglass_{metric_lower}] CoinGlass API 暫無回應，此指標無備援來源。"
        _set_cache(cache_key, result)
        if result.startswith("[DATA_MISSING:"):
            return result
        return _append_data_as_of(result, "coinglass")

    return traced_tool_execution("coinglass_data_tool", {"metric": metric}, _run)


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
        resp = _http_get("https://cryptopanic.com/api/v1/posts/", params=params, timeout=10)
        resp.raise_for_status()
        try:
            raw = resp.json()
            payload = require_json_dict(raw, source="CryptoPanic")
            results = require_list(payload, "results", source="CryptoPanic")
        except ValueError as e:
            return f"[DATA_MISSING:cryptopanic] CryptoPanic Tool Failed: invalid JSON or schema ({e})"
        posts = results[:5]
        if not posts:
            return "CryptoPanic：目前沒有符合條件的重點新聞。"

        lines: list[str] = []
        for p in posts:
            if not isinstance(p, dict):
                continue
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
            resp = _http_get(
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
                root = _response_json_dict(resp, "Twitter-v2")
                raw_tw = root.get("data", []) if root else []
                tweets = raw_tw if isinstance(raw_tw, list) else []
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
            resp = _http_get(
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
                tw_root = _response_json_dict(resp, "RapidAPI-twitter154")
                raw_r = tw_root.get("results", []) if tw_root else []
                tweets = raw_r if isinstance(raw_r, list) else []
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
        except Exception as e:
            logger.warning("ml_quant_tool BigQuery history load failed: %s", e)
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
            resp = _http_get(url, timeout=20)
            resp.raise_for_status()
            cg = _response_json_dict(resp, "CoinGecko-market_chart")
            if cg is None:
                return "ML Quant Tool Failed：CoinGecko JSON 解析失敗。"
            try:
                prices = require_list(cg, "prices", source="CoinGecko-market_chart")
            except ValueError as e:
                logger.warning("ml_quant_tool CoinGecko prices schema: %s", e)
                return "ML Quant Tool Failed：CoinGecko 價格欄位格式異常。"
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
    except Exception as e:
        logger.warning("regime_scorecard VIX yfinance failed: %s", e)

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
    except Exception as e:
        logger.warning("regime_scorecard BTC RSI yfinance failed: %s", e)

    # Fear & Greed
    try:
        resp = _http_get("https://api.alternative.me/fng/?limit=1&format=json", timeout=8)
        raw = _response_json_dict(resp, "Alternative.me")
        if raw is not None:
            try:
                data = require_list(raw, "data", source="Alternative.me")
            except ValueError:
                data = []
            if data and isinstance(data[0], dict):
                values["fear_greed"] = float(data[0].get("value", 0))
    except Exception as e:
        logger.warning("regime_scorecard fear_greed fetch failed: %s", e)

    # CoinGlass fallback：從 Binance 抓資金費率
    try:
        resp = _http_get(
            "https://fapi.binance.com/fapi/v1/fundingRate",
            params={"symbol": "BTCUSDT", "limit": 1},
            timeout=8,
        )
        items = _response_json_list(resp, "Binance-fundingRate")
        if items:
            values["funding_%"] = float(items[-1].get("fundingRate", 0)) * 100
    except Exception as e:
        logger.warning("regime_scorecard Binance funding fetch failed: %s", e)

    # 爆倉數據：僅 CoinGlass API v4（Binance BTCUSDT 過去 24h 彙總，與 coinglass_data_tool 一致）
    try:
        cg_key = os.getenv("COINGLASS_API_KEY", "")
        if cg_key:
            liq_url = f"{_COINGLASS_BASE}/api/futures/liquidation/history"
            resp_v4 = _http_get(
                liq_url,
                headers={"accept": "application/json", "CG-API-KEY": cg_key},
                params={
                    "exchange": "Binance",
                    "symbol": "BTCUSDT",
                    "interval": "1h",
                    "limit": 24,
                },
                timeout=10,
            )
            body_v4 = _response_json_dict(resp_v4, "CoinGlass-liquidation")
            if body_v4 is not None and not _coinglass_success(body_v4):
                logger.warning(
                    "Regime scorecard: CoinGlass v4 liquidation non-success: code=%r msg=%r",
                    body_v4.get("code"),
                    body_v4.get("msg"),
                )
            if body_v4 is not None and _coinglass_success(body_v4):
                try:
                    data = require_list(body_v4, "data", source="CoinGlass-liquidation")
                except ValueError:
                    data = []
                if data:
                    total_liq = 0.0
                    for d in data:
                        if not isinstance(d, dict):
                            continue
                        lg = d.get("long_liquidation_usd", d.get("longLiquidationUsd", 0)) or 0
                        sh = d.get("short_liquidation_usd", d.get("shortLiquidationUsd", 0)) or 0
                        try:
                            total_liq += float(lg) + float(sh)
                        except (TypeError, ValueError):
                            continue
                    values["liq_24h_M"] = total_liq / 1e6
    except Exception as e:
        logger.warning("Regime scorecard: liquidation fetch failed: %s", e)

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
    except Exception as e:
        logger.warning("regime_scorecard ETF flow BigQuery failed: %s", e)

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
        resp = _http_get(
            "https://api.alternative.me/fng/?limit=2&format=json",
            timeout=10,
        )
        resp.raise_for_status()
        try:
            raw = resp.json()
            raw = require_json_dict(raw, source="Alternative.me")
            data = require_list(raw, "data", source="Alternative.me")
        except ValueError as e:
            logger.warning("fear_greed_tool: %s", e)
            return "[DATA_MISSING:fear_greed] Alternative.me 回傳格式異常。"
        if not data:
            return "[DATA_MISSING:fear_greed] Alternative.me 無數據。"
        if not isinstance(data[0], dict):
            logger.warning("fear_greed_tool: data[0] not object, got %s", type(data[0]).__name__)
            return "[DATA_MISSING:fear_greed] Alternative.me 資料列格式異常。"

        today = data[0]
        today_val = int(today.get("value", 0))
        today_label = today.get("value_classification", "")

        result_parts = [f"Fear & Greed Index: {today_val}/100（{today_label}）"]

        if len(data) > 1 and isinstance(data[1], dict):
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
        except Exception as e:
            logger.warning("btc_etf_yfinance row %s failed: %s", ticker, e)
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
            resp = _http_get(endpoint, headers={"CG-API-KEY": api_key}, timeout=10)
            if resp.status_code != 200:
                continue
            payload = _response_json_dict(resp, "CoinGlass-ETF")
            if payload is None:
                continue
            if not _coinglass_success(payload):
                logger.warning(
                    "CoinGlass ETF endpoint non-success: code=%r msg=%r url=%s",
                    payload.get("code"),
                    payload.get("msg"),
                    endpoint,
                )
                continue
            data = payload.get("data")
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
            resp = _http_get(url, timeout=10)
            if resp.status_code != 200:
                continue
            try:
                raw_data = resp.json()
                if isinstance(raw_data, list):
                    items = require_json_list(raw_data, source="SoSoValue")
                else:
                    d = require_json_dict(raw_data, source="SoSoValue")
                    items = d.get("data", [])
                    if not isinstance(items, list):
                        continue
            except ValueError:
                continue
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
            resp = _http_get(url, timeout=15)
            resp.raise_for_status()
            try:
                events = require_json_list(resp.json(), source="FMP-economic_calendar")
            except ValueError as e:
                logger.warning("FMP economic_calendar: %s", e)
                events = []

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
    except Exception as e:
        logger.warning("econ_calendar Apify fallback failed: %s", e)
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
        except Exception as e:
            logger.warning("multi_timeframe %s %s failed: %s", yf_symbol, interval, e)
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
    except Exception as e:
        logger.warning("rumor_scanner Apify failed: %s", e)
        return "[DATA_MISSING:rumor_scanner] Rumor Scanner Failed：所有來源均無法取得資料。"


# ═══════════════════════════════════════════════════════════════════
# BTC 估值錨（MVRV proxy + NVT ratio）— 全免費，不需 API key
# ═══════════════════════════════════════════════════════════════════

def _mvrv_200w_ma() -> tuple[float, float] | None:
    """
    用 200 週 MA 當 MVRV proxy（免費替代 Glassnode Realized Cap）。
    回傳 (current_price, ma_200w)；比值 > 1 = 估值偏高，< 1 = 估值偏低。
    """
    try:
        import yfinance as yf  # noqa: PLC0415

        # 需要至少 200 週 × 7 天 = 1400 天的資料
        df = yf.download("BTC-USD", period="1600d", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close = df["Close"].dropna()
        if len(close) < 200:
            return None
        # 200 週 MA = 200 × 7 日 MA（取收盤的滾動 1400 日均）
        ma_200w = float(close.rolling(1400, min_periods=200).mean().iloc[-1])
        current = float(close.iloc[-1])
        if ma_200w <= 0:
            return None
        return current, ma_200w
    except Exception as e:
        logger.warning("_mvrv_200w_ma failed: %s", e)
        return None


def _nvt_ratio() -> tuple[float, float] | None:
    """
    NVT = Market Cap / 30日平均鏈上交易量（USD）。
    Market Cap: CoinGecko 免費 API。
    TX Volume: Blockchain.info 免費 charts API。
    """
    market_cap: float | None = None
    tx_vol_30d: float | None = None

    # 1. Market Cap from CoinGecko
    try:
        resp = _http_get(
            "https://api.coingecko.com/api/v3/coins/bitcoin",
            params={"localization": "false", "tickers": "false",
                    "market_data": "true", "community_data": "false",
                    "developer_data": "false"},
            timeout=15,
        )
        resp.raise_for_status()
        cg_coin = _response_json_dict(resp, "CoinGecko-coin")
        mkt = (
            cg_coin.get("market_data", {}).get("market_cap", {}).get("usd")
            if cg_coin
            else None
        )
        if mkt:
            market_cap = float(mkt)
    except Exception as e:
        logger.warning("_nvt_ratio CoinGecko market cap failed: %s", e)

    # 2. 鏈上 30 日平均交易量 from Blockchain.info（免費，無需 key）
    try:
        resp = _http_get(
            "https://api.blockchain.info/charts/estimated-transaction-volume-usd",
            params={"timespan": "30days", "rollingAverage": "8hours",
                    "format": "json", "sampled": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        bc = _response_json_dict(resp, "Blockchain.info-chart")
        values = bc.get("values", []) if bc else []
        if values and isinstance(values, list):
            daily_vols = [float(v.get("y", 0)) for v in values if v.get("y")]
            if daily_vols:
                tx_vol_30d = sum(daily_vols) / len(daily_vols)
    except Exception as e:
        logger.warning("_nvt_ratio Blockchain.info tx volume failed: %s", e)

    if market_cap and tx_vol_30d and tx_vol_30d > 0:
        return market_cap, tx_vol_30d
    return None


@tool
def valuation_anchor_tool(query: str = "") -> str:
    """
    BTC 估值錨：提供機構級估值框架，識別當前價格相對歷史公允價值的位置。

    指標：
    · MVRV proxy（200週MA比值）：Price / 200-week MA，< 1.0 = 歷史底部區，> 3.5 = 歷史頂部區
    · NVT Ratio（網路價值/交易量）：< 40 = 低估，40-100 = 合理，> 100 = 高估
    · BTC Dominance（CoinGecko）：市值佔比，反映山寨幣輪動時機

    數據來源：yfinance（MVRV）、Blockchain.info（NVT 鏈上量）、CoinGecko（市值/主導率）。
    全部免費，不需 API key。
    """
    cache_key = ("valuation_anchor", _today_utc())
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "valuation_anchor")

    def _run() -> str:
        lines = ["【BTC 估值錨（Valuation Anchor）】"]

        # ── 1. MVRV proxy via 200-week MA ─────────────────────────────
        mvrv_data = _mvrv_200w_ma()
        if mvrv_data:
            price, ma200w = mvrv_data
            ratio = price / ma200w
            if ratio < 1.0:
                zone = "🟢 歷史底部區（極度低估，長線買入信號）"
            elif ratio < 2.0:
                zone = "🟡 公允價值區（合理估值，中性偏多）"
            elif ratio < 3.5:
                zone = "🟠 偏高估值區（牛市中後段，注意風險）"
            else:
                zone = "🔴 歷史頂部區（極度高估，歷史頂部附近）"
            lines.append(
                f"· MVRV proxy（200週MA比值）: <code>{ratio:.2f}x</code>"
                f"（現價 ${price:,.0f} / 200週MA ${ma200w:,.0f}）→ {zone}"
            )
        else:
            lines.append("· MVRV proxy: <code>N/A</code>（yfinance 數據不足）")

        # ── 2. NVT Ratio ──────────────────────────────────────────────
        nvt_data = _nvt_ratio()
        if nvt_data:
            market_cap, tx_vol = nvt_data
            nvt = market_cap / tx_vol
            if nvt < 40:
                nvt_zone = "低估（鏈上活動支撐估值）"
            elif nvt < 100:
                nvt_zone = "合理（鏈上活動與估值匹配）"
            else:
                nvt_zone = "高估（價格超前鏈上基本面）"
            lines.append(
                f"· NVT Ratio: <code>{nvt:.0f}</code>"
                f"（市值 ${market_cap/1e9:.0f}B / 30日均量 ${tx_vol/1e6:.0f}M/day）→ {nvt_zone}"
            )
        else:
            lines.append("· NVT Ratio: <code>N/A</code>（CoinGecko 或 Blockchain.info 無回應）")

        # ── 3. BTC Dominance ──────────────────────────────────────────
        try:
            resp = _http_get(
                "https://api.coingecko.com/api/v3/global",
                timeout=12,
            )
            resp.raise_for_status()
            glob = _response_json_dict(resp, "CoinGecko-global")
            dom = (
                glob.get("data", {}).get("market_cap_percentage", {}).get("btc")
                if glob
                else None
            )
            if dom is not None:
                dom_f = float(dom)
                if dom_f > 60:
                    dom_hint = "BTC 主導（資金未外溢至山寨）"
                elif dom_f > 50:
                    dom_hint = "BTC 微主導（山寨輪動初期）"
                else:
                    dom_hint = "山寨季訊號（資金分散至山寨幣）"
                lines.append(f"· BTC Dominance: <code>{dom_f:.1f}%</code> → {dom_hint}")
        except Exception as e:
            logger.warning("valuation_anchor BTC dominance failed: %s", e)
            lines.append("· BTC Dominance: <code>N/A</code>")

        # ── 4. 綜合判讀 ───────────────────────────────────────────────
        if mvrv_data and nvt_data:
            ratio = mvrv_data[0] / mvrv_data[1]
            nvt = nvt_data[0] / nvt_data[1]
            if ratio < 1.5 and nvt < 60:
                verdict = "📊 估值偏低：MVRV 與 NVT 雙指標均顯示當前價格低於公允價值，歷史上為中長線佈局機會。"
            elif ratio > 3.0 or nvt > 120:
                verdict = "⚠️ 估值偏高：至少一項指標進入歷史高估區，建議縮短持倉時間框架，設置較緊停損。"
            else:
                verdict = "⚖️ 估值中性：當前價格位於歷史合理區間，趨勢動能是主要操作依據。"
            lines.append(f"→ 綜合判讀：{verdict}")

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return result

    return traced_tool_execution("valuation_anchor_tool", {}, _run)


# ═══════════════════════════════════════════════════════════════════
# BTC 鏈上數據深化（CryptoQuant → Glassnode → Blockchain.info 備援）
# ═══════════════════════════════════════════════════════════════════

def _cryptoquant_fetch(path: str) -> dict | None:
    """CryptoQuant API 通用請求（需 CRYPTOQUANT_API_KEY）。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY", "")
    if not api_key:
        return None
    try:
        resp = _http_get(
            f"https://api.cryptoquant.com/v1{path}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        return _response_json_dict(resp, "CryptoQuant")
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
        resp = _http_get(
            "https://api.blockchain.info/charts/n-unique-addresses"
            "?timespan=14days&format=json&cors=true",
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        bc = _response_json_dict(resp, "Blockchain.info-addresses")
        values = bc.get("values", []) if bc else []
        if not isinstance(values, list) or len(values) < 7:
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
        resp = _http_get(
            "https://api.glassnode.com/v1/metrics/indicators/net_unrealized_profit_loss",
            params={"a": "BTC", "i": "24h", "limit": 2, "api_key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        try:
            data = require_json_list(resp.json(), source="Glassnode")
        except ValueError:
            return None
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
            try:
                parsed_raw = _json.loads(json_m.group())
                parsed = require_json_dict(parsed_raw, source="sentiment_score-LLM-json")
            except (ValueError, _json.JSONDecodeError) as parse_err:
                logger.warning("sentiment_score_tool LLM JSON not object: %s", parse_err)
                result = f"【社群情緒量化】\n· LLM 回傳：{raw[:300]}"
                _set_cache(cache_key, result)
                return result
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
# Financial Datasets API（美股損益／資產負債／現金流 — financialdatasets.ai）
# ═══════════════════════════════════════════════════════════════════

_FD_API_BASE = (os.getenv("FINANCIAL_DATASETS_API_BASE") or "https://api.financialdatasets.ai").rstrip("/")


def _fd_fmt_money(n: object) -> str:
    if n is None:
        return "N/A"
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "N/A"
    av = abs(v)
    if av >= 1e12:
        return f"${v / 1e12:.2f}T"
    if av >= 1e9:
        return f"${v / 1e9:.2f}B"
    if av >= 1e6:
        return f"${v / 1e6:.2f}M"
    return f"${v:,.0f}"


def _fd_http_get_json(path: str, params: dict[str, str | int]) -> dict | None:
    api_key = (os.getenv("FINANCIAL_DATASETS_API_KEY") or "").strip()
    headers: dict[str, str] = {"User-Agent": "Q-Silicon/1.0 (financial-datasets-tool)"}
    if api_key:
        headers["X-API-KEY"] = api_key
    url = f"{_FD_API_BASE}{path}"
    try:
        resp = _http_get(url, params=params, headers=headers, timeout=25)
        resp.raise_for_status()
        return _response_json_dict(resp, "FinancialDatasets")
    except Exception as e:
        logger.warning("financial_datasets GET %s failed: %s", path, e)
        return None


def _fd_rows(data: dict | None, list_key: str) -> list[dict]:
    if not data or not isinstance(data, dict):
        return []
    rows = data.get(list_key)
    if not isinstance(rows, list):
        return []
    return [r for r in rows[:3] if isinstance(r, dict)]


def _fd_yoy_pct(cur: object, prev: object) -> str:
    try:
        c = float(cur)  # type: ignore[arg-type]
        p = float(prev)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "N/A"
    if p == 0:
        return "N/A"
    return f"{(c - p) / abs(p) * 100:+.1f}%"


def _fd_summarize_ticker(sym: str, period: str) -> list[str]:
    """Build human-readable lines for one ticker (income + balance + cash flow)."""
    lines: list[str] = []
    p = period if period in ("annual", "quarterly") else "annual"
    inc = _fd_http_get_json(
        "/financials/income-statements/",
        {"ticker": sym, "period": p, "limit": 2},
    )
    bal = _fd_http_get_json(
        "/financials/balance-sheets/",
        {"ticker": sym, "period": p, "limit": 1},
    )
    cf = _fd_http_get_json(
        "/financials/cash-flow-statements/",
        {"ticker": sym, "period": p, "limit": 1},
    )
    ir = _fd_rows(inc, "income_statements")
    if not ir:
        lines.append(f"· {sym}：損益表 API 無資料或請求失敗（可檢查代號或 FINANCIAL_DATASETS_API_KEY）")
        return lines
    latest = ir[0]
    prev = ir[1] if len(ir) > 1 else None
    rev = latest.get("revenue")
    ni = latest.get("net_income")
    gp = latest.get("gross_profit")
    op_inc = latest.get("operating_income")
    eps_dil = latest.get("earnings_per_share_diluted") or latest.get("earnings_per_share")
    fiscal = latest.get("fiscal_period") or latest.get("report_period") or "N/A"
    yoy_rev = _fd_yoy_pct(rev, prev.get("revenue")) if prev else "N/A"
    lines.append(
        f"· <b>{sym}</b> 損益（{p}｜{fiscal}）：營收 <code>{_fd_fmt_money(rev)}</code> "
        f"（同比 <code>{yoy_rev}</code>）｜淨利 <code>{_fd_fmt_money(ni)}</code>｜"
        f"毛利 <code>{_fd_fmt_money(gp)}</code>｜營業利益 <code>{_fd_fmt_money(op_inc)}</code>"
        + (f"｜EPS(dil) <code>{eps_dil}</code>" if eps_dil not in (None, "") else "")
    )
    br = _fd_rows(bal, "balance_sheets")
    if br:
        b0 = br[0]
        td = b0.get("total_debt")
        debt_part = f"｜總負債 <code>{_fd_fmt_money(td)}</code>" if td is not None else ""
        lines.append(
            f"  └ 資產負債：總資產 <code>{_fd_fmt_money(b0.get('total_assets'))}</code>｜"
            f"現金 <code>{_fd_fmt_money(b0.get('cash_and_equivalents'))}</code>{debt_part}"
        )
    cr = _fd_rows(cf, "cash_flow_statements")
    if cr:
        c0 = cr[0]
        lines.append(
            f"  └ 現金流：營運現金流 <code>{_fd_fmt_money(c0.get('net_cash_flow_from_operations'))}</code>｜"
            f"自由現金流 <code>{_fd_fmt_money(c0.get('free_cash_flow'))}</code>"
        )
    lines.append(
        f"  └ <i>儀表板請加一行 MetricLine：label 含 <code>FinancialDatasets</code> 與 <code>{sym}</code>，"
        f"value 摘要營收或 FCF（勿捏造工具未回傳數字）</i>"
    )
    return lines


@tool
def financial_datasets_tool(query: str) -> str:
    """
    從 Financial Datasets API（financialdatasets.ai）取得美股損益表、資產負債表、現金流摘要。
    query：留空或 \"watchlist\"＝一次查 NVDA、MSFT、AAPL（免費層常開放）；
    或單一代號如 \"NVDA\"；或 \"NVDA:quarterly\" 指定季報。
    需將回傳中的營收／現金流等數字寫入 AI 儀表板 MetricLine，且 label 须含 FinancialDatasets 字樣。
    """

    def _run() -> str:
        raw = (query or "").strip()
        low = raw.lower()
        if not low or low == "watchlist":
            tickers = ["NVDA", "MSFT", "AAPL"]
            period = "annual"
        elif ":" in raw:
            sym, per = raw.split(":", 1)
            tickers = [sym.strip().upper()[:12]]
            p2 = per.strip().lower()
            period = "quarterly" if p2.startswith("q") or "quarter" in p2 else "annual"
        else:
            tickers = [raw.upper()[:12]]
            period = "annual"
        cache_key = ("financial_datasets", ",".join(tickers), period)
        cached = _get_cache(cache_key)
        if cached:
            return _append_data_as_of(cached, "financial_datasets")
        header = (
            "【美股基本面｜Financial Datasets API】\n"
            "（以下數字僅能複述本工具輸出；若寫入戰報儀表板，每檔至少一行 label 含 FinancialDatasets）\n"
        )
        body_lines: list[str] = []
        for sym in tickers:
            if not sym or not sym.isalnum():
                continue
            body_lines.extend(_fd_summarize_ticker(sym, period))
        if not body_lines:
            msg = (
                "[DATA_MISSING:financial_datasets] 無有效 ticker 或 API 全失敗。"
                " 可設 FINANCIAL_DATASETS_API_KEY；免費層常含 AAPL/NVDA/MSFT。"
            )
            return msg
        result = header + "\n".join(body_lines)
        if not result.startswith("[DATA_MISSING"):
            _set_cache(cache_key, result)
        return _append_data_as_of(result, "financial_datasets")

    q = (query or "").strip()
    return traced_tool_execution("financial_datasets_tool", {"query": q or "watchlist"}, _run)


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

    def _run() -> str:
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
                resp = _http_get(
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
                try:
                    fred_payload = require_json_dict(resp.json(), source="FRED")
                    observations = require_list(fred_payload, "observations", source="FRED")
                except ValueError as e:
                    logger.warning("macro_context FRED %s: schema error: %s", series_id, e)
                    return None
                for obs in observations:
                    raw = str(obs.get("value", "")).strip()
                    if not raw or raw == ".":
                        continue
                    try:
                        return round(float(raw), 3)
                    except ValueError:
                        continue
            except Exception as e:
                logger.warning("macro_context FRED series %s fetch failed: %s", series_id, e)
                return None
            return None

        # Historical modern-era range; 1980s peak ~15% for 2Y, ±9% covers black-swan.
        # 20.0% was too wide — 19.84% was passing as valid data.
        _YIELD_MIN, _YIELD_MAX = 0.1, 9.0

        try:
            df10 = yf.download("^TNX", period="3d", interval="1d", progress=False, auto_adjust=True)
            if df10 is not None and not df10.empty:
                c = df10["Close"].dropna()
                if hasattr(c, "ndim") and c.ndim > 1:
                    c = c.iloc[:, 0]
                if not c.empty:
                    raw_10y = round(float(c.iloc[-1]), 3)
                    if _YIELD_MIN <= raw_10y <= _YIELD_MAX:
                        yield_10y = raw_10y
                    else:
                        logger.warning("macro_context 10Y yield out of bounds: %.3f%%", raw_10y)
        except Exception as e:
            logger.warning("macro_context 10Y yield yfinance failed: %s", e)

        try:
            df2 = yf.download("2YY=F", period="5d", interval="1d", progress=False, auto_adjust=True)
            if df2 is not None and not df2.empty:
                c = df2["Close"].dropna()
                if hasattr(c, "ndim") and c.ndim > 1:
                    c = c.iloc[:, 0]
                if not c.empty:
                    raw_2y = round(float(c.iloc[-1]), 3)
                    if _YIELD_MIN <= raw_2y <= _YIELD_MAX:
                        yield_2y = raw_2y
                    else:
                        logger.warning("macro_context 2Y yield out of bounds: %.3f%%", raw_2y)
        except Exception as e:
            logger.warning("macro_context 2Y yield yfinance failed: %s", e)
        if yield_2y is None:
            fred_2y = _fetch_latest_fred_percent("DGS2")
            if fred_2y is not None and _YIELD_MIN <= fred_2y <= _YIELD_MAX:
                yield_2y = fred_2y
            elif fred_2y is not None:
                logger.warning("macro_context FRED DGS2 out of bounds: %.3f%%", fred_2y)

        y10_str = f"{yield_10y:.3f}%" if yield_10y is not None else "N/A"
        y2_str = f"{yield_2y:.3f}%" if yield_2y is not None else "N/A"
        if yield_10y is not None and yield_2y is not None:
            spread_bp = round((yield_10y - yield_2y) * 100, 1)
            spread_str = f"{spread_bp:+.1f}bp"
            # 利差近零時勿稱「正斜率」，避免與「極端正斜率」敘事矛盾
            if spread_bp < -0.5:
                curve_signal = "利率倒掛（衰退預警）⚠️"
            elif spread_bp > 0.5:
                curve_signal = "正斜率（長端高於短端）"
            else:
                curve_signal = "曲線平坦（2Y≈10Y，利差近零）"
        else:
            spread_str = "N/A"
            curve_signal = ""

        lines.append(f"🏛️ 美債 10Y: <code>{y10_str}</code> | 2Y: <code>{y2_str}</code> | 利差: <code>{spread_str}</code> {curve_signal}")

        # ── 2. Fed SOFR 期貨隱含預期 ─────────────────────────────────────
        _SOFR_MIN, _SOFR_MAX = -0.5, 25.0
        sofr_missing = True
        try:
            df_fed = yf.download("ZQ=F", period="3d", interval="1d", progress=False, auto_adjust=True)
            if df_fed is not None and not df_fed.empty:
                c = df_fed["Close"].dropna()
                if hasattr(c, "ndim") and c.ndim > 1:
                    c = c.iloc[:, 0]
                if not c.empty:
                    raw_sofr = round(100 - float(c.iloc[-1]), 3)
                    if _SOFR_MIN <= raw_sofr <= _SOFR_MAX:
                        implied_rate = raw_sofr
                        lines.append(f"🎯 Fed SOFR 期貨隱含利率: <code>{implied_rate:.3f}%</code>")
                        sofr_missing = False
                    else:
                        logger.warning("macro_context SOFR rate out of bounds: %.3f%%", raw_sofr)
        except Exception as e:
            logger.warning("macro_context Fed SOFR futures yfinance failed: %s", e)
        if sofr_missing:
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
                    except (TypeError, ValueError, AttributeError) as ed_e:
                        logger.warning("macro_context earnings date parse %s: %s", ticker_sym, ed_e)
            except Exception as e:
                logger.warning("macro_context earnings calendar %s: %s", ticker_sym, e)
                continue

        if upcoming_earnings:
            lines.append(f"📅 本週財報: <code>{' · '.join(upcoming_earnings)}</code>")
        else:
            lines.append("📅 本週財報: <code>本週無主要科技財報</code>")

        # ── 低置信度聲明（Fix 3）：yield 缺值時自動注入 ────────────────
        na_yield_fields = []
        if yield_10y is None:
            na_yield_fields.append("10Y殖利率")
        if yield_2y is None:
            na_yield_fields.append("2Y殖利率")
        if sofr_missing:
            na_yield_fields.append("SOFR期貨")
        if na_yield_fields:
            missing_str = "、".join(na_yield_fields)
            lines.append(
                f"⚠️ 低置信度｜資料缺失原因：{missing_str} yfinance/FRED 均無回應"
                f"｜替代指標：請參考 CME FedWatch Tool 或 Bloomberg 補充利率數據"
            )

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "macro_context")

    q = (query or "").strip()
    return traced_tool_execution("macro_context_tool", {"query": q or "(default)"}, _run)


# ═══════════════════════════════════════════════════════════════════
# 相關係數矩陣（BTC vs SPX / DXY / GLD — yfinance 免費）
# ═══════════════════════════════════════════════════════════════════

@tool
def correlation_matrix_tool(query: str = "") -> str:
    """
    計算 BTC 與主要資產的 30 日滾動相關係數，識別當前 BTC 是「風險資產模式」或「數字黃金模式」。

    涵蓋：BTC/SPX（風險偏好）、BTC/DXY（美元壓制）、BTC/GLD（黃金替代）、BTC/NDX（科技連動）。
    數據來源：yfinance（免費公開）。
    """
    cache_key = ("correlation_matrix", _today_utc())
    cached = _get_cache(cache_key)
    if cached:
        return cached

    def _run() -> str:
        try:
            import pandas as pd  # noqa: PLC0415
            import yfinance as yf  # noqa: PLC0415
        except ImportError as e:
            return f"[DATA_MISSING:correlation_matrix] 套件缺失：{e}"

        tickers = {
            "BTC":  "BTC-USD",
            "SPX":  "^GSPC",
            "DXY":  "DX-Y.NYB",
            "GLD":  "GLD",
            "NDX":  "^NDX",
        }

        try:
            raw = yf.download(
                list(tickers.values()),
                period="35d",
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
        except Exception as e:
            logger.warning("correlation_matrix yfinance download failed: %s", e)
            return f"[DATA_MISSING:correlation_matrix] yfinance 下載失敗：{e}"

        # 統一取 Close（yfinance 回傳 MultiIndex 或單層皆相容）
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                closes = raw["Close"].copy()
                closes.columns = {v: k for k, v in tickers.items()}[closes.columns] if False else closes.columns
                # rename back from yahoo symbol to short name
                rev = {v: k for k, v in tickers.items()}
                closes = closes.rename(columns=rev)
            else:
                closes = raw[["Close"]].copy()
                closes.columns = ["BTC"]
        except Exception as e:
            logger.warning("correlation_matrix close extraction failed: %s", e)
            return f"[DATA_MISSING:correlation_matrix] 收盤價擷取失敗：{e}"

        closes = closes.dropna(how="all").tail(30)
        if "BTC" not in closes.columns or len(closes) < 10:
            return "[DATA_MISSING:correlation_matrix] BTC 數據不足（需 ≥10 筆）。"

        btc = closes["BTC"].dropna()

        def _corr_hint(r: float) -> str:
            if r >= 0.7:
                return "高度正相關"
            if r >= 0.4:
                return "中度正相關"
            if r >= 0.1:
                return "弱正相關"
            if r >= -0.1:
                return "近零相關"
            if r >= -0.4:
                return "弱負相關"
            if r >= -0.7:
                return "中度負相關"
            return "高度負相關"

        lines = [f"【BTC 30日相關係數（{len(btc)} 日樣本）】"]
        pair_labels = {
            "SPX": ("BTC/SPX（風險偏好）",   "↑正相關 = 風險資產模式"),
            "DXY": ("BTC/DXY（美元壓制）",   "↓負相關 = 美元走強壓制BTC"),
            "GLD": ("BTC/GLD（黃金替代性）", "↑正相關 = 數字黃金模式"),
            "NDX": ("BTC/NDX（科技連動）",   "↑正相關 = 與科技股同漲跌"),
        }
        for key, (label, interpretation) in pair_labels.items():
            if key not in closes.columns:
                lines.append(f"· {label}: N/A（數據缺失）")
                continue
            pair = closes[key].dropna()
            aligned = btc.align(pair, join="inner")[0], btc.align(pair, join="inner")[1]
            if len(aligned[0]) < 10:
                lines.append(f"· {label}: N/A（樣本不足）")
                continue
            try:
                r = float(aligned[0].corr(aligned[1]))
                lines.append(f"· {label}: <code>{r:+.2f}</code>（{_corr_hint(r)}，{interpretation}）")
            except Exception:
                lines.append(f"· {label}: N/A")

        # 加入市場模式判斷
        spx_r = None
        dxy_r = None
        if "SPX" in closes.columns and "DXY" in closes.columns:
            try:
                b2, s2 = btc.align(closes["SPX"].dropna(), join="inner")
                b3, d2 = btc.align(closes["DXY"].dropna(), join="inner")
                spx_r = float(b2.corr(s2))
                dxy_r = float(b3.corr(d2))
            except Exception:
                pass

        if spx_r is not None and dxy_r is not None:
            if spx_r > 0.5 and dxy_r < -0.3:
                mode = "⚠️ 風險資產模式（跟漲跟跌 SPX，美元強則承壓）"
            elif spx_r < 0.2 and dxy_r < -0.3:
                mode = "🥇 數字黃金模式（與股市脫鉤，對美元獨立走勢）"
            elif spx_r > 0.5 and dxy_r > 0.1:
                mode = "🔀 混合模式（同時受風險情緒與美元主導，訊號分歧）"
            else:
                mode = "📊 低相關模式（當前 BTC 走勢相對獨立於傳統資產）"
            lines.append(f"→ 當前 BTC 模式判定：{mode}")

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "yfinance")

    return traced_tool_execution("correlation_matrix_tool", {}, _run)


# ═══════════════════════════════════════════════════════════════════
# 歷史類比引擎（純 yfinance，不需向量 DB）
# ═══════════════════════════════════════════════════════════════════

def _calc_rsi(series, period: int = 14) -> float:
    """計算 RSI(period)，回傳最新值（0-100）。"""
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.dropna().iloc[-1]) if not rsi.dropna().empty else 50.0


def _feature_vector(close, idx: int, ma200, ma50) -> list[float]:
    """
    計算指定索引位置的 5 維特徵向量（皆已正規化，無單位差異）：
    [0] RSI14 / 100                 — 動量超買超賣
    [1] log(price / MA200)          — 長期估值偏離
    [2] log(price / MA50)           — 中期趨勢位置
    [3] 30日年化波動率               — 風險狀態
    [4] 30日報酬（log return）       — 近期動能
    """
    import math  # noqa: PLC0415
    window = close.iloc[max(0, idx - 60): idx + 1]
    if len(window) < 30:
        return []
    price = float(window.iloc[-1])
    ma200_val = float(ma200.iloc[idx]) if idx < len(ma200) else float("nan")
    ma50_val = float(ma50.iloc[idx]) if idx < len(ma50) else float("nan")

    if math.isnan(ma200_val) or math.isnan(ma50_val) or ma200_val <= 0 or ma50_val <= 0:
        return []

    rsi = _calc_rsi(window) / 100.0

    try:
        log_vs_ma200 = math.log(price / ma200_val)
        log_vs_ma50 = math.log(price / ma50_val)
    except (ValueError, ZeroDivisionError):
        return []

    rets = window.pct_change().dropna().tail(30)
    vol_30d = float(rets.std() * (252 ** 0.5)) if len(rets) >= 5 else 0.5

    ret_30d = math.log(price / float(window.iloc[-31])) if len(window) >= 31 else 0.0

    return [rsi, log_vs_ma200, log_vs_ma50, min(vol_30d, 3.0), ret_30d]


@tool
def historical_analog_tool(query: str = "") -> str:
    """
    在 BTC 完整歷史中搜尋與當前市場結構最相似的歷史時期，提供「歷史類比」參考。

    方法：用 5 維技術特徵向量（RSI、長/中期估值偏離、波動率、近期動能）
    計算當前與所有歷史 30 日窗口的 Euclidean distance，找出最相似的 3 個時期，
    並報告它們之後 30/60/90 日的實際報酬。

    數據來源：yfinance BTC-USD（2015 至今）。免費，無需 API key。
    """
    cache_key = ("historical_analog", _today_utc())
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "historical_analog")

    def _run() -> str:
        try:
            import numpy as np  # noqa: PLC0415
            import pandas as pd  # noqa: PLC0415
            import yfinance as yf  # noqa: PLC0415
        except ImportError as e:
            return f"[DATA_MISSING:historical_analog] 套件缺失：{e}"

        try:
            df = yf.download("BTC-USD", start="2015-01-01", interval="1d",
                             progress=False, auto_adjust=True)
        except Exception as e:
            logger.warning("historical_analog yfinance download failed: %s", e)
            return f"[DATA_MISSING:historical_analog] yfinance 下載失敗：{e}"

        if df is None or df.empty:
            return "[DATA_MISSING:historical_analog] BTC-USD 歷史數據為空。"

        close: pd.Series = df["Close"].dropna()
        if len(close) < 300:
            return "[DATA_MISSING:historical_analog] 歷史數據不足 300 天。"

        ma200 = close.rolling(200).mean()
        ma50 = close.rolling(50).mean()

        # ── 當前特徵向量 ──────────────────────────────────────────────
        cur_vec = _feature_vector(close, len(close) - 1, ma200, ma50)
        if not cur_vec:
            return "[DATA_MISSING:historical_analog] 當前特徵向量計算失敗（數據不足）。"
        cur_arr = np.array(cur_vec)

        # 特徵權重：估值偏離 > 動能 > RSI > 波動率
        weights = np.array([1.0, 2.0, 1.5, 0.8, 1.5])

        # ── 掃描所有歷史窗口（保留最近 90 天以外的，避免自我比較）──────
        distances: list[tuple[float, int]] = []
        min_history_days = 250          # MA200 需要足夠數據
        exclude_recent = 90             # 排除最近 90 天（太相似無意義）
        scan_end = len(close) - exclude_recent

        for i in range(min_history_days, scan_end):
            vec = _feature_vector(close, i, ma200, ma50)
            if not vec:
                continue
            diff = (np.array(vec) - cur_arr) * weights
            dist = float(np.sqrt(np.dot(diff, diff)))
            distances.append((dist, i))

        if not distances:
            return "[DATA_MISSING:historical_analog] 無足夠歷史窗口進行比較。"

        distances.sort(key=lambda x: x[0])

        # ── 取 Top 3，且彼此相隔至少 60 天（避免連續相鄰結果）─────────
        top_analogues: list[tuple[float, int]] = []
        for dist, idx in distances:
            if all(abs(idx - prev_idx) >= 60 for _, prev_idx in top_analogues):
                top_analogues.append((dist, idx))
            if len(top_analogues) == 3:
                break

        # ── 格式化輸出 ─────────────────────────────────────────────────
        lines = [
            "【BTC 歷史類比（最相似的 3 個歷史時期）】",
            f"基準日：{close.index[-1].strftime('%Y-%m-%d')} | "
            f"BTC 現價 ${float(close.iloc[-1]):,.0f}",
        ]

        for rank, (dist, idx) in enumerate(top_analogues, 1):
            analog_date = close.index[idx]
            analog_price = float(close.iloc[idx])

            # 計算 30/60/90 日後報酬
            def _fwd_ret(days: int) -> str:
                fwd_idx = idx + days
                if fwd_idx >= len(close):
                    return "N/A"
                fwd_price = float(close.iloc[fwd_idx])
                pct = (fwd_price - analog_price) / analog_price * 100
                sign = "+" if pct >= 0 else ""
                return f"{sign}{pct:.1f}%"

            r30, r60, r90 = _fwd_ret(30), _fwd_ret(60), _fwd_ret(90)

            # 市場狀態簡述（用當時的 MVRV proxy）
            ma200_at = float(ma200.iloc[idx])
            mvrv_at = analog_price / ma200_at if ma200_at > 0 else 0
            rsi_at = _calc_rsi(close.iloc[max(0, idx - 60): idx + 1])

            if mvrv_at < 1.0:
                zone = "底部區"
            elif mvrv_at < 2.0:
                zone = "公允區"
            elif mvrv_at < 3.5:
                zone = "偏高區"
            else:
                zone = "頂部區"

            similarity = max(0, 100 - dist * 30)   # 距離轉換為 0-100 相似度分
            lines.append(
                f"\n#{rank} {analog_date.strftime('%Y-%m-%d')}"
                f"（相似度 {similarity:.0f}/100）"
                f"\n  · 當時價格 ${analog_price:,.0f}｜RSI {rsi_at:.0f}｜MVRV {mvrv_at:.2f}x（{zone}）"
                f"\n  · 後續報酬：30日 {r30}｜60日 {r60}｜90日 {r90}"
            )

        # ── 統計中位數報酬作為綜合預期 ────────────────────────────────
        fwd_30 = []
        for _, idx in top_analogues:
            fwd_idx = idx + 30
            if fwd_idx < len(close):
                fwd_30.append((float(close.iloc[fwd_idx]) - float(close.iloc[idx])) / float(close.iloc[idx]) * 100)

        if fwd_30:
            median_30 = float(np.median(fwd_30))
            sign = "+" if median_30 >= 0 else ""
            bullish_count = sum(1 for r in fwd_30 if r > 0)
            lines.append(
                f"\n→ 3 個類比 30 日中位數報酬：<code>{sign}{median_30:.1f}%</code>"
                f"｜看漲勝率 <code>{bullish_count}/{len(fwd_30)}</code>"
                f"（歷史統計，非預測）"
            )

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "historical_analog")

    return traced_tool_execution("historical_analog_tool", {}, _run)


# ═══════════════════════════════════════════════════════════════════
# CFTC COT — CME 比特幣期貨機構持倉週報（免費公開 API）
# ═══════════════════════════════════════════════════════════════════

@tool
def cot_positioning_tool(query: str = "") -> str:
    """
    取得 CFTC Commitments of Traders（COT）報告中 CME 比特幣期貨的機構持倉。

    追蹤：
    · Asset Manager / Institutional（共同基金、退休基金）淨多空
    · Leveraged Money（對沖基金）淨多空
    · 週變化（本期 vs 上期）— 辨別機構是在加倉還是撤倉

    數據來源：CFTC 公開 OData API（免費，無需 API key），週五更新上週二數據。
    """
    cache_key = ("cot_positioning", _today_utc())
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "cftc_cot")

    def _run() -> str:
        # CME Bitcoin futures CFTC market code = 133741
        url = (
            "https://publicreporting.cftc.gov/api/odata/v1/DiscreteTradersReports"
            "?$filter=CFTC_Market_Code eq '133741'"
            "&$orderby=Report_Date_as_YYYY_MM_DD desc"
            "&$top=2"
        )
        try:
            resp = _http_get(url, timeout=20)
            resp.raise_for_status()
            try:
                odata = require_json_dict(resp.json(), source="CFTC-OData")
                rows = require_list(odata, "value", source="CFTC-OData")
            except ValueError as e:
                logger.warning("cot_positioning CFTC schema: %s", e)
                return f"[DATA_MISSING:cot_positioning] CFTC COT API 回傳格式異常：{e}"
        except Exception as e:
            logger.warning("cot_positioning CFTC API failed: %s", e)
            return f"[DATA_MISSING:cot_positioning] CFTC COT API 無回應：{e}"

        if not rows:
            return "[DATA_MISSING:cot_positioning] CFTC COT 無 Bitcoin 期貨數據（市場代碼 133741）。"

        def _net(row: dict, long_key: str, short_key: str) -> int:
            try:
                return int(row.get(long_key) or 0) - int(row.get(short_key) or 0)
            except (TypeError, ValueError):
                return 0

        cur = rows[0]
        report_date = str(cur.get("Report_Date_as_YYYY_MM_DD", "N/A"))[:10]
        oi = int(cur.get("Open_Interest_All") or 0)

        am_net = _net(cur, "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All")
        lev_net = _net(cur, "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All")

        # 週變化（對比上期）
        am_chg = lev_chg = None
        if len(rows) >= 2:
            prev = rows[1]
            am_prev = _net(prev, "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All")
            lev_prev = _net(prev, "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All")
            am_chg = am_net - am_prev
            lev_chg = lev_net - lev_prev

        def _fmt_net(net: int, chg: int | None) -> str:
            sign = "+" if net >= 0 else ""
            label = "淨多" if net >= 0 else "淨空"
            chg_str = ""
            if chg is not None:
                arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "→")
                chg_str = f"（週變化 {arrow}{abs(chg):,}）"
            return f"{sign}{net:,}（{label}）{chg_str}"

        def _regime_hint(am: int, lev: int) -> str:
            # 機構多 + 槓桿多 = 強烈看漲共識
            if am > 0 and lev > 0:
                return "📈 機構與對沖基金同向看漲，市場共識偏多"
            if am < 0 and lev < 0:
                return "📉 機構與對沖基金同向看空，機構性賣壓存在"
            if am > 0 and lev < 0:
                return "⚖️ 機構看多、槓桿基金看空，出現分歧（常見於趨勢轉折前）"
            return "⚖️ 機構看空、槓桿基金看多，投機資金與長線資金方向相反"

        lines = [
            f"【CME 比特幣期貨 COT 報告｜{report_date}】",
            f"· 總未平倉合約（OI）: <code>{oi:,}</code> 張",
            f"· Asset Manager 淨倉: <code>{_fmt_net(am_net, am_chg)}</code>",
            f"· Leveraged Money 淨倉: <code>{_fmt_net(lev_net, lev_chg)}</code>",
            f"→ {_regime_hint(am_net, lev_net)}",
        ]

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "cftc_cot")

    return traced_tool_execution("cot_positioning_tool", {}, _run)


# ═══════════════════════════════════════════════════════════════════
# Grayscale 折溢價（GBTC / ETHE — yfinance 免費）
# ═══════════════════════════════════════════════════════════════════

# Grayscale 每日公告的 BTC per share（因 1.5% 管理費每年遞減）
# 此值需定期更新；若 Grayscale 網站 API 可用則動態抓取，否則用靜態近似值
_GBTC_BTC_PER_SHARE_FALLBACK: float = 0.00092    # 2025 近似值
_ETHE_ETH_PER_SHARE_FALLBACK: float = 0.00850    # 2025 近似值


def _grayscale_btc_per_share() -> float:
    """嘗試從 Grayscale 公開 JSON 動態取得 GBTC 的 BTC per share，失敗則用靜態近似值。"""
    try:
        resp = _http_get(
            "https://grayscale.com/wp-json/grayscale/v1/get-product?ticker=GBTC",
            timeout=10,
        )
        if resp.status_code == 200:
            data = _response_json_dict(resp, "Grayscale")
            if data is None:
                return _GBTC_BTC_PER_SHARE_FALLBACK
            # 嘗試常見欄位名稱
            for key in ("bitcoinPerShare", "digital_asset_per_share", "assetsPerShare", "nav_per_share"):
                val = data.get(key)
                if val:
                    return float(val)
    except Exception as e:
        logger.debug("_grayscale_btc_per_share fetch failed, using fallback: %s", e)
    return _GBTC_BTC_PER_SHARE_FALLBACK


@tool
def grayscale_premium_tool(query: str = "") -> str:
    """
    計算 Grayscale GBTC 與 ETHE 相對 NAV 的折溢價。

    · Premium > 0%：市場需求大於供給（機構搶購信號）
    · Discount < 0%：拋售壓力 / 套利空間（ETF 核准後常見深度折價）

    數據來源：yfinance（GBTC/ETHE 市價 + BTC-USD/ETH-USD）+ Grayscale 公開 BTC per Share。
    免費，無需 API key。
    """
    cache_key = ("grayscale_premium", _today_utc())
    if cached := _get_cache(cache_key):
        return _append_data_as_of(cached, "grayscale")

    def _run() -> str:
        try:
            import yfinance as yf  # noqa: PLC0415
        except ImportError as e:
            return f"[DATA_MISSING:grayscale_premium] yfinance 載入失敗：{e}"

        lines = ["【Grayscale 信託折溢價】"]
        any_data = False

        for trust_ticker, spot_ticker, per_share_fn, label in [
            ("GBTC", "BTC-USD", _grayscale_btc_per_share, "GBTC（BTC）"),
            ("ETHE", "ETH-USD", lambda: _ETHE_ETH_PER_SHARE_FALLBACK, "ETHE（ETH）"),
        ]:
            try:
                t_data = yf.download(
                    [trust_ticker, spot_ticker],
                    period="3d", interval="1d",
                    progress=False, auto_adjust=True,
                )
                if t_data is None or t_data.empty:
                    lines.append(f"· {label}: <code>N/A</code>（yfinance 無數據）")
                    continue

                import pandas as pd  # noqa: PLC0415
                if isinstance(t_data.columns, pd.MultiIndex):
                    closes = t_data["Close"]
                else:
                    lines.append(f"· {label}: <code>N/A</code>（數據格式異常）")
                    continue

                trust_price = float(closes[trust_ticker].dropna().iloc[-1])
                spot_price = float(closes[spot_ticker].dropna().iloc[-1])
                asset_per_share = per_share_fn()

                nav = spot_price * asset_per_share
                if nav <= 0:
                    lines.append(f"· {label}: <code>N/A</code>（NAV 計算異常）")
                    continue

                premium_pct = (trust_price - nav) / nav * 100
                sign = "+" if premium_pct >= 0 else ""
                if premium_pct > 5:
                    hint = "溢價偏高（機構需求強，但注意過熱）"
                elif premium_pct >= 0:
                    hint = "小幅溢價（正常需求）"
                elif premium_pct >= -5:
                    hint = "小幅折價（輕微拋壓或套利空間）"
                elif premium_pct >= -15:
                    hint = "明顯折價（機構拋售壓力）"
                else:
                    hint = "深度折價（強烈賣壓 / 贖回潮）"

                lines.append(
                    f"· {label}: 市價 <code>${trust_price:.2f}</code>"
                    f" / NAV <code>${nav:.2f}</code>"
                    f" → <code>{sign}{premium_pct:.2f}%</code>（{hint}）"
                )
                any_data = True
            except Exception as e:
                logger.warning("grayscale_premium %s failed: %s", trust_ticker, e)
                lines.append(f"· {label}: <code>N/A</code>（{type(e).__name__}）")

        if not any_data:
            return "[DATA_MISSING:grayscale_premium] GBTC 與 ETHE 數據均無法取得。"

        result = "\n".join(lines)
        _set_cache(cache_key, result)
        return _append_data_as_of(result, "grayscale")

    return traced_tool_execution("grayscale_premium_tool", {}, _run)


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

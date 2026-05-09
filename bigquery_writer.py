"""BigQuery write operations: metrics extraction and exclusion context.

Extracted from main.py to reduce module size. Read operations remain in
tracker.py; this module handles writing daily_metrics and reading
exclusion context for the next run.
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

from config import (
    GATE_FAILURE_LOG_TABLE,
    METRICS_TABLE,
    PAPER_EXECUTION_AUDIT_TABLE,
    PROJECT_ID,
    RECOMMENDATIONS_TABLE,
    REVIEWER_LOG_TABLE,
)
from telegram_sender import strip_html

logger = logging.getLogger(__name__)

SKIP_BIGQUERY = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")
GATE_FAILURE_BQ_LOG = os.getenv("GATE_FAILURE_BQ_LOG", "1").lower() not in ("0", "false", "no")
REVIEWER_LOG_BQ = os.getenv("REVIEWER_LOG_BQ", "1").lower() not in ("0", "false", "no")
DAILY_BRIEF_JSON_BQ_TABLE = os.getenv("DAILY_BRIEF_JSON_BQ_TABLE", "").strip()
NOTEBOOKLM_COST_LOG_TABLE = os.getenv("NOTEBOOKLM_COST_LOG_TABLE", "").strip()

# ── 語義去重（Semantic Deduplication）──────────────────────────────────
_SBERT_MODEL: object = None  # None=not loaded, False=unavailable, Model=ready

try:
    from scipy.spatial.distance import cosine as _cosine_distance
except ImportError:
    _cosine_distance = None


def _get_sbert_model():
    """Lazy-load sentence-transformers model (first call ~1-2s, cached after).

    Falls back gracefully if the library is missing or the model cannot be
    loaded (e.g. no HuggingFace network access in Cloud Run, disk quota, etc.).
    """
    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SBERT_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except ImportError:
            _SBERT_MODEL = False  # sentinel: don't retry
            logger.warning("sentence-transformers not installed; semantic dedup disabled.")
        except Exception as exc:  # noqa: BLE001
            _SBERT_MODEL = False  # sentinel: don't retry
            logger.warning(
                "Failed to load SBERT model (semantic dedup disabled): %s", exc
            )
    return _SBERT_MODEL if _SBERT_MODEL is not False else None


def _semantic_dedup_titles(titles: list[str], threshold: float = 0.80) -> list[str]:
    """Filter semantically duplicate titles using cosine similarity on embeddings.

    Args:
        titles: List of news title strings.
        threshold: Cosine similarity above this value is considered a duplicate (0-1).

    Returns:
        Deduplicated list preserving original order.
    """
    if len(titles) <= 1 or _cosine_distance is None:
        return titles

    model = _get_sbert_model()
    if model is None:
        return titles

    try:
        embeddings = model.encode(titles)

        kept_indices: list[int] = []
        for i, emb_i in enumerate(embeddings):
            is_dup = False
            for j in kept_indices:
                sim = 1.0 - _cosine_distance(emb_i, embeddings[j])
                if sim > threshold:
                    logger.debug(
                        "Semantic dedup: title %d (%.30s…) %.3f-similar to %d (%.30s…), skipping.",
                        i, titles[i], sim, j, titles[j],
                    )
                    is_dup = True
                    break
            if not is_dup:
                kept_indices.append(i)

        deduped = [titles[i] for i in kept_indices]
        if len(deduped) < len(titles):
            logger.info("Semantic dedup removed %d/%d duplicate titles.", len(titles) - len(deduped), len(titles))
        return deduped
    except Exception as e:
        logger.warning("Semantic dedup failed, returning original titles: %s", e)
        return titles


_SECTION_RE_CACHE: dict[str, re.Pattern] = {}


def _extract_section(text: str, header: str, max_chars: int = 500) -> str | None:
    """從報告文字中萃取指定區塊的內容（模組級，避免重複編譯）。"""
    if header not in _SECTION_RE_CACHE:
        _SECTION_RE_CACHE[header] = re.compile(
            re.escape(header) + r'[】]?\s*\n?([\s\S]*?)(?=────|$)'
        )
    m = _SECTION_RE_CACHE[header].search(text)
    if not m:
        return None
    body = m.group(1).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "…"
    return body or None


def _extract_news_titles(text: str, max_titles: int = 20) -> list[str]:
    """從戰報中萃取所有新聞標題，供次日排除重複使用。"""
    clean = strip_html(text)
    seen: set[str] = set()
    titles: list[str] = []
    for pattern in (r'〔新聞\s*\d+〕[^\n]*\n([^\n]{10,120})', r'〔新聞\s*\d+〕\s*([^\n]{10,120})'):
        for m in re.finditer(pattern, clean):
            t = m.group(1).strip()
            if t not in seen:
                seen.add(t)
                titles.append(t)
    return titles[:max_titles]


def _safe_float(m: re.Match | None, group: int = 1) -> float | None:
    """從 regex match 安全萃取 float，失敗回傳 None。"""
    if not m:
        return None
    try:
        return float(m.group(group))
    except (ValueError, IndexError):
        return None


def extract_and_save_metrics(report_text: str, project_id: str = PROJECT_ID) -> None:
    """從戰報文字萃取關鍵指標並寫入 BigQuery daily_metrics 資料表。"""
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping metrics write.")
        return
    metrics_table = f"{project_id}.market_data.daily_metrics"
    # 先剝除 HTML 標籤，避免 <code>97.65</code> 等結構干擾 regex 萃取
    clean_text = strip_html(report_text)

    # ── 1. 萃取 DXY：多模式匹配 ──────────────────
    dxy_patterns = [
        r'ICE\s+DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'美元指數[（(]DXY[）)]?\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'DXY[^<]*?(\d{2,3}\.\d{1,4})',
    ]
    dxy = None
    for pattern in dxy_patterns:
        m = re.search(pattern, clean_text, re.IGNORECASE)
        dxy = _safe_float(m)
        if dxy is not None:
            break

    # ── 2. 萃取 ETF 資金流：匹配中文語境的流出/流入 + 億 ────────────
    etf_flow = None
    etf_match = re.search(
        r'ETF.{0,60}?(流出|外流|流入)\D{0,10}?(\d+(?:\.\d+)?)\s*億',
        clean_text, re.IGNORECASE | re.DOTALL
    )
    if not etf_match:
        etf_match = re.search(
            r'(流出|外流|流入)\s*(\d+(?:\.\d+)?)\s*億',
            clean_text, re.IGNORECASE
        )
    if etf_match:
        direction_raw = etf_match.group(1).lower()
        value = _safe_float(etf_match, 2)
        if value is not None:
            is_outflow = any(k in direction_raw for k in ('流出', '外流'))
            etf_flow = -value if is_outflow else value

    # ── 3. 萃取 IMPACT 並轉為風險數值（強利空=5 … 強利多=1），與舊 RISK x/5 相容 ──
    _IMPACT_TO_SCORE = {"強利空": 5.0, "弱利空": 4.0, "中性": 3.0, "弱利多": 2.0, "強利多": 1.0}
    avg_risk = None
    impact_matches = re.findall(
        r'IMPACT[：:]\s*(強利空|弱利空|中性|弱利多|強利多)',
        clean_text
    )
    if impact_matches:
        scores = [_IMPACT_TO_SCORE.get(m, 3.0) for m in impact_matches]
        avg_risk = round(sum(scores) / len(scores), 2)
    else:
        # 向後相容：若仍出現舊格式 RISK x/5，則沿用
        legacy = re.findall(r'RISK(?:_SCORE)?[】\s]*(\d(?:\.\d)?)\s*/\s*5', clean_text, re.IGNORECASE)
        if legacy:
            try:
                scores = [float(s) for s in legacy]
                avg_risk = round(sum(scores) / len(scores), 2)
            except ValueError:
                pass

    # ── 4. B200 租賃價已移除，保留欄位以相容既有 BigQuery schema（寫入 None）──
    gpu_b200 = None

    # ── 4b. 萃取 P2 新增指標 ──────────────────────────────────────────────────
    # sentiment_score（來自 sentiment_score_tool 輸出，範圍 -1 到 +1）
    sent_m = re.search(r'情緒分數[：:]\s*([+-]?\d+\.\d+)', clean_text)
    sentiment_score = _safe_float(sent_m)

    # SOPR（來自 onchain_metrics_tool）
    sopr_m = re.search(r'SOPR[^：:（\n]*[：:]\s*([+-]?\d+\.\d+)', clean_text, re.IGNORECASE)
    sopr = _safe_float(sopr_m)

    # 交易所 BTC 淨流向（以千 BTC 為單位）
    netflow_m = re.search(r'交易所\s*BTC\s*淨流[向入出][^：:（\n]*[：:]\s*([+-]?\d+\.?\d*)', clean_text)
    exchange_netflow = _safe_float(netflow_m)

    # ── 5. 萃取 MVRV Z-Score：多模式匹配 ───────
    mvrv_patterns = [
        r'MVRV\s*Z[-\s]?Score\s*[→\->:：]+\s*(-?\d+(?:\.\d+)?)',
        r'MVRV[：:]\s*(-?\d+(?:\.\d+)?)',
        r'MVRV[^<]*?(-?\d+(?:\.\d+)?)',
    ]
    mvrv_z = None
    for pattern in mvrv_patterns:
        m = re.search(pattern, clean_text, re.IGNORECASE)
        mvrv_z = _safe_float(m)
        if mvrv_z is not None:
            break

    # ── 6. 萃取 Agent 情報摘要（幣圈 / AI 區塊各取第一段重點）──────
    grok_summary = _extract_section(clean_text, "【幣圈新聞】")
    # AI 區塊 header 隨版本變動，依序嘗試多種可能的 header
    gpt_summary = (
        _extract_section(clean_text, "AI 產業新聞")
        or _extract_section(clean_text, "AI 數據儀表板")
        or _extract_section(clean_text, "AI 市場")
        or _extract_section(clean_text, "【AI 基建現況】")
    )

    # ── 6b. 萃取新聞標題供次日去重 ──────────────────
    all_titles = _extract_news_titles(report_text, max_titles=25)
    all_titles = _semantic_dedup_titles(all_titles, threshold=0.80)
    news_titles_str = "\n".join(f"· {t}" for t in all_titles) if all_titles else None
    logger.info("Extracted %d news titles for deduplication (after semantic dedup).", len(all_titles))

    # ── Phase 4：從評分卡萃取 regime_score（-6 到 +6）──────────────
    regime_score: float | None = None
    regime_score_m = re.search(r'市場機制評分[^（(]*[（(]([+-]?\d+)/6[）)]', clean_text)
    if regime_score_m:
        regime_score = _safe_float(regime_score_m)

    logger.info(
        "Extracted metrics — DXY: %s, ETF Flow: %s億, Avg Risk: %s, MVRV Z: %s, "
        "Sentiment: %s, SOPR: %s, Netflow: %s, RegimeScore: %s",
        dxy, etf_flow, avg_risk, mvrv_z, sentiment_score, sopr, exchange_netflow, regime_score,
    )

    # ── 7. 寫入 BigQuery ──────────────────────────────────────────
    try:
        client = bigquery.Client(project=project_id)

        schema = [
            bigquery.SchemaField("timestamp",          "TIMESTAMP"),
            bigquery.SchemaField("dxy",                "FLOAT"),
            bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
            bigquery.SchemaField("avg_risk_score",     "FLOAT"),
            bigquery.SchemaField("gpu_b200_price",     "FLOAT"),
            bigquery.SchemaField("grok_summary",       "STRING"),
            bigquery.SchemaField("gpt_summary",        "STRING"),
            bigquery.SchemaField("mvrv_z_score",       "FLOAT"),
            bigquery.SchemaField("news_titles",        "STRING"),
            # P2 新增欄位
            bigquery.SchemaField("sentiment_score",    "FLOAT"),
            bigquery.SchemaField("sopr",               "FLOAT"),
            bigquery.SchemaField("exchange_netflow",   "FLOAT"),
            # Phase 4 新增欄位
            bigquery.SchemaField("regime_score",       "FLOAT"),
        ]
        table_ref = bigquery.Table(metrics_table, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        # 既有表不會因 create_table(exists_ok=True) 自動補新欄位，需手動 migration。
        table = client.get_table(metrics_table)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [field for field in schema if field.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info("Added missing BigQuery columns: %s", ", ".join(f.name for f in missing_fields))

        row = {
            "timestamp":         datetime.now(timezone.utc).isoformat(),
            "dxy":               dxy,
            "etf_flow_millions": etf_flow,
            "avg_risk_score":    avg_risk,
            "gpu_b200_price":    gpu_b200,
            "grok_summary":      grok_summary,
            "gpt_summary":       gpt_summary,
            "mvrv_z_score":      mvrv_z,
            "news_titles":       news_titles_str,
            # P2 新增欄位
            "sentiment_score":   sentiment_score,
            "sopr":              sopr,
            "exchange_netflow":  exchange_netflow,
            # Phase 4 新增欄位
            "regime_score":      regime_score,
        }
        non_null_count = sum(1 for v in [dxy, etf_flow, avg_risk, mvrv_z] if v is not None)
        if non_null_count == 0:
            logger.warning("All key metrics are None — skipping BigQuery write to avoid empty row.")
            return
        logger.info("Writing %d/4 key metrics to BigQuery.", non_null_count)

        errors = client.insert_rows_json(metrics_table, [row])
        if errors:
            logger.error("BigQuery insert errors: %s", errors)
        else:
            logger.info("Daily metrics written to BigQuery successfully.")
    except DefaultCredentialsError as e:
        # Expected in local dev without GCP credentials — warn, don't error.
        logger.warning("BigQuery credentials not configured (metrics write skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write metrics to BigQuery: %s", e)


def _fetch_recent_recommended_assets(client: bigquery.Client, days: int = 3) -> list[str]:
    """查詢近 N 天已建議的資產代號，供排除重複標的使用。"""
    try:
        rows = list(client.query(f"""
            SELECT DISTINCT asset
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
            ORDER BY asset
        """).result())
        return [r["asset"] for r in rows if r.get("asset")]
    except Exception as e:
        logger.warning("Failed to fetch recent recommended assets: %s", e)
        return []


def _fetch_last_rotation_gate_warnings() -> str | None:
    """讀取最近 25 小時內的 scratchpad JSONL，回傳輪動相關 gate 警示文字（供 LLM 自我修正）。"""
    try:
        from scratchpad import scratchpad_dir  # 延遲匯入，避免循環依賴
        sd = scratchpad_dir()
    except Exception:
        return None
    if not sd.exists():
        return None
    cutoff = time.time() - 25 * 3600
    try:
        files = sorted(sd.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    rotation_issues: list[str] = []
    for jf in files[:5]:  # 最多掃最新 5 個檔案，避免耗時
        try:
            if jf.stat().st_mtime < cutoff:
                break
            with open(jf, encoding="utf-8") as f:
                for line in f:
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") != "gate_result":
                        continue
                    for issue in evt.get("top_issues", []):
                        if "輪動" in issue or "rotation" in str(issue).lower():
                            rotation_issues.append(str(issue))
        except OSError:
            continue
    if not rotation_issues:
        return None
    issues_text = "\n".join(f"  · {x}" for x in rotation_issues[:3])
    return (
        f"⚠️ 前次產報 Gate 輪動警示（請本次修正）：\n{issues_text}\n"
        "本日若重複選用相同標的，QSREC 的 score_gap 必須 ≥ 12（selection_score − alt_candidate_score），"
        "且 alt_candidate_score 不得高於 selection_score − 12。無法構造時請改選新標的。"
    )


def _fetch_recent_stopped_out_trades(client: bigquery.Client, days: int = 3) -> str | None:
    """
    查詢近 N 天內觸發停損（HIT_STOP）的交易紀錄，格式化為 LLM 反思提示。
    讓 AI 知道近期哪些方向判斷失誤，自動降低同類看法的信心水準。
    """
    try:
        rows = list(client.query(f"""
            SELECT asset, direction, entry_price, stop_price, exit_price,
                   pnl_pct, report_date, narrative
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE status = 'HIT_STOP'
              AND report_date >= DATE_SUB(CURRENT_DATE('Asia/Taipei'), INTERVAL {days} DAY)
            ORDER BY report_date DESC
            LIMIT 5
        """).result())
    except Exception as e:
        logger.warning("Failed to fetch stopped-out trades: %s", e)
        return None

    if not rows:
        return None

    lines = ["⚠️ 系統回饋：近期停損紀錄（請本次調整判斷方向與信心水準）："]
    for r in rows:
        asset = r.get("asset", "?")
        direction = r.get("direction", "?")
        pnl = r.get("pnl_pct")
        pnl_str = f"{pnl:+.1f}%" if pnl is not None else "N/A"
        date_str = str(r.get("report_date", ""))[:10]
        narrative = str(r.get("narrative") or "")[:60]
        lines.append(
            f"  · {date_str} ${asset} {direction} 觸及停損 {pnl_str}"
            + (f"（原因：{narrative}）" if narrative else "")
        )
    lines.append(
        "請根據以上停損紀錄：① 若近期同方向連續失敗，本次應降低該方向信心（star_rating）或考慮換方向；"
        "② 若停損原因是宏觀衝擊（VIX 急升等），請確認今日宏觀環境是否已改變。"
    )
    return "\n".join(lines)


def fetch_exclusion_context(project_id: str = PROJECT_ID, metrics_table: str = METRICS_TABLE) -> str | None:
    """從 BigQuery 讀取前一日的新聞標題列表與近期已推薦資產，供研究流程排除重複。"""
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping exclusion context fetch.")
        return None
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

        news_titles_raw = row.get("news_titles") if hasattr(row, "get") else None
        if news_titles_raw:
            parts.append("昨日已報導的新聞標題（禁止重複選用）：\n" + news_titles_raw)
        else:
            for field in ("grok_summary", "gpt_summary"):
                val = row.get(field) if hasattr(row, "get") else None
                if val:
                    parts.append(val)

        # 近 3 天已推薦資產排除（強制輪換標的）
        recent_assets = _fetch_recent_recommended_assets(client, days=3)
        if recent_assets:
            asset_list = ", ".join(f"${a}" for a in recent_assets)
            parts.append(
                f"過去 3 天已建議的標的（除非有重大新催化劑，否則禁止重複選用）：{asset_list}\n"
                "必須優先選擇不在此清單中的標的。若該標的有全新重大事件（如 ETF 核准、主網升級、財報超預期），"
                "可以再次選用，但必須明確說明「重複選用理由：XXX」。"
            )
            logger.info("Loaded %d recent recommended assets for exclusion: %s", len(recent_assets), recent_assets)

        # 注入近期停損紀錄（反思迴圈：讓 LLM 知道哪些方向判斷失誤）
        stopped_out = _fetch_recent_stopped_out_trades(client, days=3)
        if stopped_out:
            parts.append(stopped_out)
            logger.info("Injected stopped-out trade feedback into exclusion context.")

        # 注入前日 Gate 輪動警示（負反饋迴路，讓 LLM 知道上次失敗）
        rotation_warn = _fetch_last_rotation_gate_warnings()
        if rotation_warn:
            parts.append(rotation_warn)
            logger.info("Injected rotation gate warning into exclusion context.")

        try:
            from signal_weights_store import format_weights_for_crew_context

            wctx = format_weights_for_crew_context()
            if wctx:
                parts.append(wctx)
                logger.info("Injected signal weights snapshot into exclusion context.")
        except Exception as _w_err:
            logger.warning("signal_weights context skipped: %s", _w_err)

        s = "\n\n".join(parts) if parts else None
        if s and len(s) > 2500:
            s = s[:2500] + "\n…[truncated]"
        return s
    except Exception as e:
        logger.warning("Could not fetch exclusion context from BigQuery: %s", e)
        return None


def _get_last_success_report_time_utc(
    project_id: str = PROJECT_ID,
    metrics_table: str = METRICS_TABLE,
) -> str | None:
    """查詢最近一次成功寫入 metrics 的時間（視為最近成功戰報時間）。"""
    if SKIP_BIGQUERY:
        return None
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT timestamp
            FROM `{metrics_table}`
            WHERE timestamp IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return None
        row = rows[0]
        ts = row.get("timestamp") if hasattr(row, "get") else None
        if not ts:
            return None
        if hasattr(ts, "strftime"):
            return ts.strftime("%Y-%m-%d %H:%M UTC")
        return str(ts)
    except Exception as e:
        logger.warning("Could not fetch last successful report time from BigQuery: %s", e)
        return None


def _resolve_profile_for_bq(
    *,
    explicit: str | None,
    validation_profile: object | None = None,
) -> str:
    """Resolve `REPORT_PROFILE` for BQ audit rows: explicit kw > validation dict > env."""
    from brief_profiles import get_active_profile

    raw: str | None = None
    if explicit is not None and str(explicit).strip() != "":
        raw = str(explicit).strip()
    elif validation_profile is not None and str(validation_profile).strip() != "":
        raw = str(validation_profile).strip()
    return get_active_profile(raw)


def _ensure_table_has_schema(client: bigquery.Client, table_id: str, schema: list[bigquery.SchemaField]) -> None:
    table_ref = bigquery.Table(table_id, schema=schema)
    client.create_table(table_ref, exists_ok=True)
    table = client.get_table(table_id)
    existing_columns = {field.name for field in table.schema}
    missing_fields = [field for field in schema if field.name not in existing_columns]
    if missing_fields:
        table.schema = list(table.schema) + missing_fields
        client.update_table(table, ["schema"])
        logger.info(
            "Added missing BigQuery columns to %s: %s",
            table_id,
            ", ".join(field.name for field in missing_fields),
        )


def write_daily_brief_json(
    *,
    report_date: str,
    profile: str,
    payload_json: str,
    run_id: str = "",
    source: str = "pipeline",
    table_id: str | None = None,
) -> None:
    """Persist a complete DailyBriefReport JSON row when explicitly configured."""
    if SKIP_BIGQUERY:
        return
    tid = (table_id or "").strip() or DAILY_BRIEF_JSON_BQ_TABLE
    if not tid:
        return
    bq_project = tid.split(".", 1)[0] if "." in tid else PROJECT_ID
    try:
        client = bigquery.Client(project=bq_project)
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("report_date", "DATE"),
            bigquery.SchemaField("profile", "STRING"),
            bigquery.SchemaField("run_id", "STRING"),
            bigquery.SchemaField("source", "STRING"),
            bigquery.SchemaField("payload_json", "STRING"),
            bigquery.SchemaField("payload_sha256", "STRING"),
        ]
        _ensure_table_has_schema(client, tid, schema)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report_date": report_date,
            "profile": profile,
            "run_id": run_id or None,
            "source": source,
            "payload_json": payload_json,
            "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        }
        errors = client.insert_rows_json(tid, [row])
        if errors:
            logger.error("BigQuery daily brief JSON insert errors: %s", errors)
        else:
            logger.info("DailyBriefReport JSON row written to %s (%s).", tid, report_date)
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (daily brief JSON skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write daily brief JSON to BigQuery: %s", e)


def write_notebooklm_cost_log(
    *,
    run_id: str,
    notebook_id: str,
    ticker: str = "",
    question_count: int = 0,
    status: str = "unknown",
    latency_ms: int = 0,
    cost_usd: float | None = None,
    metadata: dict | None = None,
    table_id: str | None = None,
) -> None:
    """Optional NotebookLM cost/usage log; no-op unless table env is set."""
    if SKIP_BIGQUERY:
        return
    tid = (table_id or "").strip() or NOTEBOOKLM_COST_LOG_TABLE
    if not tid:
        return
    bq_project = tid.split(".", 1)[0] if "." in tid else PROJECT_ID
    try:
        client = bigquery.Client(project=bq_project)
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("run_id", "STRING"),
            bigquery.SchemaField("notebook_id", "STRING"),
            bigquery.SchemaField("ticker", "STRING"),
            bigquery.SchemaField("question_count", "INTEGER"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("latency_ms", "INTEGER"),
            bigquery.SchemaField("cost_usd", "FLOAT"),
            bigquery.SchemaField("metadata_json", "STRING"),
        ]
        _ensure_table_has_schema(client, tid, schema)
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id or None,
            "notebook_id": notebook_id or None,
            "ticker": ticker or None,
            "question_count": int(question_count or 0),
            "status": str(status or "unknown"),
            "latency_ms": int(latency_ms or 0),
            "cost_usd": cost_usd,
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        }
        errors = client.insert_rows_json(tid, [row])
        if errors:
            logger.error("BigQuery NotebookLM cost log insert errors: %s", errors)
        else:
            logger.info("NotebookLM cost log row written to %s (%s).", tid, status)
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (NotebookLM cost log skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write NotebookLM cost log to BigQuery: %s", e)


def write_llm_run_log(
    model_name: str,
    used_fallback: bool,
    retry_count: int,
    gate_passed: bool,
    gate_issues: list[str] | None = None,
    *,
    profile: str | None = None,
    project_id: str = PROJECT_ID,
) -> None:
    """Write LLM run metadata to BigQuery llm_run_log table.

    Tracks which model was used, whether fallback was triggered, how many retries
    were needed, and whether the Gate passed — enabling data-driven LLM selection.
    """
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping LLM run log write.")
        return
    llm_run_log_table = f"{project_id}.market_data.llm_run_log"
    try:
        active_profile = _resolve_profile_for_bq(explicit=profile)
        client = bigquery.Client(project=project_id)
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("model_name", "STRING"),
            bigquery.SchemaField("used_fallback", "BOOL"),
            bigquery.SchemaField("retry_count", "INTEGER"),
            bigquery.SchemaField("gate_passed", "BOOL"),
            bigquery.SchemaField("gate_issues_count", "INTEGER"),
            bigquery.SchemaField("gate_issues_preview", "STRING"),
            bigquery.SchemaField("profile", "STRING"),
        ]
        table_ref = bigquery.Table(llm_run_log_table, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        # Migrate any missing columns on an existing table.
        table = client.get_table(llm_run_log_table)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [f for f in schema if f.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info(
                "Added missing LLM run log columns: %s",
                ", ".join(f.name for f in missing_fields),
            )

        issues = gate_issues or []
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_name": model_name,
            "used_fallback": used_fallback,
            "retry_count": retry_count,
            "gate_passed": gate_passed,
            "gate_issues_count": len(issues),
            "gate_issues_preview": " | ".join(issues[:3]) if issues else None,
            "profile": active_profile,
        }
        errors = client.insert_rows_json(llm_run_log_table, [row])
        if errors:
            logger.error("BigQuery LLM run log insert errors: %s", errors)
        else:
            logger.info(
                "LLM run log written (model=%s, fallback=%s, retries=%d, gate=%s, profile=%s).",
                model_name,
                used_fallback,
                retry_count,
                gate_passed,
                active_profile,
            )
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (LLM run log skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write LLM run log to BigQuery: %s", e)


def _bucket_gate_issues(issues: list[str]) -> dict[str, int]:
    """粗分類 Gate issue 字串，供週期分析／儀表板聚合（非阻塞語意）。"""
    buckets = {k: 0 for k in ("news", "qsrec", "source", "macro", "regime", "trade", "other")}
    rules: list[tuple[str, tuple[str, ...]]] = [
        ("source", ("DATA_MISSING", "STALE_DATA", "SourceHealth", "SourceErrors", "資料缺失")),
        ("news", ("新聞", "UTC+8", "〔新聞")),
        ("qsrec", ("QSREC", "結構化", "本日選擇理由", "json")),
        ("macro", ("宏觀", "利率", "美債", "利差")),
        ("regime", ("market_regime", "mixed_regime", "regime")),
        ("trade", ("交易", "R:R", "風險預算", "進場", "停損", "觀望模式", "N/A 關鍵價格")),
    ]
    for issue in issues:
        placed = False
        low = issue
        for name, subs in rules:
            if any(s in low for s in subs):
                buckets[name] += 1
                placed = True
                break
        if not placed:
            buckets["other"] += 1
    return buckets


def write_gate_failure_log(
    *,
    attempt: int,
    validation: dict,
    report_chars: int,
    used_fallback: bool,
    profile: str | None = None,
    table_id: str | None = None,
) -> None:
    """將單次 validate_report 失敗（含僅 warning）寫入 BQ，供事後聚合與自我改善分析。

    不自動改 prompt（防注入）；僅結構化留存。設 GATE_FAILURE_BQ_LOG=0 可關閉。
    """
    if SKIP_BIGQUERY:
        return
    if not GATE_FAILURE_BQ_LOG:
        return
    issues = [str(x).strip() for x in (validation.get("issues") or []) if str(x).strip()]
    if not issues:
        return

    tid = (table_id or "").strip() or GATE_FAILURE_LOG_TABLE
    bq_project = tid.split(".", 1)[0] if "." in tid else PROJECT_ID
    blocking = validation.get("blocking_issues") or []
    warnings = validation.get("warning_issues") or []
    try:
        active_profile = _resolve_profile_for_bq(
            explicit=profile, validation_profile=validation.get("profile")
        )
        client = bigquery.Client(project=bq_project)
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("attempt", "INTEGER"),
            bigquery.SchemaField("blocking_count", "INTEGER"),
            bigquery.SchemaField("warning_count", "INTEGER"),
            bigquery.SchemaField("issue_count", "INTEGER"),
            bigquery.SchemaField("news_count", "INTEGER"),
            bigquery.SchemaField("used_fallback", "BOOL"),
            bigquery.SchemaField("bucket_counts_json", "STRING"),
            bigquery.SchemaField("issues_preview", "STRING"),
            bigquery.SchemaField("fingerprint", "STRING"),
            bigquery.SchemaField("report_chars", "INTEGER"),
            bigquery.SchemaField("profile", "STRING"),
        ]
        table_ref = bigquery.Table(tid, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        table = client.get_table(tid)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [f for f in schema if f.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info(
                "Added missing gate_failure_log columns: %s",
                ", ".join(f.name for f in missing_fields),
            )

        buckets = _bucket_gate_issues(issues)
        preview_src = " | ".join(issues[:3])
        if len(preview_src) > 512:
            preview_src = preview_src[:509] + "..."
        fp = hashlib.sha256("\n".join(sorted(issues)).encode("utf-8")).hexdigest()[:16]
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attempt": int(attempt),
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "issue_count": len(issues),
            "news_count": int(validation.get("news_count") or 0),
            "used_fallback": bool(used_fallback),
            "bucket_counts_json": json.dumps(buckets, ensure_ascii=False),
            "issues_preview": preview_src or None,
            "fingerprint": fp,
            "report_chars": int(report_chars),
            "profile": active_profile,
        }
        errors = client.insert_rows_json(tid, [row])
        if errors:
            logger.error("BigQuery gate_failure_log insert errors: %s", errors)
        else:
            logger.info(
                "gate_failure_log written (attempt=%s, issues=%d, blocking=%d, profile=%s).",
                attempt,
                len(issues),
                len(blocking),
                active_profile,
            )
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (gate_failure_log skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write gate_failure_log to BigQuery: %s", e)


def write_reviewer_log(
    *,
    run_id: str,
    profile: str | None,
    track: str,
    revision_count: int,
    python_fail_reasons: list[str],
    llm_fail_reasons: list[str],
    degraded: bool,
    final_trade_count: int,
    total_latency_ms: int,
    report_date: str | None = None,
    project_id: str = PROJECT_ID,
) -> None:
    """Write LangGraph reviewer loop outcome to BigQuery reviewer_log table.

    Called by degrade_node (degraded=True) and optionally by llm_reviewer_node
    on success (degraded=False) for quality trend monitoring.
    Respects SKIP_BIGQUERY; silently skips on missing credentials.
    report_date (YYYY-MM-DD) is the brief date, not the write time — avoids
    UTC midnight bucketing errors for late-night Asia/Taipei pipeline runs.
    """
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping reviewer_log write.")
        return
    if not REVIEWER_LOG_BQ:
        return

    try:
        active_profile = _resolve_profile_for_bq(explicit=profile)
        client = bigquery.Client(project=project_id)
        schema = [
            bigquery.SchemaField("run_id", "STRING"),
            bigquery.SchemaField("profile", "STRING"),
            bigquery.SchemaField("track", "STRING"),
            bigquery.SchemaField("revision_count", "INTEGER"),
            bigquery.SchemaField("python_fail_reasons", "STRING"),
            bigquery.SchemaField("llm_fail_reasons", "STRING"),
            bigquery.SchemaField("degraded", "BOOL"),
            bigquery.SchemaField("final_trade_count", "INTEGER"),
            bigquery.SchemaField("total_latency_ms", "INTEGER"),
            bigquery.SchemaField("report_date", "DATE"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        table_ref = bigquery.Table(REVIEWER_LOG_TABLE, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        table = client.get_table(REVIEWER_LOG_TABLE)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [f for f in schema if f.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info(
                "Added missing reviewer_log columns: %s",
                ", ".join(f.name for f in missing_fields),
            )

        now = datetime.now(timezone.utc)
        row = {
            "run_id": (run_id or "")[:64],
            "profile": active_profile,
            "track": (track or "")[:16],
            "revision_count": int(revision_count),
            "python_fail_reasons": json.dumps(python_fail_reasons or [], ensure_ascii=False)[:1024],
            "llm_fail_reasons": json.dumps(llm_fail_reasons or [], ensure_ascii=False)[:1024],
            "degraded": bool(degraded),
            "final_trade_count": int(final_trade_count),
            "total_latency_ms": int(total_latency_ms),
            "report_date": report_date or now.strftime("%Y-%m-%d"),
            "created_at": now.isoformat(),
        }
        errors = client.insert_rows_json(REVIEWER_LOG_TABLE, [row])
        if errors:
            logger.error("BigQuery reviewer_log insert errors: %s", errors)
        else:
            logger.info(
                "reviewer_log written (run_id=%s, track=%s, revision=%d, degraded=%s).",
                run_id,
                track,
                revision_count,
                degraded,
            )
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (reviewer_log skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write reviewer_log to BigQuery: %s", e)


def write_paper_execution_audit_row(
    *,
    signal_id: str,
    new_status: str,
    reason: str,
    quote_as_of: str,
    asset: str = "",
    direction: str = "",
) -> None:
    """Optional BigQuery audit row after a successful paper intent append (28a).

    Set ``PAPER_EXECUTION_AUDIT_TABLE`` to ``project.dataset.table`` and run
    ``docs/SQL/paper_execution_audit.sql``. Respects ``SKIP_BIGQUERY``; no-op if
    table env is empty or credentials are missing.
    """
    if SKIP_BIGQUERY:
        return
    tid = (PAPER_EXECUTION_AUDIT_TABLE or "").strip()
    if not tid:
        return
    bq_project = tid.split(".", 1)[0] if "." in tid else PROJECT_ID
    try:
        client = bigquery.Client(project=bq_project)
        schema = [
            bigquery.SchemaField("signal_id", "STRING"),
            bigquery.SchemaField("new_status", "STRING"),
            bigquery.SchemaField("reason", "STRING"),
            bigquery.SchemaField("quote_as_of", "STRING"),
            bigquery.SchemaField("asset", "STRING"),
            bigquery.SchemaField("direction", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]
        table_ref = bigquery.Table(tid, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        table = client.get_table(tid)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [f for f in schema if f.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info(
                "Added missing paper_execution_audit columns: %s",
                ", ".join(f.name for f in missing_fields),
            )

        row = {
            "signal_id": (signal_id or "")[:128],
            "new_status": (new_status or "")[:32],
            "reason": (reason or "")[:256],
            "quote_as_of": (quote_as_of or "")[:64],
            "asset": (asset or "")[:32],
            "direction": (direction or "")[:16],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        errors = client.insert_rows_json(tid, [row])
        if errors:
            logger.error("BigQuery paper_execution_audit insert errors: %s", errors)
        else:
            logger.info(
                "paper_execution_audit written (signal_id=%s, status=%s, reason=%s).",
                signal_id,
                new_status,
                reason,
            )
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (paper_execution_audit skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write paper_execution_audit to BigQuery: %s", e)

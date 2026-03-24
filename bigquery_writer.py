"""BigQuery write operations: metrics extraction and exclusion context.

Extracted from main.py to reduce module size. Read operations remain in
tracker.py; this module handles writing daily_metrics and reading
exclusion context for the next run.
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone

from google.auth.exceptions import DefaultCredentialsError
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE, RECOMMENDATIONS_TABLE
from telegram_sender import strip_html

logger = logging.getLogger(__name__)

SKIP_BIGQUERY = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")

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

        # 注入前日 Gate 輪動警示（負反饋迴路，讓 LLM 知道上次失敗）
        rotation_warn = _fetch_last_rotation_gate_warnings()
        if rotation_warn:
            parts.append(rotation_warn)
            logger.info("Injected rotation gate warning into exclusion context.")

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


def write_llm_run_log(
    model_name: str,
    used_fallback: bool,
    retry_count: int,
    gate_passed: bool,
    gate_issues: list[str] | None = None,
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
        client = bigquery.Client(project=project_id)
        schema = [
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("model_name", "STRING"),
            bigquery.SchemaField("used_fallback", "BOOL"),
            bigquery.SchemaField("retry_count", "INTEGER"),
            bigquery.SchemaField("gate_passed", "BOOL"),
            bigquery.SchemaField("gate_issues_count", "INTEGER"),
            bigquery.SchemaField("gate_issues_preview", "STRING"),
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
        }
        errors = client.insert_rows_json(llm_run_log_table, [row])
        if errors:
            logger.error("BigQuery LLM run log insert errors: %s", errors)
        else:
            logger.info(
                "LLM run log written (model=%s, fallback=%s, retries=%d, gate=%s).",
                model_name,
                used_fallback,
                retry_count,
                gate_passed,
            )
    except DefaultCredentialsError as e:
        logger.warning("BigQuery credentials not configured (LLM run log skipped): %s", e)
    except Exception as e:
        logger.error("Failed to write LLM run log to BigQuery: %s", e)

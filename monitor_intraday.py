"""Intraday anomaly monitor: checks BTC and VIX hourly for threshold breaches.

Fetches BTC-USD 1h price change and VIX current value via yfinance. Triggers
a Telegram alert when BTC moves ≥ threshold% or VIX exceeds threshold. Uses
BigQuery to enforce a silence period so duplicate alerts are suppressed within
a configurable window.

Environment variables:
  INTRADAY_SILENCE_HOURS      Hours to suppress repeat alerts for same event type (default: 8)
  INTRADAY_BTC_PCT_THRESHOLD  Absolute % change that triggers BTC alert (default: 8.0)
  INTRADAY_VIX_THRESHOLD      VIX level that triggers alert when strictly above (default: 36.0)
  SKIP_TELEGRAM               Set to 1/true/yes to skip Telegram sends
  SKIP_BIGQUERY               Set to 1/true/yes to skip BigQuery reads/writes
  GCP_PROJECT_ID              GCP project ID (default: my-investment-ai-agent)
  TELEGRAM_BOT_TOKEN          Telegram bot token
  TELEGRAM_CHAT_ID            Telegram chat ID
"""

import logging
import os
from datetime import datetime, timezone

import yfinance as yf

from config import PROJECT_ID
from telegram_sender import _send_telegram_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────
SILENCE_HOURS: float = float(os.getenv("INTRADAY_SILENCE_HOURS", "8"))
BTC_PCT_THRESHOLD: float = float(os.getenv("INTRADAY_BTC_PCT_THRESHOLD", "8.0"))
VIX_THRESHOLD: float = float(os.getenv("INTRADAY_VIX_THRESHOLD", "36.0"))

SKIP_TELEGRAM: bool = os.getenv("SKIP_TELEGRAM", "").lower() in ("1", "true", "yes")
SKIP_BIGQUERY: bool = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")

INTRADAY_ALERTS_TABLE = f"{PROJECT_ID}.market_data.intraday_alerts"

# Alert type constants — used as the event_type column value for silence dedup.
ALERT_TYPE_BTC = "BTC_1H_MOVE"
ALERT_TYPE_VIX = "VIX_HIGH"


# ── Market data fetching ───────────────────────────────────────────────────

def fetch_btc_1h_change() -> float | None:
    """Return BTC-USD 1-hour percentage price change.

    Downloads the last two 1h candles from yfinance and computes the close-to-close
    change. Returns None if data is unavailable.
    """
    try:
        ticker = yf.Ticker("BTC-USD")
        hist = ticker.history(period="2d", interval="1h")
        if hist is None or len(hist) < 2:
            logger.warning("BTC-USD hourly data insufficient (got %d rows)", len(hist) if hist is not None else 0)
            return None
        prev_close = float(hist["Close"].iloc[-2])
        last_close = float(hist["Close"].iloc[-1])
        if prev_close == 0:
            logger.warning("BTC prev_close is zero — cannot compute change")
            return None
        pct_change = (last_close - prev_close) / prev_close * 100.0
        logger.info("BTC-USD 1h change: %.2f%% (prev=%.2f, last=%.2f)", pct_change, prev_close, last_close)
        return pct_change
    except Exception as e:
        logger.error("Failed to fetch BTC-USD hourly data: %s", e)
        return None


def fetch_vix_current() -> float | None:
    """Return the most recent VIX closing value.

    Returns None if data is unavailable.
    """
    try:
        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="5d", interval="1d")
        if hist is None or len(hist) == 0:
            logger.warning("VIX data unavailable")
            return None
        vix_value = float(hist["Close"].iloc[-1])
        logger.info("VIX current: %.2f", vix_value)
        return vix_value
    except Exception as e:
        logger.error("Failed to fetch VIX data: %s", e)
        return None


# ── BigQuery silence period check ─────────────────────────────────────────

def _is_recently_alerted(event_type: str, silence_hours: float) -> bool:
    """Check BigQuery intraday_alerts for a recent alert of the same event type.

    Returns True (silence) if the same event_type was alerted within silence_hours.
    Falls back to False (allow) if BigQuery is unreachable so we fail open.
    """
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping silence period check for %s", event_type)
        return False
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=PROJECT_ID)
        query = f"""
            SELECT COUNT(*) AS cnt
            FROM `{INTRADAY_ALERTS_TABLE}`
            WHERE event_type = @event_type
              AND alerted_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(silence_hours)} HOUR)
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("event_type", "STRING", event_type),
            ]
        )
        rows = list(client.query(query, job_config=job_config).result())
        count = int(rows[0]["cnt"]) if rows else 0
        if count > 0:
            logger.info("Silence period active for %s (%d recent alerts within %.0fh)", event_type, count, silence_hours)
            return True
        return False
    except Exception as e:
        # Fail open — if we cannot check BigQuery, allow the alert through.
        logger.warning("Could not check BigQuery silence period for %s (allowing alert): %s", event_type, e)
        return False


def _log_alert_to_bigquery(event_type: str, details: str, value: float) -> None:
    """Insert a row into BigQuery intraday_alerts to record that an alert was sent."""
    if SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1 — skipping BigQuery alert log for %s", event_type)
        return
    try:
        from google.cloud import bigquery

        client = bigquery.Client(project=PROJECT_ID)
        schema = [
            bigquery.SchemaField("alerted_at", "TIMESTAMP"),
            bigquery.SchemaField("event_type", "STRING"),
            bigquery.SchemaField("value",      "FLOAT"),
            bigquery.SchemaField("details",    "STRING"),
        ]
        table_ref = bigquery.Table(INTRADAY_ALERTS_TABLE, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        row = {
            "alerted_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "value":      value,
            "details":    details,
        }
        errors = client.insert_rows_json(INTRADAY_ALERTS_TABLE, [row])
        if errors:
            logger.error("BigQuery insert errors for intraday alert: %s", errors)
        else:
            logger.info("Intraday alert logged to BigQuery: %s = %.2f", event_type, value)
    except Exception as e:
        logger.error("Failed to log intraday alert to BigQuery: %s", e)


# ── Telegram sending ───────────────────────────────────────────────────────

def _send_alert(message: str) -> None:
    """Send a Telegram message using existing telegram_sender infrastructure."""
    if SKIP_TELEGRAM:
        logger.info("SKIP_TELEGRAM=1 — skipping Telegram send. Message: %s", message)
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping send")
        return
    # _send_telegram_report handles chunking, retries, and HTML sanitisation.
    _send_telegram_report(message, token, chat_id, image_path="__no_image__")


# ── Alert evaluation ───────────────────────────────────────────────────────

def _evaluate_btc(btc_pct: float | None) -> None:
    """Trigger a BTC alert if 1h change exceeds threshold and silence period has passed."""
    if btc_pct is None:
        logger.info("BTC data unavailable — skipping BTC check")
        return

    abs_change = abs(btc_pct)
    if abs_change < BTC_PCT_THRESHOLD:
        logger.info("BTC 1h change %.2f%% below threshold %.1f%% — no alert", btc_pct, BTC_PCT_THRESHOLD)
        return

    direction = "📈 上漲" if btc_pct > 0 else "📉 下跌"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    details = f"BTC 1h change {btc_pct:+.2f}%"

    if _is_recently_alerted(ALERT_TYPE_BTC, SILENCE_HOURS):
        logger.info("BTC alert suppressed by silence period (%.0fh)", SILENCE_HOURS)
        return

    message = (
        f"<b>⚠️ Q-Silicon 盤中異常警報</b>\n"
        f"<code>類型: BTC 單小時大幅波動</code>\n"
        f"<code>BTC 1h 變化: {btc_pct:+.2f}% {direction}</code>\n"
        f"<code>觸發閾值: ±{BTC_PCT_THRESHOLD:.1f}%</code>\n"
        f"<code>時間: {ts}</code>"
    )
    logger.info("Triggering BTC alert: %s", details)
    _send_alert(message)
    _log_alert_to_bigquery(ALERT_TYPE_BTC, details, btc_pct)


def _evaluate_vix(vix: float | None) -> None:
    """Trigger a VIX alert if current value exceeds threshold and silence period has passed."""
    if vix is None:
        logger.info("VIX data unavailable — skipping VIX check")
        return

    if vix <= VIX_THRESHOLD:
        logger.info("VIX %.2f at or below threshold %.1f — no alert", vix, VIX_THRESHOLD)
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    details = f"VIX current {vix:.2f}"

    if _is_recently_alerted(ALERT_TYPE_VIX, SILENCE_HOURS):
        logger.info("VIX alert suppressed by silence period (%.0fh)", SILENCE_HOURS)
        return

    message = (
        f"<b>⚠️ Q-Silicon 盤中異常警報</b>\n"
        f"<code>類型: VIX 恐慌指數偏高</code>\n"
        f"<code>VIX: {vix:.2f}</code>\n"
        f"<code>觸發閾值: >{VIX_THRESHOLD:.1f}</code>\n"
        f"<code>時間: {ts}</code>"
    )
    logger.info("Triggering VIX alert: %s", details)
    _send_alert(message)
    _log_alert_to_bigquery(ALERT_TYPE_VIX, details, vix)


# ── Entry point ────────────────────────────────────────────────────────────

def run_monitor() -> None:
    """Fetch market data and evaluate anomaly conditions."""
    logger.info(
        "Starting intraday monitor — BTC threshold: ±%.1f%%, VIX threshold: >%.1f, silence: %.0fh",
        BTC_PCT_THRESHOLD,
        VIX_THRESHOLD,
        SILENCE_HOURS,
    )
    btc_pct = fetch_btc_1h_change()
    vix = fetch_vix_current()
    _evaluate_btc(btc_pct)
    _evaluate_vix(vix)
    logger.info("Intraday monitor run complete.")


if __name__ == "__main__":
    run_monitor()

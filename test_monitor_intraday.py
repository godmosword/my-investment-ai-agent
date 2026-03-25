"""Tests for monitor_intraday.py — intraday BTC/VIX anomaly monitoring.

All tests are marked @pytest.mark.smoke so they run in the fast CI smoke pass.
External dependencies (yfinance, BigQuery, Telegram) are mocked throughout.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reload_monitor(**env_overrides):
    """Reload monitor_intraday with optional env var overrides."""
    for key, val in env_overrides.items():
        os.environ[key] = val
    # Remove cached module so module-level constants are re-evaluated.
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m
    return m


def _make_hist(prices: list[float]) -> pd.DataFrame:
    """Build a minimal yfinance-style DataFrame with a Close column."""
    return pd.DataFrame({"Close": prices})


# ---------------------------------------------------------------------------
# fetch_btc_1h_change
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_fetch_btc_returns_pct_change(monkeypatch):
    """fetch_btc_1h_change computes correct % change from last two candles."""
    import monitor_intraday as m

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist([100.0, 110.0])

    with patch("monitor_intraday.yf.Ticker", return_value=mock_ticker, create=True):
        result = m.fetch_btc_1h_change()

    assert result == pytest.approx(10.0)


@pytest.mark.smoke
def test_fetch_btc_returns_none_on_insufficient_data():
    """fetch_btc_1h_change returns None when fewer than 2 rows returned."""
    import monitor_intraday as m

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist([100.0])

    with patch("monitor_intraday.yf.Ticker", return_value=mock_ticker, create=True):
        result = m.fetch_btc_1h_change()

    assert result is None


@pytest.mark.smoke
def test_fetch_btc_returns_none_on_exception():
    """fetch_btc_1h_change returns None when yfinance raises."""
    import monitor_intraday as m

    mock_ticker = MagicMock()
    mock_ticker.history.side_effect = RuntimeError("network error")

    with patch("monitor_intraday.yf.Ticker", return_value=mock_ticker, create=True):
        result = m.fetch_btc_1h_change()

    assert result is None


# ---------------------------------------------------------------------------
# fetch_vix_current
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_fetch_vix_returns_latest_close():
    """fetch_vix_current returns the last Close value from the DataFrame."""
    import monitor_intraday as m

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = _make_hist([28.0, 32.5])

    with patch("monitor_intraday.yf.Ticker", return_value=mock_ticker, create=True):
        result = m.fetch_vix_current()

    assert result == pytest.approx(32.5)


@pytest.mark.smoke
def test_fetch_vix_returns_none_on_empty_data():
    """fetch_vix_current returns None when history is empty."""
    import monitor_intraday as m

    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame({"Close": []})

    with patch("monitor_intraday.yf.Ticker", return_value=mock_ticker, create=True):
        result = m.fetch_vix_current()

    assert result is None


# ---------------------------------------------------------------------------
# Threshold logic — no alert when below thresholds
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_no_alert_when_btc_below_threshold(capsys):
    """No Telegram send or BigQuery write when BTC change is below threshold."""
    import monitor_intraday as m

    with (
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_btc(2.5)  # below default 8.0% threshold

    mock_send.assert_not_called()
    mock_log.assert_not_called()


@pytest.mark.smoke
def test_no_alert_when_vix_below_threshold():
    """No Telegram send or BigQuery write when VIX is at or below threshold."""
    import monitor_intraday as m

    with (
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_vix(29.9)  # below default 36.0 threshold

    mock_send.assert_not_called()
    mock_log.assert_not_called()


@pytest.mark.smoke
def test_no_alert_when_data_unavailable():
    """No alert fired when both BTC and VIX return None."""
    import monitor_intraday as m

    with (
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_btc(None)
        m._evaluate_vix(None)

    mock_send.assert_not_called()
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Alert fires when thresholds exceeded
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_btc_alert_fires_above_threshold():
    """_evaluate_btc sends alert and logs to BQ when threshold exceeded."""
    import monitor_intraday as m

    with (
        patch.object(m, "_is_recently_alerted", return_value=False),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_btc(9.0)  # above 8.0% threshold

    mock_send.assert_called_once()
    mock_log.assert_called_once_with(m.ALERT_TYPE_BTC, pytest.approx("BTC 1h change +9.00%", abs=0), pytest.approx(9.0))


@pytest.mark.smoke
def test_vix_alert_fires_above_threshold():
    """_evaluate_vix sends alert and logs to BQ when threshold exceeded."""
    import monitor_intraday as m

    with (
        patch.object(m, "_is_recently_alerted", return_value=False),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_vix(40.0)  # above 36.0 threshold

    mock_send.assert_called_once()
    mock_log.assert_called_once()


@pytest.mark.smoke
def test_btc_negative_move_triggers_alert():
    """_evaluate_btc fires for large negative BTC moves."""
    import monitor_intraday as m

    with (
        patch.object(m, "_is_recently_alerted", return_value=False),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery"),
    ):
        m._evaluate_btc(-8.5)  # |−8.5%| ≥ 8% threshold

    mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# Silence period suppresses re-alerts
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_silence_period_suppresses_btc_alert():
    """_evaluate_btc skips alert when silence period is active."""
    import monitor_intraday as m

    with (
        patch.object(m, "_is_recently_alerted", return_value=True),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_btc(10.0)  # well above threshold

    mock_send.assert_not_called()
    mock_log.assert_not_called()


@pytest.mark.smoke
def test_silence_period_suppresses_vix_alert():
    """_evaluate_vix skips alert when silence period is active."""
    import monitor_intraday as m

    with (
        patch.object(m, "_is_recently_alerted", return_value=True),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery") as mock_log,
    ):
        m._evaluate_vix(50.0)  # well above threshold

    mock_send.assert_not_called()
    mock_log.assert_not_called()


@pytest.mark.smoke
def test_is_recently_alerted_returns_false_when_skip_bigquery(monkeypatch):
    """_is_recently_alerted returns False (allow) when SKIP_BIGQUERY=1."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    # With SKIP_BIGQUERY=1, the function must return False without querying BQ.
    result = m._is_recently_alerted("BTC_1H_MOVE", 4.0)
    assert result is False


# ---------------------------------------------------------------------------
# SKIP_TELEGRAM respected
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_skip_telegram_env_var_respected(monkeypatch):
    """_send_alert does NOT call _send_telegram_report when SKIP_TELEGRAM=1."""
    monkeypatch.setenv("SKIP_TELEGRAM", "1")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    with patch("monitor_intraday._send_telegram_report") as mock_report:
        m._send_alert("test alert")

    mock_report.assert_not_called()


@pytest.mark.smoke
def test_skip_telegram_false_calls_report(monkeypatch):
    """_send_alert calls _send_telegram_report when SKIP_TELEGRAM is not set."""
    monkeypatch.setenv("SKIP_TELEGRAM", "0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake-chat")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    with patch("monitor_intraday._send_telegram_report") as mock_report:
        m._send_alert("test alert")

    mock_report.assert_called_once()


# ---------------------------------------------------------------------------
# BigQuery log skipped when SKIP_BIGQUERY=1
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_skip_bigquery_log_alert(monkeypatch):
    """_log_alert_to_bigquery does nothing when SKIP_BIGQUERY=1."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    with patch("monitor_intraday.bigquery", create=True) as mock_bq:
        m._log_alert_to_bigquery("BTC_1H_MOVE", "BTC 1h change +7.00%", 7.0)
        # bigquery.Client should never be instantiated
        mock_bq.Client.assert_not_called()


# ---------------------------------------------------------------------------
# Full run_monitor integration (all mocked)
# ---------------------------------------------------------------------------

@pytest.mark.smoke
def test_run_monitor_no_alert_below_thresholds(monkeypatch):
    """run_monitor completes without sending alerts when values are within range."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    monkeypatch.setenv("SKIP_TELEGRAM", "1")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    with (
        patch.object(m, "fetch_btc_1h_change", return_value=1.5),
        patch.object(m, "fetch_vix_current", return_value=20.0),
        patch.object(m, "_send_alert") as mock_send,
    ):
        m.run_monitor()

    mock_send.assert_not_called()


@pytest.mark.smoke
def test_run_monitor_sends_alert_when_btc_spikes(monkeypatch):
    """run_monitor sends exactly one alert when only BTC exceeds threshold."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    monkeypatch.setenv("SKIP_TELEGRAM", "1")
    sys.modules.pop("monitor_intraday", None)
    import monitor_intraday as m

    with (
        patch.object(m, "fetch_btc_1h_change", return_value=8.0),
        patch.object(m, "fetch_vix_current", return_value=20.0),
        patch.object(m, "_is_recently_alerted", return_value=False),
        patch.object(m, "_send_alert") as mock_send,
        patch.object(m, "_log_alert_to_bigquery"),
    ):
        m.run_monitor()

    # Only BTC alert should fire; VIX is fine.
    assert mock_send.call_count == 1

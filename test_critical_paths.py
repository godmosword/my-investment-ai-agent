"""Tests for critical paths: Telegram HTML sanitization, send retry logic,
cache eviction, HTTP session singleton, env validation, and schema guards."""

import os
import unittest
from unittest.mock import patch, MagicMock

from main import (
    sanitize_telegram_html,
    _balance_telegram_html_tags,
    _send_telegram_report,
    _validate_critical_env_strict,
    _validate_env_types,
    _validate_required_keys,
)
from tools import (
    _get_http_session,
    _set_cache,
    _get_cache,
    _CACHE,
    _CACHE_MAX_SIZE,
    fear_greed_tool,
)


# ── 1. Telegram HTML sanitization edge cases ──────────────────────────

class TestTelegramSanitization(unittest.TestCase):
    """Edge cases for sanitize_telegram_html and _balance_telegram_html_tags."""

    def test_nested_tags_stay_valid(self):
        result = sanitize_telegram_html("<b><i>text</i></b>")
        self.assertIn("<b>", result)
        self.assertIn("<i>text</i>", result)
        self.assertIn("</b>", result)

    def test_unmatched_closing_tag_dropped(self):
        result = sanitize_telegram_html("hello</b>world")
        self.assertNotIn("</b>", result)
        self.assertIn("hello", result)
        self.assertIn("world", result)

    def test_unclosed_tag_gets_auto_closed(self):
        result = sanitize_telegram_html("<b>open text")
        self.assertIn("<b>", result)
        self.assertIn("</b>", result)

    def test_unsafe_script_tag_stripped(self):
        result = sanitize_telegram_html("<script>alert(1)</script>")
        self.assertNotIn("<script>", result)
        self.assertNotIn("</script>", result)
        # The angle brackets should be escaped
        self.assertIn("&lt;script&gt;", result)

    def test_ampersand_handling(self):
        result = sanitize_telegram_html("A & B")
        self.assertIn("&amp;", result)
        # Already-escaped ampersands should not be double-escaped
        result2 = sanitize_telegram_html("A &amp; B")
        self.assertIn("&amp;", result2)
        self.assertNotIn("&amp;amp;", result2)

    def test_empty_string(self):
        self.assertEqual(sanitize_telegram_html(""), "")

    def test_balance_drops_orphan_closing(self):
        result = _balance_telegram_html_tags("text</i>more")
        self.assertNotIn("</i>", result)

    def test_balance_auto_closes_open_tag(self):
        result = _balance_telegram_html_tags("<b>bold")
        self.assertTrue(result.endswith("</b>"))


# ── 2. Telegram send retry logic ──────────────────────────────────────

class TestTelegramSendRetry(unittest.TestCase):
    """Test _send_telegram_report retries on failure and falls back to plain text."""

    def setUp(self):
        """Ensure telebot.apihelper stub exists for the local import inside _send_telegram_report."""
        import sys
        if "telebot.apihelper" not in sys.modules:
            from types import ModuleType
            mod = ModuleType("telebot.apihelper")
            mod.SESSION_TIME_TO_LIVE = 300
            sys.modules["telebot.apihelper"] = mod
            # Also attach to the telebot stub
            sys.modules["telebot"].apihelper = mod

    @patch("main.time.sleep")
    @patch("telegram_sender.telebot.TeleBot")
    @patch("main.os.path.exists", return_value=False)
    def test_retries_on_send_failure(self, _mock_exists, mock_bot_cls, _mock_sleep):
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot
        # Fail twice, then succeed
        mock_bot.send_message.side_effect = [
            Exception("timeout"),
            Exception("timeout"),
            None,  # success
        ]
        _send_telegram_report("hello", "TOKEN", "CHAT")
        self.assertEqual(mock_bot.send_message.call_count, 3)

    @patch("main.time.sleep")
    @patch("telegram_sender.telebot.TeleBot")
    @patch("main.os.path.exists", return_value=False)
    def test_falls_back_to_plain_text_on_html_error(self, _mock_exists, mock_bot_cls, _mock_sleep):
        mock_bot = MagicMock()
        mock_bot_cls.return_value = mock_bot
        # First call (HTML) fails with parse error, second call (plain text) succeeds
        mock_bot.send_message.side_effect = [
            Exception("can't parse entities"),
            None,  # plain text succeeds
        ]
        _send_telegram_report("<b>hello</b>", "TOKEN", "CHAT")
        # Second call should not have parse_mode="HTML"
        last_call = mock_bot.send_message.call_args_list[-1]
        self.assertNotIn("HTML", str(last_call))


# ── 3. Cache eviction ─────────────────────────────────────────────────

class TestCacheEviction(unittest.TestCase):
    """Test that _set_cache evicts old entries when cache exceeds _CACHE_MAX_SIZE."""

    def setUp(self):
        _CACHE.clear()

    def tearDown(self):
        _CACHE.clear()

    def test_cache_evicts_when_full(self):
        # Fill cache to max
        for i in range(_CACHE_MAX_SIZE):
            _set_cache(("key", str(i)), f"value_{i}")
        self.assertEqual(len(_CACHE), _CACHE_MAX_SIZE)

        # Add one more — should trigger eviction of 1/4 of entries
        _set_cache(("key", "overflow"), "overflow_value")
        self.assertLessEqual(len(_CACHE), _CACHE_MAX_SIZE)
        # The new entry should exist
        self.assertIsNotNone(_get_cache(("key", "overflow")))

    def test_cache_get_returns_none_for_missing(self):
        self.assertIsNone(_get_cache(("nonexistent",)))

    def test_cache_round_trip(self):
        _set_cache(("test",), "hello")
        self.assertEqual(_get_cache(("test",)), "hello")


# ── 4. requests.Session singleton ─────────────────────────────────────

class TestHttpSession(unittest.TestCase):
    """Test _get_http_session returns the same Session on repeated calls."""

    def setUp(self):
        import tools_cache_http

        self._orig = tools_cache_http._HTTP_SESSION
        tools_cache_http._HTTP_SESSION = None

    def tearDown(self):
        import tools_cache_http

        tools_cache_http._HTTP_SESSION = self._orig

    def test_returns_same_session(self):
        s1 = _get_http_session()
        s2 = _get_http_session()
        self.assertIs(s1, s2)

    def test_session_has_user_agent(self):
        s = _get_http_session()
        self.assertIn("Q-Silicon", s.headers.get("User-Agent", ""))


# ── 5. Startup env validation ─────────────────────────────────────────

class TestEnvValidation(unittest.TestCase):
    """Test _validate_env_types and _validate_required_keys."""

    @patch.dict(os.environ, {"MAX_REPORT_RETRIES": "not_a_number"})
    def test_validate_env_types_raises_for_non_numeric(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_env_types()
        self.assertIn("MAX_REPORT_RETRIES", str(ctx.exception))

    @patch.dict(os.environ, {"MAX_REPORT_RETRIES": "5"})
    def test_validate_env_types_ok_for_valid_number(self):
        # Should not raise
        _validate_env_types()

    @patch.dict(os.environ, {"NEWS_FRESHNESS_WINDOW_HOURS": "not_int"})
    def test_validate_env_types_raises_for_bad_news_freshness_window(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_env_types()
        self.assertIn("NEWS_FRESHNESS_WINDOW_HOURS", str(ctx.exception))

    @patch.dict(os.environ, {
        "PIPELINE_STRICT_ENV": "1",
        "SKIP_TELEGRAM": "1",
        "SKIP_BIGQUERY": "1",
    }, clear=False)
    def test_validate_critical_env_strict_ok_when_both_skipped(self):
        _validate_critical_env_strict()

    @patch.dict(os.environ, {
        "PIPELINE_STRICT_ENV": "1",
        "SKIP_TELEGRAM": "",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "SKIP_BIGQUERY": "1",
    }, clear=False)
    def test_validate_critical_env_strict_raises_without_telegram_when_not_skipped(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_critical_env_strict()
        self.assertIn("TELEGRAM", str(ctx.exception).upper())

    @patch.dict(os.environ, {
        "PIPELINE_STRICT_ENV": "1",
        "SKIP_TELEGRAM": "1",
        "SKIP_BIGQUERY": "",
        "GCP_PROJECT_ID": "",
        "GCP_SA_KEY": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
    }, clear=False)
    def test_validate_critical_env_strict_raises_without_gcp_when_bq_not_skipped(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_critical_env_strict()
        self.assertIn("GCP_PROJECT_ID", str(ctx.exception))

    @patch.dict(os.environ, {
        "PIPELINE_STRICT_ENV": "1",
        "SKIP_TELEGRAM": "1",
        "SKIP_BIGQUERY": "",
        "GCP_PROJECT_ID": "my-project",
        "GCP_SA_KEY": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
    }, clear=False)
    def test_validate_critical_env_strict_raises_without_sa_when_bq_not_skipped(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_critical_env_strict()
        self.assertIn("GCP_SA_KEY", str(ctx.exception))

    @patch.dict(os.environ, {
        "XAI_API_KEY": "",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
        "APIFY_API_TOKEN": "",
    }, clear=False)
    def test_validate_required_keys_raises_for_missing(self):
        with self.assertRaises(RuntimeError) as ctx:
            _validate_required_keys()
        self.assertIn("XAI_API_KEY", str(ctx.exception))

    @patch.dict(os.environ, {
        "XAI_API_KEY": "x",
        "OPENAI_API_KEY": "x",
        "GEMINI_API_KEY": "x",
        "APIFY_API_TOKEN": "x",
    }, clear=False)
    def test_validate_required_keys_ok_when_present(self):
        # Should not raise
        _validate_required_keys()


# ── 6. Schema validation guards ───────────────────────────────────────

class TestSchemaGuards(unittest.TestCase):
    """Test fear_greed_tool returns DATA_MISSING for malformed responses."""

    def setUp(self):
        _CACHE.clear()

    def tearDown(self):
        _CACHE.clear()

    @patch("tools_legacy._http_get")
    def test_fear_greed_non_dict_returns_data_missing(self, mock_http_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        # Return a list instead of a dict — malformed
        mock_resp.json.return_value = [1, 2, 3]
        mock_http_get.return_value = mock_resp

        result = fear_greed_tool()
        self.assertIn("DATA_MISSING", result)

    @patch("tools_legacy._http_get")
    def test_fear_greed_empty_data_returns_data_missing(self, mock_http_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"data": []}
        mock_http_get.return_value = mock_resp

        result = fear_greed_tool()
        self.assertIn("DATA_MISSING", result)


# ── 7. BigQuery DefaultCredentialsError handling ──────────────────────

class TestBigQueryCredentialsError(unittest.TestCase):
    """extract_and_save_metrics and fetch_exclusion_context must not crash or
    log ERROR-level noise when GCP credentials are absent (local dev)."""

    def _make_creds_error(self):
        try:
            from google.auth.exceptions import DefaultCredentialsError
            return DefaultCredentialsError("no credentials")
        except ImportError:
            return Exception("Could not automatically determine credentials")

    @patch("bigquery_writer.SKIP_BIGQUERY", False)
    @patch("bigquery_writer.bigquery.Client")
    def test_extract_metrics_logs_warning_not_error_on_missing_creds(
        self, mock_client_cls
    ):
        """DefaultCredentialsError should be logged at WARNING, not ERROR."""
        import bigquery_writer
        mock_client_cls.side_effect = self._make_creds_error()

        with self.assertLogs("bigquery_writer", level="WARNING") as cm:
            # Should not raise
            bigquery_writer.extract_and_save_metrics("dummy report text")

        # Must NOT contain any ERROR-level log for this scenario
        error_logs = [line for line in cm.output if line.startswith("ERROR")]
        self.assertEqual(
            error_logs, [],
            f"Expected no ERROR logs for missing credentials, got: {error_logs}",
        )

    @patch("bigquery_writer.SKIP_BIGQUERY", True)
    @patch("bigquery_writer.bigquery.Client")
    def test_extract_metrics_skips_bigquery_when_flag_set(self, mock_client_cls):
        """SKIP_BIGQUERY=True must cause early return before any BQ calls."""
        import bigquery_writer
        bigquery_writer.extract_and_save_metrics("dummy report text")
        mock_client_cls.assert_not_called()

    @patch("bigquery_writer.SKIP_BIGQUERY", True)
    @patch("bigquery_writer.bigquery.Client")
    def test_fetch_exclusion_context_skips_when_flag_set(self, mock_client_cls):
        """SKIP_BIGQUERY=True must cause early return before any BQ calls."""
        import bigquery_writer
        result = bigquery_writer.fetch_exclusion_context()
        self.assertIsNone(result)
        mock_client_cls.assert_not_called()


class TestBacktestSignalWeightsPayload(unittest.TestCase):
    def test_build_payload_from_scipy_optimal_weights(self):
        from backtest import build_signal_weights_payload_from_opt

        p = build_signal_weights_payload_from_opt(
            {
                "optimal_weights": {
                    "sig_dxy": 0.25,
                    "sig_etf": 0.25,
                    "sig_risk": 0.25,
                    "sig_mvrv": 0.25,
                },
                "optimal_sharpe": 1.2,
            },
            source="test",
        )
        self.assertIsNotNone(p)
        assert p is not None
        self.assertIn("dxy", p["weights"])
        self.assertAlmostEqual(p["weights"]["dxy"], 0.25)

    def test_build_payload_from_ml_weights_dict(self):
        from backtest import build_signal_weights_payload_from_opt

        p = build_signal_weights_payload_from_opt(
            {"weights": {"dxy": 0.1, "etf_flow": 0.3}, "sharpe": 0.5},
            source="test",
        )
        self.assertIsNotNone(p)
        assert p is not None
        self.assertEqual(p["weights"]["etf_flow"], 0.3)


if __name__ == "__main__":
    unittest.main()

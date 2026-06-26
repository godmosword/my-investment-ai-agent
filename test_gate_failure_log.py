"""Tests for write_gate_failure_log() in bigquery_writer.py."""

import os
import unittest
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.smoke
class TestWriteGateFailureLog(unittest.TestCase):
    def test_skip_when_skip_bigquery(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "1"}):
            import importlib

            import bigquery_writer

            importlib.reload(bigquery_writer)
            with patch("bigquery_writer.bigquery") as mock_bq:
                bigquery_writer.write_gate_failure_log(
                    attempt=1,
                    validation={"issues": ["x"], "blocking_issues": ["x"], "warning_issues": []},
                    report_chars=100,
                    used_fallback=False,
                )
                mock_bq.Client.assert_not_called()

    def test_skip_when_disabled_env(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "GATE_FAILURE_BQ_LOG": "0"}):
            import importlib

            import bigquery_writer

            importlib.reload(bigquery_writer)
            with patch("bigquery_writer.bigquery") as mock_bq:
                bigquery_writer.write_gate_failure_log(
                    attempt=1,
                    validation={"issues": ["a"], "blocking_issues": [], "warning_issues": ["a"]},
                    report_chars=50,
                    used_fallback=True,
                )
                mock_bq.Client.assert_not_called()

    def test_skip_when_no_issues(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "GATE_FAILURE_BQ_LOG": "1"}):
            import importlib

            import bigquery_writer

            importlib.reload(bigquery_writer)
            with patch("bigquery_writer.bigquery") as mock_bq:
                bigquery_writer.write_gate_failure_log(
                    attempt=1,
                    validation={"issues": [], "valid": True},
                    report_chars=50,
                    used_fallback=False,
                )
                mock_bq.Client.assert_not_called()

    def test_inserts_row_with_buckets(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "GATE_FAILURE_BQ_LOG": "1"}):
            import importlib

            import bigquery_writer

            importlib.reload(bigquery_writer)

            mock_client = MagicMock()
            mock_client.insert_rows_json.return_value = []
            mock_client.get_table.return_value = MagicMock(schema=[])

            with patch("bigquery_writer.bigquery") as mock_bq:
                mock_bq.Client.return_value = mock_client

                def _make_field(name, _typ):
                    f = MagicMock()
                    f.name = name
                    return f

                mock_bq.SchemaField = MagicMock(side_effect=_make_field)
                mock_bq.Table = MagicMock()

                bigquery_writer.write_gate_failure_log(
                    attempt=2,
                    validation={
                        "issues": ["缺少新聞時間未統一標示 UTC+8", "缺少 QSREC"],
                        "blocking_issues": ["缺少新聞時間未統一標示 UTC+8"],
                        "warning_issues": ["缺少 QSREC"],
                        "news_count": 5,
                        "profile": "crypto-only",
                    },
                    report_chars=4000,
                    used_fallback=True,
                )

            mock_client.insert_rows_json.assert_called_once()
            row = mock_client.insert_rows_json.call_args[0][1][0]
            self.assertEqual(row["attempt"], 2)
            self.assertEqual(row["issue_count"], 2)
            self.assertEqual(row["blocking_count"], 1)
            self.assertEqual(row["warning_count"], 1)
            self.assertEqual(row["news_count"], 5)
            self.assertTrue(row["used_fallback"])
            self.assertEqual(row["report_chars"], 4000)
            self.assertIn("bucket_counts_json", row)
            self.assertIn("fingerprint", row)
            self.assertTrue(len(row["fingerprint"]) <= 16)
            self.assertEqual(row["profile"], "crypto-only")

    def test_profile_kwarg_overrides_validation(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "GATE_FAILURE_BQ_LOG": "1"}):
            import importlib

            import bigquery_writer

            importlib.reload(bigquery_writer)

            mock_client = MagicMock()
            mock_client.insert_rows_json.return_value = []
            mock_client.get_table.return_value = MagicMock(schema=[])

            with patch("bigquery_writer.bigquery") as mock_bq:
                mock_bq.Client.return_value = mock_client

                def _make_field(name, _typ):
                    f = MagicMock()
                    f.name = name
                    return f

                mock_bq.SchemaField = MagicMock(side_effect=_make_field)
                mock_bq.Table = MagicMock()

                bigquery_writer.write_gate_failure_log(
                    attempt=1,
                    validation={
                        "issues": ["x"],
                        "blocking_issues": ["x"],
                        "warning_issues": [],
                        "profile": "full",
                    },
                    report_chars=100,
                    used_fallback=False,
                    profile="lite",
                )

            row = mock_client.insert_rows_json.call_args[0][1][0]
            self.assertEqual(row["profile"], "lite")


class TestBucketGateIssues(unittest.TestCase):
    def test_buckets(self):
        from bigquery_writer import _bucket_gate_issues

        issues = [
            "缺少新聞",
            "[DATA_MISSING:coinglass]",
            "缺少 market_regime",
        ]
        b = _bucket_gate_issues(issues)
        self.assertGreater(b.get("news", 0), 0)
        self.assertGreater(b.get("source", 0), 0)
        self.assertGreater(b.get("regime", 0), 0)


if __name__ == "__main__":
    unittest.main()

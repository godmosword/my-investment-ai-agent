"""Tests for write_llm_run_log() in bigquery_writer.py."""

import os
import unittest
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.smoke
class TestWriteLlmRunLog(unittest.TestCase):
    def test_skip_when_skip_bigquery_set(self):
        """Should return immediately when SKIP_BIGQUERY=1."""
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "1"}):
            # Re-import to pick up env var change (module-level SKIP_BIGQUERY).
            import importlib
            import bigquery_writer
            importlib.reload(bigquery_writer)
            # Should not raise and not call BigQuery client.
            with patch("bigquery_writer.bigquery") as mock_bq:
                bigquery_writer.write_llm_run_log("grok", False, 0, True)
                mock_bq.Client.assert_not_called()

    def test_writes_row_on_success(self):
        """Should call insert_rows_json with correct data."""
        with patch.dict(os.environ, {"SKIP_BIGQUERY": ""}):
            import importlib
            import bigquery_writer
            importlib.reload(bigquery_writer)

            mock_client = MagicMock()
            mock_client.insert_rows_json.return_value = []
            mock_client.get_table.return_value = MagicMock(schema=[])

            with patch("bigquery_writer.bigquery") as mock_bq:
                mock_bq.Client.return_value = mock_client
                def _make_field(name, typ):
                    f = MagicMock()
                    f.name = name
                    return f
                mock_bq.SchemaField = MagicMock(side_effect=_make_field)
                mock_bq.Table = MagicMock()

                bigquery_writer.write_llm_run_log(
                    model_name="xai/grok-4",
                    used_fallback=False,
                    retry_count=1,
                    gate_passed=True,
                    gate_issues=[],
                )

            mock_client.insert_rows_json.assert_called_once()
            row = mock_client.insert_rows_json.call_args[0][1][0]
            assert row["model_name"] == "xai/grok-4"
            assert row["used_fallback"] is False
            assert row["retry_count"] == 1
            assert row["gate_passed"] is True
            assert row["gate_issues_count"] == 0

    def test_gate_issues_preview_truncated_to_3(self):
        """gate_issues_preview should contain at most 3 issues joined with ' | '."""
        with patch.dict(os.environ, {"SKIP_BIGQUERY": ""}):
            import importlib
            import bigquery_writer
            importlib.reload(bigquery_writer)

            mock_client = MagicMock()
            mock_client.insert_rows_json.return_value = []
            mock_client.get_table.return_value = MagicMock(schema=[])

            with patch("bigquery_writer.bigquery") as mock_bq:
                mock_bq.Client.return_value = mock_client
                def _make_field(name, typ):
                    f = MagicMock()
                    f.name = name
                    return f
                mock_bq.SchemaField = MagicMock(side_effect=_make_field)
                mock_bq.Table = MagicMock()

                bigquery_writer.write_llm_run_log(
                    model_name="openai/gpt-4o",
                    used_fallback=True,
                    retry_count=3,
                    gate_passed=False,
                    gate_issues=["issue1", "issue2", "issue3", "issue4"],
                )

            row = mock_client.insert_rows_json.call_args[0][1][0]
            assert row["gate_issues_count"] == 4
            # Preview should contain exactly 3 issues
            assert row["gate_issues_preview"].count(" | ") == 2
            assert "issue4" not in row["gate_issues_preview"]

    def test_credentials_error_logs_warning_not_raises(self):
        """DefaultCredentialsError should be caught and logged, not re-raised."""
        with patch.dict(os.environ, {"SKIP_BIGQUERY": ""}):
            import importlib
            import bigquery_writer
            importlib.reload(bigquery_writer)

            from google.auth.exceptions import DefaultCredentialsError
            with patch("bigquery_writer.bigquery") as mock_bq:
                mock_bq.Client.side_effect = DefaultCredentialsError("no creds")
                # Should not raise
                bigquery_writer.write_llm_run_log("model", False, 0, False)

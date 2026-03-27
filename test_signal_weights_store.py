"""Tests for versioned ML weights storage."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import signal_weights_store as sws


class TestSignalWeightsStore(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_write_load_format_rollback(self):
        with mock.patch("signal_weights_store._repo_root", return_value=self.td):
            p = sws.write_weights(
                {
                    "version": "v1",
                    "source": "test",
                    "weights": {"a": 0.5, "b": 0.25},
                }
            )
            self.assertTrue(p.is_file())
            loaded = sws.load_active_weights()
            assert loaded is not None
            self.assertEqual(loaded.get("version"), "v1")

            sws.write_weights(
                {"version": "v2", "source": "test", "weights": {"a": 1.0}},
                backup_previous=True,
            )
            self.assertEqual(sws.load_active_weights().get("version"), "v2")

            self.assertTrue(sws.rollback_weights())
            self.assertEqual(sws.load_active_weights().get("version"), "v1")

            with mock.patch.dict("os.environ", {"WEIGHTS_CONTEXT_ENABLED": "1"}, clear=False):
                ctx = sws.format_weights_for_crew_context()
            assert ctx is not None
            self.assertIn("v1", ctx)
            self.assertIn("0.5000", ctx)

    def test_format_returns_none_when_disabled(self):
        with mock.patch("signal_weights_store._repo_root", return_value=self.td):
            sws.write_weights({"version": "x", "weights": {"z": 1.0}})
            with mock.patch.dict("os.environ", {"WEIGHTS_CONTEXT_ENABLED": "0"}, clear=False):
                self.assertIsNone(sws.format_weights_for_crew_context())


if __name__ == "__main__":
    unittest.main()

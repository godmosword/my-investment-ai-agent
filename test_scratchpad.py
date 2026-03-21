"""Unit tests for scratchpad JSONL (Phase 1)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scratchpad


class TestScratchpad(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self._path = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_begin_run_writes_init_and_jsonl_parseable(self):
        with mock.patch.dict(os.environ, {"SCRATCHPAD_DIR": str(self._path / "sp"), "SCRATCHPAD_ENABLED": "1"}):
            scratchpad.begin_run({"test": True})
            p = scratchpad.current_scratchpad_path()
            self.assertIsNotNone(p)
            assert p is not None
            self.assertTrue(p.exists())
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["type"], "init")
            self.assertIn("runId", row)
            scratchpad.finalize_run("test_done")
            self.assertIsNone(scratchpad.current_run_id())

    def test_gate_result_and_run_end(self):
        with mock.patch.dict(os.environ, {"SCRATCHPAD_DIR": str(self._path / "sp2"), "SCRATCHPAD_ENABLED": "1"}):
            scratchpad.begin_run({})
            p = scratchpad.current_scratchpad_path()
            assert p is not None
            scratchpad.append_gate_result(
                1,
                {"valid": False, "news_count": 3, "issues": ["a", "b"]},
            )
            scratchpad.finalize_run("completed_invalid", {"x": 1})
            lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
            types = [x["type"] for x in lines]
            self.assertIn("init", types)
            self.assertIn("gate_result", types)
            self.assertIn("run_end", types)
            gate = next(x for x in lines if x["type"] == "gate_result")
            self.assertEqual(gate.get("attempt"), 1)
            self.assertFalse(gate.get("valid"))

    def test_traced_tool_execution_logs_when_run_active(self):
        with mock.patch.dict(os.environ, {"SCRATCHPAD_DIR": str(self._path / "sp3"), "SCRATCHPAD_ENABLED": "1"}):
            scratchpad.begin_run({})

            def _fn() -> str:
                return "hello tool output"

            out = scratchpad.traced_tool_execution("dummy_tool", {"q": "x"}, _fn)
            self.assertEqual(out, "hello tool output")
            p = scratchpad.current_scratchpad_path()
            assert p is not None
            lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
            tnames = [(x.get("type"), x.get("toolName")) for x in lines if x["type"] in ("tool_call", "tool_result")]
            self.assertTrue(any(t == ("tool_call", "dummy_tool") for t in tnames))
            self.assertTrue(any(t[0] == "tool_result" and t[1] == "dummy_tool" for t in tnames))
            scratchpad.finalize_run("ok")

    def test_disabled_no_file(self):
        with mock.patch.dict(os.environ, {"SCRATCHPAD_ENABLED": "0"}):
            scratchpad.begin_run({})
            self.assertIsNone(scratchpad.current_scratchpad_path())


if __name__ == "__main__":
    unittest.main()

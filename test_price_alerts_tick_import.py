"""Regression tests for lean push alert tick imports."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_push_alert_helpers_do_not_require_fastapi():
    script = """
import builtins
import sys

original_import = builtins.__import__

def blocked_import(name, *args, **kwargs):
    if name == "fastapi" or name.startswith("fastapi."):
        raise ModuleNotFoundError("No module named 'fastapi'")
    return original_import(name, *args, **kwargs)

for module_name in list(sys.modules):
    if module_name == "price_alerts" or module_name.startswith("fastapi"):
        sys.modules.pop(module_name, None)

builtins.__import__ = blocked_import
import price_alerts

alert = {"direction": "above", "target_price": 100}
assert price_alerts.triggered(alert, 101.0) is True
assert price_alerts.telegram_enabled() is False
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parent,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_push_digest_workflow_does_not_import_api_router():
    workflow = Path(".github/workflows/push-digest-tick.yml").read_text(encoding="utf-8")
    assert "api_routers.price_alerts" not in workflow

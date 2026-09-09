"""Startup boundary: ``import api`` must not drag Job-side heavy deps in.

The HTTP API (``uvicorn api:app``) and the daily-brief Job (``python main.py``)
share one image but must not share one import graph. These checks run in a clean
subprocess so the stubs installed by the root ``conftest.py`` cannot mask a
regression.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Env that must NOT be required to import the app or to list its routes.
_CLEARED_ENV_KEYS = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GCP_PROJECT_ID",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "WEB_PUSH_REDIS_URL",
    "WEB_PUSH_VAPID_PRIVATE_KEY",
    "QSILICON_MASTER_KEY",
)

# Modules that belong to the Job / heavy analytics path, not to API startup.
_FORBIDDEN_AT_IMPORT = (
    "crewai",
    "litellm",
    "sentence_transformers",
    "scipy",
    "yfinance",
    "telebot",
    "redis",
    "jinja2",
    "streamlit",
    "matplotlib",
    "crew",
    "main",
    "bigquery_writer",
    "tracker",
)

_PROBE = f"""
import json, os, sys
import api
watched = {_CLEARED_ENV_KEYS!r}
sys.stdout.write(json.dumps({{
    "loaded": sorted(m for m in sys.modules if "." not in m),
    "google_cloud_loaded": [m for m in sys.modules if m == "google.cloud" or m.startswith("google.cloud.")],
    "paths": sorted(api.app.openapi()["paths"]),
    "env_present": sorted(k for k in watched if os.environ.get(k)),
}}))
"""


def _run_probe() -> dict:
    # Inherit PATH / site-packages so the same interpreter that runs pytest can
    # find FastAPI. Still clear GCP/LLM env and use a blank HOME so ADC files
    # in the developer home cannot leak into the probe.
    inherited_pp = os.pathsep.join(p for p in sys.path if p)
    parent_pp = os.environ.get("PYTHONPATH", "")
    pythonpath = os.pathsep.join(
        x for x in (str(_REPO_ROOT), inherited_pp, parent_pp) if x
    )
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/tmp",
        "PYTHONPATH": pythonpath,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, f"import api failed with a cleared env:\n{proc.stderr}"
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def probe() -> dict:
    return _run_probe()


@pytest.mark.smoke
def test_import_api_succeeds_without_gcp_llm_redis_telegram_env(probe):
    # `_run_probe` already asserts the subprocess exited 0.
    assert probe["env_present"] == [], "probe env was not clean"
    assert probe["paths"], "app exposes no routes"


@pytest.mark.smoke
def test_healthz_is_on_the_route_table(probe):
    assert "/healthz" in probe["paths"]


@pytest.mark.smoke
@pytest.mark.parametrize("module", _FORBIDDEN_AT_IMPORT)
def test_job_side_modules_stay_off_the_startup_path(probe, module):
    assert module not in probe["loaded"], (
        f"{module!r} is imported by `import api`; keep it lazy so FastAPI startup "
        "does not depend on the Job path"
    )


@pytest.mark.smoke
def test_google_cloud_stays_off_the_startup_path(probe):
    assert probe["google_cloud_loaded"] == [], (
        "google.cloud is imported by `import api`; keep BigQuery lazy so FastAPI "
        "startup does not require GCP libraries"
    )

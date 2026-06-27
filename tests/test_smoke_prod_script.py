from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_smoke_prod_checks_frontend_api_contract_routes(tmp_path: Path):
    calls_file = tmp_path / "curl-calls.txt"
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
url="${@: -1}"
printf '%s\n' "$url" >> "$CURL_CALLS_FILE"
case "$url" in
  */api/options/summary|*/api/options/gex/NVDA|*/api/options/flow/NVDA|*/api/data-health|*/api/symbols/BTC/quote|*/openapi.json|*/insights|*/news|*/dashboard|*/columns|*/portfolio)
    printf '200'
    ;;
  */docs|*/healthz)
    printf '404'
    ;;
  *)
    printf '500'
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)

    env = {
        **os.environ,
        "BASE_URL": "https://pwa.example.test",
        "API_BASE": "https://api.example.test",
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CURL_CALLS_FILE": str(calls_file),
    }
    result = subprocess.run(
        ["bash", "scripts/smoke-prod.sh"],
        cwd="data-verification-ui",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    calls = calls_file.read_text(encoding="utf-8").splitlines()
    assert "https://api.example.test/api/data-health" in calls
    assert "https://api.example.test/api/options/summary" in calls
    assert "https://api.example.test/api/options/gex/NVDA" in calls
    assert "https://api.example.test/api/options/flow/NVDA" in calls

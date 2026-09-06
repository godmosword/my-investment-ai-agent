from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run_smoke(tmp_path: Path, fake_curl_body: str) -> subprocess.CompletedProcess[str]:
    calls_file = tmp_path / "curl-calls.txt"
    fake_curl = tmp_path / "curl"
    fake_curl.write_text(fake_curl_body, encoding="utf-8")
    fake_curl.chmod(0o755)
    env = {
        **os.environ,
        "BASE_URL": "https://pwa.example.test",
        "API_BASE": "https://api.example.test",
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "CURL_CALLS_FILE": str(calls_file),
    }
    return subprocess.run(
        ["bash", "scripts/smoke-prod.sh"],
        cwd="data-verification-ui",
        env=env,
        text=True,
        capture_output=True,
        check=False,
    ), calls_file


def test_smoke_prod_requires_exact_healthz_body(tmp_path: Path):
    result, calls_file = _run_smoke(
        tmp_path,
        """#!/usr/bin/env bash
set -euo pipefail
out=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "-o" ]]; then
    out="${args[$((i+1))]}"
  fi
done
url="${@: -1}"
printf '%s\n' "$url" >> "$CURL_CALLS_FILE"
case "$url" in
  */healthz)
    if [[ -n "$out" ]]; then
      printf '%s' '{"ok": true, "service": "api"}' > "$out"
    fi
    printf '200'
    ;;
  */api/options/summary|*/api/options/gex/NVDA|*/api/options/flow/NVDA|*/api/data-health|*/api/symbols/BTC/quote|*/insights|*/news|*/dashboard|*/columns|*/portfolio)
    printf '200'
    ;;
  */docs|*/openapi.json)
    printf '200'
    ;;
  *)
    printf '500'
    ;;
esac
""",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    calls = calls_file.read_text(encoding="utf-8").splitlines()
    assert "https://api.example.test/healthz" in calls
    assert "https://api.example.test/api/data-health" in calls
    assert "https://api.example.test/api/options/summary" in calls
    assert "https://api.example.test/api/options/gex/NVDA" in calls
    assert "https://api.example.test/api/options/flow/NVDA" in calls


def test_smoke_prod_fails_when_only_docs_openapi_are_200(tmp_path: Path):
    result, _calls_file = _run_smoke(
        tmp_path,
        """#!/usr/bin/env bash
set -euo pipefail
out=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "-o" ]]; then
    out="${args[$((i+1))]}"
  fi
done
url="${@: -1}"
printf '%s\n' "$url" >> "$CURL_CALLS_FILE"
case "$url" in
  */healthz)
    if [[ -n "$out" ]]; then
      printf '%s' '{"status":"ok"}' > "$out"
    fi
    printf '404'
    ;;
  */docs|*/openapi.json|*/insights|*/news|*/dashboard|*/columns|*/portfolio)
    printf '200'
    ;;
  *)
    printf '500'
    ;;
esac
""",
    )
    assert result.returncode != 0
    assert "/healthz" in (result.stdout + result.stderr)


def test_smoke_prod_fails_on_wrong_healthz_body(tmp_path: Path):
    result, _calls_file = _run_smoke(
        tmp_path,
        """#!/usr/bin/env bash
set -euo pipefail
out=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
  if [[ "${args[$i]}" == "-o" ]]; then
    out="${args[$((i+1))]}"
  fi
done
url="${@: -1}"
printf '%s\n' "$url" >> "$CURL_CALLS_FILE"
case "$url" in
  */healthz)
    if [[ -n "$out" ]]; then
      printf '%s' '{"status":"ok"}' > "$out"
    fi
    printf '200'
    ;;
  */insights|*/news|*/dashboard|*/columns|*/portfolio)
    printf '200'
    ;;
  *)
    printf '500'
    ;;
esac
""",
    )
    assert result.returncode != 0
    assert "healthz body" in (result.stdout + result.stderr)

#!/usr/bin/env python3
"""Repo-side env checks for TODOS queue 35 (Reviewer production rollout).

Does not replace staging watch in docs/REVIEWER_PRODUCTION_ROLLOUT.md — use after
staging env vars are set to catch missing tables / flags before cutover.

Usage:
  python3 scripts/verify_reviewer_rollout_env.py
  python3 scripts/verify_reviewer_rollout_env.py --strict  # fail if USE_LANGGRAPH_ENGINE off
"""

from __future__ import annotations

import argparse
import os
import sys


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _check_bq_table_fqtn(fqtn: str) -> tuple[bool, str]:
    if not fqtn or "." not in fqtn:
        return True, "REVIEWER_LOG_BQ unset (skip BQ existence)"
    if _truthy("SKIP_BIGQUERY"):
        return True, "SKIP_BIGQUERY=1 (skip BQ existence)"
    cred = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not cred:
        return True, "GOOGLE_APPLICATION_CREDENTIALS unset (skip BQ existence)"
    try:
        from google.cloud import bigquery

        client = bigquery.Client()
        client.get_table(fqtn)
        return True, f"BQ table exists: {fqtn}"
    except Exception as exc:  # noqa: BLE001
        return False, f"BigQuery: {exc}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--strict",
        action="store_true",
        help="Require USE_LANGGRAPH_ENGINE=1",
    )
    args = p.parse_args()
    failures: list[str] = []

    lg = _truthy("USE_LANGGRAPH_ENGINE") or (os.getenv("USE_LANGGRAPH_ENGINE") or "").strip() == "1"
    if args.strict and not lg:
        failures.append("USE_LANGGRAPH_ENGINE not enabled (--strict)")

    print(f"[35] USE_LANGGRAPH_ENGINE effective={lg}")
    llm_rev = _truthy("GRAPH_LLM_TRADE_REVIEWER")
    print(f"[35] GRAPH_LLM_TRADE_REVIEWER={llm_rev} (deterministic-only when false)")

    fqtn = (os.getenv("REVIEWER_LOG_BQ") or "").strip()
    ok, msg = _check_bq_table_fqtn(fqtn)
    print(f"[35] {msg}")
    if not ok:
        failures.append(msg)

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\nOK — see docs/REVIEWER_PRODUCTION_ROLLOUT.md for staging watch + cutover checklist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

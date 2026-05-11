#!/usr/bin/env python3
"""Repo-side checks for TODOS queue 18–21 (Web Push / probe wiring).

Does **not** replace GCP runbook steps; use after cloud DDL/Redis/VAPID are set to
verify env + optional live probes. Exit 0 = all checks pass; 1 = one or more failed.

Usage:
  python3 scripts/verify_ops_queue_18_21.py
  python3 scripts/verify_ops_queue_18_21.py --strict   # fail if WEB_PUSH_ENABLED but Redis URL missing
"""

from __future__ import annotations

import argparse
import os
import sys


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _check_redis(url: str) -> tuple[bool, str]:
    if not url:
        return True, "WEB_PUSH_REDIS_URL unset (skip ping)"
    try:
        import redis

        r = redis.from_url(url, decode_responses=True)
        r.ping()
        return True, "Redis PING ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"Redis: {exc}"


def _check_bq_table_fqtn(fqtn: str) -> tuple[bool, str]:
    """Optional: verify table exists when GOOGLE_APPLICATION_CREDENTIALS + project available."""
    if not fqtn or "." not in fqtn:
        return True, "BQ table env unset (skip)"
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
        help="If WEB_PUSH_ENABLED=1, require WEB_PUSH_REDIS_URL non-empty",
    )
    args = p.parse_args()

    failures: list[str] = []

    wp_on = _truthy("WEB_PUSH_ENABLED")
    redis_url = (os.getenv("WEB_PUSH_REDIS_URL") or "").strip()
    vapid_pub = (os.getenv("VAPID_PUBLIC_KEY") or os.getenv("VITE_WEB_PUSH_VAPID_PUBLIC_KEY") or "").strip()
    vapid_priv = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    admin_key = (os.getenv("WEB_PUSH_ADMIN_KEY") or "").strip()
    sub_table = (os.getenv("WEB_PUSH_SUBSCRIPTIONS_TABLE") or "").strip()
    probe_table = (os.getenv("PRICE_PROBE_LOG_TABLE") or "").strip()

    if wp_on and args.strict and not redis_url:
        failures.append("WEB_PUSH_ENABLED=1 but WEB_PUSH_REDIS_URL empty (--strict)")

    ok, msg = _check_redis(redis_url)
    if not ok:
        failures.append(msg)
    print(f"[18-19] {msg}")

    if wp_on:
        if not vapid_pub:
            failures.append("WEB_PUSH on but no VAPID public key (VAPID_PUBLIC_KEY or VITE_WEB_PUSH_VAPID_PUBLIC_KEY)")
        if not vapid_priv:
            failures.append("WEB_PUSH on but VAPID_PRIVATE_KEY missing on backend")
        print(f"[20] VAPID public set={bool(vapid_pub)} private set={bool(vapid_priv)}")
        if not admin_key:
            print("[21] WEB_PUSH_ADMIN_KEY unset — test-send cannot be verified from this script")
        else:
            print("[21] WEB_PUSH_ADMIN_KEY set (use curl POST /api/push/test-send per RUNBOOK)")
    else:
        print("[20-21] WEB_PUSH_ENABLED off — VAPID/test-send checks skipped")

    for label, fqtn in (
        ("WEB_PUSH_SUBSCRIPTIONS_TABLE", sub_table),
        ("PRICE_PROBE_LOG_TABLE", probe_table),
    ):
        ok, msg = _check_bq_table_fqtn(fqtn)
        print(f"[18] {label}: {msg}")
        if not ok:
            failures.append(f"{label}: {msg}")

    if failures:
        print("\nFAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("\nOK — see docs/OPS_QUEUE_18_21_RUNBOOK.md for cloud checklist + TODOS checkboxes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

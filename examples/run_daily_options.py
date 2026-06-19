#!/usr/bin/env python3
"""Example: run the daily options flow + GEX pipeline.

Offline (no network, no BigQuery), using bundled mock fixtures:

    MOCK_APIS=1 SKIP_BIGQUERY=1 python3 examples/run_daily_options.py

Live (needs a paid Polygon Options plan + POLYGON_API_KEY):

    POLYGON_API_KEY=... python3 examples/run_daily_options.py MU NVDA AMD
"""

from __future__ import annotations

import logging
import os
import sys

# Allow running from the repo root without installation.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.options.pipeline import run_daily_options_pipeline  # noqa: E402
from tools.options.prompts import build_analysis_user_prompt  # noqa: E402


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    watchlist = [a.strip().upper() for a in argv if a.strip()] or None

    summary = run_daily_options_pipeline(watchlist)

    print("=== 能力（capabilities） ===")
    print(", ".join(c.value for c in summary.capabilities) or "(none)")
    print("\n=== 文字摘要 ===")
    print(summary.text_summary or "(empty)")
    print("\n=== 結構化 JSON（前 800 字，供 LLM analysis-only） ===")
    payload = summary.model_dump_json(indent=2)
    print(payload[:800] + ("…" if len(payload) > 800 else ""))
    print("\n=== LLM user prompt 範例（截斷） ===")
    print(build_analysis_user_prompt(payload)[:200] + "…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Daily options flow + GEX tick entrypoint.

Callable from GitHub Actions, Cloud Run / Cloud Scheduler, or cron:

    python3 scripts/options_flow_tick.py            # uses OPTIONS_WATCHLIST or default
    python3 scripts/options_flow_tick.py MU NVDA    # explicit watchlist

Prints the structured PipelineSummary as JSON to stdout (for downstream Telegram /
Agent consumption). Per-symbol failures are isolated inside the pipeline.
"""

from __future__ import annotations

import logging
import sys


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from tools.options.pipeline import run_daily_options_pipeline

    watchlist = [a.strip().upper() for a in argv if a.strip()] or None
    summary = run_daily_options_pipeline(watchlist)
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

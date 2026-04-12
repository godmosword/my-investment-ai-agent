#!/usr/bin/env python3
"""CLI: run one paper execution tick (M5). Same logic as ``POST /api/paper/execution-tick`` without HTTP.

Usage:
  python scripts/paper_execution_tick.py

Requires ``EXECUTION_INTENT_STORE`` (or default .qsilicon/execution_intents.jsonl) and network for yfinance.
"""

from __future__ import annotations

import json
import sys

from paper_execution import run_paper_execution_tick


def main() -> int:
    rows = run_paper_execution_tick()
    print(json.dumps({"written": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

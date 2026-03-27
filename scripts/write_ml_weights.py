#!/usr/bin/env python3
"""Write versioned ML weights JSON for signal_weights_store (optional crew context).

Usage:
  python scripts/write_ml_weights.py path/to/weights.json
  python scripts/write_ml_weights.py   # reads stdin JSON

Example weights.json:
  {
    "version": 3,
    "source": "backtest_walkforward",
    "weights": {"dxy": 0.12, "etf_flow": 0.18, "risk": 0.2, "mvrv": 0.15}
  }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root without install
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from signal_weights_store import write_weights  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw)
    if "weights" not in data or not isinstance(data["weights"], dict):
        raise SystemExit("JSON must contain object 'weights' with string->number map")
    out = write_weights(data, backup_previous=True)
    print(f"OK wrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
結構化預檢：以合成戰報骨架呼叫 validate_report（無 LLM、無 Telegram）。

對齊 TODOS「結構化預檢 dry-run」：適合 staging／CI 快速確認 Gate 迴歸。

用法：
  SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python3 scripts/validate_report_dry_run.py
  # 預期 exit 0（預設骨架應通過 validate_report；呢喃相關 warning 仍可能列入 issues）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _root()
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.setdefault("SKIP_TELEGRAM", "1")
    os.environ.setdefault("SKIP_BIGQUERY", "1")

    from report_html_gates import validate_report  # noqa: PLC0415

    # Local import: same directory as this script (no main.py / crew import chain).
    import importlib.util  # noqa: PLC0415

    sk_path = root / "scripts" / "report_skeleton_validate.py"
    spec = importlib.util.spec_from_file_location("_report_skeleton_validate", sk_path)
    if spec is None or spec.loader is None:
        print("missing scripts/report_skeleton_validate.py", file=sys.stderr)
        return 1
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    report = mod.minimal_valid_report_text()
    profile = (os.getenv("REPORT_PROFILE") or "").strip() or None
    result = validate_report(report, profile=profile)
    valid = bool(result.get("valid"))
    issues = list(result.get("issues") or [])
    print(
        f"validate_report dry-run: profile={result.get('profile', 'full')} "
        f"valid={valid} issues={len(issues)}"
    )
    for i, issue in enumerate(issues[:24], 1):
        line = str(issue).replace("\n", " ")[:200]
        print(f"  {i}. {line}")
    if len(issues) > 24:
        print(f"  … +{len(issues) - 24} more")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
check_report.py — 本地日報品質速查 CLI（方案 C）

用法：
  python check_report.py report.html          # 指定 HTML 檔案
  python check_report.py --latest             # 讀取最新 scratchpad JSONL 裡的報告
  python check_report.py --llm report.html    # 加上 LLM 評分（需 OPENAI_API_KEY）

輸出：純文字 Q-Score 卡片到 stdout，非零 exit code 代表品質不過關。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from report_judge import (
    domain_quality_check,
    format_quality_card,
    hard_pattern_judge_pass,
    hard_pattern_judge_reason,
    llm_quality_judge,
)


def _strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", text)


def _load_html_from_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _load_html_from_latest_scratchpad() -> str:
    """從最新的 scratchpad JSONL 找最後一筆 final_report。"""
    candidates = sorted(Path(".").glob("scratchpad*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("找不到 scratchpad*.jsonl，請指定 HTML 檔案或先跑一次 main.py")
    latest = candidates[0]
    print(f"[info] 讀取 scratchpad: {latest}", file=sys.stderr)
    report_html: str | None = None
    with open(latest, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "final_report" in rec and rec["final_report"]:
                report_html = rec["final_report"]
    if not report_html:
        raise ValueError(f"{latest} 中找不到 final_report 欄位")
    return report_html


def main() -> None:
    parser = argparse.ArgumentParser(description="本地日報品質速查")
    parser.add_argument("file", nargs="?", help="HTML 報告檔案路徑")
    parser.add_argument("--latest", action="store_true", help="從最新 scratchpad JSONL 讀取")
    parser.add_argument("--llm", action="store_true", help="執行 LLM 評分（需 OPENAI_API_KEY）")
    args = parser.parse_args()

    # ── 取得報告內容 ──────────────────────────────────────────────
    if args.latest:
        try:
            html = _load_html_from_latest_scratchpad()
        except (FileNotFoundError, ValueError) as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(2)
    elif args.file:
        if not Path(args.file).exists():
            print(f"[error] 找不到檔案：{args.file}", file=sys.stderr)
            sys.exit(2)
        html = _load_html_from_file(args.file)
    else:
        parser.print_help()
        sys.exit(0)

    # ── 硬規則檢查 ────────────────────────────────────────────────
    hard_pass = hard_pattern_judge_pass(html)
    hard_reason = hard_pattern_judge_reason(html)

    print("=" * 60)
    print("🔍 硬規則檢查")
    if hard_pass:
        print("  ✅ 通過（無 API 錯誤 / Traceback 外洩）")
    else:
        print(f"  ❌ 失敗 — 命中關鍵字：{hard_reason}")
    print()

    # ── 域專用品質檢查 ────────────────────────────────────────────
    dqc = domain_quality_check(html)
    card_html = format_quality_card(dqc)
    card_plain = _strip_html(card_html)
    print("📊 Domain Q-Score 卡片")
    print(card_plain)
    print()

    # 細項
    tools = dqc.get("tools", {})
    print("  工具出現明細：")
    for k, v in tools.items():
        print(f"    {'✅' if v else '❌'} {k}")
    src = dqc.get("source_health", {})
    print("  來源健康：", src)
    print(f"  情境分析：{dqc.get('scenario_legs')}/{dqc.get('trade_legs')} 腿")
    print(f"  執行摘要：{'有' if dqc.get('has_exec') else '無'}")
    print()

    # ── LLM 評分（可選）──────────────────────────────────────────
    if args.llm:
        print("🤖 LLM 評分中…")
        result = llm_quality_judge(html)
        if result.get("raw_error"):
            print(f"  ⚠️  LLM 評分跳過：{result['raw_error']}")
        else:
            print(f"  Overall: {result.get('overall_score')}  pass={result.get('pass')}")
            for dim, score in (result.get("rubric") or {}).items():
                print(f"    {dim}: {score}")
            for r in (result.get("reasons") or []):
                print(f"    · {r}")
        print()

    # ── 退出碼 ────────────────────────────────────────────────────
    overall = dqc.get("overall", 0.0)
    if not hard_pass or overall < 55:
        print(f"❌ 品質不過關（hard_pass={hard_pass}, overall={overall}）")
        sys.exit(1)
    elif overall < 75:
        print(f"⚠️  品質尚可，建議優化（overall={overall}）")
        sys.exit(0)
    else:
        print(f"✅ 品質良好（overall={overall}）")
        sys.exit(0)


if __name__ == "__main__":
    main()

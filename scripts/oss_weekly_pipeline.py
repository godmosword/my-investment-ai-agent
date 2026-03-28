#!/usr/bin/env python3
"""一鍵：GitHub 搜尋 → digest → 改版計畫 MD → 合併週報條目至 TODOS.md。

環境變數：繼承 SCOUT_*、GITHUB_TOKEN、OSS_README_MAX_CHARS。
  OSS_SCOUT_DATE        — 強制報告日 YYYY-MM-DD（預設 UTC 今日）
  OSS_WEEKLY_SKIP_TODOS — 1 時不修改 TODOS.md
  OSS_WEEKLY_MAX_WEEKS  — TODOS 內保留週數上限（預設 8）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# scripts/ as cwd for imports
_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from oss_scout_candidates import build_payload, search_repositories  # noqa: E402
from oss_repo_digest import digest_candidates  # noqa: E402
from oss_suitability import label_for_score, score_repo  # noqa: E402

MARK_BEGIN = "<!-- OSS_SCOUT_AUTO_BEGIN -->"
MARK_END = "<!-- OSS_SCOUT_AUTO_END -->"
SECTION_HEADER = """## OSS Scout 週報（自動）

> 每週搜尋 GitHub 熱門／指定 topic 之 repo，拉取 README 與 **啟發式適配度**；**是否實作由維護者勾選**。詳稿見 `docs/oss_candidates/YYYY-MM-DD-revision-plan-draft.md`。
"""


def _today_utc() -> str:
    raw = (os.environ.get("OSS_SCOUT_DATE") or "").strip()
    if raw:
        return raw
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _enrich_repos(repos: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    out = []
    for r in repos:
        row = dict(r)
        s, why = score_repo(row)
        row["fit_score"] = s
        row["fit_rationale"] = why
        row["fit_label"] = label_for_score(s)
        row["readme_blurb"] = (row.get("readme_excerpt") or "")[:500]
        out.append(row)
    high = [x for x in out if x["fit_score"] >= 4]
    low = [x for x in out if x["fit_score"] <= 2 or x.get("error")]
    return out, high, low


def _render_plan(
    date: str,
    bundle: dict,
    repos: list[dict],
    repos_high: list[dict],
    repos_low: list[dict],
) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_ROOT / "templates")),
        autoescape=False,
    )
    try:
        tpl = env.get_template("oss_weekly_plan.md.j2")
    except TemplateNotFound as e:
        raise RuntimeError(f"template missing: {e}") from e
    return tpl.render(
        date=date,
        query=bundle.get("query"),
        sort=bundle.get("sort"),
        per_page=bundle.get("per_page"),
        total_count=bundle.get("total_count"),
        repos=repos,
        repos_high=repos_high,
        repos_low=repos_low,
    )


def _build_todos_block(date: str, repos: list[dict]) -> str:
    lines = [
        f"**本週 OSS 候選（{date}）** — 依適配度排序；勾選後再評估 spike／PR（**不自動合併**）。",
        "",
        f"研究稿：[`docs/oss_candidates/{date}-revision-plan-draft.md`](docs/oss_candidates/{date}-revision-plan-draft.md)",
        "",
    ]
    for r in sorted(repos, key=lambda x: (-x["fit_score"], x.get("full_name") or "")):
        stars = r.get("stargazers_count")
        star_s = str(stars) if stars is not None else "?"
        fn = r.get("full_name") or "?"
        lines.append(
            f"- [ ] **（{r['fit_label']}｜{r['fit_score']}/5）** `{fn}`（★{star_s}）— {r['fit_rationale']}"
        )
    return "\n".join(lines)


def _trim_weekly_blocks(inner: str, max_blocks: int) -> str:
    inner = inner.strip()
    if not inner:
        return ""
    blocks = re.split(r"\n(?=### )", inner)
    blocks = [b.strip() for b in blocks if b.strip()]
    return "\n\n---\n\n".join(blocks[:max_blocks])


def merge_todos(todos_path: Path, date: str, block_md: str) -> None:
    try:
        max_w = int(os.environ.get("OSS_WEEKLY_MAX_WEEKS") or "8")
    except ValueError:
        max_w = 8
    max_w = max(1, min(max_w, 52))

    text = todos_path.read_text(encoding="utf-8")
    new_block = f"### {date}\n\n{block_md.strip()}\n"

    if MARK_BEGIN not in text or MARK_END not in text:
        insertion = (
            f"\n{SECTION_HEADER}\n{MARK_BEGIN}\n\n"
            f"{new_block}\n\n{MARK_END}\n\n"
        )
        anchor = "## 修訂紀錄"
        if anchor in text:
            text = text.replace(anchor, insertion + anchor, 1)
        else:
            text = text.rstrip() + "\n" + insertion
        todos_path.write_text(text, encoding="utf-8")
        return

    i = text.index(MARK_BEGIN) + len(MARK_BEGIN)
    j = text.index(MARK_END)
    inner = text[i:j]
    combined = new_block + ("\n\n---\n\n" + inner.strip() if inner.strip() else "")
    combined = _trim_weekly_blocks(combined, max_w)
    text = text[:i] + "\n\n" + combined + "\n\n" + text[j:]
    todos_path.write_text(text, encoding="utf-8")


def run_pipeline(*, skip_todos: bool, date_override: str | None) -> int:
    date = date_override or _today_utc()
    out_dir = _ROOT / "docs" / "oss_candidates"
    out_dir.mkdir(parents=True, exist_ok=True)

    cand_path = out_dir / f"{date}-candidates.json"
    dig_path = out_dir / f"{date}-digest.json"
    plan_path = out_dir / f"{date}-revision-plan-draft.md"

    query = (os.environ.get("SCOUT_GITHUB_QUERY") or "topic:quantitative-finance stars:>20").strip()
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    sort = (os.environ.get("SCOUT_SORT") or "stars").strip().lower()
    try:
        per_page = int(os.environ.get("SCOUT_PER_PAGE") or "20")
    except ValueError:
        per_page = 20

    try:
        raw = search_repositories(query, token, sort=sort, per_page=per_page)
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 1

    bundle = build_payload(raw, query=query, sort=sort, per_page=per_page)
    cand_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = digest_candidates(bundle.get("items") or [], token)
    digest_obj = {"source": cand_path.name, "date": date, "repos": rows}
    dig_path.write_text(json.dumps(digest_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    repos, repos_high, repos_low = _enrich_repos(rows)
    md = _render_plan(date, bundle, repos, repos_high, repos_low)
    plan_path.write_text(md, encoding="utf-8")

    if not skip_todos and os.environ.get("OSS_WEEKLY_SKIP_TODOS", "").lower() not in (
        "1",
        "true",
        "yes",
    ):
        merge_todos(_ROOT / "TODOS.md", date, _build_todos_block(date, repos))

    print(f"Wrote {cand_path.relative_to(_ROOT)}")
    print(f"Wrote {dig_path.relative_to(_ROOT)}")
    print(f"Wrote {plan_path.relative_to(_ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="OSS weekly: search + digest + plan + TODOS merge")
    parser.add_argument("--skip-todos", action="store_true", help="Do not modify TODOS.md")
    parser.add_argument("--date", help="Override report date YYYY-MM-DD")
    args = parser.parse_args()
    return run_pipeline(skip_todos=args.skip_todos, date_override=args.date)


if __name__ == "__main__":
    raise SystemExit(main())

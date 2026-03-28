#!/usr/bin/env python3
"""Scout 候選輔助：呼叫 GitHub Search API，輸出 JSON 至 stdout（BL-09）。

仍須人類審閱後開 PR；流程見 docs/oss_candidates/README.md。

環境變數：
  GITHUB_TOKEN       — 建議設定以提高 rate limit
  SCOUT_GITHUB_QUERY — 預設 topic:quantitative-finance stars:>20
  SCOUT_SORT         — stars | forks | help-wanted-issues | updated（預設 stars）
  SCOUT_PER_PAGE     — 1–100（預設 20）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

_VALID_SORTS = frozenset({"stars", "forks", "help-wanted-issues", "updated"})


def search_repositories(
    query: str,
    token: str,
    *,
    sort: str = "stars",
    per_page: int = 20,
) -> dict:
    """Call GitHub search/repositories (for tests: patch this or urlopen)."""
    if sort not in _VALID_SORTS:
        raise ValueError(f"invalid sort={sort!r}, expected one of {_VALID_SORTS}")
    per_page = max(1, min(100, per_page))
    q = urllib.parse.quote(query, safe="")
    url = (
        f"https://api.github.com/search/repositories?q={q}"
        f"&sort={urllib.parse.quote(sort)}&order=desc&per_page={per_page}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Q-Silicon-oss-scout",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _slim_items(data: dict) -> list[dict]:
    items = data.get("items") or []
    return [
        {
            "full_name": it.get("full_name"),
            "html_url": it.get("html_url"),
            "description": (it.get("description") or "")[:240],
            "stargazers_count": it.get("stargazers_count"),
            "forks_count": it.get("forks_count"),
            "updated_at": it.get("updated_at"),
            "pushed_at": it.get("pushed_at"),
            "archived": it.get("archived"),
            "topics": it.get("topics") or [],
        }
        for it in items
    ]


def build_payload(data: dict, *, query: str, sort: str, per_page: int) -> dict:
    return {
        "query": query,
        "sort": sort,
        "per_page": per_page,
        "total_count": data.get("total_count"),
        "items": _slim_items(data),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub OSS scout (search repositories)")
    parser.add_argument("--dry-run", action="store_true", help="Print config only, no network")
    parser.add_argument(
        "--out-json",
        metavar="PATH",
        help="Also write JSON to PATH (e.g. docs/oss_candidates/YYYY-MM-DD-candidates.json)",
    )
    args = parser.parse_args()

    query = (os.environ.get("SCOUT_GITHUB_QUERY") or "topic:quantitative-finance stars:>20").strip()
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    sort = (os.environ.get("SCOUT_SORT") or "stars").strip().lower()
    try:
        per_page = int(os.environ.get("SCOUT_PER_PAGE") or "20")
    except ValueError:
        per_page = 20

    if sort not in _VALID_SORTS:
        print(json.dumps({"error": f"invalid SCOUT_SORT={sort!r}"}, indent=2), file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "query": query,
                    "sort": sort,
                    "per_page": per_page,
                    "hint": "Remove --dry-run and set GITHUB_TOKEN to fetch live results.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    try:
        data = search_repositories(query, token, sort=sort, per_page=per_page)
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(json.dumps({"error": str(e), "body": body[:2000]}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except OSError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    payload = build_payload(data, query=query, sort=sort, per_page=per_page)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.out_json:
        path = args.out_json
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

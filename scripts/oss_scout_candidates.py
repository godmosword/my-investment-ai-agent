#!/usr/bin/env python3
"""Scout 候選輔助：呼叫 GitHub Search API，輸出 JSON 至 stdout（BL-09）。

仍須人類審閱後開 PR；流程見 docs/oss_candidates/README.md。

環境變數：
  GITHUB_TOKEN   — 建議設定以提高 rate limit
  SCOUT_GITHUB_QUERY — 預設 topic:quantitative-finance stars:>20
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _search_repositories(query: str, token: str) -> dict:
    q = urllib.parse.quote(query, safe="")
    url = f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=20"
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


def main() -> int:
    query = (os.environ.get("SCOUT_GITHUB_QUERY") or "topic:quantitative-finance stars:>20").strip()
    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    if "--dry-run" in sys.argv:
        print(
            json.dumps(
                {
                    "query": query,
                    "hint": "Remove --dry-run and set GITHUB_TOKEN to fetch live results.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    try:
        data = _search_repositories(query, token)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(json.dumps({"error": str(e), "body": body[:2000]}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    except OSError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    items = data.get("items") or []
    slim = [
        {
            "full_name": it.get("full_name"),
            "html_url": it.get("html_url"),
            "description": (it.get("description") or "")[:240],
            "stargazers_count": it.get("stargazers_count"),
            "updated_at": it.get("updated_at"),
        }
        for it in items
    ]
    print(json.dumps({"total_count": data.get("total_count"), "items": slim}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

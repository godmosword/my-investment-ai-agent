#!/usr/bin/env python3
"""對 scout 產出的候選 JSON 逐筆拉取 GitHub REST：repo 摘要 + README 前 N 字。

環境變數：
  GITHUB_TOKEN           — 建議設定
  OSS_README_MAX_CHARS   — README 截斷長度（預設 8000）
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.request
from typing import Any


def _request_json(url: str, token: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Q-Silicon-oss-digest",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_repo_detail(full_name: str, token: str) -> dict[str, Any]:
    """GET /repos/{owner}/{repo} + readme metadata."""
    owner, _, repo = full_name.partition("/")
    if not owner or not repo:
        return {"full_name": full_name, "error": "invalid full_name"}
    base = f"https://api.github.com/repos/{owner}/{repo}"
    out: dict[str, Any] = {"full_name": full_name, "html_url": f"https://github.com/{full_name}"}
    try:
        meta = _request_json(base, token)
    except urllib.error.HTTPError as e:
        out["error"] = f"repo {e.code}"
        return out
    except OSError as e:
        out["error"] = str(e)
        return out

    lic = meta.get("license") or {}
    out.update(
        {
            "description": (meta.get("description") or "")[:500],
            "stargazers_count": meta.get("stargazers_count"),
            "forks_count": meta.get("forks_count"),
            "pushed_at": meta.get("pushed_at"),
            "updated_at": meta.get("updated_at"),
            "archived": meta.get("archived"),
            "default_branch": meta.get("default_branch"),
            "topics": meta.get("topics") or [],
            "license_spdx": lic.get("spdx_id"),
            "homepage": meta.get("homepage"),
        }
    )

    try:
        readme = _request_json(f"{base}/readme", token)
        raw_b64 = readme.get("content") or ""
        decoded = base64.b64decode(raw_b64.replace("\n", "")).decode("utf-8", errors="replace")
        out["readme_html_url"] = readme.get("html_url")
    except urllib.error.HTTPError:
        out["readme_excerpt"] = ""
        out["readme_note"] = "no_readme_or_forbidden"
    except OSError as e:
        out["readme_excerpt"] = ""
        out["readme_note"] = str(e)
    else:
        max_c = int(os.environ.get("OSS_README_MAX_CHARS") or "8000")
        out["readme_excerpt"] = decoded[:max_c]
        if len(decoded) > max_c:
            out["readme_truncated"] = True

    return out


def digest_candidates(
    items: list[dict],
    token: str,
) -> list[dict[str, Any]]:
    return [fetch_repo_detail(str(it.get("full_name") or ""), token) for it in items if it.get("full_name")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch README + metadata for scout candidates JSON")
    parser.add_argument("candidates_json", help="Path to candidates JSON (with items[])")
    parser.add_argument("--out-json", required=True, metavar="PATH", help="Write digest JSON")
    args = parser.parse_args()

    token = (os.environ.get("GITHUB_TOKEN") or "").strip()
    with open(args.candidates_json, encoding="utf-8") as f:
        bundle = json.load(f)
    items = bundle.get("items") or []
    rows = digest_candidates(items, token)
    out = {
        "source": os.path.basename(args.candidates_json),
        "repos": rows,
    }
    text = json.dumps(out, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Optional YAML brief layout (Phase 4b).

``BRIEF_LAYOUT_FILE`` points to a YAML file; when unset or empty, callers use
built-in ``PROFILES`` only (Phase 2 behavior). When set, ``blocks`` may reorder
or omit coarse block ids, but each id must appear in ``BLOCK_IDS`` (whitelist)
and in the active profile's baseline list (no blocks outside that profile).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Final

import yaml

from brief_profiles import BLOCK_IDS

logger = logging.getLogger(__name__)

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent
_BLOCK_WHITELIST: Final[frozenset[str]] = frozenset(BLOCK_IDS)


def _resolve_layout_path(raw: str) -> Path:
    text = raw.strip()
    p = Path(text)
    if p.is_absolute():
        return p
    return (_REPO_ROOT / p).resolve()


def _parse_layout_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("brief layout YAML root must be a mapping")
    return data


def merge_profile_blocks_from_file(
    profile: str,
    baseline: tuple[str, ...],
    *,
    layout_path: str | None = None,
) -> tuple[str, ...]:
    """Return ``baseline`` merged with YAML ``blocks`` when path is readable.

    ``layout_path`` defaults to ``os.environ.get("BRIEF_LAYOUT_FILE")``.
    Missing env, blank path, missing file, or wrong ``applies_to_profile`` →
    ``baseline`` unchanged (may log warning).
    """
    raw = layout_path if layout_path is not None else os.environ.get("BRIEF_LAYOUT_FILE")
    if raw is None or str(raw).strip() == "":
        return baseline

    path = _resolve_layout_path(str(raw))
    if not path.is_file():
        logger.warning("BRIEF_LAYOUT_FILE set but not a file: %s — using built-in profile", path)
        return baseline

    try:
        with path.open(encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
    except OSError as exc:
        logger.warning("BRIEF_LAYOUT_FILE read failed (%s): %s — using built-in profile", path, exc)
        return baseline
    except yaml.YAMLError as exc:
        raise ValueError(f"BRIEF_LAYOUT_FILE invalid YAML ({path}): {exc}") from exc

    payload = _parse_layout_payload(loaded)
    applies = payload.get("applies_to_profile")
    if applies is not None and str(applies).strip().lower() != profile.strip().lower():
        logger.warning(
            "BRIEF_LAYOUT_FILE %s applies_to_profile=%r does not match active profile=%r — ignoring layout",
            path,
            applies,
            profile,
        )
        return baseline

    blocks = payload.get("blocks")
    if blocks is None:
        logger.warning("BRIEF_LAYOUT_FILE %s has no 'blocks' key — using built-in profile", path)
        return baseline
    if not isinstance(blocks, list):
        raise ValueError(f"BRIEF_LAYOUT_FILE 'blocks' must be a list (got {type(blocks).__name__})")
    if len(blocks) == 0:
        raise ValueError("BRIEF_LAYOUT_FILE 'blocks' must not be empty")

    base_set = frozenset(baseline)
    seen: set[str] = set()
    out: list[str] = []
    for i, raw_id in enumerate(blocks):
        if not isinstance(raw_id, str):
            raise ValueError(f"BRIEF_LAYOUT_FILE blocks[{i}] must be str, got {type(raw_id).__name__}")
        bid = raw_id.strip()
        if bid in seen:
            raise ValueError(f"BRIEF_LAYOUT_FILE duplicate block id: {bid!r}")
        seen.add(bid)
        if bid not in _BLOCK_WHITELIST:
            raise ValueError(
                f"BRIEF_LAYOUT_FILE unknown block id {bid!r}; "
                f"allowed ids are from BLOCK_IDS whitelist"
            )
        if bid not in base_set:
            raise ValueError(
                f"BRIEF_LAYOUT_FILE block {bid!r} is not in built-in profile {profile!r}; "
                "only reorder or omit blocks from that profile"
            )
        out.append(bid)

    if frozenset(out) != base_set:
        missing = sorted(base_set - frozenset(out))
        extra_msg = f"; missing from layout: {missing}" if missing else ""
        raise ValueError(
            "BRIEF_LAYOUT_FILE 'blocks' must include every block of the built-in profile "
            f"(same set as baseline for {profile!r}){extra_msg}"
        )

    return tuple(out)

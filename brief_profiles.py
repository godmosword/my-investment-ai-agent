"""Telegram daily brief profiles (Phase 2 modularization).

`full` must remain byte-identical to Phase 0 output (see `test_telegram_template_modularization`).
`lite` omits previous_recs, macro_framework, prediction_markets, crypto/ai blocks ①–③,
and the institutional thesis block — see `modularization_plan.md` PROFILES["lite"].
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

# Baseline coarse block ids (modularization_plan § BLOCK_IDS; Phase 5 may insert roundtable).
BLOCK_IDS: Final[tuple[str, ...]] = (
    "header",
    "exec_summary",
    "previous_recs",
    "market_mode",
    "macro_framework",
    "prediction_markets",
    "crypto_dashboard",
    "crypto_news",
    "crypto_chatter",
    "crypto_trades",
    "ai_bridge",
    "ai_dashboard",
    "ai_news",
    "ai_chatter",
    "ai_trades",
    "current_affairs_roundtable",
    "institutional_view",
    "source_health",
    "qsrec",
)

_PROFILE_FULL: Final[tuple[str, ...]] = BLOCK_IDS
_PROFILE_LITE: Final[tuple[str, ...]] = (
    "header",
    "exec_summary",
    "market_mode",
    "crypto_trades",
    "ai_trades",
    "qsrec",
)
_PROFILE_CRYPTO_ONLY: Final[tuple[str, ...]] = (
    "header",
    "exec_summary",
    "market_mode",
    "macro_framework",
    "prediction_markets",
    "crypto_dashboard",
    "crypto_news",
    "crypto_chatter",
    "crypto_trades",
    "source_health",
    "qsrec",
)

PROFILES: Final[dict[str, tuple[str, ...]]] = {
    "full": _PROFILE_FULL,
    "lite": _PROFILE_LITE,
    "crypto-only": _PROFILE_CRYPTO_ONLY,
}

# Template path relative to `templates/` (Jinja FileSystemLoader root).
_PROFILE_TEMPLATE: Final[dict[str, str]] = {
    "full": "profiles/telegram_full.j2",
    "lite": "profiles/telegram_lite.j2",
    "crypto-only": "profiles/telegram_crypto_only.j2",
}


@dataclass(frozen=True, slots=True)
class BlockRegistryEntry:
    """Maps a logical block id to the Jinja macro module (for docs / future codegen)."""

    template_subpath: str  # under templates/blocks/
    macro_name: str
    empty_behavior: str = "omit_if_empty"  # narrative for operators; not enforced here


BLOCK_REGISTRY: Final[dict[str, BlockRegistryEntry]] = {
    "header": BlockRegistryEntry("_header.j2", "telegram_header"),
    "exec_summary": BlockRegistryEntry("_exec_summary.j2", "telegram_exec_summary"),
    "previous_recs": BlockRegistryEntry("_previous_recs.j2", "telegram_previous_recs"),
    "market_mode": BlockRegistryEntry("_market_mode.j2", "telegram_market_mode"),
    "macro_framework": BlockRegistryEntry("_macro_framework.j2", "telegram_macro_framework"),
    "prediction_markets": BlockRegistryEntry(
        "_prediction_markets.j2", "telegram_prediction_markets"
    ),
    "crypto_dashboard": BlockRegistryEntry("_crypto_section.j2", "telegram_crypto_section"),
    "crypto_news": BlockRegistryEntry("_crypto_section.j2", "telegram_crypto_section"),
    "crypto_chatter": BlockRegistryEntry("_crypto_section.j2", "telegram_crypto_section"),
    "crypto_trades": BlockRegistryEntry("_crypto_trades_only.j2", "telegram_crypto_trades_only"),
    "ai_bridge": BlockRegistryEntry("_ai_section.j2", "telegram_ai_section"),
    "ai_dashboard": BlockRegistryEntry("_ai_section.j2", "telegram_ai_section"),
    "ai_news": BlockRegistryEntry("_ai_section.j2", "telegram_ai_section"),
    "ai_chatter": BlockRegistryEntry("_ai_section.j2", "telegram_ai_section"),
    "ai_trades": BlockRegistryEntry("_ai_trades_only.j2", "telegram_ai_trades_only"),
    "current_affairs_roundtable": BlockRegistryEntry(
        "_current_affairs_roundtable.j2", "telegram_current_affairs_roundtable"
    ),
    "institutional_view": BlockRegistryEntry(
        "_institutional_view.j2", "telegram_institutional_view"
    ),
    "source_health": BlockRegistryEntry("_footer_tail.j2", "telegram_footer_tail"),
    "qsrec": BlockRegistryEntry("_footer_tail.j2", "telegram_footer_tail"),
}


def _normalize_profile(raw: str | None) -> str:
    if raw is None or str(raw).strip() == "":
        return "full"
    p = str(raw).strip().lower()
    if p in PROFILES:
        return p
    raise ValueError(
        f"REPORT_PROFILE must be one of {sorted(PROFILES.keys())!r}; got {raw!r}"
    )


def get_active_profile(explicit: str | None = None) -> str:
    """Resolve profile: explicit arg > env `REPORT_PROFILE` > `full`."""
    if explicit is not None and str(explicit).strip() != "":
        return _normalize_profile(explicit)
    return _normalize_profile(os.environ.get("REPORT_PROFILE"))


def profile_block_ids(profile: str) -> tuple[str, ...]:
    """Coarse block order for ``profile``, optionally merged from ``BRIEF_LAYOUT_FILE``."""
    from brief_profiles_layout import merge_profile_blocks_from_file

    p = _normalize_profile(profile)
    base = PROFILES[p]
    return merge_profile_blocks_from_file(p, base)


def telegram_profile_template_relpath(profile: str) -> str:
    """Relative path under `templates/` for the profile root template."""
    p = _normalize_profile(profile)
    return _PROFILE_TEMPLATE[p]


def assert_registry_covers_block_ids() -> None:
    """Invariant: every id in BLOCK_IDS appears in BLOCK_REGISTRY."""
    missing = [bid for bid in BLOCK_IDS if bid not in BLOCK_REGISTRY]
    if missing:
        raise RuntimeError(f"BLOCK_REGISTRY missing keys: {missing}")

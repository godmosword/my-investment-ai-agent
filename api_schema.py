"""Minimal API response schema guard helpers.

Centralises the recurring pattern of validating that third-party API responses
have the expected structure before downstream code tries to access nested fields.
Used by CoinGlass, NewsAPI, CryptoPanic, and other tool paths in ``tools_legacy`` / ``tools``.

Usage example::

    data = require_json_dict(response, source="CoinGlass")
    items = require_list(data, path="data.list", source="CoinGlass")
    rows = require_json_list(raw, source="FMP")  # top-level JSON array from resp.json()
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def require_json_dict(resp: Any, source: str = "") -> dict:
    """Assert that *resp* is a dict (i.e. the parsed JSON is an object).

    Returns the dict unchanged on success.  Raises ``ValueError`` on failure so
    callers can catch it and return a ``[DATA_MISSING:…]`` sentinel instead of
    crashing or silently producing wrong output.

    Args:
        resp: The value to validate, typically the result of ``response.json()``.
        source: Human-readable API source name for log messages.

    Raises:
        ValueError: If *resp* is not a dict.
    """
    if not isinstance(resp, dict):
        log_schema_mismatch(source, expected="dict", got=resp)
        label = f" [{source}]" if source else ""
        raise ValueError(
            f"API{label} returned unexpected type {type(resp).__name__!r}; expected a JSON object (dict)."
        )
    return resp


def require_json_list(resp: Any, source: str = "") -> list:
    """Assert that *resp* is a list (top-level JSON array).

    Use for APIs that return ``[...]`` at the root (e.g. Binance funding rate,
    FMP economic calendar, HuggingFace models list).

    Raises:
        ValueError: If *resp* is not a list.
    """
    if not isinstance(resp, list):
        log_schema_mismatch(source, expected="list", got=resp)
        label = f" [{source}]" if source else ""
        raise ValueError(
            f"API{label} returned unexpected type {type(resp).__name__!r}; expected a JSON array (list)."
        )
    return resp


def require_list(obj: Any, path: str, source: str = "") -> list:
    """Navigate *obj* along a dot-separated *path* and assert the result is a list.

    For example, ``require_list(data, "data.list", source="CoinGlass")`` is
    equivalent to ``data["data"]["list"]`` but with a clear error message instead
    of a bare ``KeyError`` or ``TypeError``.

    Returns the list unchanged on success.  Raises ``ValueError`` on failure.

    Args:
        obj: A dict (possibly nested) to navigate.
        path: Dot-separated key path, e.g. ``"results"`` or ``"data.items"``.
        source: Human-readable API source name for log messages.

    Raises:
        ValueError: If any key is missing or the final value is not a list.
    """
    current: Any = obj
    for key in path.split("."):
        if not isinstance(current, dict):
            log_schema_mismatch(source, expected=f"dict at '{key}'", got=current)
            label = f" [{source}]" if source else ""
            raise ValueError(
                f"API{label}: expected a dict at path segment '{key}', "
                f"got {type(current).__name__!r}."
            )
        if key not in current:
            log_schema_mismatch(source, expected=f"key '{key}' in response", got=list(current.keys()))
            label = f" [{source}]" if source else ""
            raise ValueError(
                f"API{label}: missing key '{key}' in response. "
                f"Available keys: {sorted(current.keys())}"
            )
        current = current[key]
    if not isinstance(current, list):
        log_schema_mismatch(source, expected=f"list at path '{path}'", got=current)
        label = f" [{source}]" if source else ""
        raise ValueError(
            f"API{label}: expected a list at path '{path}', got {type(current).__name__!r}."
        )
    return current


def log_schema_mismatch(source: str, expected: str, got: Any) -> None:
    """Log a structured warning when an API response does not match expectations.

    Deliberately does NOT raise — callers decide whether to raise or degrade.

    Args:
        source: Human-readable API source name (e.g. ``"CoinGlass"``).
        expected: Description of what was expected (e.g. ``"dict"``).
        got: The actual value that was received.
    """
    got_repr = repr(got)
    if len(got_repr) > 200:
        got_repr = got_repr[:200] + "…"
    label = f"[{source}] " if source else ""
    logger.warning(
        "API schema mismatch %sexpected=%s got_type=%s got_preview=%s",
        label,
        expected,
        type(got).__name__,
        got_repr,
    )

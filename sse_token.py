"""Short-lived SSE auth tokens (Phase 3 backlog closure).

EventSource cannot send custom headers, so SSE today accepts either the long-lived
``API_STREAM_AUTH_KEY`` via query (``stream_key=``) or header. To reduce exposure
of that key in browser-side query strings, we mint short-lived single-purpose
tokens minted from the long-lived key.

Design notes:
- In-memory only (process-local). Tokens disappear on restart — acceptable for
  browser sessions; the underlying ``API_STREAM_AUTH_KEY`` remains the source of
  truth.
- TTL is bounded by ``SSE_TOKEN_TTL_SECONDS`` (default 60, clamped to [10, 600]).
- ``mint`` requires the long-lived key (mirrors how the SSE endpoint already
  authenticates), so issuing tokens is no weaker than direct SSE access.
- ``verify`` is a side-effect-free check; tokens are reusable until expiry to
  support reconnects without minting a new token each time.
"""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass


DEFAULT_TTL_SECONDS = 60
MIN_TTL_SECONDS = 10
MAX_TTL_SECONDS = 600


@dataclass(frozen=True)
class MintedToken:
    token: str
    expires_at: float
    ttl_seconds: int


_TOKENS: dict[str, float] = {}


def _now() -> float:
    return time.time()


def _ttl_seconds() -> int:
    try:
        raw = int(os.getenv("SSE_TOKEN_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))
    except (TypeError, ValueError):
        raw = DEFAULT_TTL_SECONDS
    return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, raw))


def _gc(now: float | None = None) -> None:
    cutoff = now if now is not None else _now()
    expired = [tok for tok, exp in _TOKENS.items() if exp <= cutoff]
    for tok in expired:
        _TOKENS.pop(tok, None)


def reset_for_tests() -> None:
    _TOKENS.clear()


def mint() -> MintedToken:
    ttl = _ttl_seconds()
    now = _now()
    _gc(now)
    token = secrets.token_urlsafe(24)
    expires_at = now + ttl
    _TOKENS[token] = expires_at
    return MintedToken(token=token, expires_at=expires_at, ttl_seconds=ttl)


def verify(token: str | None) -> bool:
    if not token:
        return False
    now = _now()
    _gc(now)
    exp = _TOKENS.get(token)
    if exp is None:
        return False
    return exp > now

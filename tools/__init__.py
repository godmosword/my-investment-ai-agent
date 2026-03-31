"""Crew-facing tools package.

Legacy implementation: ``tools_legacy`` (repository root module). New code lives under
``tools.base``, ``tools.market``, … per ``docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md``.
"""

from __future__ import annotations

import tools_legacy as _tools_legacy

from . import base  # noqa: F401 — expose ``tools.base``
from . import market  # noqa: F401 — expose ``tools.market``

# Mirror full legacy surface (``from legacy import *`` omits leading-underscore names).
for _name in dir(_tools_legacy):
    if _name.startswith("__") or _name in ("base", "market"):
        continue
    globals()[_name] = getattr(_tools_legacy, _name)

__all__ = sorted(n for n in globals() if not n.startswith("_"))

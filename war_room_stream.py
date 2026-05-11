"""War-room SSE stream state: version counter + per-node event queue.

Thread-safety: all mutations hold _events_lock so graph nodes (sync threads)
can safely enqueue while the async FastAPI SSE handler drains.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

_stream_version = 0

# Per-node event queue: bounded deque protects against unbounded growth.
_node_events: deque[dict[str, Any]] = deque(maxlen=200)
_events_lock = threading.RLock()


def bump_war_room_stream_version() -> None:
    global _stream_version
    with _events_lock:
        _stream_version += 1


def get_war_room_stream_version() -> int:
    with _events_lock:
        return _stream_version


def emit_graph_node_event(node_name: str, data: dict[str, Any]) -> None:
    """Enqueue a node-completion event; called from synchronous graph nodes."""
    event: dict[str, Any] = {
        "node": node_name,
        "ts": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    with _events_lock:
        _node_events.append(event)
    bump_war_room_stream_version()


def drain_graph_node_events(max_items: int = 50) -> list[dict[str, Any]]:
    """Pop and return up to *max_items* pending node events (FIFO). Thread-safe."""
    out: list[dict[str, Any]] = []
    with _events_lock:
        while _node_events and len(out) < max_items:
            out.append(_node_events.popleft())
    return out

"""Bumps for SSE war-room stream (M4): version counter so clients detect intent writes without relying on mtime alone."""

from __future__ import annotations

_stream_version = 0


def bump_war_room_stream_version() -> None:
    global _stream_version
    _stream_version += 1


def get_war_room_stream_version() -> int:
    return _stream_version

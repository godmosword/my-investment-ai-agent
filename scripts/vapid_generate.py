#!/usr/bin/env python3
"""產生 Web Push VAPID 金鑰對（URL-safe public + PEM private）。

用法::

    python scripts/vapid_generate.py

貼入 ``.env``::

    WEB_PUSH_VAPID_PUBLIC_KEY=...
    WEB_PUSH_VAPID_PRIVATE_KEY=...   # PEM；多行可改為 \\n 單行

PWA：``VITE_WEB_PUSH_VAPID_PUBLIC_KEY`` 與後端 **public** 相同。
"""
from __future__ import annotations

import base64
import sys

from cryptography.hazmat.primitives import serialization


def main() -> int:
    try:
        from py_vapid import Vapid
    except ImportError:
        print("Install: pip install py-vapid", file=sys.stderr)
        return 1

    v = Vapid()
    v.generate_keys()
    raw = v.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    priv_pem = v.private_key.to_pem().decode()
    print("WEB_PUSH_VAPID_PUBLIC_KEY=" + pub)
    print("WEB_PUSH_VAPID_PRIVATE_KEY=" + priv_pem.replace("\n", "\\n"))
    print("VITE_WEB_PUSH_VAPID_PUBLIC_KEY=" + pub, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

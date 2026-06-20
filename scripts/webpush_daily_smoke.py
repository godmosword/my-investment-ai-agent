#!/usr/bin/env python3
"""日報 Web Push 端到端 staging 驗證（preflight 診斷 + 可選實送）。

切換日報為 Web Push（取代 Telegram）前，在 staging 跑此腳本確認整條鏈路：
裝置已透過 Portal 訂閱 → 共享 Redis 有訂閱 → VAPID 就緒 → 推送顯示 → 點開深連結。

用法::

    # 只診斷（不送）：印出 VAPID / Redis / 訂閱數 / 將使用的 url
    python scripts/webpush_daily_smoke.py

    # 實送一則「戰報已更新」測試通知到目前所有訂閱者（與日報相同 broadcast 路徑）
    python scripts/webpush_daily_smoke.py --send

需要的環境變數（見 docs/PWA_WEB_PUSH.md「日報投遞」）::

    WEB_PUSH_ENABLED=1
    WEB_PUSH_REDIS_URL=redis://…          # 共享訂閱（記憶體 store 在新 process 為空）
    WEB_PUSH_VAPID_PRIVATE_KEY=…          # PEM（scripts/vapid_generate.py）
    WEB_PUSH_PORTAL_URL=https://…vercel.app   # 組深連結 /report/{date}

退出碼：0=preflight OK（或實送 sent>0）；1=preflight 不滿足；2=實送失敗/無收件人。
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# 允許從 repo 根目錄外執行（web_push_store 在根目錄）。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _report_date() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def _preflight() -> tuple[bool, list[str]]:
    """回傳 (ok, 診斷行)。對齊 main._deliver_daily_brief_webpush 的 preflight。"""
    import web_push_store

    lines: list[str] = []
    enabled = web_push_store.web_push_enabled()
    redis_url = (os.getenv("WEB_PUSH_REDIS_URL") or "").strip()
    vapid = bool((os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY") or "").strip())
    summary_only = (os.getenv("WEB_PUSH_REDIS_SUMMARY_ONLY") or "").strip().lower() in ("1", "true", "yes")
    portal = (os.getenv("WEB_PUSH_PORTAL_URL") or "").strip().rstrip("/")

    lines.append(f"WEB_PUSH_ENABLED          : {'yes' if enabled else 'NO'}")
    lines.append(f"WEB_PUSH_REDIS_URL        : {'set' if redis_url else 'MISSING (Job 無共享訂閱)'}")
    lines.append(f"WEB_PUSH_REDIS_SUMMARY_ONLY: {'1 (無法 pywebpush!)' if summary_only else '0'}")
    lines.append(f"WEB_PUSH_VAPID_PRIVATE_KEY: {'set' if vapid else 'MISSING'}")
    lines.append(f"WEB_PUSH_PORTAL_URL       : {portal or '(空 → 開 Portal 首頁)'}")

    count = 0
    try:
        count = web_push_store.subscription_count()
    except Exception as exc:  # noqa: BLE001
        lines.append(f"subscription_count error  : {exc}")
    lines.append(f"subscription_count        : {count}")

    ok = enabled and bool(redis_url) and vapid and not summary_only and count > 0
    return ok, lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="日報 Web Push staging 驗證")
    parser.add_argument("--send", action="store_true", help="實送一則測試通知到所有訂閱者")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # noqa: BLE001 — dotenv 可選
        pass

    import web_push_store

    date = _report_date()
    portal = (os.getenv("WEB_PUSH_PORTAL_URL") or "").strip().rstrip("/")
    url = f"{portal}/report/{date}" if portal.startswith(("http://", "https://")) else None

    ok, lines = _preflight()
    print("── Web Push 日報 preflight ──")
    for ln in lines:
        print(f"  {ln}")
    print(f"  deep-link url             : {url or '(無；SW 會開 Portal 首頁)'}")

    if not ok:
        print("\n[FAIL] preflight 不滿足：上面標 MISSING/NO/0 的項目需先補。日報會 no-op 並 log，不送達。")
        return 1

    if not args.send:
        print("\n[OK] preflight 通過。加 --send 實際推一則測試通知到目前訂閱者。")
        return 0

    title = "Q-Silicon 戰報"
    body = f"今日 AI 半導體戰報已更新（{date}），點開查看全文。"
    result = web_push_store.broadcast(
        title,
        body,
        url,
        cap=web_push_store._int_env("WEB_PUSH_DAILY_SEND_MAX", 50),
        timeout=10,
    )
    print(f"\n── broadcast 結果 ──\n  {result}")
    if result.get("ok"):
        print("\n[OK] 已送出。請在裝置上確認通知顯示，並點開驗證導向正確報告頁。")
        return 0
    print("\n[FAIL] 實送未成功（sent=0）。檢查 VAPID/訂閱有效性與上面的 errors。")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

import { useEffect, useState } from "react";

/**
 * FE-6 — shared offline banner used on pages whose data lives behind
 * `/api/*` (which service-worker.js serves NetworkOnly). When the
 * browser reports `navigator.onLine === false` we surface a non-silent
 * banner so users know the data may be stale.
 *
 * Usage:
 *   <OfflineBanner />                              // default copy
 *   <OfflineBanner message="無法連線伺服器，資料可能不是最新。" />
 */
export default function OfflineBanner({
  message = "目前離線：資料源於 /api 為 NetworkOnly，部分內容可能不是最新。",
  testId = "today-offline-banner",
}) {
  const [isOnline, setIsOnline] = useState(() =>
    typeof globalThis.navigator !== "undefined" ? globalThis.navigator.onLine : true,
  );

  useEffect(() => {
    const bump = () => setIsOnline(Boolean(globalThis.navigator?.onLine));
    globalThis.addEventListener?.("online", bump);
    globalThis.addEventListener?.("offline", bump);
    return () => {
      globalThis.removeEventListener?.("online", bump);
      globalThis.removeEventListener?.("offline", bump);
    };
  }, []);

  if (isOnline) return null;

  return (
    <div
      className="today-offline-banner"
      role="status"
      aria-live="polite"
      data-testid={testId}
    >
      <span aria-hidden="true">⚠</span>
      <span>{message}</span>
    </div>
  );
}

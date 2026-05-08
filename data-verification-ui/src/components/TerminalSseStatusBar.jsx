import { useWarRoomSseStatus } from "../hooks/useWarRoomSse";

const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";

/**
 * 日報終端內即時串流狀態（與 SideNav SseDot 同源）。
 * 僅 Tailwind `md:hidden`（窄版）顯示：桌面側欄已有燈號。
 */
export default function TerminalSseStatusBar() {
  const { sseStatus } = useWarRoomSseStatus();

  if (!SSE_ENABLED) return null;

  const dotClass =
    sseStatus === "connected"
      ? "sse-dot sse-dot--connected"
      : sseStatus === "error"
        ? "sse-dot sse-dot--error"
        : "sse-dot";

  const shortLabel =
    sseStatus === "connected" ? "已連線" : sseStatus === "error" ? "連線失敗" : "連線中…";

  const ariaLabel = `戰情室即時串流：${shortLabel}`;

  return (
    <div
      className="terminal-sse-bar md:hidden"
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
      data-testid="terminal-sse-status-bar"
    >
      <span className="terminal-sse-bar__label">即時串流</span>
      <span className={dotClass} title={ariaLabel} aria-hidden="true" />
      <span className="terminal-sse-bar__text">{shortLabel}</span>
    </div>
  );
}

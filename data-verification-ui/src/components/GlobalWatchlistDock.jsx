import { useState } from "react";
import Watchlist from "./Watchlist";
import PriceAlertsPanel from "./PriceAlertsPanel";
import WorkspacePanel from "./WorkspacePanel";

export default function GlobalWatchlistDock() {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-[calc(var(--nav-h)+28px)] right-3 z-40 md:bottom-4">
      {open ? (
        <div
          data-testid="global-watchlist-panel"
          className="mb-2 max-h-[75vh] w-[min(360px,calc(100vw-24px))] overflow-auto rounded-lg border border-white/15 bg-[var(--bg,#05070a)] p-2 shadow-2xl"
        >
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <div data-testid="global-watchlist-title" className="text-[12px] font-semibold text-cyan-200">
              共享監控
            </div>
            <button
              type="button"
              data-testid="global-watchlist-close"
              className="min-h-[44px] rounded border border-white/15 px-3 text-[12px] text-white/70 hover:text-white"
              onClick={() => setOpen(false)}
            >
              關閉
            </button>
          </div>
          <div className="space-y-2">
            <Watchlist
              compact
              dataTestId="global-watchlist"
              title="觀察清單"
              description="跨板塊共享 · localStorage"
            />
            <PriceAlertsPanel compact />
            <WorkspacePanel compact />
          </div>
        </div>
      ) : null}
      <button
        type="button"
        data-testid="global-watchlist-toggle"
        aria-label={open ? "關閉共享監控" : "開啟共享監控"}
        className="min-h-[44px] rounded-full border border-cyan-300/40 bg-cyan-500/15 px-3 py-2 text-[12px] font-semibold text-cyan-100 shadow-xl backdrop-blur hover:bg-cyan-500/25 md:px-4 md:text-[13px]"
        onClick={() => setOpen((value) => !value)}
      >
        監控清單
      </button>
    </div>
  );
}

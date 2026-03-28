/**
 * Glassbox 圖表用示範資料：僅在 API 失敗或 VITE_GLASSBOX_MOCK=1 時顯示，避免誤當實盤。
 */
export const MOCK_EQUITY_CURVE = [
  { date: "2026-01-01", cumulative_pnl: 0, label: "1/1" },
  { date: "2026-01-08", cumulative_pnl: 1.2, label: "1/8" },
  { date: "2026-01-15", cumulative_pnl: -0.4, label: "1/15" },
  { date: "2026-01-22", cumulative_pnl: 2.1, label: "1/22" },
  { date: "2026-02-01", cumulative_pnl: 1.8, label: "2/1" },
  { date: "2026-02-14", cumulative_pnl: 3.6, label: "2/14" },
  { date: "2026-03-01", cumulative_pnl: 2.9, label: "3/1" },
];

export const MOCK_WIN_LOSS_PIE = [
  { name: "命中目標", value: 7, fill: "#10b981" },
  { name: "觸發停損", value: 4, fill: "#ef4444" },
];

export function useMockCharts() {
  return import.meta.env.VITE_GLASSBOX_MOCK === "1";
}

import { createChart } from "lightweight-charts";
import { palette } from "../../design/tokens";

/**
 * 共用 lightweight-charts 主題（對齊 design tokens；與既有圖表視覺等價）。
 * 色彩取自 tokens.palette.regime，避免各圖表各自硬編。
 */
export const CHART_THEME = {
  up: palette.regime.on, // #34d399
  down: palette.regime.off, // #f87171
  accent: palette.accent, // #22d3ee
  text: "#8b9cb3",
  grid: "rgba(120, 160, 200, 0.08)",
  border: "rgba(120, 160, 200, 0.15)",
};

/**
 * 建立一個套用 Q-Silicon 深色主題的 chart。
 * @param {HTMLElement} rootEl
 * @param {{ height?: number }} [opts]
 */
export function createThemedChart(rootEl, { height = 180 } = {}) {
  return createChart(rootEl, {
    width: rootEl.clientWidth,
    height,
    layout: { background: { color: "transparent" }, textColor: CHART_THEME.text },
    grid: {
      vertLines: { color: CHART_THEME.grid },
      horzLines: { color: CHART_THEME.grid },
    },
    rightPriceScale: { borderColor: CHART_THEME.border },
    timeScale: { borderColor: CHART_THEME.border },
    crosshair: { mode: 1 },
  });
}

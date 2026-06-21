import { useEffect, useMemo, useRef } from "react";
import { LineSeries } from "lightweight-charts";
import { createThemedChart, CHART_THEME } from "./themedChart";
import { ChartEmpty } from "./ChartStates";

/**
 * Track Record 已實現權益曲線（themed line）。x=closed_at（日），y=value（累積權益）。
 * 數字由 /api/track-record/summary 的 equity_curve 注入，前端不重算（無數據幻覺紅線）。
 *
 * @param {{ curve?: Array<{closed_at?:string, value?:number|null}>, height?:number }} props
 */
function fin(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function EquityCurveChart({ curve = [], height = 180 }) {
  const rootRef = useRef(null);

  const points = useMemo(() => {
    const byDate = new Map(); // 同日多筆 → 保留最後（當日累積權益）
    for (const row of curve) {
      const time = String(row?.closed_at || "").trim().slice(0, 10);
      const value = fin(row?.value);
      if (!time || value == null) continue;
      byDate.set(time, value);
    }
    return [...byDate.entries()]
      .map(([time, value]) => ({ time, value }))
      .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  }, [curve]);

  useEffect(() => {
    if (!rootRef.current || points.length === 0) return undefined;
    const chart = createThemedChart(rootRef.current, { height });
    const series = chart.addSeries(LineSeries, {
      color: CHART_THEME.accent,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    });
    series.setData(points);
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (rootRef.current) chart.applyOptions({ width: rootRef.current.clientWidth });
    };
    globalThis.addEventListener?.("resize", handleResize);
    return () => {
      globalThis.removeEventListener?.("resize", handleResize);
      chart.remove();
    };
  }, [points, height]);

  if (points.length === 0) return <ChartEmpty label="尚無已實現權益曲線" />;

  return <div data-testid="equity-curve-chart" ref={rootRef} className="w-full" />;
}

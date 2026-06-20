import { useEffect, useMemo, useRef } from "react";
import { BaselineSeries, createChart } from "lightweight-charts";

/**
 * GEX 歷史折線（lightweight-charts BaselineSeries）：以 0 為基準，
 * 正 gamma（抑制波動）顯示為上方綠、負 gamma（放大波動）為下方紅。
 * 數字由後端 history 注入，前端不重算（無數據幻覺紅線）。
 *
 * @param {{ history?: Array<{ trade_date?: string, total_gex?: number|null }> }} props
 */
function finiteNumber(value) {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export default function GexHistoryChart({ history = [] }) {
  const rootRef = useRef(null);

  const points = useMemo(() => {
    const seen = new Set();
    const out = [];
    for (const row of history) {
      const time = String(row?.trade_date || "").trim();
      const value = finiteNumber(row?.total_gex);
      if (!time || value == null || seen.has(time)) continue;
      seen.add(time);
      out.push({ time, value });
    }
    return out.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
  }, [history]);

  useEffect(() => {
    if (!rootRef.current || points.length === 0) return undefined;

    const chart = createChart(rootRef.current, {
      width: rootRef.current.clientWidth,
      height: 180,
      layout: { background: { color: "transparent" }, textColor: "#8b9cb3" },
      grid: {
        vertLines: { color: "rgba(120, 160, 200, 0.08)" },
        horzLines: { color: "rgba(120, 160, 200, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(120, 160, 200, 0.15)" },
      timeScale: { borderColor: "rgba(120, 160, 200, 0.15)" },
      crosshair: { mode: 1 },
    });

    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: 0 },
      topLineColor: "#34d399",
      topFillColor1: "rgba(52, 211, 153, 0.22)",
      topFillColor2: "rgba(52, 211, 153, 0.02)",
      bottomLineColor: "#f87171",
      bottomFillColor1: "rgba(248, 113, 113, 0.02)",
      bottomFillColor2: "rgba(248, 113, 113, 0.22)",
      lineWidth: 2,
      priceLineVisible: false,
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
  }, [points]);

  if (points.length === 0) {
    return (
      <div data-testid="options-gex-chart-empty" className="text-[12px] text-white/50">
        尚無 GEX 歷史可繪製。
      </div>
    );
  }

  return (
    <div data-testid="options-gex-chart">
      <div className="mb-1 text-[12px] font-semibold text-white/70">GEX 歷史（每 1% 移動 USD；0 軸上方=正 gamma）</div>
      <div ref={rootRef} className="w-full" />
    </div>
  );
}

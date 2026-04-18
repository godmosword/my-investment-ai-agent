import { useEffect, useMemo, useRef } from "react";
import { CandlestickSeries, createChart, createSeriesMarkers } from "lightweight-charts";

function markerColor(item) {
  const d = String(item.direction ?? "").toUpperCase();
  if (d.includes("LONG") || d === "BUY") return "#34d399";
  if (d.includes("SHORT") || d === "SELL") return "#f87171";
  return item.type === "signal" ? "#2ee6be" : "#8b9cb3";
}

function toMarker(item) {
  const isShort =
    String(item.direction ?? "")
      .toUpperCase()
      .includes("SHORT") || String(item.direction ?? "").toUpperCase() === "SELL";
  const sid = item.signal_id != null ? String(item.signal_id) : "";
  /** K 線標記旁短字（hover 同源）；過長時截斷以利可讀。 */
  const markerText =
    sid.length > 0
      ? `${item.label ?? "evt"} · ${sid.length > 28 ? `${sid.slice(0, 14)}…${sid.slice(-10)}` : sid}`
      : item.label ?? "event";
  return {
    time: item.time,
    position: isShort ? "belowBar" : "aboveBar",
    color: markerColor(item),
    shape: "circle",
    text: markerText,
  };
}

export default function SymbolCandleChart({ symbol, priceSeries = [], eventMarkers = [] }) {
  const rootRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const markersRef = useRef(null);
  const markers = useMemo(() => eventMarkers.map(toMarker), [eventMarkers]);

  useEffect(() => {
    if (!rootRef.current) return undefined;
    const chart = createChart(rootRef.current, {
      width: rootRef.current.clientWidth,
      height: 220,
      layout: { background: { color: "transparent" }, textColor: "#8b9cb3" },
      grid: {
        vertLines: { color: "rgba(120, 160, 200, 0.12)" },
        horzLines: { color: "rgba(120, 160, 200, 0.12)" },
      },
      rightPriceScale: { borderColor: "rgba(120, 160, 200, 0.18)" },
      timeScale: { borderColor: "rgba(120, 160, 200, 0.18)" },
      crosshair: { mode: 1 },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#f87171",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    if (typeof createSeriesMarkers === "function") {
      markersRef.current = createSeriesMarkers(series, []);
    }

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: Math.floor(entry.contentRect.width),
      });
    });
    resizeObserver.observe(rootRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
  }, []);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.setData(Array.isArray(priceSeries) ? priceSeries : []);
    if (markersRef.current && typeof markersRef.current.setMarkers === "function") {
      markersRef.current.setMarkers(markers);
    } else if (typeof series.setMarkers === "function") {
      series.setMarkers(markers);
    }
    chart.timeScale().fitContent();
  }, [priceSeries, markers]);

  if (!Array.isArray(priceSeries) || priceSeries.length === 0) {
    return (
      <div className="terminal-chart-empty">
        {symbol} 暫無 OHLC 資料（請確認行情來源與 symbol 對映）。
      </div>
    );
  }

  return <div className="terminal-chart-wrap" ref={rootRef} />;
}

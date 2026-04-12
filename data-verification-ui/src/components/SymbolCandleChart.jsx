import { useEffect, useMemo, useRef } from "react";
import { createChart, createSeriesMarkers } from "lightweight-charts";

function toMarker(item) {
  return {
    time: item.time,
    position: "aboveBar",
    color: item.type === "signal" ? "#2ee6be" : "#8b9cb3",
    shape: "circle",
    text: item.label ?? "event",
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
    const series = chart.addCandlestickSeries({
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

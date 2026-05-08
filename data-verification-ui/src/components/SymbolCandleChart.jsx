import { useEffect, useMemo, useRef, useState } from "react";
import { CandlestickSeries, HistogramSeries, LineSeries, createChart, createSeriesMarkers } from "lightweight-charts";

const PERIODS = [
  { label: "1W", days: 7 },
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "全部", days: null },
];

function finiteNumber(value) {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function timeMs(time) {
  if (time && typeof time === "object") {
    const { year, month, day } = time;
    if (Number.isFinite(year) && Number.isFinite(month) && Number.isFinite(day)) {
      return Date.UTC(year, month - 1, day);
    }
  }
  const parsed = Date.parse(String(time ?? ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function timeKey(time) {
  if (time && typeof time === "object") {
    return `${time.year ?? ""}-${time.month ?? ""}-${time.day ?? ""}`;
  }
  return String(time ?? "");
}

function normalizeCandle(row) {
  const time = row?.time;
  const open = finiteNumber(row?.open);
  const high = finiteNumber(row?.high);
  const low = finiteNumber(row?.low);
  const close = finiteNumber(row?.close);
  if (time == null || open == null || high == null || low == null || close == null) return null;

  const volume = finiteNumber(row?.volume);
  return {
    time,
    open,
    high,
    low,
    close,
    ...(volume == null ? {} : { volume }),
  };
}

function calcMA(data, period) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) continue;
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: sum / period });
  }
  return result;
}

function filterByDays(data, days) {
  if (!days || data.length === 0) return data;
  const latestMs = data.reduce((max, d) => {
    const ms = timeMs(d.time);
    return ms == null ? max : Math.max(max, ms);
  }, Number.NEGATIVE_INFINITY);
  if (!Number.isFinite(latestMs)) return data;
  const cutoffMs = latestMs - days * 24 * 60 * 60 * 1000;
  return data.filter((d) => {
    const ms = timeMs(d.time);
    return ms != null && ms >= cutoffMs;
  });
}

function markerColor(item) {
  const d = String(item.direction ?? "").toUpperCase();
  if (d.includes("LONG") || d === "BUY") return "#34d399";
  if (d.includes("SHORT") || d === "SELL") return "#f87171";
  return item.type === "signal" ? "#2ee6be" : "#8b9cb3";
}

function toMarker(item) {
  const isShort =
    String(item.direction ?? "").toUpperCase().includes("SHORT") ||
    String(item.direction ?? "").toUpperCase() === "SELL";
  const sid = item.signal_id != null ? String(item.signal_id) : "";
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
  const [activePeriod, setActivePeriod] = useState("1M");

  const rootRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const volRef = useRef(null);
  const ma20Ref = useRef(null);
  const ma50Ref = useRef(null);
  const markersRef = useRef(null);

  const normalizedPriceSeries = useMemo(
    () => (Array.isArray(priceSeries) ? priceSeries.map(normalizeCandle).filter(Boolean) : []),
    [priceSeries],
  );
  const hasPriceData = normalizedPriceSeries.length > 0;

  const filteredData = useMemo(() => {
    const period = PERIODS.find((p) => p.label === activePeriod);
    return filterByDays(normalizedPriceSeries, period?.days ?? null);
  }, [normalizedPriceSeries, activePeriod]);

  const visibleTimes = useMemo(
    () => new Set(filteredData.map((d) => timeKey(d.time))),
    [filteredData],
  );

  const markers = useMemo(
    () =>
      (Array.isArray(eventMarkers) ? eventMarkers : [])
        .map(toMarker)
        .filter((m) => visibleTimes.has(timeKey(m.time))),
    [eventMarkers, visibleTimes],
  );

  const ma20FullData = useMemo(() => calcMA(normalizedPriceSeries, 20), [normalizedPriceSeries]);
  const ma50FullData = useMemo(() => calcMA(normalizedPriceSeries, 50), [normalizedPriceSeries]);
  const ma20Data = useMemo(
    () => ma20FullData.filter((d) => visibleTimes.has(timeKey(d.time))),
    [ma20FullData, visibleTimes],
  );
  const ma50Data = useMemo(
    () => ma50FullData.filter((d) => visibleTimes.has(timeKey(d.time))),
    [ma50FullData, visibleTimes],
  );

  const volData = useMemo(
    () =>
      filteredData
        .filter((d) => d.volume != null && Number.isFinite(d.volume))
        .map((d) => ({
          time: d.time,
          value: d.volume,
          color: d.close >= d.open ? "rgba(52,211,153,0.45)" : "rgba(248,113,113,0.45)",
        })),
    [filteredData],
  );
  const hasVolume = volData.length > 0;

  /* Create / recreate chart when OHLC becomes available or volume histogram toggles */
  useEffect(() => {
    if (!rootRef.current || !hasPriceData) return undefined;

    const chart = createChart(rootRef.current, {
      width: rootRef.current.clientWidth,
      height: hasVolume ? 260 : 220,
      layout: { background: { color: "transparent" }, textColor: "#8b9cb3" },
      grid: {
        vertLines: { color: "rgba(120, 160, 200, 0.1)" },
        horzLines: { color: "rgba(120, 160, 200, 0.1)" },
      },
      rightPriceScale: { borderColor: "rgba(120, 160, 200, 0.15)" },
      timeScale: {
        borderColor: "rgba(120, 160, 200, 0.15)",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: { mode: 1 },
    });

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#f87171",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });

    const ma20 = chart.addSeries(LineSeries, {
      color: "#2ee6be",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    const ma50 = chart.addSeries(LineSeries, {
      color: "#8b5cf6",
      lineWidth: 1.5,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    let vol = null;
    if (hasVolume) {
      vol = chart.addSeries(HistogramSeries, {
        color: "rgba(120,160,200,0.3)",
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
      });
      chart.priceScale("vol").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
        drawTicks: false,
        borderVisible: false,
      });
    }

    chartRef.current = chart;
    candleRef.current = candle;
    ma20Ref.current = ma20;
    ma50Ref.current = ma50;
    volRef.current = vol;

    if (typeof createSeriesMarkers === "function") {
      markersRef.current = createSeriesMarkers(candle, []);
    }

    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry || !chartRef.current) return;
      chartRef.current.applyOptions({ width: Math.floor(entry.contentRect.width) });
    });
    ro.observe(rootRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      ma20Ref.current = null;
      ma50Ref.current = null;
      volRef.current = null;
      markersRef.current = null;
    };
  }, [hasPriceData, hasVolume]);

  /* Update series data */
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !hasPriceData) return;

    candle.setData(filteredData);
    if (ma20Ref.current) ma20Ref.current.setData(ma20Data);
    if (ma50Ref.current) ma50Ref.current.setData(ma50Data);
    if (volRef.current && hasVolume) volRef.current.setData(volData);

    if (markersRef.current?.setMarkers) {
      markersRef.current.setMarkers(markers);
    } else if (typeof candle.setMarkers === "function") {
      candle.setMarkers(markers);
    }

    chart.timeScale().fitContent();
  }, [filteredData, ma20Data, ma50Data, volData, markers, hasVolume, hasPriceData]);

  if (!hasPriceData) {
    return (
      <div className="terminal-chart-empty" role="status" data-testid={`terminal-chart-empty-${symbol}`}>
        {symbol} 暫無 OHLC 資料（請確認行情來源與 symbol 對映）。
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 8 }}>
      {/* Period tabs */}
      <div
        style={{
          display: "flex",
          gap: 4,
          marginBottom: 6,
          alignItems: "center",
        }}
      >
        {PERIODS.map(({ label }) => (
          <button
            key={label}
            type="button"
            onClick={() => setActivePeriod(label)}
            aria-pressed={activePeriod === label}
            style={{
              padding: "3px 9px",
              fontSize: 11,
              fontWeight: 600,
              borderRadius: 5,
              border: "1px solid",
              cursor: "pointer",
              transition: "all 0.15s",
              borderColor:
                activePeriod === label ? "var(--accent)" : "var(--border)",
              background:
                activePeriod === label ? "var(--accent-soft)" : "transparent",
              color: activePeriod === label ? "var(--accent)" : "var(--muted)",
            }}
          >
            {label}
          </button>
        ))}
        {/* MA legend */}
        <div
          style={{
            marginLeft: "auto",
            display: "flex",
            gap: 10,
            fontSize: 10,
            color: "var(--muted)",
            alignItems: "center",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              style={{ display: "inline-block", width: 14, height: 2, background: "#2ee6be", borderRadius: 1 }}
            />
            MA20
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <span
              style={{ display: "inline-block", width: 14, height: 2, background: "#8b5cf6", borderRadius: 1 }}
            />
            MA50
          </span>
        </div>
      </div>

      <div className="terminal-chart-wrap" ref={rootRef} />
    </div>
  );
}

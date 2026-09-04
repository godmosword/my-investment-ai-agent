import { finiteNumber } from "../utils/finiteNumber";

export default function MetricCard({ label, value, delta, unit = "", format }) {
  const n = finiteNumber(value);
  const display = n == null ? "UNKNOWN" : (format ? format(n) : `${n}${unit}`);

  let deltaClass = "delta-flat";
  let deltaStr = null;
  if (delta != null) {
    const sign = delta > 0 ? "+" : "";
    deltaStr = `${sign}${delta.toFixed(2)}${unit}`;
    deltaClass = delta > 0 ? "delta-up" : delta < 0 ? "delta-down" : "delta-flat";
  }

  return (
    <div className="metric-card" data-testid="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" data-testid="metric-card-value">{display}</div>
      {deltaStr && <div className={`metric-delta ${deltaClass}`}>{deltaStr}</div>}
    </div>
  );
}

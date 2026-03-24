export default function MetricCard({ label, value, delta, unit = "", format }) {
  const display = value == null ? "—" : (format ? format(value) : `${value}${unit}`);

  let deltaClass = "delta-flat";
  let deltaStr = null;
  if (delta != null) {
    const sign = delta > 0 ? "+" : "";
    deltaStr = `${sign}${delta.toFixed(2)}${unit}`;
    deltaClass = delta > 0 ? "delta-up" : delta < 0 ? "delta-down" : "delta-flat";
  }

  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{display}</div>
      {deltaStr && <div className={`metric-delta ${deltaClass}`}>{deltaStr}</div>}
    </div>
  );
}

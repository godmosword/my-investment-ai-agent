function fmt(v) {
  if (v == null) return "—";
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function Stars({ n }) {
  if (n == null) return null;
  return <span className="stars">{"★".repeat(n)}{"☆".repeat(Math.max(0, 4 - n))}</span>;
}

function StatusBadge({ status }) {
  if (!status) return null;
  const key = status.toLowerCase();
  return <span className={`status-badge status-${key}`}>{status.replace("_", " ")}</span>;
}

export default function TradeCard({ trade }) {
  const isLong = trade.direction?.toUpperCase() === "LONG";
  const pnlColor = trade.pnl_pct > 0 ? "delta-up" : trade.pnl_pct < 0 ? "delta-down" : "delta-flat";

  return (
    <div className="trade-card">
      <div className="trade-header">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="trade-asset">{trade.asset}</span>
          <span className={`trade-direction direction-${isLong ? "long" : "short"}`}>
            {trade.direction}
          </span>
          {trade.category && (
            <span style={{ fontSize: 10, color: "var(--muted)" }}>{trade.category}</span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Stars n={trade.confidence} />
          <StatusBadge status={trade.status} />
        </div>
      </div>

      <div className="trade-prices">
        <div className="price-item">
          <span className="price-label">進場</span>
          <span className="price-value">{fmt(trade.entry_price)}</span>
        </div>
        <div className="price-item">
          <span className="price-label">目標</span>
          <span className="price-value" style={{ color: "var(--green)" }}>
            {fmt(trade.target_price)}
          </span>
        </div>
        <div className="price-item">
          <span className="price-label">停損</span>
          <span className="price-value" style={{ color: "var(--red)" }}>
            {fmt(trade.stop_price)}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, marginBottom: 4 }}>
        {trade.rr_ratio != null && (
          <span style={{ color: "var(--muted)" }}>
            R:R <strong style={{ color: "var(--text)" }}>{trade.rr_ratio}</strong>
          </span>
        )}
        {trade.timeframe && (
          <span style={{ color: "var(--muted)" }}>
            週期 <strong style={{ color: "var(--text)" }}>{trade.timeframe}</strong>
          </span>
        )}
        {trade.position_pct != null && (
          <span style={{ color: "var(--muted)" }}>
            倉位 <strong style={{ color: "var(--text)" }}>{trade.position_pct}%</strong>
          </span>
        )}
        {trade.pnl_pct != null && (
          <span>
            P&L <strong className={pnlColor}>{trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct}%</strong>
          </span>
        )}
      </div>

      {trade.narrative && (
        <div className="trade-narrative">{trade.narrative}</div>
      )}
    </div>
  );
}

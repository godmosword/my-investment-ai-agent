import { useState } from "react";
import { formatAsOfZh } from "../../utils/formatAsOfZh";

/**
 * `data_provenance`（snapshot API）摺疊面板 — 舊稱 Terminal 內嵌區塊，抽出共用。
 */
export default function ProvenancePopover({ provenance, className = "" }) {
  const [open, setOpen] = useState(false);
  if (!provenance || typeof provenance !== "object") return null;
  const ohlc = provenance.ohlc || {};
  const dm = provenance.daily_metrics || {};
  const rec = provenance.recommendations || {};
  return (
    <div className={`terminal-provenance ${className}`}>
      <button type="button" className="terminal-provenance-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▼" : "▶"} 資料溯源（來源 / as-of）
      </button>
      {open ? (
        <div className="terminal-provenance-body">
          <div className="terminal-provenance-row">
            <strong>OHLC</strong>
            <span>
              {ohlc.source ?? "—"} · bar {formatAsOfZh(ohlc.as_of)}
              {ohlc.underlying_symbol ? (
                <>
                  {" "}
                  · yf: <code>{ohlc.underlying_symbol}</code>
                </>
              ) : null}
              {ohlc.interval ? (
                <>
                  {" "}
                  · <code>{ohlc.interval}</code>
                </>
              ) : null}
            </span>
          </div>
          <div className="terminal-provenance-row">
            <strong>日報指標</strong>
            <span>
              {dm.source ?? "—"} · {formatAsOfZh(dm.as_of)}
              {dm.table_id ? (
                <>
                  {" "}
                  · <code className="terminal-provenance-code">{dm.table_id}</code>
                </>
              ) : null}
            </span>
          </div>
          <div className="terminal-provenance-row">
            <strong>建議列</strong>
            <span>
              {rec.source ?? "—"} · {formatAsOfZh(rec.as_of)}
              {rec.query_window_days != null ? <> · 視窗 {rec.query_window_days} 日</> : null}
              {rec.table_id ? (
                <>
                  {" "}
                  · <code className="terminal-provenance-code">{rec.table_id}</code>
                </>
              ) : null}
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}

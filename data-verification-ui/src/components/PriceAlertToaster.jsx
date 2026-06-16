import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { PRICE_ALERT_SSE_EVENT } from "../hooks/useWarRoomSse";

const TOAST_TTL_MS = 8000;
const MAX_VISIBLE = 4;

/**
 * @typedef {Object} PriceAlertDetail
 * @property {string} alert_id
 * @property {string} symbol
 * @property {string} direction
 * @property {number} target_price
 * @property {number} last_price
 * @property {string} [note]
 * @property {string} [ts]
 */

/** Listens to PRICE_ALERT_SSE_EVENT and shows transient toasts. Mount inside WarRoomSseProvider. */
export default function PriceAlertToaster() {
  /** @type {[Array<PriceAlertDetail & {key: string}>, Function]} */
  const [toasts, setToasts] = useState([]);
  const navigate = useNavigate();

  const dismiss = useCallback((key) => {
    setToasts((prev) => prev.filter((t) => t.key !== key));
  }, []);

  const openDeepDive = useCallback(
    (symbol, key) => {
      const s = String(symbol ?? "").trim().toUpperCase();
      if (!s) {
        dismiss(key);
        return;
      }
      dismiss(key);
      navigate(`/insights?symbol=${encodeURIComponent(s)}&from=alert`);
    },
    [dismiss, navigate],
  );

  useEffect(() => {
    const onAlert = (ev) => {
      const detail = ev?.detail;
      if (!detail || !detail.symbol) return;
      const key = `${detail.alert_id ?? detail.symbol}-${detail.ts ?? Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => {
        const next = [...prev, { ...detail, key }];
        return next.length > MAX_VISIBLE ? next.slice(next.length - MAX_VISIBLE) : next;
      });
      globalThis.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.key !== key));
      }, TOAST_TTL_MS);
    };
    globalThis.addEventListener(PRICE_ALERT_SSE_EVENT, onAlert);
    return () => globalThis.removeEventListener(PRICE_ALERT_SSE_EVENT, onAlert);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      data-testid="price-alert-toaster"
      style={{
        position: "fixed",
        right: 16,
        bottom: 76, // above BottomNav
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        maxWidth: 340,
      }}
    >
      {toasts.map((t) => {
        const dir = String(t.direction ?? "").toLowerCase();
        const color = dir === "above" ? "var(--green, #22c55e)" : "var(--red, #ef4444)";
        const arrow = dir === "above" ? "▲" : "▼";
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => openDeepDive(t.symbol, t.key)}
            className="card"
            style={{
              cursor: "pointer",
              textAlign: "left",
              borderLeft: `3px solid ${color}`,
              padding: "10px 12px",
              background: "var(--bg-elevated, rgba(20,22,28,0.96))",
              backdropFilter: "blur(8px)",
              boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            }}
            aria-label={`Open ${t.symbol} deep dive from price alert`}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 700 }}>
              <span style={{ color }}>{arrow}</span>
              <span style={{ color: "var(--text)" }}>{t.symbol}</span>
              <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--muted)" }}>price alert</span>
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
              {dir.toUpperCase()} {Number(t.target_price).toFixed(2)} — last {Number(t.last_price).toFixed(2)}
            </div>
            {t.note ? (
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4, fontStyle: "italic" }}>
                {t.note}
              </div>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

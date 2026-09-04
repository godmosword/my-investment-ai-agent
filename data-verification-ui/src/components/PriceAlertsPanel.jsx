import { useState } from "react";
import {
  useCheckPriceAlerts,
  useCreatePriceAlert,
  useDeletePriceAlert,
  usePriceAlerts,
} from "../hooks/useApi";
import { finiteNumber } from "../utils/finiteNumber";

function money(value) {
  const n = finiteNumber(value);
  if (n == null) return "UNKNOWN";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(n);
}

function countLabel(value) {
  const n = finiteNumber(value);
  return n == null ? "UNKNOWN" : n;
}

function directionLabel(direction) {
  if (direction === "above") return "高於";
  if (direction === "below") return "低於";
  return direction;
}

export default function PriceAlertsPanel({ compact = false } = {}) {
  const alertsQuery = usePriceAlerts();
  const createAlert = useCreatePriceAlert();
  const deleteAlert = useDeletePriceAlert();
  const checkAlerts = useCheckPriceAlerts();
  const [form, setForm] = useState({ symbol: "", direction: "above", target_price: "", note: "" });
  const [message, setMessage] = useState("");

  const alerts = alertsQuery.data?.alerts ?? [];

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: key === "symbol" ? value.toUpperCase() : value }));
  };

  const submit = (event) => {
    event.preventDefault();
    const symbol = form.symbol.trim().toUpperCase();
    const target = Number(form.target_price);
    if (!symbol || !Number.isFinite(target) || target <= 0) {
      setMessage("請輸入 symbol 與有效價格");
      return;
    }
    createAlert.mutate(
      {
        symbol,
        direction: form.direction,
        target_price: target,
        note: form.note,
      },
      {
        onSuccess: () => {
          setForm({ symbol: "", direction: "above", target_price: "", note: "" });
          setMessage("警示已建立");
        },
        onError: (err) => setMessage(`建立失敗：${err.message}`),
      },
    );
  };

  const checkNow = () => {
    checkAlerts.mutate(
      { sendPush: false },
      {
        onSuccess: (data) =>
          setMessage(`已檢查 ${countLabel(data?.checked)} 筆，觸發 ${countLabel(data?.triggered)} 筆`),
        onError: (err) => setMessage(`檢查失敗：${err.message}`),
      },
    );
  };

  return (
    <section className="card p-3" data-testid="price-alerts-panel">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="card-title">價格警示</div>
          <div className="text-[12px] text-[var(--muted)]">Web Push 觸發佇列 · 僅模擬</div>
        </div>
        <button
          type="button"
          data-testid="price-alerts-check"
          className="min-h-[44px] rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/80 hover:bg-white/5"
          onClick={checkNow}
          disabled={checkAlerts.isPending}
        >
          {checkAlerts.isPending ? "檢查中…" : "檢查"}
        </button>
      </div>

      <form className={`grid gap-2 ${compact ? "grid-cols-1" : "grid-cols-1 md:grid-cols-[1fr_120px_140px_auto]"}`} onSubmit={submit}>
        <input
          value={form.symbol}
          onChange={(e) => setField("symbol", e.target.value)}
          className="min-h-[44px] rounded border border-white/15 bg-black/25 px-2 text-[13px] text-white"
          placeholder="NVDA"
          maxLength={16}
        />
        <select
          data-testid="price-alerts-direction"
          value={form.direction}
          onChange={(e) => setField("direction", e.target.value)}
          className="min-h-[44px] rounded border border-white/15 bg-black/25 px-2 text-[13px] text-white"
        >
          <option value="above">高於</option>
          <option value="below">低於</option>
        </select>
        <input
          value={form.target_price}
          onChange={(e) => setField("target_price", e.target.value)}
          className="min-h-[44px] rounded border border-white/15 bg-black/25 px-2 text-[13px] text-white"
          placeholder="900"
          inputMode="decimal"
        />
        <button
          type="submit"
          data-testid="price-alerts-add"
          className="min-h-[44px] rounded bg-cyan-700 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-cyan-600"
          disabled={createAlert.isPending}
        >
          新增
        </button>
      </form>

      {message ? (
        <div className="mt-2 rounded border border-white/10 bg-white/[0.03] px-2 py-1 text-[12px] text-white/70" data-testid="price-alerts-status" role="status">
          {message}
        </div>
      ) : null}

      <div className="mt-3 space-y-2">
        {alertsQuery.isLoading ? (
          <div className="text-[13px] text-[var(--muted)]" data-testid="price-alerts-loading">
            載入警示…
          </div>
        ) : null}
        {!alertsQuery.isLoading && alerts.length === 0 ? (
          <div className="text-[13px] text-[var(--muted)]" data-testid="price-alerts-empty">
            尚無價格警示。
          </div>
        ) : null}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            data-testid="price-alerts-row"
            className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/10 bg-white/[0.03] px-2 py-2 text-[12px]"
          >
            <div>
              <span className="font-mono text-white">{alert.symbol}</span>
              <span className="ml-2 text-white/65" data-testid="price-alerts-row-direction">
                {directionLabel(alert.direction)}{" "}
                <span data-testid="price-alerts-row-price">{money(alert.target_price)}</span>
              </span>
              {alert.triggered_at ? (
                <span className="ml-2 text-emerald-300" data-testid="price-alerts-triggered">
                  已觸發
                </span>
              ) : null}
              {alert.error ? <span className="ml-2 text-red-300">{alert.error}</span> : null}
            </div>
            <button
              type="button"
              data-testid="price-alerts-remove"
              className="min-h-[44px] rounded border border-white/15 px-2 text-white/60 hover:text-red-300"
              onClick={() => deleteAlert.mutate(alert.id)}
            >
              移除
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

import { useState } from "react";
import {
  useCheckPriceAlerts,
  useCreatePriceAlert,
  useDeletePriceAlert,
  usePriceAlerts,
} from "../hooks/useApi";

function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(n);
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
          setMessage("Alert 已建立");
        },
        onError: (err) => setMessage(`建立失敗：${err.message}`),
      },
    );
  };

  const checkNow = () => {
    checkAlerts.mutate(
      { sendPush: false },
      {
        onSuccess: (data) => setMessage(`已檢查 ${data.checked ?? 0} 筆，觸發 ${data.triggered ?? 0} 筆`),
        onError: (err) => setMessage(`檢查失敗：${err.message}`),
      },
    );
  };

  return (
    <section className="card p-3" data-testid="price-alerts-panel">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="card-title">Price Alerts</div>
          <div className="text-[12px] text-[var(--muted)]">Web Push trigger queue · paper-only</div>
        </div>
        <button
          type="button"
          className="min-h-[40px] rounded border border-white/15 px-3 py-1.5 text-[12px] text-white/80 hover:bg-white/5"
          onClick={checkNow}
          disabled={checkAlerts.isPending}
        >
          {checkAlerts.isPending ? "Checking…" : "Check"}
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
          value={form.direction}
          onChange={(e) => setField("direction", e.target.value)}
          className="min-h-[44px] rounded border border-white/15 bg-black/25 px-2 text-[13px] text-white"
        >
          <option value="above">above</option>
          <option value="below">below</option>
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
          className="min-h-[44px] rounded bg-cyan-700 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-cyan-600"
          disabled={createAlert.isPending}
        >
          Add
        </button>
      </form>

      {message ? (
        <div className="mt-2 rounded border border-white/10 bg-white/[0.03] px-2 py-1 text-[12px] text-white/70" role="status">
          {message}
        </div>
      ) : null}

      <div className="mt-3 space-y-2">
        {alertsQuery.isLoading ? <div className="text-[13px] text-[var(--muted)]">載入 alerts…</div> : null}
        {!alertsQuery.isLoading && alerts.length === 0 ? (
          <div className="text-[13px] text-[var(--muted)]">尚無 price alert。</div>
        ) : null}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded border border-white/10 bg-white/[0.03] px-2 py-2 text-[12px]"
          >
            <div>
              <span className="font-mono text-white">{alert.symbol}</span>
              <span className="ml-2 text-white/65">
                {alert.direction} {money(alert.target_price)}
              </span>
              {alert.triggered_at ? <span className="ml-2 text-emerald-300">triggered</span> : null}
              {alert.error ? <span className="ml-2 text-red-300">{alert.error}</span> : null}
            </div>
            <button
              type="button"
              className="min-h-[32px] rounded border border-white/15 px-2 text-white/60 hover:text-red-300"
              onClick={() => deleteAlert.mutate(alert.id)}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

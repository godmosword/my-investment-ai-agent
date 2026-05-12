import { useEffect, useRef, useState } from "react";
import { useExecutionIntentAllowedStatuses, usePatchExecutionIntent } from "../hooks/useApi";

/**
 * Modal for updating an execution intent's status (Q30).
 * Calls PATCH /api/execution-intents/{signal_id}.
 *
 * @param {{ row: object | null, onClose: () => void }} props
 */
export default function IntentUpdateModal({ row, onClose }) {
  const { data: statusData } = useExecutionIntentAllowedStatuses();
  const patchMutation = usePatchExecutionIntent();

  const clientPatchable = statusData?.client_patchable ?? [];
  const [status, setStatus] = useState(row?.status ?? "");
  const [note, setNote] = useState("");
  const [entryPrice, setEntryPrice] = useState("");
  const [targetPrice, setTargetPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");

  const dialogRef = useRef(null);

  useEffect(() => {
    if (row) {
      setStatus(row.status ?? "");
      setNote("");
      setEntryPrice(row.reference_entry_price != null ? String(row.reference_entry_price) : "");
      setTargetPrice(row.reference_target_price != null ? String(row.reference_target_price) : "");
      setStopPrice(row.reference_stop_price != null ? String(row.reference_stop_price) : "");
      patchMutation.reset();
    }
  }, [row]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!row) return null;

  const toFloatOrNull = (s) => {
    const n = parseFloat(s);
    return Number.isFinite(n) ? n : null;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    patchMutation.mutate(
      {
        signalId: row.signal_id,
        status,
        note,
        reference_entry_price: toFloatOrNull(entryPrice),
        reference_target_price: toFloatOrNull(targetPrice),
        reference_stop_price: toFloatOrNull(stopPrice),
      },
      { onSuccess: onClose },
    );
  };

  return (
    <div
      data-testid="intent-update-modal-overlay"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        ref={dialogRef}
        data-testid="intent-update-modal"
        role="dialog"
        aria-modal="true"
        aria-label="更新意圖狀態"
        className="w-full max-w-md rounded-lg border border-[color:var(--border)] bg-[var(--panel,#1a1a1a)] p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-white">更新意圖狀態</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted)] hover:text-white"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>

        <div className="mb-4 rounded bg-black/30 px-3 py-2 text-[12px] text-[var(--muted)]">
          <span className="font-mono text-white/80">{row.signal_id}</span>
          {" · "}
          {row.asset} {row.direction}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-[13px] text-white/80">
            狀態
            <select
              data-testid="intent-status-select"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              required
              className="rounded border border-white/15 bg-black/50 px-2 py-1.5 text-[13px] text-white"
            >
              {clientPatchable.length === 0 ? (
                <option value={row.status}>{row.status}</option>
              ) : (
                clientPatchable.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))
              )}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-[13px] text-white/80">
            備註（選填）
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              maxLength={2000}
              placeholder="操作原因…"
              className="rounded border border-white/15 bg-black/50 px-2 py-1 text-[13px] text-white placeholder:text-white/30 resize-none"
            />
          </label>

          <div className="grid grid-cols-3 gap-2">
            {[
              ["進場價", entryPrice, setEntryPrice, "intent-entry-price"],
              ["目標價", targetPrice, setTargetPrice, "intent-target-price"],
              ["停損價", stopPrice, setStopPrice, "intent-stop-price"],
            ].map(([label, val, setter, tid]) => (
              <label key={label} className="flex flex-col gap-1 text-[12px] text-white/70">
                {label}
                <input
                  data-testid={tid}
                  type="number"
                  step="any"
                  value={val}
                  onChange={(e) => setter(e.target.value)}
                  placeholder="—"
                  className="rounded border border-white/15 bg-black/50 px-2 py-1 text-[12px] text-white placeholder:text-white/30"
                />
              </label>
            ))}
          </div>

          {patchMutation.isError ? (
            <p className="text-[12px] text-red-400" role="alert">
              錯誤：{patchMutation.error?.message}
            </p>
          ) : null}

          <div className="mt-1 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-white/20 px-3 py-1.5 text-[13px] text-white/70 hover:bg-white/5"
            >
              取消
            </button>
            <button
              type="submit"
              data-testid="intent-update-submit"
              disabled={patchMutation.isPending}
              className="rounded bg-emerald-700/80 px-3 py-1.5 text-[13px] font-semibold text-white hover:bg-emerald-600 disabled:opacity-40"
            >
              {patchMutation.isPending ? "更新中…" : "確認更新"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

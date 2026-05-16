import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import PortfolioRiskPanel from "../../../components/PortfolioRiskPanel";
import {
  useAddHolding,
  useDeleteHolding,
  useImportCsv,
  usePortfolioHoldings,
  usePortfolioPnl,
} from "../../../hooks/useApi";
import { PORTAL_PHASE4_GATE0 } from "../../../constants/portalPhase4";

function money(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "$0";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(n);
}

function number(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function signedMoney(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "$0";
  const sign = n > 0 ? "+" : "";
  return `${sign}${money(n, digits)}`;
}

function pct(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(digits)}%`;
}

function toneClass(value) {
  const n = Number(value);
  if (n > 0) return "text-green-400";
  if (n < 0) return "text-red-400";
  return "text-gray-400";
}

function csvEscape(value) {
  const s = String(value ?? "");
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function toCsv(rows) {
  const header = ["symbol", "shares", "cost_basis", "opened_at", "notes"];
  const lines = rows.map((row) =>
    header
      .map((key) => csvEscape(row[key]))
      .join(","),
  );
  return `${header.join(",")}\n${lines.join("\n")}\n`;
}

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function AddHoldingModal({ onClose, onSubmit, pending }) {
  const [form, setForm] = useState({
    symbol: "",
    shares: "",
    cost_basis: "",
    opened_at: todayDate(),
    notes: "",
  });
  const [error, setError] = useState("");

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: key === "symbol" ? value.toUpperCase() : value }));
  };

  const submit = (e) => {
    e.preventDefault();
    const symbol = form.symbol.trim().toUpperCase();
    const shares = Number(form.shares);
    const costBasis = Number(form.cost_basis);
    if (!symbol) {
      setError("請輸入 Symbol");
      return;
    }
    if (!Number.isFinite(shares) || shares <= 0) {
      setError("Shares 必須大於 0");
      return;
    }
    if (!Number.isFinite(costBasis) || costBasis < 0) {
      setError("Avg Cost/share 不可為負");
      return;
    }
    setError("");
    onSubmit({
      symbol,
      shares,
      cost_basis: costBasis,
      opened_at: form.opened_at,
      notes: form.notes,
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <form
        data-testid="portfolio-add-modal"
        className="w-full max-w-md rounded-lg border border-[color:var(--border)] bg-[var(--panel,#1a1a1a)] p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-white">新增倉位</h2>
          <button type="button" className="text-[var(--muted)] hover:text-white" onClick={onClose}>
            x
          </button>
        </div>
        <label className="mb-3 block text-[12px] text-[var(--muted)]">
          Symbol
          <input
            value={form.symbol}
            onChange={(e) => setField("symbol", e.target.value)}
            className="mt-1 w-full rounded border border-white/15 bg-black/25 px-2 py-2 font-mono text-[13px] text-white"
            placeholder="NVDA"
          />
        </label>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-[12px] text-[var(--muted)]">
            Shares
            <input
              type="number"
              step="any"
              value={form.shares}
              onChange={(e) => setField("shares", e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-black/25 px-2 py-2 text-[13px] text-white"
            />
          </label>
          <label className="block text-[12px] text-[var(--muted)]">
            Avg Cost/share
            <input
              type="number"
              step="any"
              value={form.cost_basis}
              onChange={(e) => setField("cost_basis", e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-black/25 px-2 py-2 text-[13px] text-white"
            />
          </label>
        </div>
        <label className="mt-3 block text-[12px] text-[var(--muted)]">
          Date Opened
          <input
            type="date"
            value={form.opened_at}
            onChange={(e) => setField("opened_at", e.target.value)}
            className="mt-1 w-full rounded border border-white/15 bg-black/25 px-2 py-2 text-[13px] text-white"
          />
        </label>
        <label className="mt-3 block text-[12px] text-[var(--muted)]">
          Notes
          <textarea
            value={form.notes}
            onChange={(e) => setField("notes", e.target.value)}
            className="mt-1 min-h-[72px] w-full rounded border border-white/15 bg-black/25 px-2 py-2 text-[13px] text-white"
            placeholder="optional"
          />
        </label>
        {error ? <div className="mt-3 text-[12px] text-red-300">{error}</div> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" className="rounded border border-white/15 px-3 py-2 text-[13px] text-white/70" onClick={onClose}>
            取消
          </button>
          <button
            type="submit"
            disabled={pending}
            className="rounded bg-emerald-700 px-3 py-2 text-[13px] font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
          >
            {pending ? "新增中…" : "新增"}
          </button>
        </div>
      </form>
    </div>
  );
}

function KpiCard({ label, value, sub, valueClass = "text-white", testId }) {
  return (
    <div className="card p-3" data-testid={testId}>
      <div className="metric-label">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${valueClass}`}>{value}</div>
      {sub ? <div className="mt-1 text-[12px] text-[var(--muted)]">{sub}</div> : null}
    </div>
  );
}

function HoldingCards({ rows, onDelete }) {
  return (
    <div className="space-y-2 md:hidden">
      {rows.map((row) => (
        <div key={row.id} data-testid={`portfolio-holding-card-${row.symbol}`} className="card p-3">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div>
              <div className="font-mono text-[15px] font-semibold text-white">{row.symbol}</div>
              <div className="text-[12px] text-[var(--muted)]">{row.opened_at}</div>
            </div>
            <button
              type="button"
              className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/60 hover:text-red-300"
              onClick={() => onDelete(row.id)}
            >
              刪除
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <div><span className="text-[var(--muted)]">Shares</span><br />{number(row.shares)}</div>
            <div><span className="text-[var(--muted)]">Avg Cost</span><br />{money(row.cost_basis, 2)}</div>
            <div><span className="text-[var(--muted)]">Last</span><br />{row.error ? "N/A" : money(row.last_price, 2)}</div>
            <div><span className="text-[var(--muted)]">Weight</span><br />{row.error ? "—" : pct(row.weight)}</div>
            <div className={toneClass(row.day_change_pct)}><span className="text-[var(--muted)]">Day Δ</span><br />{row.error ? "—" : pct(row.day_change_pct)}</div>
            <div className={toneClass(row.pnl)}><span className="text-[var(--muted)]">P&L</span><br />{row.error ? "quote unavailable" : `${signedMoney(row.pnl)} (${pct(row.pnl_pct)})`}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function PortfolioHome() {
  const holdingsQuery = usePortfolioHoldings();
  const pnlQuery = usePortfolioPnl();
  const addHolding = useAddHolding();
  const deleteHolding = useDeleteHolding();
  const importCsv = useImportCsv();
  const fileInputRef = useRef(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState("");

  const rawHoldings = holdingsQuery.data?.holdings ?? [];
  const rows = pnlQuery.data?.holdings ?? rawHoldings;
  const totalValue = pnlQuery.data?.total_value ?? 0;
  const totalPnl = pnlQuery.data?.total_pnl ?? 0;
  const totalDayPnl = pnlQuery.data?.total_day_pnl ?? 0;
  const totalCost = totalValue - totalPnl;
  const totalPnlPct = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const dayPct = totalValue > 0 ? (totalDayPnl / totalValue) * 100 : 0;
  const isLoading = holdingsQuery.isLoading || pnlQuery.isLoading;
  const error = holdingsQuery.error || pnlQuery.error;

  const holdingsForExport = useMemo(() => rawHoldings, [rawHoldings]);

  const submitHolding = (payload) => {
    addHolding.mutate(payload, {
      onSuccess: () => {
        setModalOpen(false);
        setToast("已新增倉位");
      },
      onError: (err) => setToast(`新增失敗：${err.message}`),
    });
  };

  const deleteRow = (id) => {
    if (!id) return;
    deleteHolding.mutate(id, {
      onSuccess: () => setToast("已刪除倉位"),
      onError: (err) => setToast(`刪除失敗：${err.message}`),
    });
  };

  const importFile = async (file) => {
    if (!file) return;
    try {
      const text = await file.text();
      importCsv.mutate(text, {
        onSuccess: (data) => setToast(`已匯入 ${data.imported ?? 0} 筆倉位`),
        onError: (err) => setToast(`匯入失敗：${err.message}`),
      });
    } catch (err) {
      setToast(`讀取 CSV 失敗：${err instanceof Error ? err.message : err}`);
    }
  };

  const handleCsvDrop = (e) => {
    e.preventDefault();
    importFile(e.dataTransfer.files?.[0]);
  };

  const exportCsv = () => {
    const csv = toCsv(holdingsForExport);
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "portfolio_holdings.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      data-testid="portfolio-home"
      className="px-3 py-4 pb-24"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleCsvDrop}
    >
      {modalOpen ? (
        <AddHoldingModal
          pending={addHolding.isPending}
          onClose={() => setModalOpen(false)}
          onSubmit={submitHolding}
        />
      ) : null}

      <div className="page-header">
        <div className="page-title">Portfolio Tracker</div>
        <div className="page-subtitle">手動倉位 · CSV 匯入 · quote MTM（JSONL v1）</div>
      </div>

      <div
        data-testid="portfolio-workbench-intro"
        className="card mb-3 border border-emerald-500/20 bg-emerald-950/15 p-3 text-[12px] leading-relaxed text-white/80"
      >
        <span className="font-semibold text-emerald-100/95">工作台 · 持倉主問</span>
        ：先確認總市值與今日損益，再用
        <Link to="/insights" className="mx-1 text-emerald-200 underline-offset-2 hover:text-emerald-100 hover:underline">
          觀點
        </Link>
        對照訊號與標的深挖；需要宏觀背景可到「數據儀表板」。路徑目標 ≤ {PORTAL_PHASE4_GATE0.maxWorkbenchPathClicks}{" "}
        次點擊。
      </div>

      <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        <KpiCard
          label="總市值"
          value={money(totalValue)}
          sub={isLoading ? "載入中…" : "mark-to-market"}
          testId="portfolio-total-value"
        />
        <KpiCard
          label="今日損益"
          value={signedMoney(totalDayPnl)}
          sub={pct(dayPct)}
          valueClass={toneClass(totalDayPnl)}
        />
        <KpiCard
          label="總損益"
          value={signedMoney(totalPnl)}
          sub={pct(totalPnlPct)}
          valueClass={toneClass(totalPnl)}
        />
      </div>

      <PortfolioRiskPanel />

      <div className="mb-3 flex flex-wrap gap-2">
        <button
          type="button"
          data-testid="portfolio-add-button"
          className="rounded bg-emerald-700 px-3 py-2 text-[13px] font-semibold text-white hover:bg-emerald-600"
          onClick={() => setModalOpen(true)}
        >
          + 新增倉位
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            importFile(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          data-testid="portfolio-import-button"
          className="rounded border border-white/15 px-3 py-2 text-[13px] font-semibold text-white/80 hover:bg-white/5"
          onClick={() => fileInputRef.current?.click()}
        >
          匯入 CSV
        </button>
        <button
          type="button"
          className="rounded border border-white/15 px-3 py-2 text-[13px] font-semibold text-white/80 hover:bg-white/5 disabled:opacity-40"
          onClick={exportCsv}
          disabled={holdingsForExport.length === 0}
        >
          匯出
        </button>
      </div>

      {toast ? (
        <div className="mb-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-100" role="status">
          {toast}
        </div>
      ) : null}

      {error ? (
        <div className="error-msg mb-3 text-[13px]">
          無法載入 portfolio：<code>{error.message}</code>
        </div>
      ) : null}

      {!isLoading && !error && rows.length === 0 ? (
        <div className="card mb-4 p-3 text-[13px] text-[var(--muted)]">
          尚無持倉。請新增倉位或匯入 CSV。
        </div>
      ) : null}

      {rows.length > 0 ? (
        <>
          <div data-testid="portfolio-holdings-table" className="mb-4 hidden overflow-x-auto rounded border border-[color:var(--border)] md:block">
            <table className="w-full min-w-[760px] text-left text-[13px]">
              <thead className="bg-[var(--panel)] text-[11px] uppercase text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2">Shares</th>
                  <th className="px-3 py-2">Avg Cost</th>
                  <th className="px-3 py-2">Last</th>
                  <th className="px-3 py-2">Day Δ</th>
                  <th className="px-3 py-2">P&L</th>
                  <th className="px-3 py-2">Weight</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-[color:var(--border)]">
                    <td className="px-3 py-2 font-mono font-semibold text-white">{row.symbol}</td>
                    <td className="px-3 py-2">{number(row.shares)}</td>
                    <td className="px-3 py-2">{money(row.cost_basis, 2)}</td>
                    <td className="px-3 py-2">{row.error ? "N/A" : money(row.last_price, 2)}</td>
                    <td className={`px-3 py-2 ${toneClass(row.day_change_pct)}`}>{row.error ? "—" : pct(row.day_change_pct)}</td>
                    <td className={`px-3 py-2 ${toneClass(row.pnl)}`}>
                      {row.error ? "quote unavailable" : `${signedMoney(row.pnl)} (${pct(row.pnl_pct)})`}
                    </td>
                    <td className="px-3 py-2">{row.error ? "—" : pct(row.weight)}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        className="rounded border border-white/15 px-2 py-1 text-[11px] text-white/60 hover:text-red-300"
                        onClick={() => deleteRow(row.id)}
                      >
                        刪除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mb-4">
            <HoldingCards rows={rows} onDelete={deleteRow} />
          </div>
        </>
      ) : null}

    </div>
  );
}

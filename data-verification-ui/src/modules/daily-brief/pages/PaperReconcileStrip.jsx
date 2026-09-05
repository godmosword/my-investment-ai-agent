import { Link } from "react-router-dom";
import {
  useExecutionIntents,
  usePaperLifecycle,
  useReport,
  useReports,
  useTrackRecordClosed,
} from "../../../hooks/useApi";
import {
  closedRecordsFrom,
  extractBriefSymbols,
  intentRowsFrom,
  lifecycleRowsFrom,
  reconcileSymbol,
} from "../paperReconcile";

function reportListRows(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.reports)) return data.reports;
  return [];
}

function latestReportDate(data) {
  for (const row of reportListRows(data)) {
    const date = String(row?.report_date ?? row?.date ?? "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(date)) return date;
  }
  return "";
}

function StripShell({ stateTestId, role, children }) {
  return (
    <div className="card mb-3 p-3 text-[12px]" data-testid="paper-reconcile-strip" role={role}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="card-title">紙上對帳</div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/insights?tab=track-record"
            data-testid="paper-reconcile-link-track-record"
            className="inline-flex min-h-[32px] items-center rounded border border-white/15 px-2.5 text-[11px] text-white/75 hover:bg-white/5"
          >
            實績
          </Link>
          <Link
            to="/insights?tab=paper"
            data-testid="paper-reconcile-link-paper"
            className="inline-flex min-h-[32px] items-center rounded border border-white/15 px-2.5 text-[11px] text-white/75 hover:bg-white/5"
          >
            生命週期
          </Link>
        </div>
      </div>
      <div className="mt-2" data-testid={stateTestId}>
        {children}
      </div>
    </div>
  );
}

function statusTestId(kind) {
  if (kind === "unknown") return "paper-reconcile-missing-field";
  if (kind === "none") return "paper-reconcile-none";
  if (kind === "open") return "paper-reconcile-open";
  if (kind === "closed") return "paper-reconcile-closed";
  return "paper-reconcile-status";
}

export default function PaperReconcileStrip() {
  const reports = useReports(5);
  const latestDate = latestReportDate(reports.data);
  const detail = useReport(latestDate);
  const lifecycle = usePaperLifecycle();
  const intents = useExecutionIntents(100);
  const closed = useTrackRecordClosed(50, 0);

  const reportLoading = reports.isLoading || (Boolean(latestDate) && detail.isLoading);
  const reportError = Boolean(reports.isError || (latestDate && detail.isError));
  const symbols = extractBriefSymbols(detail.data);

  if (reportLoading) {
    return (
      <StripShell stateTestId="paper-reconcile-loading" role="status">
        <span className="text-[var(--muted)]">載入紙上對帳…</span>
      </StripShell>
    );
  }

  if (reportError) {
    return (
      <StripShell stateTestId="paper-reconcile-error" role="alert">
        <span className="text-red-300">紙上對帳暫時無法載入日報標的。</span>
      </StripShell>
    );
  }

  if (!symbols.length) {
    return (
      <StripShell stateTestId="paper-reconcile-empty" role="status">
        <span className="text-[var(--muted)]">UNKNOWN：日報未提供已解析標的</span>
      </StripShell>
    );
  }

  const paperLoading = lifecycle.isLoading || intents.isLoading || closed.isLoading;
  const paperError = Boolean(lifecycle.isError || intents.isError || closed.isError);

  if (paperLoading) {
    return (
      <StripShell stateTestId="paper-reconcile-loading" role="status">
        <span className="text-[var(--muted)]">載入紙上對帳…</span>
      </StripShell>
    );
  }

  if (paperError) {
    return (
      <StripShell stateTestId="paper-reconcile-error" role="alert">
        <span className="text-red-300">紙上對帳暫時無法載入紙上資料。</span>
      </StripShell>
    );
  }

  const lifecycleRows = lifecycleRowsFrom(lifecycle.data);
  const intentRows = intentRowsFrom(intents.data);
  const closedRecords = closedRecordsFrom(closed.data);
  const rows = symbols.map((symbol) => ({
    symbol,
    ...reconcileSymbol(symbol, { lifecycleRows, intentRows, closedRecords }),
  }));

  return (
    <StripShell stateTestId="paper-reconcile-rows" role="region">
      <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
        {rows.map((row) => (
          <li
            key={row.symbol}
            data-testid="paper-reconcile-row"
            data-symbol={row.symbol}
            data-status={row.kind}
            className="inline-flex items-center gap-1.5 rounded border border-white/10 px-2 py-1 font-mono text-[11px] text-white/85"
          >
            <span data-testid="paper-reconcile-symbol">{row.symbol}</span>
            <span data-testid={statusTestId(row.kind)}>{row.label}</span>
            {row.kind === "closed" ? (
              <span data-testid="paper-reconcile-return">{row.returnValue}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </StripShell>
  );
}

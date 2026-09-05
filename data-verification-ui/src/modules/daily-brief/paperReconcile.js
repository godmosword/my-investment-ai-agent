/** Brief ↔ paper universe reconcile. Render API values only; do not scrape prose. */

export const PAPER_OPEN_STATUSES = new Set([
  "APPROVED_FOR_PAPER",
  "PAPER_SUBMITTED",
  "PAPER_FILLED",
]);

export const PAPER_CLOSED_STATUSES = new Set(["PAPER_CLOSED", "CLOSED", "EXITED"]);

export function normalizeSymbol(raw) {
  return String(raw ?? "").trim().toUpperCase();
}

function addSymbol(out, seen, raw) {
  const symbol = normalizeSymbol(raw);
  if (!symbol || seen.has(symbol)) return;
  seen.add(symbol);
  out.push(symbol);
}

function addFromList(out, seen, value) {
  if (!Array.isArray(value)) return;
  for (const item of value) {
    if (typeof item === "string") {
      addSymbol(out, seen, item);
    } else if (item && typeof item === "object") {
      addSymbol(out, seen, item.asset ?? item.ticker ?? item.symbol);
    }
  }
}

/** Symbols already parsed on the report payload. Never scrape grok/gpt prose. */
export function extractBriefSymbols(report) {
  if (!report || typeof report !== "object") return [];
  const out = [];
  const seen = new Set();
  addFromList(out, seen, report.tickers);
  addFromList(out, seen, report.focus_symbols);
  addFromList(out, seen, report.assets);
  addFromList(out, seen, report.symbols);
  addFromList(out, seen, report.recommendations);
  return out;
}

export function rowSymbol(row) {
  if (!row || typeof row !== "object") return "";
  return normalizeSymbol(row.asset ?? row.ticker ?? row.symbol);
}

export function rowsMatching(rows, symbol) {
  const want = normalizeSymbol(symbol);
  if (!want || !Array.isArray(rows)) return [];
  return rows.filter((row) => rowSymbol(row) === want);
}

function statusOf(row) {
  if (!row || typeof row !== "object" || !("status" in row)) return null;
  const status = String(row.status ?? "").trim().toUpperCase();
  return status || "";
}

/**
 * Closed return from an API row. Missing / non-finite → null (caller shows UNKNOWN).
 * Finite 0 stays 0.
 */
export function finiteReturnOf(row) {
  if (!row || typeof row !== "object") return null;
  if (!("return_pct" in row) && !("return" in row) && !("pnl_pct" in row)) return null;
  const raw = row.return_pct ?? row.return ?? row.pnl_pct;
  if (raw == null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

/**
 * @returns {{ kind: "none"|"open"|"closed"|"unknown", label: string, returnValue?: number }}
 */
export function reconcileSymbol(symbol, { lifecycleRows, intentRows, closedRecords } = {}) {
  const life = rowsMatching(lifecycleRows, symbol);
  const intents = rowsMatching(intentRows, symbol);
  const closed = rowsMatching(closedRecords, symbol);
  const live = [...life, ...intents];
  const all = [...live, ...closed];

  if (all.length === 0) {
    return { kind: "none", label: "無紙上記錄" };
  }

  // Open only from lifecycle + intents. Track-record closed can still carry
  // older APPROVED_FOR_PAPER mark-to-market snapshots for the same signal.
  const liveClosed = live.filter((row) => PAPER_CLOSED_STATUSES.has(statusOf(row) || ""));
  const liveOpen = live.filter((row) => PAPER_OPEN_STATUSES.has(statusOf(row) || ""));
  if (liveOpen.length && !liveClosed.length) {
    return { kind: "open", label: "紙上未結" };
  }

  const closedRows = [
    ...closed.filter((row) => {
      const status = statusOf(row);
      return status === null || status === "" || PAPER_CLOSED_STATUSES.has(status);
    }),
    ...life.filter((row) => PAPER_CLOSED_STATUSES.has(statusOf(row) || "")),
    ...intents.filter((row) => PAPER_CLOSED_STATUSES.has(statusOf(row) || "")),
  ];

  if (closedRows.length) {
    for (const row of closedRows) {
      const ret = finiteReturnOf(row);
      if (ret != null) {
        return { kind: "closed", label: "紙上已結", returnValue: ret };
      }
    }
    return { kind: "unknown", label: "UNKNOWN" };
  }

  const missingStatus = all.some((row) => statusOf(row) === null || statusOf(row) === "");
  if (missingStatus) {
    return { kind: "unknown", label: "UNKNOWN" };
  }

  return { kind: "none", label: "無紙上記錄" };
}

export function intentRowsFrom(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.rows)) return data.rows;
  return [];
}

export function lifecycleRowsFrom(data) {
  if (Array.isArray(data?.rows)) return data.rows;
  if (Array.isArray(data)) return data;
  return [];
}

export function closedRecordsFrom(data) {
  if (Array.isArray(data?.records)) return data.records;
  if (Array.isArray(data)) return data;
  return [];
}

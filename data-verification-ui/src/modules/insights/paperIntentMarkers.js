export const PAPER_INTENT_STATUSES = Object.freeze([
  "APPROVED_FOR_PAPER",
  "PAPER_SUBMITTED",
  "PAPER_FILLED",
  "PAPER_CLOSED",
]);

function rowsFromPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.rows)) return payload.rows;
  return [];
}

/** Map an evidence timestamp to candle timeKey (YYYY-MM-DD). No price invention. */
export function chartTimeFromEvidence(raw) {
  if (raw == null || raw === "") return null;
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;
  }
  const ms = Date.parse(String(raw));
  if (!Number.isFinite(ms)) return null;
  const d = new Date(ms);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function rowSymbol(row) {
  return String(row?.asset ?? row?.symbol ?? "")
    .trim()
    .toUpperCase();
}

/**
 * PAPER execution-intent rows for one symbol → SymbolCandleChart eventMarkers.
 * time/direction/signal_id/label only from row fields.
 */
export function paperIntentMarkers(payload, symbol) {
  const want = String(symbol ?? "")
    .trim()
    .toUpperCase();
  if (!want) return [];
  const paper = new Set(PAPER_INTENT_STATUSES);
  const out = [];
  for (const row of rowsFromPayload(payload)) {
    if (rowSymbol(row) !== want) continue;
    if (!paper.has(String(row?.status ?? "").trim())) continue;
    const time = chartTimeFromEvidence(row.status_updated_at || row.created_at);
    if (!time) continue;
    const sid = row.signal_id != null ? String(row.signal_id) : "";
    const label = row.label != null && String(row.label).trim() !== "" ? String(row.label) : "QSREC PAPER";
    out.push({
      time,
      direction: row.direction ?? "",
      signal_id: sid,
      label,
    });
  }
  return out;
}

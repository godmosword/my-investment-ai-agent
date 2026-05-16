/** Shared paper-trading position helpers — used by QuantHome. */

export function finiteNumber(value) {
  if (value == null || (typeof value === "string" && value.trim() === "")) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function paperEntry(r) {
  return finiteNumber(r.paper_fill_price ?? r.paper_entry ?? r.reference_entry_price ?? r.entry_price);
}

export function paperExit(r) {
  return finiteNumber(r.paper_exit_price ?? r.paper_exit);
}

/** Rows counted as closed for paper P&L stats (API + legacy aliases). */
export function isPaperClosedRow(r) {
  const s = String(r.status ?? "").toUpperCase();
  return s === "PAPER_CLOSED" || s === "CLOSED" || s === "EXITED";
}

export function calcStats(rows) {
  if (!rows || rows.length === 0) return null;
  const closed = rows.filter(isPaperClosedRow);
  const settled = closed.filter((r) => {
    const px = paperExit(r);
    const en = paperEntry(r);
    return px != null && en != null && en !== 0;
  });
  if (settled.length === 0) return null;

  const wins = settled.filter((r) => {
    const px = paperExit(r);
    const en = paperEntry(r);
    const dir = (r.direction ?? "").toUpperCase();
    if (dir !== "LONG" && dir !== "SHORT") return false;
    return dir === "LONG" ? px > en : px < en;
  });

  const winRate = settled.length > 0 ? Math.round((wins.length / settled.length) * 100) : 0;

  const pnls = settled
    .map((r) => {
      const px = paperExit(r);
      const en = paperEntry(r);
      const dir = (r.direction ?? "").toUpperCase();
      if (dir !== "LONG" && dir !== "SHORT") return null;
      const raw = dir === "LONG" ? (px - en) / en : (en - px) / en;
      return raw * 100;
    })
    .filter((v) => Number.isFinite(v));

  const avgPnl = pnls.length > 0 ? pnls.reduce((a, b) => a + b, 0) / pnls.length : 0;

  const winPnls = pnls.filter((v) => v > 0);
  const losePnls = pnls.filter((v) => v < 0);
  const avgWin = winPnls.length ? winPnls.reduce((a, b) => a + b, 0) / winPnls.length : 0;
  const avgLoss = losePnls.length
    ? Math.abs(losePnls.reduce((a, b) => a + b, 0) / losePnls.length)
    : 1;
  const rr = avgLoss > 0 ? (avgWin / avgLoss).toFixed(2) : "—";

  return { total: settled.length, wins: wins.length, winRate, avgPnl: avgPnl.toFixed(2), rr };
}

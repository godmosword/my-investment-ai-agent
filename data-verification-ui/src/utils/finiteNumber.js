/** Missing / non-finite → null. Real finite 0 stays 0. */
export function finiteNumber(value) {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

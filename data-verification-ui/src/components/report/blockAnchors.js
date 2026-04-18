/**
 * Stable DOM id for ``#block-*`` deep links (visualization_plan V2 / V5 push).
 * @param {string} [blockId]
 */
export function blockSectionDomId(blockId) {
  const s = String(blockId ?? "unknown");
  return `block-${s.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

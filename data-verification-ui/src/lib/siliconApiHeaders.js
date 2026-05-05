/** localStorage key — 與 TODOS 隊列 26／TERMINAL_FRONTEND_PLAN 對齊。 */
export const QSILICON_MASTER_KEY_STORAGE = "qsi_master_key";

/**
 * 優先序：`localStorage[qsi_master_key]` → `import.meta.env.VITE_QSILICON_KEY`。
 * @returns {string}
 */
export function readEffectiveSiliconKey() {
  if (typeof localStorage !== "undefined") {
    try {
      const v = localStorage.getItem(QSILICON_MASTER_KEY_STORAGE);
      if (v && String(v).trim()) return String(v).trim();
    } catch {
      /* ignore */
    }
  }
  return String(import.meta.env.VITE_QSILICON_KEY ?? "").trim();
}

/** @returns {Record<string, string>} */
export function siliconHeadersForFetch() {
  const k = readEffectiveSiliconKey();
  if (!k) return {};
  return { "X-Q-Silicon-Key": k };
}

/**
 * 合併既有 fetch headers 與 `X-Q-Silicon-Key`（後者覆寫同名）。
 * @param {HeadersInit | undefined} init
 * @returns {Headers}
 */
export function mergeSiliconHeaders(init) {
  const out = new Headers(init ?? undefined);
  const extra = siliconHeadersForFetch();
  for (const [name, value] of Object.entries(extra)) {
    out.set(name, value);
  }
  return out;
}

/**
 * Portal Phase 4 — Gate 0 預設（讀者層 × 工作台層 IA）。
 * 維護者若 REVIEW 後要改決策，請同步 `TODOS.md` 隊列 44「Gate 0」段落。
 */
export const PORTAL_PHASE4_GATE0 = {
  /** 工作台「主戰場」兩條路由（對齊 Master Plan 建議預設）。 */
  workbenchPrimaryRoutes: ["/insights", "/portfolio"],
  /** 第三條狀態台（macro）；與上兩條並列於工作台層，但不佔「兩條主戰場」名額。 */
  workbenchMacroRoute: "/dashboard",
  /**
   * 讀者層首屏：避免多區高密度「報價表／矩陣表」。
   * 現有 digest 卡片流（非 HTML table 報價牆）視為符合本旗標。
   */
  readerFirstScreenAvoidDenseTables: true,
  /** 融合第一刀：單向（新聞／專欄 → 觀點）。 */
  fusionDirection: "reader_to_insights",
  /** 「終端感」保留元素上限（三至五項；供文件／UI 文案對齊）。 */
  terminalToneKeep: ["Command Bar", "mono symbol chips", "macro spark grid", "SSE WATCH", "Workspace dock"],
  /** 工作台關鍵路徑：警報 → 標的／狀態 →（可選）脈絡 — 最大點擊數 N。 */
  maxWorkbenchPathClicks: 3,
};

/** `/insights` 或帶 `?symbol=` 的深連結（重用既有 SymbolDeepDive 契約）。 */
export function insightsSymbolHref(symbol) {
  const s = String(symbol ?? "").trim().toUpperCase();
  if (!s) return "/insights";
  return `/insights?symbol=${encodeURIComponent(s)}`;
}

/**
 * Command Bar placeholder：讀者頁偏「搜尋／跳轉」語意，工作台頁保留 GO／RUN 語感。
 * @param {string} pathname
 */
export function getTerminalCommandBarPlaceholder(pathname) {
  const raw = String(pathname || "/").trim() || "/";
  const path = raw.split("?")[0] || "/";
  if (path === "/news" || path === "/columns") {
    return "搜尋主題焦點… 或 /insights、/portfolio、AAPL GO、RUN";
  }
  return "AAPL <GO> | /columns | MACRO | RUN";
}

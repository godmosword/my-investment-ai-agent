import { useEffect } from "react";
import { blockSectionDomId } from "./blockAnchors";
import { gateIssueLiClass } from "./gateIssueSeverity";

/**
 * Gate 全文滑層：backdrop、Esc 關閉、依區塊跳 `#block-*`。
 */
export default function GateIssuesDrawer({
  open,
  onClose,
  issuesByBlock,
  issuesUnmapped,
  allIssues,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const entries = Object.entries(issuesByBlock || {}).filter(
    ([, lines]) => Array.isArray(lines) && lines.length > 0
  );
  const unmapped = Array.isArray(issuesUnmapped) ? issuesUnmapped.filter(Boolean) : [];
  const flat = Array.isArray(allIssues) ? allIssues.filter(Boolean) : [];

  return (
    <div className="gate-drawer-root" role="dialog" aria-modal="true" aria-labelledby="gate-drawer-title">
      <button type="button" className="gate-drawer-backdrop" onClick={onClose} aria-label="關閉 Gate 詳情" />
      <aside className="gate-drawer-panel">
        <div className="gate-drawer-head">
          <h2 id="gate-drawer-title" className="gate-drawer-title">
            Gate 問題詳情
          </h2>
          <button type="button" className="gate-drawer-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="gate-drawer-body">
          {flat.length > 0 ? (
            <section className="gate-drawer-section">
              <div className="gate-drawer-section-label">完整清單（橫幅同源）</div>
              <ol className="gate-drawer-issues-flat">
                {flat.map((line, i) => (
                  <li key={i} className={gateIssueLiClass(line)}>
                    {line}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <section className="gate-drawer-section">
            <div className="gate-drawer-section-label">依區塊（錨點）</div>
            {entries.length === 0 ? (
              <p className="gate-drawer-muted">無已對應區塊之問題。</p>
            ) : (
              <ul className="gate-drawer-block-list">
                {entries.map(([bid, lines]) => (
                  <li key={bid} className="gate-drawer-block-item">
                    <a href={`#${blockSectionDomId(bid)}`} className="gate-drawer-anchor" onClick={onClose}>
                      #{bid}
                    </a>
                    <span className="gate-drawer-count"> · {lines.length} 則</span>
                    <ul className="gate-drawer-lines">
                      {lines.map((line, i) => (
                        <li key={i} className={gateIssueLiClass(line)}>
                          {line}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {unmapped.length > 0 ? (
            <section className="gate-drawer-section">
              <div className="gate-drawer-section-label">未能對應區塊</div>
              <ul className="gate-drawer-lines">
                {unmapped.map((line, i) => (
                  <li key={i} className={gateIssueLiClass(line)}>
                    {line}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </aside>
    </div>
  );
}

/**
 * 共通區塊外殼：`#block-*` 錨點、標題列、Gate／截至 chip。
 * @param {string} [dataSection] — 對應 `block_id`，供 E2E／可及性以 `data-section` 選取（visualization_plan V2）。
 */
export default function BlockSectionShell({ id, dataSection, title, headerExtras, children }) {
  const ds = dataSection != null && String(dataSection).trim() !== "" ? String(dataSection).trim() : undefined;
  return (
    <section id={id} className="structured-report-block" {...(ds ? { "data-section": ds } : {})}>
      <div className="section-header">
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span>{title}</span>
          {headerExtras}
        </div>
      </div>
      {children}
    </section>
  );
}

/**
 * 共通區塊外殼：`#block-*` 錨點、標題列、Gate／截至 chip。
 */
export default function BlockSectionShell({ id, title, headerExtras, children }) {
  return (
    <section id={id} className="structured-report-block">
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

import BlockSectionShell from "./BlockSectionShell";

export default function MetricsDashboardBlock({ anchor, title, headerExtras, payload }) {
  const lines = Array.isArray(payload) ? payload : [];
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <tbody>
            {lines.map((row, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: "1px solid var(--border)",
                  fontWeight: row.is_section_header ? 600 : 400,
                  background: row.is_section_header ? "rgba(255,255,255,0.03)" : undefined,
                }}
              >
                <td style={{ padding: "8px 6px", verticalAlign: "top", color: "var(--muted)" }}>
                  {row.status_emoji ? `${row.status_emoji} ` : ""}
                  {row.label}
                </td>
                <td style={{ padding: "8px 6px", textAlign: "right", fontFamily: "ui-monospace, monospace" }}>
                  {row.value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </BlockSectionShell>
  );
}

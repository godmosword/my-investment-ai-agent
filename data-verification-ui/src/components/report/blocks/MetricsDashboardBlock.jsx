import BlockSectionShell from "./BlockSectionShell";

/** Inline sparkline (pure SVG, no deps) */
function Sparkline({ values, color = "var(--accent)" }) {
  if (!Array.isArray(values) || values.length < 2) return null;
  const nums = values.map(Number).filter((v) => !Number.isNaN(v));
  if (nums.length < 2) return null;
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const range = max - min || 1;
  const W = 52, H = 20;
  const pts = nums
    .map((v, i) => {
      const x = (i / (nums.length - 1)) * W;
      const y = H - ((v - min) / range) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const lastUp = nums[nums.length - 1] >= nums[nums.length - 2];
  const lineColor = lastUp ? "var(--green)" : "var(--red)";
  return (
    <svg width={W} height={H} style={{ display: "block", flexShrink: 0 }}>
      <polyline
        points={pts}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        opacity={0.85}
      />
    </svg>
  );
}

export default function MetricsDashboardBlock({ anchor, title, headerExtras, payload, blockId }) {
  const lines = Array.isArray(payload) ? payload : [];
  return (
    <BlockSectionShell id={anchor} dataSection={blockId} title={title} headerExtras={headerExtras}>
      <div className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <tbody>
            {lines.map((row, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: "1px solid var(--border)",
                  fontWeight: row.is_section_header ? 600 : 400,
                  background: row.is_section_header ? "rgba(0,0,0,0.02)" : undefined,
                }}
              >
                <td style={{ padding: "8px 6px", verticalAlign: "middle", color: "var(--muted)" }}>
                  {row.status_emoji ? `${row.status_emoji} ` : ""}
                  {row.label}
                </td>
                <td
                  style={{
                    padding: "8px 6px",
                    textAlign: "right",
                    fontFamily: "'JetBrains Mono', ui-monospace, monospace",
                    verticalAlign: "middle",
                  }}
                >
                  {row.value}
                </td>
                <td style={{ padding: "8px 0 8px 8px", width: 56, verticalAlign: "middle" }}>
                  <Sparkline values={row.history} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </BlockSectionShell>
  );
}

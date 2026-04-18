import BlockSectionShell from "./BlockSectionShell";

export default function NewsLinesBlock({ anchor, title, headerExtras, payload }) {
  const raw = String(payload ?? "");
  return (
    <BlockSectionShell id={anchor} title={title} headerExtras={headerExtras}>
      <div className="card">
        {raw.split("\n").map((line, i) => (
          <div
            key={i}
            style={{
              fontSize: 12,
              color: "var(--muted)",
              padding: "3px 0",
              borderBottom: "1px solid var(--border)",
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </BlockSectionShell>
  );
}

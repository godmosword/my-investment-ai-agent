import TradeCard from "../../TradeCard";
import { unwrapTradesPayload } from "../structuredBlockContent";
import BlockSectionShell from "./BlockSectionShell";

export default function TradesBlock({ anchor, title, headerExtras, payload }) {
  const { rows, introHtml, disclaimer } = unwrapTradesPayload(payload);
  const shellTitle = `${title} (${rows.length})`;
  return (
    <BlockSectionShell id={anchor} title={shellTitle} headerExtras={headerExtras}>
      {disclaimer ? (
        <div
          className="card"
          style={{
            marginBottom: 10,
            fontSize: 12,
            color: "var(--muted)",
            borderColor: "rgba(251,191,36,0.35)",
            background: "rgba(251,191,36,0.06)",
          }}
        >
          {disclaimer}
        </div>
      ) : null}
      {introHtml ? (
        <div className="summary-block mb-3" dangerouslySetInnerHTML={{ __html: introHtml }} />
      ) : null}
      {rows.map((t, i) => (
        <TradeCard key={i} trade={t} />
      ))}
    </BlockSectionShell>
  );
}

import GateStatusBadge from "../common/GateStatusBadge";
import AsOfChip from "../common/AsOfChip";
import { blockSectionTitle } from "./legacyBlockContent";
import { blockContentForBlock } from "./structuredBlockContent";
import { blockSectionDomId } from "./blockAnchors";
import CurrentAffairsRoundtableBlock from "./blocks/CurrentAffairsRoundtableBlock";
import TextSummaryBlock from "./blocks/TextSummaryBlock";
import NewsLinesBlock from "./blocks/NewsLinesBlock";
import TradesBlock from "./blocks/TradesBlock";
import MetricsDashboardBlock from "./blocks/MetricsDashboardBlock";
import NewsItemsBlock from "./blocks/NewsItemsBlock";
import TrustedHtmlBlock from "./blocks/TrustedHtmlBlock";
import InstitutionalViewBlock from "./blocks/InstitutionalViewBlock";
import ExecSummaryBlock from "./blocks/ExecSummaryBlock";
import MarketModeBlock from "./blocks/MarketModeBlock";

export default function BlockSection({
  blockId,
  registryEntry,
  legacy,
  dailyBriefReport,
  structuredOk,
  blockGateIssues,
  asOf,
}) {
  const title = blockSectionTitle(blockId, registryEntry);
  const content = blockContentForBlock(blockId, {
    dbr: dailyBriefReport,
    legacy,
    structuredOk,
  });

  if (content.kind === "skip") return null;

  const anchor = blockSectionDomId(blockId);
  const gateCount = Array.isArray(blockGateIssues) ? blockGateIssues.length : 0;

  const headerExtras = (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        alignItems: "center",
        gap: "8px 10px",
        marginTop: 4,
      }}
    >
      {gateCount > 0 ? (
        <span title={blockGateIssues.join("\n")}>
          <GateStatusBadge variant="critical">Gate {gateCount}</GateStatusBadge>
        </span>
      ) : null}
      {asOf ? (
        <AsOfChip
          label="截至"
          asOf={asOf}
          source="BigQuery · daily_metrics"
          className="!py-0.5 !text-[10px]"
        />
      ) : null}
    </div>
  );

  switch (content.kind) {
    case "text":
      return (
        <TextSummaryBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "news":
      return <NewsLinesBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />;
    case "trades":
      return <TradesBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />;
    case "metrics":
      return (
        <MetricsDashboardBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "news_items":
      return (
        <NewsItemsBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "html":
      return (
        <TrustedHtmlBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "roundtable":
      return (
        <CurrentAffairsRoundtableBlock
          anchor={anchor}
          title={title}
          headerExtras={headerExtras}
          payload={content.payload ?? {}}
        />
      );
    case "institutional_split":
      return (
        <InstitutionalViewBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "exec_summary":
      return (
        <ExecSummaryBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    case "market_mode":
      return (
        <MarketModeBlock anchor={anchor} title={title} headerExtras={headerExtras} payload={content.payload} />
      );
    default:
      return null;
  }
}

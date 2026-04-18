import { Link } from "react-router-dom";
import MetricCard from "../MetricCard";
import TradeCard from "../TradeCard";
import SymbolFocusBar from "../SymbolFocusBar";
import { blockSectionTitle, legacyContentForBlock } from "./legacyBlockContent";

function BlockSection({ blockId, registryEntry, legacy }) {
  const title = blockSectionTitle(blockId, registryEntry);
  const content = legacyContentForBlock(blockId, legacy);

  if (content.kind === "skip") return null;

  if (content.kind === "text") {
    return (
      <>
        <div className="section-header">{title}</div>
        <div className="summary-block">{content.payload}</div>
      </>
    );
  }

  if (content.kind === "news") {
    const raw = String(content.payload ?? "");
    return (
      <>
        <div className="section-header">{title}</div>
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
      </>
    );
  }

  if (content.kind === "trades") {
    const rows = content.payload ?? [];
    return (
      <>
        <div className="section-header">
          {title} ({rows.length})
        </div>
        {rows.map((t, i) => (
          <TradeCard key={i} trade={t} />
        ))}
      </>
    );
  }

  return null;
}

/**
 * @param {{
 *   reportDate: string,
 *   payload: {
 *     profile: string,
 *     block_ids: string[],
 *     block_registry: Record<string, { template_subpath: string, macro_name: string }>,
 *     structured_body_available?: boolean,
 *     legacy: Record<string, unknown>,
 *   }
 * }} props
 */
export default function StructuredReportView({ reportDate, payload }) {
  const legacy = payload?.legacy ?? {};
  const blockIds = Array.isArray(payload?.block_ids) ? payload.block_ids : [];
  const registry = payload?.block_registry ?? {};
  const structuredOk = payload?.structured_body_available === true;

  return (
    <>
      <SymbolFocusBar compact />
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <Link to="/archive" style={{ color: "var(--muted)", textDecoration: "none", fontSize: 14 }}>
            ← 返回
          </Link>
        </div>
        <div className="page-title">{reportDate}</div>
        <div className="page-subtitle">
          每日投資戰報 · 區塊視圖（{payload?.profile ?? "full"}）
          {!structuredOk && (
            <span style={{ color: "var(--muted)", fontSize: 12, marginLeft: 8 }}>
              結構化本文尚未入庫 · 顯示 legacy 摘要
            </span>
          )}
        </div>
      </div>

      <div className="metrics-grid">
        <MetricCard label="DXY" value={legacy.dxy} format={(v) => v.toFixed(2)} />
        <MetricCard
          label="ETF 資金流"
          value={legacy.etf_flow_millions}
          unit="億"
          format={(v) => (v > 0 ? `+${v}` : `${v}`)}
        />
        <MetricCard label="MVRV Z" value={legacy.mvrv_z_score} format={(v) => v.toFixed(2)} />
        <MetricCard
          label="風險評分"
          value={legacy.avg_risk_score}
          unit="/5"
          format={(v) => v.toFixed(1)}
        />
      </div>

      {blockIds.map((bid) => (
        <BlockSection
          key={bid}
          blockId={bid}
          registryEntry={registry[bid]}
          legacy={legacy}
        />
      ))}
    </>
  );
}

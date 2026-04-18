/**
 * 開發用：預覽 Visualization V1 共用元件。僅 `import.meta.env.DEV` 掛載於 `/design`。
 */
import AsOfChip from "../components/common/AsOfChip";
import ProvenancePopover from "../components/common/ProvenancePopover";
import ProfileBadge from "../components/common/ProfileBadge";
import GateStatusBadge from "../components/common/GateStatusBadge";
import SourceLink from "../components/common/SourceLink";
import MockBanner from "../components/common/MockBanner";
import { palette } from "../design/tokens";

const sampleProvenance = {
  ohlc: { source: "yfinance", as_of: new Date().toISOString(), underlying_symbol: "BTC-USD", interval: "1d" },
  daily_metrics: { source: "bigquery", as_of: new Date().toISOString(), table_id: "proj.dataset.daily_metrics" },
  recommendations: { source: "bigquery", as_of: new Date().toISOString(), query_window_days: 30 },
};

export default function DesignShowcase() {
  return (
    <div className="page-content" style={{ maxWidth: 480, margin: "0 auto" }}>
      <div className="page-header">
        <div className="page-title">Design（dev）</div>
        <p className="page-subtitle" style={{ opacity: 0.85 }}>
          Visualization V1 — tokens 與共用元件預覽
        </p>
      </div>

      <div className="section-header subtle">Palette（tokens.js）</div>
      <div className="metrics-grid" style={{ marginBottom: 16 }}>
        <div className="metric-card">
          <div className="metric-label">regime.on</div>
          <div className="metric-value" style={{ color: palette.regime.on }}>
            {palette.regime.on}
          </div>
        </div>
        <div className="metric-card">
          <div className="metric-label">accent</div>
          <div className="metric-value" style={{ color: palette.accent }}>
            {palette.accent}
          </div>
        </div>
      </div>

      <div className="section-header subtle">AsOfChip</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <AsOfChip asOf={new Date().toISOString()} source="BigQuery · daily_metrics" />
        <AsOfChip asOf={null} source="mock" label="指標" polling />
      </div>

      <div className="section-header subtle">ProfileBadge / GateStatusBadge</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <ProfileBadge profile="full" />
        <ProfileBadge profile="lite" />
        <ProfileBadge profile="crypto-only" />
        <GateStatusBadge variant="pass">Gate OK</GateStatusBadge>
        <GateStatusBadge variant="warn">WARN</GateStatusBadge>
        <GateStatusBadge variant="critical">CRITICAL</GateStatusBadge>
      </div>

      <div className="section-header subtle">SourceLink</div>
      <p className="page-subtitle" style={{ marginBottom: 16 }}>
        <SourceLink href="https://example.com">外部來源</SourceLink>
      </p>

      <div className="section-header subtle">MockBanner</div>
      <MockBanner variant="today">
        <code>VITE_GLASSBOX_MOCK=1</code> 範例 banner
      </MockBanner>

      <div className="section-header subtle" style={{ marginTop: 20 }}>
        ProvenancePopover
      </div>
      <div className="card" style={{ padding: 12 }}>
        <ProvenancePopover provenance={sampleProvenance} />
      </div>
    </div>
  );
}

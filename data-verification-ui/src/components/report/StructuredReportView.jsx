import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import MetricCard from "../MetricCard";
import SymbolFocusBar from "../SymbolFocusBar";
import AsOfChip from "../common/AsOfChip";
import BriefProfileBar from "./BriefProfileBar";
import BlockSection from "./BlockSection";
import BriefSectionCard from "./BriefSectionCard";
import TickerStrip from "./TickerStrip";
import GateBadge from "./GateBadge";
import GateIssuesNavigator from "./GateIssuesNavigator";
import GateIssuesDrawer from "./GateIssuesDrawer";
import BriefLayoutsReference from "./BriefLayoutsReference";
import { blockSectionTitle } from "./legacyBlockContent";
import { gateIssueLiClass } from "./gateIssueSeverity";

/**
 * @param {{
 *   reportDate: string,
 *   profile?: string,
 *   onProfileChange?: (profile: string) => void,
 *   payload: {
 *     profile: string,
 *     block_ids: string[],
 *     block_registry: Record<string, { template_subpath: string, macro_name: string }>,
 *     structured_body_available?: boolean,
 *     daily_brief_report?: Record<string, unknown> | null,
 *     gate_summary?: {
 *       issues_by_block?: Record<string, string[]>,
 *       issues_unmapped?: string[],
 *       ok?: boolean | null,
 *       available?: boolean,
 *     },
 *     legacy: Record<string, unknown>,
 *   }
 * }} props
 */
export default function StructuredReportView({
  reportDate,
  payload,
  profile: profileProp,
  onProfileChange,
}) {
  const legacy = payload?.legacy ?? {};
  const dailyBriefReport = payload?.daily_brief_report ?? null;
  const blockIds = Array.isArray(payload?.block_ids) ? payload.block_ids : [];
  const registry = payload?.block_registry ?? {};
  const structuredOk = payload?.structured_body_available === true;
  const profileUi = profileProp ?? payload?.profile ?? "full";
  const asOf = legacy?.timestamp;
  const gateSummary = payload?.gate_summary ?? {};
  const issuesByBlock = gateSummary?.issues_by_block ?? {};
  const issuesUnmapped = gateSummary?.issues_unmapped ?? [];
  const gateBanner =
    gateSummary?.available === true && gateSummary?.ok === false && Array.isArray(gateSummary?.issues);
  const showGateNavigator =
    Object.keys(issuesByBlock).some((k) => Array.isArray(issuesByBlock[k]) && issuesByBlock[k].length > 0) ||
    (Array.isArray(issuesUnmapped) && issuesUnmapped.length > 0);
  const gateIssueLines = Array.isArray(gateSummary?.issues) ? gateSummary.issues : [];
  const canOpenGateDrawer = gateIssueLines.length > 0 || showGateNavigator;

  const [gateDrawerOpen, setGateDrawerOpen] = useState(false);

  useEffect(() => {
    const scrollToHash = () => {
      const raw = window.location.hash?.replace(/^#/, "") ?? "";
      if (!raw || !raw.startsWith("block-")) return;
      requestAnimationFrame(() => {
        document.getElementById(raw)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    };
    scrollToHash();
    window.addEventListener("hashchange", scrollToHash);
    return () => window.removeEventListener("hashchange", scrollToHash);
  }, [reportDate, blockIds.join("|")]);

  return (
    <>
      <SymbolFocusBar compact />
      <TickerStrip />
      <div className="page-header" data-testid="structured-report-view">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <Link to="/insights" style={{ color: "var(--muted)", textDecoration: "none", fontSize: 14 }}>
            ← 返回
          </Link>
        </div>
        <div className="page-title">{reportDate}</div>
        <div
          className="page-subtitle"
          style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px 12px" }}
        >
          <span>
            每日投資戰報 · 區塊視圖（{payload?.profile ?? "full"}）
            {!structuredOk && (
              <span style={{ color: "var(--muted)", fontSize: 12, marginLeft: 8 }}>
                結構化本文尚未入庫 · 顯示 legacy 摘要
              </span>
            )}
          </span>
          {typeof onProfileChange === "function" ? (
            <BriefProfileBar value={profileUi} onChange={onProfileChange} />
          ) : null}
          <GateBadge gateSummary={gateSummary} />
          <AsOfChip label="資料截至" asOf={asOf} source="BigQuery · daily_metrics" />
          <a
            href={`/api/reports/${reportDate}/html?download=1&profile=${profileUi}`}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontWeight: 600,
              color: "var(--accent)",
              textDecoration: "none",
              padding: "3px 10px",
              borderRadius: 6,
              border: "1px solid rgba(10,124,104,0.25)",
              background: "rgba(10,124,104,0.06)",
            }}
          >
            ↓ 匯出 HTML
          </a>
        </div>
      </div>

      <BriefLayoutsReference />

      {gateBanner ? (
        <div
          className="card"
          style={{
            marginBottom: 12,
            borderColor: "rgba(248,113,113,0.35)",
            background: "rgba(248,113,113,0.06)",
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>Gate 未通過（摘要）</div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "var(--muted)" }}>
            {(gateSummary.issues ?? []).slice(0, 12).map((line, i) => (
              <li key={i} className={gateIssueLiClass(line)} style={{ marginBottom: 4 }}>
                {line}
              </li>
            ))}
          </ul>
          {Array.isArray(gateSummary?.issues_unmapped) && gateSummary.issues_unmapped.length > 0 ? (
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 8 }}>
              另有 {gateSummary.issues_unmapped.length} 則未能自動對應區塊（見清單全文）。
            </div>
          ) : null}
        </div>
      ) : null}

      {canOpenGateDrawer ? (
        <div style={{ marginBottom: 12 }}>
          <button
            type="button"
            className="terminal-btn terminal-btn--small"
            onClick={() => setGateDrawerOpen(true)}
          >
            開啟 Gate 詳情（滑層）
          </button>
        </div>
      ) : null}

      {showGateNavigator ? (
        <GateIssuesNavigator issuesByBlock={issuesByBlock} issuesUnmapped={issuesUnmapped} />
      ) : null}

      {canOpenGateDrawer ? (
        <GateIssuesDrawer
          open={gateDrawerOpen}
          onClose={() => setGateDrawerOpen(false)}
          issuesByBlock={issuesByBlock}
          issuesUnmapped={issuesUnmapped}
          allIssues={gateIssueLines}
        />
      ) : null}

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
        <BriefSectionCard key={bid} blockId={bid} label={blockSectionTitle(bid, registry[bid])}>
          <BlockSection
            blockId={bid}
            registryEntry={registry[bid]}
            legacy={legacy}
            dailyBriefReport={dailyBriefReport}
            structuredOk={structuredOk}
            blockGateIssues={issuesByBlock[bid]}
            asOf={asOf}
          />
        </BriefSectionCard>
      ))}
    </>
  );
}

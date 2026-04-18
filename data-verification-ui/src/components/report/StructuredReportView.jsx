import { useEffect } from "react";
import { Link } from "react-router-dom";
import MetricCard from "../MetricCard";
import TradeCard from "../TradeCard";
import SymbolFocusBar from "../SymbolFocusBar";
import AsOfChip from "../common/AsOfChip";
import GateStatusBadge from "../common/GateStatusBadge";
import BriefProfileBar from "./BriefProfileBar";
import { blockSectionTitle } from "./legacyBlockContent";
import { blockContentForBlock, unwrapTradesPayload } from "./structuredBlockContent";

/** Stable DOM id for ``#block-*`` deep links (visualization_plan V2). */
export function blockSectionDomId(blockId) {
  const s = String(blockId ?? "unknown");
  return `block-${s.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
}

function BlockSection({
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
          <GateStatusBadge variant="critical">
            Gate {gateCount}
          </GateStatusBadge>
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

  if (content.kind === "text") {
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
        <div className="summary-block">{content.payload}</div>
      </section>
    );
  }

  if (content.kind === "news") {
    const raw = String(content.payload ?? "");
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
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
      </section>
    );
  }

  if (content.kind === "trades") {
    const { rows, introHtml, disclaimer } = unwrapTradesPayload(content.payload);
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>
              {title} ({rows.length})
            </span>
            {headerExtras}
          </div>
        </div>
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
          /* Pipeline-generated HTML (whitelist); same trust boundary as Telegram template */
          <div
            className="summary-block mb-3"
            dangerouslySetInnerHTML={{ __html: introHtml }}
          />
        ) : null}
        {rows.map((t, i) => (
          <TradeCard key={i} trade={t} />
        ))}
      </section>
    );
  }

  if (content.kind === "metrics") {
    const lines = Array.isArray(content.payload) ? content.payload : [];
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
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
      </section>
    );
  }

  if (content.kind === "news_items") {
    const items = Array.isArray(content.payload) ? content.payload : [];
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>
              {title} ({items.length})
            </span>
            {headerExtras}
          </div>
        </div>
        {items.map((n, i) => (
          <div key={i} className="card" style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>
              {n.timestamp_line} · #{n.index}
            </div>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>{n.title}</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 6 }}>{n.source_and_nature}</div>
            <div style={{ fontSize: 13, lineHeight: 1.45 }}>{n.summary}</div>
            <div style={{ fontSize: 13, marginTop: 8, color: "rgb(167 243 208)" }}>{n.investment_takeaway}</div>
            <div style={{ fontSize: 11, marginTop: 6, color: "var(--muted)" }}>
              編輯共識：{n.editor_consensus}
              {n.pricing_note ? ` · 定價：${n.pricing_note}` : ""}
            </div>
          </div>
        ))}
      </section>
    );
  }

  if (content.kind === "html") {
    /* Assembled / BQ-injected HTML (previous_recs, source_observability, etc.) — trusted pipeline output only */
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
        <div className="summary-block" dangerouslySetInnerHTML={{ __html: String(content.payload ?? "") }} />
      </section>
    );
  }

  if (content.kind === "roundtable") {
    const rt = content.payload ?? {};
    const voices = Array.isArray(rt.voices) ? rt.voices : [];
    const unresolved = Array.isArray(rt.unresolved) ? rt.unresolved : [];
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
        <div className="card" style={{ marginBottom: 10 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>{rt.topic}</div>
          {voices.map((v, i) => (
            <div
              key={i}
              style={{
                borderTop: i === 0 ? undefined : "1px solid var(--border)",
                paddingTop: i === 0 ? 0 : 10,
                marginTop: i === 0 ? 0 : 10,
              }}
            >
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>{v.role}</div>
              <div style={{ fontSize: 13, lineHeight: 1.5 }}>{v.viewpoint}</div>
              {v.evidence_anchor ? (
                <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>錨點：{v.evidence_anchor}</div>
              ) : null}
              {v.disagreement ? (
                <div style={{ fontSize: 12, marginTop: 4, color: "rgb(254 202 202)" }}>分歧：{v.disagreement}</div>
              ) : null}
            </div>
          ))}
          {rt.consensus ? (
            <div style={{ marginTop: 12, fontSize: 13, borderTop: "1px solid var(--border)", paddingTop: 10 }}>
              <span style={{ color: "var(--muted)", fontSize: 11 }}>共識</span>
              <div style={{ marginTop: 4 }}>{rt.consensus}</div>
            </div>
          ) : null}
          {unresolved.filter(Boolean).length > 0 ? (
            <div style={{ marginTop: 10, fontSize: 12 }}>
              <span style={{ color: "var(--muted)", fontSize: 11 }}>未解問題</span>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                {unresolved.filter(Boolean).map((u, j) => (
                  <li key={j} style={{ marginBottom: 4 }}>
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </section>
    );
  }

  if (content.kind === "institutional_split") {
    const { thesisText, disclaimerHtml } = content.payload ?? {};
    return (
      <section id={anchor} className="structured-report-block">
        <div className="section-header">
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <span>{title}</span>
            {headerExtras}
          </div>
        </div>
        {thesisText ? (
          <div className="summary-block" style={{ whiteSpace: "pre-wrap" }}>
            {thesisText}
          </div>
        ) : null}
        {disclaimerHtml ? (
          <div
            className="summary-block"
            style={{ marginTop: thesisText ? 10 : 0 }}
            /* Fixed whitelist HTML from assemble, not LLM raw */
            dangerouslySetInnerHTML={{ __html: String(disclaimerHtml) }}
          />
        ) : null}
      </section>
    );
  }

  return null;
}

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
  const gateBanner =
    gateSummary?.available === true && gateSummary?.ok === false && Array.isArray(gateSummary?.issues);

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
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
          <Link to="/archive" style={{ color: "var(--muted)", textDecoration: "none", fontSize: 14 }}>
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
          <AsOfChip label="資料截至" asOf={asOf} source="BigQuery · daily_metrics" />
        </div>
      </div>

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
              <li key={i} style={{ marginBottom: 4 }}>
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
          dailyBriefReport={dailyBriefReport}
          structuredOk={structuredOk}
          blockGateIssues={issuesByBlock[bid]}
          asOf={asOf}
        />
      ))}
    </>
  );
}

import { radius, shadow } from "../../../design/tokens";

/**
 * 〔時事多觀點〕— mobile 直向堆疊、md+ 三欄 voice 卡（visualization_plan V4）。
 * @param {{ title: import("react").ReactNode, headerExtras: import("react").ReactNode, anchor: string, payload: Record<string, unknown> }} props
 */
export default function CurrentAffairsRoundtableBlock({ title, headerExtras, anchor, payload }) {
  const rt = payload ?? {};
  const topic = String(rt.topic ?? "—");
  const voices = Array.isArray(rt.voices) ? rt.voices : [];
  const unresolved = Array.isArray(rt.unresolved) ? rt.unresolved : [];
  const consensus = rt.consensus;

  return (
    <section id={anchor} className="structured-report-block">
      <div className="section-header">
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span>{title}</span>
          {headerExtras}
        </div>
      </div>
      <div
        className="card"
        style={{
          marginBottom: 10,
          borderRadius: radius.md,
          boxShadow: shadow.card,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 12, color: "var(--text)" }}>{topic}</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {voices.map((v, i) => (
            <div
              key={i}
              className="flex flex-col border border-[color:var(--border)] p-3"
              style={{
                borderRadius: radius.sm,
                background: "rgba(255,255,255,0.02)",
              }}
            >
              <div className="text-[11px] text-[var(--muted)]" style={{ marginBottom: 4 }}>
                {v.role}
              </div>
              <div className="text-[13px] leading-[1.5] text-[var(--text)]">{v.viewpoint}</div>
              {v.evidence_anchor ? (
                <div className="mt-2 text-[11px] text-[var(--muted)]">錨點：{v.evidence_anchor}</div>
              ) : null}
              {v.disagreement ? (
                <div className="mt-2 text-[12px] text-red-200/90">分歧：{v.disagreement}</div>
              ) : null}
            </div>
          ))}
        </div>
        {consensus ? (
          <div
            className="mt-4 border-t border-[color:var(--border)] pt-3 text-[13px]"
            style={{ borderColor: "var(--border)" }}
          >
            <span className="text-[11px] text-[var(--muted)]">共識</span>
            <div className="mt-1 text-[var(--text)]">{consensus}</div>
          </div>
        ) : null}
        {unresolved.filter(Boolean).length > 0 ? (
          <div className="mt-3 text-[12px]">
            <span className="text-[11px] text-[var(--muted)]">未解問題</span>
            <ul className="ml-[18px] mt-1.5 list-disc">
              {unresolved.filter(Boolean).map((u, j) => (
                <li key={j} className="mb-1">
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

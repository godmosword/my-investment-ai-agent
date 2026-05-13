function metaLine(event) {
  const parts = [];
  if (event.estimate != null && event.estimate !== "") parts.push(`預期 ${event.estimate}`);
  if (event.previous != null && event.previous !== "") parts.push(`前值 ${event.previous}`);
  return parts.join(" · ");
}

export default function CatalystCalendar({ catalysts = [] }) {
  return (
    <section className="card h-full" data-testid="catalyst-calendar">
      <div className="card-title">Catalyst Calendar</div>
      {catalysts.length === 0 ? (
        <div className="text-[13px] text-[var(--muted)]">未取得未來 7 天高影響事件。</div>
      ) : (
        <div className="space-y-2">
          {catalysts.map((event, idx) => (
            <div
              key={`${event.date}-${event.name}-${idx}`}
              className="rounded-lg border border-[color:var(--border)] bg-white/60 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-[12px] text-[var(--muted)]">{event.date || "TBD"}</span>
                <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-700">
                  {event.importance || "high"}
                </span>
              </div>
              <div className="mt-1 text-[13px] font-semibold text-[var(--text)]">{event.name}</div>
              {metaLine(event) ? <div className="mt-1 text-[12px] text-[var(--muted)]">{metaLine(event)}</div> : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

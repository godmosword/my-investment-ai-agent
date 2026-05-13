import CatalystCalendar from "../../../components/CatalystCalendar";
import Sparkline from "../../../components/Sparkline";
import TodayBtcSnapshotStrip from "../../../components/TodayBtcSnapshotStrip";
import { useMacroSnapshot } from "../../../hooks/useApi";

function formatValue(indicator) {
  if (!indicator) return "N/A";
  if (indicator.display) return indicator.display;
  const n = Number(indicator.value);
  if (!Number.isFinite(n)) return "N/A";
  if (indicator.unit === "USD") return `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
  return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function formatChange(value, unit = "%") {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(unit === "bp" ? 1 : 2)}${unit}`;
}

function toneFor(indicator) {
  const n = Number(indicator?.change_5d ?? indicator?.change_1d);
  if (!Number.isFinite(n)) return "neutral";
  return n > 0 ? "up" : n < 0 ? "down" : "neutral";
}

function deltaClass(indicator) {
  const tone = toneFor(indicator);
  if (tone === "up") return "delta-up";
  if (tone === "down") return "delta-down";
  return "delta-flat";
}

function MacroCard({ indicator }) {
  const tone = toneFor(indicator);
  return (
    <article
      className="metric-card flex min-h-[168px] flex-col gap-2"
      data-testid={`macro-indicator-${indicator.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="metric-label">{indicator.label}</div>
          <div className="metric-value">{formatValue(indicator)}</div>
        </div>
        <span className={`metric-delta ${deltaClass(indicator)}`}>
          5D {formatChange(indicator.change_5d, indicator.change_unit || "%")}
        </span>
      </div>
      <div className="mt-auto">
        <Sparkline values={indicator.spark || []} tone={tone} label={`${indicator.label} sparkline`} />
      </div>
      <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--muted)]">
        <span>1D {formatChange(indicator.change_1d, indicator.change_unit || "%")}</span>
        <span className="truncate">{indicator.source}</span>
      </div>
    </article>
  );
}

function regimeTone(label) {
  if (label === "risk_on") return "regime-on";
  if (label === "risk_off") return "regime-off";
  return "regime-neutral";
}

function RegimePanel({ regime }) {
  const drivers = regime?.drivers ?? [];
  const label = regime?.label ?? "neutral";
  return (
    <section className="card h-full" data-testid="macro-regime-panel">
      <div className="card-title">Regime Breakdown</div>
      <div className={`regime-badge ${regimeTone(label)}`}>{label.replace("_", " ").toUpperCase()} · {regime?.score ?? 0}</div>
      <div className="space-y-2">
        {drivers.map((driver) => (
          <div key={driver.name} className="flex items-center justify-between gap-3 text-[13px]">
            <span className="text-[var(--muted)]">{driver.name}</span>
            <span className={driver.score > 0 ? "text-green-600" : driver.score < 0 ? "text-red-600" : "text-[var(--muted)]"}>
              {driver.note} · {driver.score > 0 ? "+" : ""}{driver.score}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function DashboardHome() {
  const macro = useMacroSnapshot();
  const data = macro.data;
  const order = data?.indicator_order ?? [];
  const indicators = order.map((id) => data?.indicators?.[id]).filter(Boolean);

  return (
    <div data-testid="dashboard-home" className="px-3 py-4 pb-24 md:px-0 md:pb-0">
      <div className="page-header">
        <div className="page-title">數據儀表板</div>
        <div className="page-subtitle">
          Macro snapshot · {data?.as_of ? new Date(data.as_of).toLocaleString("zh-TW", { hour12: false }) : "loading"}
          {data?.cached ? " · cached" : ""}
        </div>
      </div>

      <TodayBtcSnapshotStrip />

      {macro.isLoading ? <div className="loading" data-testid="macro-dashboard-loading">載入 macro snapshot…</div> : null}
      {macro.error ? (
        <div className="error-msg mb-3" data-testid="macro-dashboard-error">
          無法載入 macro snapshot：<code>{macro.error.message}</code>
        </div>
      ) : null}

      {indicators.length > 0 ? (
        <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="macro-indicator-grid">
          {indicators.map((indicator) => (
            <MacroCard key={indicator.id} indicator={indicator} />
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <CatalystCalendar catalysts={data?.catalysts ?? []} />
        <RegimePanel regime={data?.regime} />
      </div>
    </div>
  );
}

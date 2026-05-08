import { NavLink } from "react-router-dom";
import { useWarRoomSseStatus } from "../../hooks/useWarRoomSse";

const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";

const PRIMARY_TABS = [
  { to: "/today",   icon: "📊", label: "今日戰情室" },
  { to: "/charts",  icon: "📈", label: "圖表" },
  { to: "/trades",  icon: "💼", label: "交易記錄" },
  { to: "/briefs",  icon: "🖥️", label: "日報終端" },
  { to: "/archive", icon: "🗄",  label: "存檔" },
];

const MODULE_TABS = [
  { to: "/analysis",  icon: "🔬", label: "投資分析" },
  { to: "/positions", icon: "📌", label: "倉位管理" },
  { to: "/industries",icon: "🏭", label: "產業趨勢" },
  { to: "/quant",     icon: "⚡", label: "量化交易" },
];

const SYSTEM_TABS = [
  { to: "/settings", icon: "⚙️", label: "設定" },
];

function SseDot() {
  const { sseStatus } = useWarRoomSseStatus();

  if (!SSE_ENABLED) return null;

  const dotClass =
    sseStatus === "connected"
      ? "sse-dot sse-dot--connected"
      : sseStatus === "error"
        ? "sse-dot sse-dot--error"
        : "sse-dot";
  const title =
    sseStatus === "connected"
      ? "SSE 已連線"
      : sseStatus === "error"
        ? "SSE 連線失敗"
        : "SSE 連線中…";

  return (
    <span
      className={dotClass}
      title={title}
      role="status"
      aria-live="polite"
      aria-label={title}
    />
  );
}

function NavItem({ to, icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `side-nav__item${isActive ? " active" : ""}`}
      aria-label={label}
    >
      <span className="side-nav__icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </NavLink>
  );
}

export default function SideNav() {
  return (
    <nav className="side-nav" aria-label="主導航">
      <div className="side-nav__logo">
        <span aria-hidden="true">◈</span>
        <div>
          <div>Q-Silicon</div>
          <div className="side-nav__logo-sub">Investment AI</div>
        </div>
      </div>

      <div className="side-nav__section">主功能</div>
      {PRIMARY_TABS.map(({ to, icon, label }) => (
        <NavItem key={to} to={to} icon={icon} label={label} end={to === "/today"} />
      ))}

      <div className="side-nav__divider" />
      <div className="side-nav__section">分析模組</div>
      {MODULE_TABS.map(({ to, icon, label }) => (
        <NavItem key={to} to={to} icon={icon} label={label} />
      ))}

      <div className="side-nav__divider" />
      {SYSTEM_TABS.map(({ to, icon, label }) => (
        <NavItem key={to} to={to} icon={icon} label={label} />
      ))}

      <div className="side-nav__footer">
        <div
          style={{
            fontSize: 10,
            color: "var(--muted)",
            opacity: 0.5,
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span>即時串流</span>
          <SseDot />
        </div>
      </div>
    </nav>
  );
}

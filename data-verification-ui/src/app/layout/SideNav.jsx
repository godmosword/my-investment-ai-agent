import { NavLink } from "react-router-dom";
import { useWarRoomSseStatus } from "../../hooks/useWarRoomSse";

const SSE_ENABLED = import.meta.env.VITE_SSE_ENABLED === "1";

const PRIMARY_TABS = [
  { to: "/news",      icon: "📰", label: "科技即時報" },
  { to: "/dashboard", icon: "📊", label: "數據儀表板" },
  { to: "/insights",  icon: "🖥️", label: "投資觀點" },
  { to: "/columns",   icon: "🏭", label: "科技專欄" },
  { to: "/portfolio", icon: "📌", label: "Portfolio" },
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

      <div className="side-nav__section">五板塊</div>
      {PRIMARY_TABS.map(({ to, icon, label }) => (
        <NavItem key={to} to={to} icon={icon} label={label} end />
      ))}

      <div className="side-nav__divider" />
      {SYSTEM_TABS.map(({ to, icon, label }) => (
        <NavItem key={to} to={to} icon={icon} label={label} />
      ))}

      <div className="side-nav__footer">
        <div
          className="side-nav__hint"
          data-testid="side-nav-shortcut-hint"
          title="鍵盤捷徑：⌘K 聚焦 Command Bar；G→B 觀點 / G→M 監控 / G→S 設定"
        >
          <span>捷徑</span>
          <kbd>⌘K</kbd>
          <span>·</span>
          <kbd>G B</kbd>
          <kbd>G M</kbd>
          <kbd>G S</kbd>
        </div>
        <div
          style={{
            fontSize: 10,
            color: "var(--muted)",
            opacity: 0.5,
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 6,
          }}
        >
          <span>即時串流</span>
          <SseDot />
        </div>
      </div>
    </nav>
  );
}

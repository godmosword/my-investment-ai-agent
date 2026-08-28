import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/news",      icon: "📰", label: "科技即時報" },
  { to: "/dashboard", icon: "📊", label: "數據儀表板" },
  { to: "/insights",  icon: "🖥️", label: "投資觀點" },
  { to: "/columns",   icon: "🏭", label: "科技專欄" },
  { to: "/portfolio", icon: "📌", label: "Portfolio" },
  { to: "/settings", icon: "⚙️", label: "設定" },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="主導航（底部）">
      {TABS.map(({ to, icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end
          className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
          aria-label={label}
        >
          <span className="nav-icon" aria-hidden="true">{icon}</span>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

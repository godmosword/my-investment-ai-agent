import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/",         icon: "📊", label: "今日" },
  { to: "/charts",   icon: "📈", label: "圖表" },
  { to: "/trades",   icon: "💼", label: "交易" },
  { to: "/terminal", icon: "🖥️", label: "終端" },
  { to: "/archive",  icon: "🗄",  label: "存檔" },
  { to: "/settings", icon: "⚙️", label: "設定" },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      {TABS.map(({ to, icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
        >
          <span className="nav-icon">{icon}</span>
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

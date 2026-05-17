import { lazy, Suspense, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import BottomNav from "../../components/BottomNav";
import Shell from "../layout/Shell";
import { useSymbolFocus } from "../../context/SymbolFocusContext";

/** Route-level code split：降低首包體積（對齊 Master Plan §3.6）。 */
const NewsHome = lazy(() => import("../../modules/news/pages/NewsHome"));
const DashboardHome = lazy(() => import("../../modules/dashboard/pages/DashboardHome"));
const InsightsHome = lazy(() => import("../../modules/insights/pages/InsightsHome"));
const ColumnsHome = lazy(() => import("../../modules/columns/pages/ColumnsHome"));
const PortfolioHome = lazy(() => import("../../modules/portfolio/pages/PortfolioHome"));
const AnalysisHome = lazy(() => import("../../modules/investment-analysis/pages/AnalysisHome"));
const IndustriesHome = lazy(() => import("../../modules/industry-trends/pages/IndustriesHome"));
const Report = lazy(() => import("../../pages/Report"));
const Settings = lazy(() => import("../../pages/Settings"));
const ApiKeyPage = lazy(() => import("../../pages/ApiKeyPage"));
const Archive = lazy(() => import("../../pages/Archive"));

const DesignShowcase = import.meta.env.DEV ? lazy(() => import("../../pages/DesignShowcase")) : null;
const routeFallback = <div className="loading">載入終端…</div>;

function RedirectWithSearch({ to }) {
  const { search, hash } = useLocation();
  return <Navigate to={`${to}${search}${hash}`} replace />;
}

function SymbolQuerySync() {
  const { search } = useLocation();
  const { setSymbol } = useSymbolFocus();
  useEffect(() => {
    const params = new URLSearchParams(search);
    const symbol = String(params.get("symbol") || "").trim().toUpperCase();
    if (symbol) setSymbol(symbol);
  }, [search, setSymbol]);
  return null;
}

export default function PortalRoutes() {
  const { pathname } = useLocation();
  const hideChrome = pathname === "/api-key";
  return (
    <Shell hideModuleNav={hideChrome}>
      <SymbolQuerySync />
      <main id="main-content" tabIndex={-1} className="page-content">
        <Suspense fallback={routeFallback}>
          <Routes>
            <Route path="/" element={<RedirectWithSearch to="/insights" />} />
            <Route path="/briefs" element={<RedirectWithSearch to="/insights" />} />
            <Route path="/terminal" element={<RedirectWithSearch to="/insights" />} />
            <Route path="/news" element={<NewsHome />} />
            <Route path="/dashboard" element={<DashboardHome />} />
            <Route path="/insights" element={<InsightsHome />} />
            <Route path="/columns" element={<ColumnsHome />} />
            <Route path="/portfolio" element={<PortfolioHome />} />
            <Route path="/analysis" element={<AnalysisHome />} />
            <Route path="/industries" element={<IndustriesHome />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/api-key" element={<ApiKeyPage />} />
            <Route path="/report/:date" element={<Report />} />
            {import.meta.env.DEV && DesignShowcase ? (
              <Route path="/design" element={<DesignShowcase />} />
            ) : null}
          </Routes>
        </Suspense>
      </main>
      {!hideChrome ? <BottomNav /> : null}
    </Shell>
  );
}

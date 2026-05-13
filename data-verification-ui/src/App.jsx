import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BottomNav from "./components/BottomNav";
import ErrorBoundary from "./components/ErrorBoundary";
import { WarRoomSseProvider } from "./hooks/useWarRoomSse";
import { SymbolFocusProvider } from "./context/SymbolFocusContext";
import Shell from "./app/layout/Shell";
import Report from "./pages/Report";
import Settings from "./pages/Settings";
import ApiKeyPage from "./pages/ApiKeyPage";
import NewsHome from "./modules/news/pages/NewsHome";
import DashboardHome from "./modules/dashboard/pages/DashboardHome";
import InsightsHome from "./modules/insights/pages/InsightsHome";
import ColumnsHome from "./modules/columns/pages/ColumnsHome";
import PortfolioHome from "./modules/portfolio/pages/PortfolioHome";

const DesignShowcase = import.meta.env.DEV ? lazy(() => import("./pages/DesignShowcase")) : null;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

const routeFallback = <div className="loading">載入終端…</div>;

function RedirectWithSearch({ to }) {
  const { search, hash } = useLocation();
  return <Navigate to={`${to}${search}${hash}`} replace />;
}

function AppRoutes() {
  const { pathname } = useLocation();
  const hideChrome = pathname === "/api-key";
  return (
    <Shell hideModuleNav={hideChrome}>
      <main className="page-content">
        <Routes>
          <Route path="/" element={<RedirectWithSearch to="/insights" />} />
          <Route path="/briefs" element={<RedirectWithSearch to="/insights" />} />
          <Route path="/terminal" element={<RedirectWithSearch to="/insights" />} />
          <Route path="/news" element={<NewsHome />} />
          <Route path="/dashboard" element={<DashboardHome />} />
          <Route path="/insights" element={<InsightsHome />} />
          <Route path="/columns" element={<ColumnsHome />} />
          <Route path="/portfolio" element={<PortfolioHome />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/api-key" element={<ApiKeyPage />} />
          <Route path="/report/:date" element={<Report />} />
          {import.meta.env.DEV && DesignShowcase ? (
            <Route
              path="/design"
              element={
                <Suspense fallback={routeFallback}>
                  <DesignShowcase />
                </Suspense>
              }
            />
          ) : null}
        </Routes>
      </main>
      {!hideChrome ? <BottomNav /> : null}
    </Shell>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SymbolFocusProvider>
          <WarRoomSseProvider>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </WarRoomSseProvider>
        </SymbolFocusProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

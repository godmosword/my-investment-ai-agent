import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BottomNav from "./components/BottomNav";
import WarRoomSseBridge from "./components/WarRoomSseBridge";
import { SymbolFocusProvider } from "./context/SymbolFocusContext";
import Shell from "./app/layout/Shell";
import Today from "./pages/Today";
import Charts from "./pages/Charts";
import Trades from "./pages/Trades";
import Archive from "./pages/Archive";
import Report from "./pages/Report";
import Settings from "./pages/Settings";
import ApiKeyPage from "./pages/ApiKeyPage";
import AnalysisHome from "./modules/investment-analysis/pages/AnalysisHome";
import PositionsHome from "./modules/position-management/pages/PositionsHome";
import IndustriesHome from "./modules/industry-trends/pages/IndustriesHome";
import QuantHome from "./modules/quant-trading/pages/QuantHome";

const DailyBriefPage = lazy(() => import("./modules/daily-brief/pages/DailyBriefPage"));
const DesignShowcase = import.meta.env.DEV ? lazy(() => import("./pages/DesignShowcase")) : null;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

const briefFallback = <div className="loading">載入終端…</div>;

function AppRoutes() {
  const { pathname } = useLocation();
  const hideChrome = pathname === "/api-key";
  return (
    <Shell hideModuleNav={hideChrome}>
      <main className="page-content">
        <Routes>
          <Route path="/" element={<Navigate to="/briefs" replace />} />
          <Route path="/today" element={<Today />} />
          <Route path="/charts" element={<Charts />} />
          <Route path="/trades" element={<Trades />} />
          <Route
            path="/briefs"
            element={
              <Suspense fallback={briefFallback}>
                <DailyBriefPage />
              </Suspense>
            }
          />
          <Route
            path="/terminal"
            element={
              <Suspense fallback={briefFallback}>
                <DailyBriefPage />
              </Suspense>
            }
          />
          <Route path="/analysis" element={<AnalysisHome />} />
          <Route path="/positions" element={<PositionsHome />} />
          <Route path="/industries" element={<IndustriesHome />} />
          <Route path="/quant" element={<QuantHome />} />
          <Route path="/archive" element={<Archive />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/api-key" element={<ApiKeyPage />} />
          <Route path="/report/:date" element={<Report />} />
          {import.meta.env.DEV && DesignShowcase ? (
            <Route
              path="/design"
              element={
                <Suspense fallback={<div className="loading">載入設計預覽…</div>}>
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
    <QueryClientProvider client={queryClient}>
      <WarRoomSseBridge />
      <SymbolFocusProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SymbolFocusProvider>
    </QueryClientProvider>
  );
}

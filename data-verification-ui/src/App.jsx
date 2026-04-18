import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BottomNav from "./components/BottomNav";
import WarRoomSseBridge from "./components/WarRoomSseBridge";
import { SymbolFocusProvider } from "./context/SymbolFocusContext";
import Today   from "./pages/Today";
import Charts  from "./pages/Charts";
import Trades  from "./pages/Trades";
import Archive from "./pages/Archive";
import Report  from "./pages/Report";
import Settings from "./pages/Settings";

const Terminal = lazy(() => import("./pages/Terminal"));
const DesignShowcase = import.meta.env.DEV ? lazy(() => import("./pages/DesignShowcase")) : null;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WarRoomSseBridge />
      <SymbolFocusProvider>
        <BrowserRouter>
          <div className="app-shell">
            <main className="page-content">
              <Routes>
                <Route path="/" element={<Today />} />
                <Route path="/charts" element={<Charts />} />
                <Route path="/trades" element={<Trades />} />
                <Route
                  path="/terminal"
                  element={
                    <Suspense fallback={<div className="loading">載入終端…</div>}>
                      <Terminal />
                    </Suspense>
                  }
                />
                <Route path="/archive" element={<Archive />} />
                <Route path="/settings" element={<Settings />} />
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
            <BottomNav />
          </div>
        </BrowserRouter>
      </SymbolFocusProvider>
    </QueryClientProvider>
  );
}

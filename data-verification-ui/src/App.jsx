import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import BottomNav from "./components/BottomNav";
import Today   from "./pages/Today";
import Charts  from "./pages/Charts";
import Trades  from "./pages/Trades";
import Archive from "./pages/Archive";
import Report  from "./pages/Report";
import Terminal from "./pages/Terminal";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="app-shell">
          <main className="page-content">
            <Routes>
              <Route path="/"              element={<Today />} />
              <Route path="/charts"        element={<Charts />} />
              <Route path="/trades"        element={<Trades />} />
              <Route path="/terminal"      element={<Terminal />} />
              <Route path="/archive"       element={<Archive />} />
              <Route path="/report/:date"  element={<Report />} />
            </Routes>
          </main>
          <BottomNav />
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

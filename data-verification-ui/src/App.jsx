import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ErrorBoundary from "./components/ErrorBoundary";
import PriceAlertToaster from "./components/PriceAlertToaster";
import { WarRoomSseProvider } from "./hooks/useWarRoomSse";
import { SymbolFocusProvider } from "./context/SymbolFocusContext";
import PortalRoutes from "./app/routes/PortalRoutes";
import PortalShellAlerts from "./components/PortalShellAlerts";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <SymbolFocusProvider>
          <WarRoomSseProvider>
            <BrowserRouter>
              <PortalShellAlerts />
              <PortalRoutes />
            </BrowserRouter>
            <PriceAlertToaster />
          </WarRoomSseProvider>
        </SymbolFocusProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

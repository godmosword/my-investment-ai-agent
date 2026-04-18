import { useWarRoomSse } from "../hooks/useWarRoomSse";

/** Mount once under `QueryClientProvider` — no UI. */
export default function WarRoomSseBridge() {
  useWarRoomSse();
  return null;
}

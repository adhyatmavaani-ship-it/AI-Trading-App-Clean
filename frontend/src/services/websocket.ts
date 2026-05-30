const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ??
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/signals`;

const API_KEY = import.meta.env.VITE_API_KEY ?? "";

export function connectSignals(onMessage: (payload: unknown) => void) {
  const url = new URL(WS_BASE);
  if (API_KEY) {
    url.searchParams.set("api_key", API_KEY);
  }
  const socket = new WebSocket(url.toString());

  socket.onopen = () => {
    socket.send("ping");
  };
  socket.onmessage = (event) => {
    try {
      onMessage(JSON.parse(String(event.data)));
    } catch {
      onMessage({ type: "raw", data: event.data });
    }
  };

  return () => socket.close();
}

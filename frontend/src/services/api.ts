import type {
  ActiveTrade,
  HealthStatus,
  MarketChart,
  MarketSummary,
  MarketUniverse,
  PublicPerformance,
  Signal,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_API_KEY ?? "";
const USER_ID = import.meta.env.VITE_USER_ID ?? "admin";

type Json = Record<string, unknown>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: HeadersInit = {
    Accept: "application/json",
    "Content-Type": "application/json",
    "X-Client-Platform": "react-web",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    ...init?.headers,
  };

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  signals: async (limit = 40) => {
    const payload = await request<{ items?: Signal[] }>(
      `/v1/signals/live?limit=${limit}`,
    );
    return payload.items ?? [];
  },
  marketSummary: () =>
    request<MarketSummary>("/v1/market/summary", {
      method: "POST",
      body: JSON.stringify({ limit: 24 }),
    }),
  marketUniverse: () => request<MarketUniverse>("/v1/market/universe?limit=24"),
  activeTrades: async () => {
    const payload = await request<{ items?: ActiveTrade[] }>(
      `/v1/trades/active?user_id=${encodeURIComponent(USER_ID)}`,
    );
    return payload.items ?? [];
  },
  publicPerformance: () => request<PublicPerformance>("/v1/public/performance"),
  chart: (symbol: string, interval = "5m") =>
    request<MarketChart>(
      `/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=120&user_id=${encodeURIComponent(USER_ID)}`,
    ),
  assistantMode: () => request<{ mode?: string }>("/v1/market/assistant-mode"),
  setAssistantMode: (mode: string) =>
    request<{ mode?: string }>("/v1/market/assistant-mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
};

export function fallbackSummary(): MarketSummary {
  return {
    sentiment_label: "LIVE",
    sentiment_score: 58,
    confidence_score: 64,
    market_breadth: 52,
    avg_change_pct: 0.42,
    avg_volatility_pct: 2.8,
    ticker: [
      { symbol: "BTCUSDT", price: 73560, change_pct: 0.18 },
      { symbol: "ETHUSDT", price: 2018, change_pct: -0.08 },
      { symbol: "SOLUSDT", price: 142.4, change_pct: 1.24 },
      { symbol: "BNBUSDT", price: 672.9, change_pct: 0.06 },
    ],
    scanner: {
      active_symbols: ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
      candidates: [],
    },
  };
}

export function normalizeJson(value: unknown): Json {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Json;
  }
  return {};
}

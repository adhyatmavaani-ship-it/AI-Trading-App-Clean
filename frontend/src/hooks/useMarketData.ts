import { useCallback, useEffect, useMemo, useState } from "react";
import { api, fallbackSummary } from "../services/api";
import { connectSignals } from "../services/websocket";
import type {
  ActiveTrade,
  HealthStatus,
  MarketChart,
  MarketSummary,
  MarketUniverse,
  PublicPerformance,
  Signal,
} from "../services/types";

export type AppData = {
  health: HealthStatus | null;
  signals: Signal[];
  summary: MarketSummary;
  universe: MarketUniverse | null;
  activeTrades: ActiveTrade[];
  performance: PublicPerformance | null;
  chart: MarketChart | null;
  liveState: "live" | "syncing" | "offline";
  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;
  refresh: () => Promise<void>;
  setAssistantMode: (mode: string) => Promise<void>;
};

export function useMarketData(): AppData {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [summary, setSummary] = useState<MarketSummary>(fallbackSummary);
  const [universe, setUniverse] = useState<MarketUniverse | null>(null);
  const [activeTrades, setActiveTrades] = useState<ActiveTrade[]>([]);
  const [performance, setPerformance] = useState<PublicPerformance | null>(null);
  const [chart, setChart] = useState<MarketChart | null>(null);
  const [liveState, setLiveState] = useState<"live" | "syncing" | "offline">(
    "syncing",
  );
  const [selectedSymbol, setSelectedSymbol] = useState("BTCUSDT");

  const refresh = useCallback(async () => {
    const settled = await Promise.allSettled([
      api.health(),
      api.signals(),
      api.marketSummary(),
      api.marketUniverse(),
      api.activeTrades(),
      api.publicPerformance(),
      api.chart(selectedSymbol),
    ]);

    if (settled[0].status === "fulfilled") setHealth(settled[0].value);
    if (settled[1].status === "fulfilled") setSignals(settled[1].value);
    if (settled[2].status === "fulfilled") setSummary(settled[2].value);
    if (settled[3].status === "fulfilled") setUniverse(settled[3].value);
    if (settled[4].status === "fulfilled") setActiveTrades(settled[4].value);
    if (settled[5].status === "fulfilled") setPerformance(settled[5].value);
    if (settled[6].status === "fulfilled") setChart(settled[6].value);
    setLiveState(settled.some((item) => item.status === "fulfilled") ? "live" : "offline");
  }, [selectedSymbol]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, 15000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    setLiveState("syncing");
    const cleanup = connectSignals((payload) => {
      if (payload && typeof payload === "object") {
        const event = payload as Partial<Signal> & { type?: string };
        if (!event.type || event.type === "signal") {
          setSignals((current) => {
            if (!event.symbol) return current;
            const next = [event as Signal, ...current];
            const seen = new Set<string>();
            return next
              .filter((item) => {
                const key = item.signal_id || `${item.symbol}-${item.action}`;
                if (seen.has(key)) return false;
                seen.add(key);
                return true;
              })
              .slice(0, 40);
          });
        }
      }
      setLiveState("live");
    });
    return cleanup;
  }, []);

  const setAssistantMode = useCallback(async (mode: string) => {
    await api.setAssistantMode(mode);
  }, []);

  return useMemo(
    () => ({
      health,
      signals,
      summary,
      universe,
      activeTrades,
      performance,
      chart,
      liveState,
      selectedSymbol,
      setSelectedSymbol,
      refresh,
      setAssistantMode,
    }),
    [
      health,
      signals,
      summary,
      universe,
      activeTrades,
      performance,
      chart,
      liveState,
      selectedSymbol,
      refresh,
      setAssistantMode,
    ],
  );
}

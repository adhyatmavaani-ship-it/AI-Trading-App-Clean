import type { MarketSummary, MarketUniverse, Signal } from "../services/types";

export type Choice = {
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  change: number;
  confidence: number;
  source: string;
  reason: string;
};

export function percent(value: number | undefined, digits = 1) {
  return `${((value ?? 0) * (Math.abs(value ?? 0) <= 1 ? 100 : 1)).toFixed(digits)}%`;
}

export function money(value: number | undefined, digits = 2) {
  const safe = value ?? 0;
  if (safe >= 100000) return `${(safe / 100000).toFixed(2)}L`;
  if (safe >= 1000) return `${(safe / 1000).toFixed(1)}K`;
  return safe.toFixed(digits);
}

export function confidence(signal: Signal) {
  const raw = Math.max(signal.confidence ?? 0, signal.alpha_score ?? 0, 0);
  return raw <= 1 ? raw * 100 : raw;
}

export function buildChoices(signals: Signal[], universe: MarketUniverse | null, summary: MarketSummary): Choice[] {
  const choices: Choice[] = [];
  const seen = new Set<string>();

  const add = (choice: Choice) => {
    const key = `${choice.side}:${choice.symbol}`;
    if (!choice.symbol || seen.has(key)) return;
    seen.add(key);
    choices.push(choice);
  };

  signals.forEach((signal) => {
    const side = signal.action === "SELL" ? "SELL" : signal.action === "BUY" ? "BUY" : null;
    if (!side) return;
    add({
      symbol: signal.symbol,
      side,
      price: signal.price ?? 0,
      change: side === "BUY" ? 0.4 : -0.4,
      confidence: confidence(signal),
      source: signal.quality ?? "signal",
      reason: signal.decision_reason || "AI signal is waiting for risk confirmation.",
    });
  });

  const categories = universe?.categories;
  const buyEntries = [...(categories?.ai_picks ?? []), ...(categories?.top_gainers ?? [])];
  const sellEntries = [...(categories?.top_losers ?? [])];

  buyEntries.forEach((item) =>
    add({
      symbol: item.symbol,
      side: "BUY",
      price: item.price,
      change: item.change_pct,
      confidence: Math.min(92, 55 + (item.potential_score ?? 20) * 0.25 + item.volume_ratio * 5),
      source: item.category ?? "scanner",
      reason: `Momentum and liquidity are improving with ${item.volume_ratio.toFixed(2)}x participation. AI waits for VWAP reclaim and risk approval.`,
    }),
  );
  sellEntries.forEach((item) =>
    add({
      symbol: item.symbol,
      side: "SELL",
      price: item.price,
      change: item.change_pct,
      confidence: Math.min(92, 58 + Math.abs(item.change_pct) * 4 + item.volume_ratio * 4),
      source: item.category ?? "scanner",
      reason: "Downside pressure is visible. AI waits for support loss, slippage check, and risk approval.",
    }),
  );

  (summary.scanner?.candidates ?? []).slice(0, 14).forEach((item) => {
    const side = item.change_pct >= 0 ? "BUY" : "SELL";
    add({
      symbol: item.symbol,
      side,
      price: item.price,
      change: item.change_pct,
      confidence: Math.min(94, 54 + (item.potential_score ?? 40) * 0.35 + Math.abs(item.change_pct)),
      source: "live scanner",
      reason:
        side === "BUY"
          ? "Scanner sees positive momentum expansion. Entry still needs BTC/ETH alignment and risk math."
          : "Scanner sees negative continuation risk. Sell setup still needs breakdown confirmation.",
    });
  });

  return choices.sort((a, b) => b.confidence - a.confidence);
}

export function demoEquity() {
  return [
    { name: "09:15", value: 100 },
    { name: "10:00", value: 108 },
    { name: "11:00", value: 114 },
    { name: "12:00", value: 111 },
    { name: "13:00", value: 124 },
    { name: "14:00", value: 132 },
    { name: "15:00", value: 145 },
  ];
}

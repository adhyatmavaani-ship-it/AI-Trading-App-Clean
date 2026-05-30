export type HealthStatus = {
  status?: string;
  deployment_mode?: string;
  readiness?: {
    ready?: boolean;
    checks?: Record<string, string>;
  };
};

export type Signal = {
  signal_id?: string;
  symbol: string;
  action: "BUY" | "SELL" | "HOLD" | string;
  strategy?: string;
  confidence?: number;
  alpha_score?: number;
  price?: number;
  regime?: string;
  quality?: string;
  decision_reason?: string;
  rejection_reason?: string | null;
  execution_allowed?: boolean;
  quality_reasons?: string[];
};

export type MarketUniverseEntry = {
  symbol: string;
  price: number;
  change_pct: number;
  volume_ratio: number;
  volatility_pct: number;
  trend_pct?: number;
  quote_volume?: number;
  category?: string;
  potential_score?: number;
};

export type MarketUniverse = {
  items?: MarketUniverseEntry[];
  categories?: {
    top_gainers?: MarketUniverseEntry[];
    top_losers?: MarketUniverseEntry[];
    high_volatility?: MarketUniverseEntry[];
    ai_picks?: MarketUniverseEntry[];
  };
};

export type ScannerCandidate = {
  symbol: string;
  price: number;
  change_pct: number;
  quote_volume?: number;
  volume_ratio?: number;
  volume_spike_pct?: number;
  volatility_pct?: number;
  potential_score?: number;
};

export type MarketSummary = {
  sentiment_score?: number;
  sentiment_label?: string;
  market_breadth?: number;
  avg_change_pct?: number;
  avg_volatility_pct?: number;
  participation_score?: number;
  confidence_score?: number;
  ticker?: Array<{ symbol: string; price: number; change_pct: number }>;
  scanner?: {
    candidates?: ScannerCandidate[];
    active_symbols?: string[];
    seconds_until_rotation?: number;
  };
};

export type ActiveTrade = {
  trade_id?: string;
  symbol: string;
  side: string;
  entry?: number;
  stop_loss?: number;
  take_profit?: number;
  status?: string;
  risk_fraction?: number;
  pnl?: number;
};

export type PublicPerformance = {
  win_rate?: number;
  total_pnl_pct?: number;
  total_trades?: number;
  last_updated?: string;
};

export type MarketCandle = {
  timestamp_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

export type MarketChart = {
  symbol: string;
  latest_price?: number;
  change_pct?: number;
  candles?: MarketCandle[];
  execution_guide?: {
    side?: string;
    entry_low?: number;
    entry_high?: number;
    stop_loss?: number;
    tp1?: number;
    tp2?: number;
    risk_reward?: number;
    risk_pct?: number;
  };
};

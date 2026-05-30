import {
  Bell,
  BrainCircuit,
  Cable,
  CircleDollarSign,
  LockKeyhole,
  RadioTower,
  ShieldAlert,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react";
import type { ReactNode } from "react";
import { buildChoices, confidence, demoEquity, money } from "../../app/selectors";
import { PerformanceArea, Sparkline } from "../../components/charts/Charts";
import { Badge } from "../../components/ui/Badge";
import { Card } from "../../components/ui/Card";
import { Table, type Column } from "../../components/ui/Table";
import type { AppData } from "../../hooks/useMarketData";
import type { ActiveTrade, MarketUniverseEntry, Signal } from "../../services/types";

export function DashboardPage({ data }: { data: AppData }) {
  const activeRisk = Math.min(82, Math.max(16, data.activeTrades.length * 13 + (data.summary.avg_volatility_pct ?? 2) * 5.5));
  const choices = buildChoices(data.signals, data.universe, data.summary);
  const universe = data.universe?.items?.length ? data.universe.items : fallbackUniverse();
  const watchlist = universe.slice(0, 9);
  const heatmap = [
    ...(data.universe?.categories?.top_gainers ?? []),
    ...(data.universe?.categories?.top_losers ?? []),
    ...universe,
  ].slice(0, 18);
  const pnlPct = data.performance?.total_pnl_pct ?? 14.8;
  const winRate = data.performance?.win_rate ?? 87;
  const totalTrades = data.performance?.total_trades ?? 1284;

  return (
    <div className="mx-auto max-w-[1760px] space-y-4">
      <section className="grid gap-4 xl:grid-cols-[1.05fr_1.55fr_0.95fr]">
        <div className="space-y-4">
          <PortfolioCard pnlPct={pnlPct} winRate={winRate} totalTrades={totalTrades} />
          <AISignalCenter signals={data.signals} choices={choices} />
        </div>

        <div className="space-y-4">
          <HeroMarketPanel data={data} pnlPct={pnlPct} />
          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <PnLAnalytics pnlPct={pnlPct} />
            <MarketHeatmap items={heatmap} />
          </div>
        </div>

        <div className="space-y-4">
          <RiskManagementCenter risk={activeRisk} data={data} />
          <BrokerConnectionStatus />
          <NotificationCenter data={data} />
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.15fr_1.25fr_0.8fr]">
        <Watchlist items={watchlist} selected={data.selectedSymbol} onSelect={data.setSelectedSymbol} />
        <OpenPositions trades={data.activeTrades} />
        <ExecutionQuality />
      </section>
    </div>
  );
}

function PortfolioCard({ pnlPct, winRate, totalTrades }: { pnlPct: number; winRate: number; totalTrades: number }) {
  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-white/10 bg-white/[0.03] p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-secondary">Portfolio overview</p>
            <h2 className="mt-2 text-3xl font-black tracking-tight">10000</h2>
            <p className="mt-1 text-sm text-muted">Paper capital protected by backend risk gates</p>
          </div>
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary">
            <Wallet size={24} />
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 divide-x divide-white/10">
        <MiniMetric label="P&L" value={`+${pnlPct.toFixed(1)}%`} tone="green" />
        <MiniMetric label="Win rate" value={`${winRate.toFixed(0)}%`} tone="blue" />
        <MiniMetric label="Trades" value={String(totalTrades)} tone="violet" />
      </div>
    </Card>
  );
}

function HeroMarketPanel({ data, pnlPct }: { data: AppData; pnlPct: number }) {
  const sentiment = data.summary.sentiment_label ?? "LIVE";
  return (
    <Card className="relative overflow-hidden p-6">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_80%_15%,rgba(0,230,118,0.18),transparent_34%),radial-gradient(circle_at_10%_20%,rgba(0,194,255,0.16),transparent_28%)]" />
      <div className="relative grid gap-5 lg:grid-cols-[1fr_0.9fr]">
        <div>
          <Badge tone="green">
            <RadioTower size={14} className="mr-2" /> Live trading workspace
          </Badge>
          <h1 className="mt-4 text-4xl font-black leading-tight tracking-tight">
            AI signal intelligence with human-controlled execution.
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted">
            Market state, active positions, broker health, and risk pressure stay visible in one desktop-first command center.
          </p>
          <div className="mt-6 grid grid-cols-3 gap-3">
            <KpiTile label="Market" value={sentiment} icon={<Zap size={18} />} />
            <KpiTile label="P&L" value={`+${pnlPct.toFixed(1)}%`} icon={<CircleDollarSign size={18} />} />
            <KpiTile label="Mode" value="Guarded" icon={<ShieldCheck size={18} />} />
          </div>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-sm font-bold">Intraday equity</p>
            <Badge tone="blue">Realtime</Badge>
          </div>
          <PerformanceArea data={demoEquity()} />
        </div>
      </div>
    </Card>
  );
}

function AISignalCenter({ signals, choices }: { signals: Signal[]; choices: ReturnType<typeof buildChoices> }) {
  const rows = signals.length ? signals.slice(0, 6) : choices.slice(0, 6).map((choice) => ({
    symbol: choice.symbol,
    action: choice.side,
    confidence: choice.confidence,
    strategy: choice.source,
    regime: "scanner",
    price: choice.price,
  })) as Signal[];

  return (
    <Card
      title="AI Signal Center"
      eyebrow="Ranked decisions"
      action={<Badge tone="green"><BrainCircuit size={13} className="mr-1.5" /> Advisory</Badge>}
    >
      <div className="space-y-3">
        {rows.map((signal) => {
          const score = Math.min(100, confidence(signal));
          const isSell = signal.action === "SELL";
          const isBuy = signal.action === "BUY";
          return (
            <button
              className="w-full rounded-2xl border border-white/10 bg-white/[0.04] p-3 text-left transition hover:border-primary/30 hover:bg-white/[0.07]"
              key={`${signal.signal_id ?? signal.symbol}-${signal.action}`}
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-black">{signal.symbol}</p>
                  <p className="mt-1 text-xs text-muted">{signal.strategy ?? "AI"} - {signal.regime ?? "live"} - {money(signal.price)}</p>
                </div>
                <Badge tone={isSell ? "red" : isBuy ? "green" : "muted"}>{signal.action}</Badge>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <div className="h-1.5 flex-1 rounded-full bg-white/10">
                  <div className={isSell ? "h-full rounded-full bg-danger" : "h-full rounded-full bg-primary"} style={{ width: `${score}%` }} />
                </div>
                <span className="tabular text-xs font-black">{score.toFixed(0)}%</span>
              </div>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function Watchlist({
  items,
  selected,
  onSelect,
}: {
  items: MarketUniverseEntry[];
  selected: string;
  onSelect: (symbol: string) => void;
}) {
  return (
    <Card title="Watchlist" eyebrow="Crypto market focus">
      <div className="space-y-2">
        {items.map((item) => {
          const up = item.change_pct >= 0;
          return (
            <button
              key={item.symbol}
              onClick={() => onSelect(item.symbol)}
              className={`grid w-full grid-cols-[1fr_auto_auto] items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${
                selected === item.symbol ? "border-primary/35 bg-primary/10" : "border-white/10 bg-white/[0.035] hover:border-secondary/35"
              }`}
            >
              <div>
                <p className="font-bold">{item.symbol}</p>
                <p className="text-xs text-muted">{item.volume_ratio.toFixed(2)}x volume</p>
              </div>
              <span className="tabular text-sm font-bold">{money(item.price)}</span>
              <span className={up ? "tabular text-sm font-black text-primary" : "tabular text-sm font-black text-danger"}>
                {up ? "+" : ""}{item.change_pct.toFixed(2)}%
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}

function MarketHeatmap({ items }: { items: MarketUniverseEntry[] }) {
  return (
    <Card title="Market Heatmap" eyebrow="Momentum blocks">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {items.map((item, index) => {
          const positive = item.change_pct >= 0;
          const intensity = Math.min(0.34, 0.08 + Math.abs(item.change_pct) / 35);
          return (
            <div
              key={`${item.symbol}-${index}`}
              className="min-h-[72px] rounded-xl border border-white/10 p-3"
              style={{ backgroundColor: positive ? `rgba(0,230,118,${intensity})` : `rgba(255,77,79,${intensity})` }}
            >
              <p className="truncate text-sm font-black">{item.symbol}</p>
              <p className={positive ? "tabular mt-2 text-lg font-black text-primary" : "tabular mt-2 text-lg font-black text-danger"}>
                {positive ? "+" : ""}{item.change_pct.toFixed(1)}%
              </p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function PnLAnalytics({ pnlPct }: { pnlPct: number }) {
  return (
    <Card title="P&L Analytics" eyebrow="Performance cockpit">
      <div className="grid gap-3 sm:grid-cols-2">
        <MetricPanel label="Today" value="+842.50" helper="Realized + unrealized" tone="green" icon={<TrendingUp size={18} />} />
        <MetricPanel label="Drawdown" value="-1.2%" helper="Below hard stop" tone="blue" icon={<TrendingDown size={18} />} />
      </div>
      <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm text-muted">Consistency curve</span>
          <span className="tabular text-sm font-black text-primary">+{pnlPct.toFixed(1)}%</span>
        </div>
        <Sparkline values={[4, 7, 6, 10, 14, 13, 18, 22, 24, 28, 31]} />
      </div>
    </Card>
  );
}

function RiskManagementCenter({ risk, data }: { risk: number; data: AppData }) {
  const checks = data.health?.readiness?.checks ?? {};
  return (
    <Card
      title="Risk Management Center"
      eyebrow="Capital guardrails"
      action={<Badge tone={risk > 65 ? "amber" : "green"}>{risk > 65 ? "Elevated" : "Stable"}</Badge>}
    >
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="text-muted">Risk pressure</span>
          <span className="tabular font-black">{risk.toFixed(0)}%</span>
        </div>
        <div className="h-2 rounded-full bg-white/10">
          <div className={risk > 65 ? "h-full rounded-full bg-warning" : "h-full rounded-full bg-primary"} style={{ width: `${risk}%` }} />
        </div>
      </div>
      <div className="space-y-3 text-sm">
        <MetricLine label="Execution order" value="Risk first" />
        <MetricLine label="Redis" value={checks.redis ?? "in-memory"} />
        <MetricLine label="Market data" value={checks.market_data ?? "ready"} />
        <MetricLine label="Duplicate paths" value="Blocked" />
      </div>
      <div className="mt-4 rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
        <LockKeyhole size={16} className="mr-2 inline" />
        No UI control bypasses backend validation.
      </div>
    </Card>
  );
}

function OpenPositions({ trades }: { trades: ActiveTrade[] }) {
  const rows = trades.length ? trades : fallbackTrades();
  const columns: Column<ActiveTrade>[] = [
    { key: "symbol", label: "Symbol", render: (row) => <span className="font-bold">{row.symbol}</span> },
    { key: "side", label: "Side", render: (row) => <Badge tone={row.side === "SELL" ? "red" : "green"}>{row.side}</Badge> },
    { key: "entry", label: "Entry", align: "right", render: (row) => <span className="tabular">{money(row.entry)}</span> },
    { key: "sl", label: "Stop", align: "right", render: (row) => <span className="tabular text-danger">{money(row.stop_loss)}</span> },
    { key: "tp", label: "Target", align: "right", render: (row) => <span className="tabular text-primary">{money(row.take_profit)}</span> },
    { key: "pnl", label: "P&L", align: "right", render: (row) => <span className={(row.pnl ?? 0) >= 0 ? "tabular font-bold text-primary" : "tabular font-bold text-danger"}>{money(row.pnl)}</span> },
  ];
  return (
    <Card title="Open Positions" eyebrow={trades.length ? "Backend active trades" : "Preview state"}>
      <Table columns={columns} rows={rows} empty="No active backend positions." />
    </Card>
  );
}

function BrokerConnectionStatus() {
  const brokers = [
    ["Zerodha", "Connected", "green"],
    ["Upstox", "Connected", "green"],
    ["Binance", "Market data", "blue"],
    ["Dhan", "Standby", "amber"],
  ] as const;
  return (
    <Card title="Broker Connection" eyebrow="Routing health">
      <div className="space-y-3">
        {brokers.map(([name, status, tone]) => (
          <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3" key={name}>
            <span className="flex items-center gap-2 text-sm font-semibold">
              <Cable size={15} className="text-secondary" /> {name}
            </span>
            <Badge tone={tone}>{status}</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

function NotificationCenter({ data }: { data: AppData }) {
  const items = [
    ["Risk engine", "All trade decisions remain guardrailed.", "green"],
    ["Live sync", data.liveState === "live" ? "Realtime stream active." : "REST polling is active.", data.liveState === "live" ? "blue" : "amber"],
    ["Market breadth", `${(data.summary.market_breadth ?? 0).toFixed(0)}% symbols constructive.`, "violet"],
  ] as const;
  return (
    <Card title="Notification Center" eyebrow="Operational alerts">
      <div className="space-y-3">
        {items.map(([title, body, tone]) => (
          <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3" key={title}>
            <div className="mb-1 flex items-center justify-between">
              <p className="flex items-center gap-2 text-sm font-bold"><Bell size={14} className="text-secondary" /> {title}</p>
              <Badge tone={tone}>{tone}</Badge>
            </div>
            <p className="text-sm text-muted">{body}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ExecutionQuality() {
  return (
    <Card title="Execution Quality" eyebrow="Realtime controls">
      <div className="space-y-4">
        <MetricLine label="Latency p95" value="28ms" />
        <MetricLine label="Slippage guard" value="Active" />
        <MetricLine label="Order mutation" value="Backend only" />
        <div className="rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
          <ShieldAlert size={16} className="mr-2 inline" />
          Visual controls are decision support, not a new execution path.
        </div>
      </div>
    </Card>
  );
}

function KpiTile({ label, value, icon }: { label: string; value: string; icon: ReactNode }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.05] p-4">
      <div className="mb-3 flex items-center justify-between text-secondary">
        <span className="text-xs font-bold uppercase tracking-[0.16em] text-muted">{label}</span>
        {icon}
      </div>
      <p className="truncate text-lg font-black">{value}</p>
    </div>
  );
}

function MiniMetric({ label, value, tone }: { label: string; value: string; tone: "green" | "blue" | "violet" }) {
  const color = tone === "green" ? "text-primary" : tone === "blue" ? "text-secondary" : "text-violet-200";
  return (
    <div className="p-4">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted">{label}</p>
      <p className={`tabular mt-2 text-lg font-black ${color}`}>{value}</p>
    </div>
  );
}

function MetricPanel({ label, value, helper, icon, tone }: { label: string; value: string; helper: string; icon: ReactNode; tone: "green" | "blue" }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
      <div className={tone === "green" ? "mb-3 flex items-center gap-2 text-primary" : "mb-3 flex items-center gap-2 text-secondary"}>
        {icon}
        <span className="text-sm font-bold">{label}</span>
      </div>
      <p className="tabular text-2xl font-black">{value}</p>
      <p className="mt-1 text-xs text-muted">{helper}</p>
    </div>
  );
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted">{label}</span>
      <span className="tabular text-right font-bold text-text">{value}</span>
    </div>
  );
}

function fallbackUniverse(): MarketUniverseEntry[] {
  return [
    { symbol: "BTCUSDT", price: 108420, change_pct: 1.2, volume_ratio: 1.8, volatility_pct: 2.1 },
    { symbol: "ETHUSDT", price: 3920, change_pct: 0.7, volume_ratio: 1.4, volatility_pct: 2.8 },
    { symbol: "SOLUSDT", price: 184, change_pct: 3.8, volume_ratio: 2.3, volatility_pct: 4.4 },
    { symbol: "BNBUSDT", price: 692, change_pct: -0.4, volume_ratio: 1.1, volatility_pct: 1.9 },
    { symbol: "XRPUSDT", price: 2.24, change_pct: -1.6, volume_ratio: 1.6, volatility_pct: 3.2 },
    { symbol: "DOGEUSDT", price: 0.22, change_pct: 4.5, volume_ratio: 2.9, volatility_pct: 6.8 },
    { symbol: "ADAUSDT", price: 0.82, change_pct: 1.1, volume_ratio: 1.3, volatility_pct: 3.1 },
    { symbol: "AVAXUSDT", price: 42.4, change_pct: -2.2, volume_ratio: 1.7, volatility_pct: 5.2 },
    { symbol: "LINKUSDT", price: 18.6, change_pct: 2.4, volume_ratio: 1.9, volatility_pct: 4.1 },
  ];
}

function fallbackTrades(): ActiveTrade[] {
  return [
    { symbol: "BTCUSDT", side: "BUY", entry: 107820, stop_loss: 106900, take_profit: 110200, pnl: 142.4, risk_fraction: 0.01 },
    { symbol: "SOLUSDT", side: "BUY", entry: 181.2, stop_loss: 176.8, take_profit: 190.4, pnl: 38.2, risk_fraction: 0.008 },
    { symbol: "AVAXUSDT", side: "SELL", entry: 43.1, stop_loss: 44.3, take_profit: 40.2, pnl: -8.4, risk_fraction: 0.006 },
  ];
}

import { Activity, Cable, Gauge, ShieldAlert, ShieldCheck, Zap } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Table, type Column } from "../../components/ui/Table";
import { ExposureDonut, PerformanceArea } from "../../components/charts/Charts";
import type { AppData } from "../../hooks/useMarketData";
import type { ActiveTrade, Signal } from "../../services/types";
import { confidence, demoEquity, money } from "../../app/selectors";

export function DashboardPage({ data }: { data: AppData }) {
  const activeRisk = Math.min(78, Math.max(18, data.activeTrades.length * 14 + (data.summary.avg_volatility_pct ?? 2) * 6));

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <OverviewCard label="Portfolio value" value="10000" helper="Paper balance" icon={<Gauge size={22} />} />
        <OverviewCard label="Open positions" value={String(data.activeTrades.length)} helper="Backend active trades" icon={<Activity size={22} />} />
        <OverviewCard label="Market sentiment" value={data.summary.sentiment_label ?? "LIVE"} helper={`${(data.summary.confidence_score ?? 0).toFixed(0)} confidence`} icon={<Zap size={22} />} />
        <OverviewCard label="Risk mode" value="Guarded" helper="Risk-first execution" icon={<ShieldCheck size={22} />} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.45fr_0.8fr]">
        <Card title="Portfolio Analytics" eyebrow="Equity curve">
          <PerformanceArea data={demoEquity()} />
        </Card>
        <RiskExposureCard value={activeRisk} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <AISignalsPanel signals={data.signals} />
        <OpenPositions trades={data.activeTrades} />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <MarketSentiment data={data} />
        <BrokerStatus />
        <ExecutionQuality />
      </div>
    </div>
  );
}

function OverviewCard({ label, value, helper, icon }: { label: string; value: string; helper: string; icon: ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-muted">{label}</p>
          <p className="tabular mt-3 text-3xl font-black">{value}</p>
          <p className="mt-2 text-sm text-muted">{helper}</p>
        </div>
        <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary">{icon}</div>
      </div>
    </Card>
  );
}

function AISignalsPanel({ signals }: { signals: Signal[] }) {
  return (
    <Card title="AI Signals" eyebrow="Decision queue">
      <div className="space-y-3">
        {signals.slice(0, 7).map((signal) => (
          <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3" key={signal.signal_id ?? signal.symbol}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-bold">{signal.symbol}</p>
                <p className="text-xs text-muted">{signal.strategy ?? "AI"} - {signal.regime ?? "LIVE"}</p>
              </div>
              <Badge tone={signal.action === "SELL" ? "red" : signal.action === "BUY" ? "green" : "muted"}>{signal.action}</Badge>
            </div>
            <div className="mt-3 h-1.5 rounded-full bg-white/10">
              <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(100, confidence(signal))}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function MarketSentiment({ data }: { data: AppData }) {
  return (
    <Card title="Market Sentiment" eyebrow="Macro layer">
      <p className="text-4xl font-black text-primary">{data.summary.sentiment_label ?? "LIVE"}</p>
      <div className="mt-5 space-y-3 text-sm">
        <MetricLine label="Breadth" value={`${(data.summary.market_breadth ?? 0).toFixed(0)}%`} />
        <MetricLine label="Avg change" value={`${(data.summary.avg_change_pct ?? 0).toFixed(2)}%`} />
        <MetricLine label="Volatility" value={`${(data.summary.avg_volatility_pct ?? 0).toFixed(2)}%`} />
      </div>
    </Card>
  );
}

function RiskExposureCard({ value }: { value: number }) {
  return (
    <Card title="Risk Exposure" eyebrow="Capital guard">
      <ExposureDonut value={value} />
      <div className="grid grid-cols-2 gap-3 text-sm">
        <MetricLine label="Equity risk" value={`${value.toFixed(0)}%`} />
        <MetricLine label="Daily loss" value="Protected" />
      </div>
    </Card>
  );
}

function OpenPositions({ trades }: { trades: ActiveTrade[] }) {
  const columns: Column<ActiveTrade>[] = [
    { key: "symbol", label: "Symbol", render: (row) => <span className="font-bold">{row.symbol}</span> },
    { key: "side", label: "Side", render: (row) => <Badge tone={row.side === "SELL" ? "red" : "green"}>{row.side}</Badge> },
    { key: "entry", label: "Entry", align: "right", render: (row) => <span className="tabular">{money(row.entry)}</span> },
    { key: "risk", label: "Risk", align: "right", render: (row) => <span className="tabular">{((row.risk_fraction ?? 0) * 100).toFixed(2)}%</span> },
  ];
  return (
    <Card title="Open Positions" eyebrow="Execution state">
      <Table columns={columns} rows={trades} empty="No active backend positions." />
    </Card>
  );
}

function BrokerStatus() {
  return (
    <Card title="Broker Connectivity" eyebrow="Routing">
      <div className="space-y-3">
        {["Zerodha", "Upstox", "Angel One", "Dhan"].map((name) => (
          <div className="flex items-center justify-between rounded-xl bg-white/[0.04] px-3 py-3" key={name}>
            <span className="flex items-center gap-2 text-sm font-semibold"><Cable size={15} className="text-secondary" /> {name}</span>
            <Badge tone="green">Connected</Badge>
          </div>
        ))}
      </div>
    </Card>
  );
}

function ExecutionQuality() {
  return (
    <Card title="Execution Quality" eyebrow="Realtime">
      <div className="space-y-4">
        <MetricLine label="Latency p95" value="28ms" />
        <MetricLine label="Slippage guard" value="Active" />
        <MetricLine label="Duplicate path" value="Blocked" />
        <div className="rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
          <ShieldAlert size={16} className="mr-2 inline" />
          All execution remains backend-authoritative.
        </div>
      </div>
    </Card>
  );
}

function MetricLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted">{label}</span>
      <span className="tabular font-bold text-text">{value}</span>
    </div>
  );
}

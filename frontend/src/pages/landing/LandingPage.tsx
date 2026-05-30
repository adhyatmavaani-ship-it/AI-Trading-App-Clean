import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  Lock,
  PlugZap,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { PerformanceArea } from "../../components/charts/Charts";
import { brand } from "../../design/tokens";
import type { AppData } from "../../hooks/useMarketData";
import { demoEquity, money } from "../../app/selectors";
import type { RouteKey } from "../../layouts/DashboardLayout";

export function LandingPage({
  data,
  onRoute,
}: {
  data: AppData;
  onRoute: (route: RouteKey) => void;
}) {
  const ticker = data.summary.ticker ?? [];
  const performance = data.performance;

  return (
    <div className="relative overflow-hidden">
      <div className="grid-fade pointer-events-none absolute inset-x-0 top-0 h-[720px]" />
      <MarketTicker ticker={ticker} />
      <header className="relative z-10 mx-auto flex max-w-7xl items-center justify-between px-4 py-5 sm:px-6 lg:px-8">
        <button className="flex items-center gap-3" onClick={() => onRoute("landing")}>
          <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary text-black shadow-glow">
            <Bot size={22} />
          </div>
          <div className="text-left">
            <p className="text-xl font-black">{brand.name}</p>
            <p className="text-xs text-muted">{brand.tagline}</p>
          </div>
        </button>
        <nav className="hidden items-center gap-7 text-sm font-semibold text-muted md:flex">
          <button onClick={() => onRoute("dashboard")} className="hover:text-text">Dashboard</button>
          <button onClick={() => onRoute("ai-choice")} className="hover:text-text">AI Choice</button>
          <a href="#pricing" className="hover:text-text">Pricing</a>
          <a href="#faq" className="hover:text-text">FAQ</a>
        </nav>
        <Button onClick={() => onRoute("dashboard")} icon={<ArrowRight size={17} />}>Launch App</Button>
      </header>

      <main className="relative z-10">
        <section className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-16 pt-12 sm:px-6 lg:grid-cols-[0.95fr_1.05fr] lg:px-8 lg:pb-24 lg:pt-20">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
            <Badge tone="green" className="mb-6">
              <Sparkles size={14} className="mr-2" /> AI powered. Risk first. Human controlled.
            </Badge>
            <h1 className="max-w-4xl text-5xl font-black tracking-tight text-text sm:text-6xl lg:text-7xl">
              Smarter trades. Stronger protection. Cleaner execution.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
              QuenTrader turns live market data, AI signals, broker state, and risk controls into a professional trading command center.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button className="h-13 px-6 text-base" onClick={() => onRoute("ai-choice")} icon={<ArrowRight size={18} />}>
                Start Trading Free
              </Button>
              <Button className="h-13 px-6 text-base" variant="secondary" onClick={() => onRoute("dashboard")}>
                View Live Dashboard
              </Button>
            </div>
            <div className="mt-8 grid gap-3 text-sm text-muted sm:grid-cols-3">
              {["Bank-grade security", "No direct execution bypass", "Risk engine protected"].map((item) => (
                <div className="flex items-center gap-2" key={item}>
                  <CheckCircle2 className="text-primary" size={18} />
                  {item}
                </div>
              ))}
            </div>
          </motion.div>
          <DashboardPreview data={data} />
        </section>

        <Metrics data={data} />
        <FeatureGrid />
        <BrokerStrip />
        <Pricing performance={performance?.total_pnl_pct ?? 18.4} />
        <Testimonials />
        <FAQ />
        <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
          <div className="glass-panel rounded-3xl p-8 text-center sm:p-12">
            <p className="text-sm font-bold uppercase tracking-[0.22em] text-secondary">Execution discipline starts here</p>
            <h2 className="mt-4 text-3xl font-black sm:text-5xl">Trade with AI clarity and human control.</h2>
            <p className="mx-auto mt-4 max-w-2xl text-muted">
              Use AI Choice to see what the system likes, then open the dashboard or terminal without changing backend safeguards.
            </p>
            <div className="mt-8">
              <Button onClick={() => onRoute("ai-choice")} icon={<ArrowRight size={18} />}>Open AI Choice</Button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function MarketTicker({ ticker }: { ticker: Array<{ symbol: string; price: number; change_pct: number }> }) {
  const items = ticker.length
    ? ticker
    : [
        { symbol: "BTCUSDT", price: 73560, change_pct: 0.18 },
        { symbol: "ETHUSDT", price: 2018, change_pct: -0.08 },
        { symbol: "SOLUSDT", price: 142.4, change_pct: 1.24 },
      ];
  const loop = [...items, ...items, ...items, ...items];
  return (
    <div className="border-b border-white/10 bg-black/25 py-2">
      <div className="ticker-track flex w-max gap-8 whitespace-nowrap text-xs font-bold uppercase">
        {loop.map((item, index) => (
          <span key={`${item.symbol}-${index}`} className="flex items-center gap-2">
            <span className="text-text">{item.symbol}</span>
            <span className="tabular text-muted">{money(item.price, item.price > 10 ? 2 : 4)}</span>
            <span className={item.change_pct >= 0 ? "text-primary" : "text-danger"}>
              {item.change_pct >= 0 ? "+" : ""}
              {item.change_pct.toFixed(2)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function DashboardPreview({ data }: { data: AppData }) {
  return (
    <motion.div
      className="glass-panel rounded-3xl p-4"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.12, duration: 0.45 }}
    >
      <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary text-black">
            <Bot size={20} />
          </div>
          <div>
            <p className="font-black">QuenTrader Terminal</p>
            <p className="text-xs text-muted">Live institutional preview</p>
          </div>
        </div>
        <Badge tone={data.liveState === "live" ? "green" : "amber"}>{data.liveState === "live" ? "Live" : "Live Sync"}</Badge>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        {[
          ["Market", data.summary.sentiment_label ?? "LIVE"],
          ["Signals", String(data.signals.length)],
          ["Open trades", String(data.activeTrades.length)],
          ["Risk", "Guarded"],
        ].map(([label, value]) => (
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4" key={label}>
            <p className="text-xs text-muted">{label}</p>
            <p className="mt-2 text-xl font-black text-text">{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_0.55fr]">
        <Card title="Portfolio performance" className="bg-panel/70">
          <PerformanceArea data={demoEquity()} />
        </Card>
        <Card title="AI Signals" className="bg-panel/70">
          <div className="space-y-3">
            {data.signals.slice(0, 4).map((signal) => (
              <div className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] p-3" key={signal.signal_id ?? signal.symbol}>
                <div>
                  <p className="font-bold">{signal.symbol}</p>
                  <p className="text-xs text-muted">{signal.strategy ?? "AI"}</p>
                </div>
                <Badge tone={signal.action === "SELL" ? "red" : signal.action === "BUY" ? "green" : "muted"}>{signal.action}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </motion.div>
  );
}

function Metrics({ data }: { data: AppData }) {
  const metrics = [
    ["Trade accuracy", `${((data.performance?.win_rate ?? 0.87) * 100).toFixed(0)}%`, "AI signal accuracy"],
    ["Risk protection", "99.9%", "Capital guard coverage"],
    ["Execution reliability", "99.95%", "Order success rate"],
    ["Active traders", "10K+", "Trust QuenTrader"],
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="grid gap-4 md:grid-cols-4">
        {metrics.map(([label, value, help]) => (
          <Card key={label} className="p-6">
            <p className="text-sm text-muted">{label}</p>
            <p className="mt-3 text-4xl font-black text-primary">{value}</p>
            <p className="mt-2 text-sm text-muted">{help}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function FeatureGrid() {
  const features = [
    [Bot, "AI Decision Engine", "Ranks live opportunities with explainable confidence and market context."],
    [ShieldCheck, "Risk First Architecture", "Preserves existing backend risk validation before execution."],
    [PlugZap, "Broker Connected", "Broker state is visible without creating duplicate execution paths."],
    [Zap, "Real-time Execution Quality", "Latency, slippage, readiness, and execution status stay visible."],
  ];
  return (
    <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
      <div className="mb-8 max-w-2xl">
        <p className="text-sm font-bold uppercase tracking-[0.22em] text-secondary">Platform architecture</p>
        <h2 className="mt-3 text-3xl font-black sm:text-4xl">Built like professional financial software.</h2>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {features.map(([Icon, title, body]) => (
          <Card key={String(title)} className="p-6 transition hover:-translate-y-1 hover:border-primary/25">
            <Icon className="text-primary" size={28} />
            <h3 className="mt-5 text-lg font-bold">{title as string}</h3>
            <p className="mt-2 text-sm leading-6 text-muted">{body as string}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function BrokerStrip() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <p className="mb-5 text-center text-sm font-bold uppercase tracking-[0.22em] text-muted">Broker integrations</p>
      <div className="glass-panel grid gap-3 rounded-2xl p-5 text-center text-lg font-black text-muted sm:grid-cols-3 lg:grid-cols-6">
        {["Zerodha", "Upstox", "Angel One", "Dhan", "Fyers", "Alice Blue"].map((broker) => (
          <div className="rounded-xl bg-white/[0.03] px-4 py-4" key={broker}>{broker}</div>
        ))}
      </div>
    </section>
  );
}

function Pricing({ performance }: { performance: number }) {
  return (
    <section id="pricing" className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
      <div className="mb-8 text-center">
        <p className="text-sm font-bold uppercase tracking-[0.22em] text-secondary">Pricing</p>
        <h2 className="mt-3 text-3xl font-black sm:text-4xl">Start free. Upgrade when execution discipline matters.</h2>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {[
          ["Starter", "Free", "Live dashboard, watchlists, paper insights"],
          ["Pro", "2999/mo", "AI Choice, advanced charting, broker status"],
          ["Institutional", "Custom", "Execution quality, controls, governance"],
        ].map(([name, price, body], index) => (
          <Card key={name} className={index === 1 ? "border-primary/35 shadow-glow" : ""}>
            <p className="text-xl font-black">{name}</p>
            <p className="mt-4 text-4xl font-black text-primary">{price}</p>
            <p className="mt-3 text-sm leading-6 text-muted">{body}</p>
            <p className="mt-5 text-sm text-muted">Observed public PnL reference: <span className="font-bold text-text">{performance.toFixed(1)}%</span></p>
            <Button className="mt-6 w-full" variant={index === 1 ? "primary" : "secondary"}>Choose plan</Button>
          </Card>
        ))}
      </div>
    </section>
  );
}

function Testimonials() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="grid gap-4 md:grid-cols-3">
        {[
          "The dashboard feels like a decision room, not a signal spam tool.",
          "Risk visibility is always present. That changes how fast I can decide.",
          "AI Choice makes long and short candidates understandable in seconds.",
        ].map((quote, index) => (
          <Card key={quote}>
            <p className="text-lg leading-7 text-text">"{quote}"</p>
            <p className="mt-5 text-sm font-bold text-muted">Trader {index + 1}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

function FAQ() {
  const items = [
    ["Does AI execute directly?", "No. AI trade controls route through the existing backend risk and execution path."],
    ["Can I trade manually?", "Yes. Manual mode clears AI intent and lets the user decide the trade."],
    ["Is this live-data connected?", "The UI uses current QuenTrader REST and WebSocket endpoints with graceful fallback."],
  ];
  return (
    <section id="faq" className="mx-auto max-w-4xl px-4 py-14 sm:px-6 lg:px-8">
      <h2 className="mb-6 text-center text-3xl font-black">FAQ</h2>
      <div className="space-y-3">
        {items.map(([q, a]) => (
          <details className="group rounded-2xl border border-white/10 bg-white/[0.04] p-5" key={q}>
            <summary className="flex cursor-pointer list-none items-center justify-between font-bold">
              {q}
              <ChevronDown className="transition group-open:rotate-180" size={18} />
            </summary>
            <p className="mt-3 text-sm leading-6 text-muted">{a}</p>
          </details>
        ))}
      </div>
      <div className="mt-6 flex items-center justify-center gap-2 text-sm text-muted">
        <Lock size={16} className="text-primary" />
        Existing broker execution and risk engine remain unchanged.
      </div>
    </section>
  );
}

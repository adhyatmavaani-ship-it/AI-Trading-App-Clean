import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  CandlestickChart,
  CheckCircle2,
  Layers3,
  LockKeyhole,
  MousePointer2,
  Radar,
  Route,
  ShieldCheck,
  SlidersHorizontal,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import type { ComponentProps } from "react";
import { useEffect, useMemo, useState } from "react";
import { confidence, money } from "../../app/selectors";
import { AdvancedTradingChart } from "../../components/charts/AdvancedTradingChart";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Tabs } from "../../components/ui/Tabs";
import type { AppData } from "../../hooks/useMarketData";
import type { MarketChart } from "../../services/types";

type TradeMode = "manual" | "ai";
type Side = "BUY" | "SELL";
type WorkspaceProfile = "ai" | "scout" | "execution";

export function TradeTerminalPage({ data, onToast }: { data: AppData; onToast: (message: string) => void }) {
  const [mode, setMode] = useState<TradeMode>("manual");
  const [side, setSide] = useState<Side>("BUY");
  const [profile, setProfile] = useState<WorkspaceProfile>("scout");
  const [showForecast, setShowForecast] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [amountPreset, setAmountPreset] = useState(25);
  const [contextPoint, setContextPoint] = useState<{ x: number; y: number } | null>(null);
  const guide = data.chart?.execution_guide;

  const symbolChoices = useMemo(() => {
    const fromUniverse = data.universe?.items?.map((item) => item.symbol) ?? [];
    const fromSignals = data.signals.map((item) => item.symbol);
    return Array.from(new Set([data.selectedSymbol, ...fromUniverse, ...fromSignals, "BTCUSDT", "ETHUSDT", "SOLUSDT"])).slice(0, 12);
  }, [data.selectedSymbol, data.signals, data.universe?.items]);

  const stagedPrice = data.chart?.latest_price ?? data.summary.ticker?.find((item) => item.symbol === data.selectedSymbol)?.price ?? 0;
  const [orderLines, setOrderLines] = useState({
    limit: stagedPrice,
    stop: guide?.stop_loss ?? stagedPrice * 0.99,
    target: guide?.tp1 ?? stagedPrice * 1.02,
  });

  useEffect(() => {
    if (!stagedPrice) return;
    setOrderLines({
      limit: guide?.entry_low ?? stagedPrice,
      stop: guide?.stop_loss ?? stagedPrice * 0.99,
      target: guide?.tp1 ?? stagedPrice * 1.02,
    });
  }, [guide?.entry_low, guide?.stop_loss, guide?.tp1, stagedPrice]);

  const selectedSignal = useMemo(
    () => data.signals.find((signal) => signal.symbol === data.selectedSymbol),
    [data.selectedSymbol, data.signals],
  );

  const stageManual = () => {
    onToast(`Manual ${side} staged for ${data.selectedSymbol} at ${money(orderLines.limit)}. Execution remains backend-gated.`);
  };

  const armAi = async () => {
    await data.setAssistantMode("FULL_AUTO").catch(() => undefined);
    onToast(`AI plan monitoring ${data.selectedSymbol}. It will wait for backend-approved conditions.`);
  };

  return (
    <div className="relative space-y-5">
      <Card className="p-6">
        <div className="flex flex-col justify-between gap-5 xl:flex-row xl:items-center">
          <div>
            <Badge tone="blue" className="mb-4">
              <CandlestickChart size={14} className="mr-2" /> Execution terminal
            </Badge>
            <h2 className="text-3xl font-black">Trade with chart context and hard risk boundaries</h2>
            <p className="mt-2 max-w-3xl text-muted">
              Manual mode keeps the trader in control. AI mode prepares an advisory plan and waits for existing backend validation, stop loss, take profit, and trailing logic.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Tabs
              value={profile}
              onChange={setProfile}
              items={[
                { value: "ai", label: "AI Mode" },
                { value: "scout", label: "Scout Mode" },
                { value: "execution", label: "Execution" },
              ]}
            />
            <Tabs
              value={mode}
              onChange={setMode}
              items={[
                { value: "manual", label: "Manual" },
                { value: "ai", label: "AI Trade" },
              ]}
            />
          </div>
        </div>
      </Card>

      <div className={profile === "ai" ? "grid gap-5 xl:grid-cols-[1.05fr_0.95fr]" : "grid gap-5 xl:grid-cols-[1.45fr_0.75fr]"}>
        <Card
          title={`${data.selectedSymbol} Pro Chart`}
          eyebrow="AI-enhanced market structure"
          action={
            <div className="flex flex-wrap items-center gap-2">
              <ToggleButton active={showForecast} onClick={() => setShowForecast((value) => !value)} label="AI Forecast" icon={<BrainCircuit size={14} />} />
              <ToggleButton active={showZones} onClick={() => setShowZones((value) => !value)} label="S/R Zones" icon={<Layers3 size={14} />} />
              <Badge tone={data.liveState === "live" ? "green" : "amber"}>{data.liveState}</Badge>
            </div>
          }
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {symbolChoices.map((symbol) => (
              <button
                key={symbol}
                onClick={() => data.setSelectedSymbol(symbol)}
                onContextMenu={(event) => {
                  event.preventDefault();
                  data.setSelectedSymbol(symbol);
                  setContextPoint({ x: event.clientX, y: event.clientY });
                }}
                className={
                  data.selectedSymbol === symbol
                    ? "holographic-pulse rounded-full bg-primary px-3 py-1.5 text-xs font-black text-black"
                    : data.signals.some((signal) => signal.symbol === symbol)
                      ? "holographic-pulse rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-bold text-primary transition hover:border-primary"
                      : "rounded-full border border-white/10 px-3 py-1.5 text-xs font-bold text-muted transition hover:border-secondary/40 hover:text-text"
                }
              >
                {symbol}
              </button>
            ))}
          </div>
          <AdvancedTradingChart
            symbol={data.selectedSymbol}
            candles={data.chart?.candles ?? []}
            signals={data.signals}
            showForecast={showForecast}
            showZones={showZones}
            orderLines={orderLines}
            onContextSummary={(x, y) => setContextPoint({ x, y })}
          />
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <Metric label="Last price" value={money(stagedPrice)} />
            <Metric label="Change" value={`${(data.chart?.change_pct ?? 0).toFixed(2)}%`} />
            <Metric label="Risk/reward" value={guide?.risk_reward ? `${guide.risk_reward.toFixed(2)}R` : "Waiting"} />
            <Metric label="Risk pct" value={guide?.risk_pct ? `${guide.risk_pct.toFixed(2)}%` : "Guarded"} />
          </div>
        </Card>

        {mode === "manual" ? (
          <ManualPanel
            symbol={data.selectedSymbol}
            side={side}
            onSide={setSide}
            price={stagedPrice}
            guide={guide}
            amountPreset={amountPreset}
            onAmountPreset={setAmountPreset}
            orderLines={orderLines}
            onOrderLines={setOrderLines}
            onStage={stageManual}
          />
        ) : (
          <AIPlanPanel symbol={data.selectedSymbol} guide={guide} onArm={() => void armAi()} signal={selectedSignal} />
        )}
      </div>

      <div className={profile === "ai" ? "grid gap-5 lg:grid-cols-2" : "grid gap-5 lg:grid-cols-4"}>
        <CorrelationGrid />
        <SmartRoutingPanel side={side} amountPreset={amountPreset} volatility={data.summary.avg_volatility_pct ?? 0} />
        <RiskRule title="BTC/ETH anchor" body="AI waits for market-leader alignment before trusting altcoin setups." />
        <RiskRule title="Liquidity and slippage" body="Thin books, bad depth, or aggressive spread expansion keep decisions advisory." />
        <RiskRule title="Risk survival rule" body="Hard invalidation, 1-2% risk, and trailing stop behavior stay under backend control." />
      </div>

      {contextPoint && (
        <ContextSummaryPanel
          x={contextPoint.x}
          y={contextPoint.y}
          symbol={data.selectedSymbol}
          signal={selectedSignal}
          volatility={data.summary.avg_volatility_pct ?? 0}
          onClose={() => setContextPoint(null)}
        />
      )}
    </div>
  );
}

function ManualPanel({
  symbol,
  side,
  onSide,
  price,
  guide,
  amountPreset,
  onAmountPreset,
  orderLines,
  onOrderLines,
  onStage,
}: {
  symbol: string;
  side: Side;
  onSide: (side: Side) => void;
  price: number;
  guide: MarketChart["execution_guide"];
  amountPreset: number;
  onAmountPreset: (value: number) => void;
  orderLines: { limit: number; stop: number; target: number };
  onOrderLines: (value: { limit: number; stop: number; target: number }) => void;
  onStage: () => void;
}) {
  const min = Math.max(0.0001, price * 0.94);
  const max = Math.max(price * 1.06, min * 1.01);

  return (
    <Card title="One-Click Execution Panel" eyebrow="Human controlled">
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Button variant={side === "BUY" ? "primary" : "secondary"} icon={<TrendingUp size={16} />} onClick={() => onSide("BUY")}>Buy</Button>
        <Button variant={side === "SELL" ? "danger" : "secondary"} icon={<TrendingDown size={16} />} onClick={() => onSide("SELL")}>Sell</Button>
      </div>
      <div className="mb-4 grid grid-cols-3 gap-2">
        {[25, 50, 100].map((value) => (
          <button
            key={value}
            onClick={() => onAmountPreset(value)}
            className={amountPreset === value ? "rounded-xl bg-primary px-3 py-2 text-sm font-black text-black" : "rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-bold text-muted"}
          >
            {value}%
          </button>
        ))}
      </div>
      <div className="space-y-3">
        <Field label="Symbol" value={symbol} readOnly />
        <Field label="Reference price" value={price ? String(price) : ""} readOnly />
        <Field label="Quantity" placeholder="Enter quantity" />
        <Field label="Stop loss" defaultValue={guide?.stop_loss ? String(guide.stop_loss) : ""} placeholder="Required" />
        <Field label="Take profit" defaultValue={guide?.tp1 ? String(guide.tp1) : ""} placeholder="Optional" />
      </div>
      <div className="mt-5 space-y-3 rounded-2xl border border-white/10 bg-white/[0.035] p-4">
        <p className="flex items-center gap-2 text-sm font-black"><SlidersHorizontal size={16} className="text-secondary" /> Chart line controls</p>
        <LineControl label="Limit" value={orderLines.limit} min={min} max={max} onChange={(limit) => onOrderLines({ ...orderLines, limit })} />
        <LineControl label="SL" value={orderLines.stop} min={min} max={max} onChange={(stop) => onOrderLines({ ...orderLines, stop })} />
        <LineControl label="TP" value={orderLines.target} min={min} max={max} onChange={(target) => onOrderLines({ ...orderLines, target })} />
      </div>
      <Button className="mt-5 w-full" variant="secondary" icon={<MousePointer2 size={16} />} onClick={onStage}>
        Stage Manual Intent
      </Button>
      <div className="mt-4 rounded-xl border border-warning/25 bg-warning/10 p-3 text-sm text-warning">
        <AlertTriangle size={16} className="mr-2 inline" />
        This UI does not add a new execution path. Broker execution remains backend-authoritative.
      </div>
    </Card>
  );
}

function AIPlanPanel({
  symbol,
  guide,
  onArm,
  signal,
}: {
  symbol: string;
  guide: MarketChart["execution_guide"];
  onArm: () => void;
  signal?: AppData["signals"][number];
}) {
  return (
    <Card title="AI Trade Plan" eyebrow="Conservative automation">
      <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4">
        <div className="flex items-center gap-3 text-primary">
          <Bot size={22} />
          <p className="font-black">AI will wait for perfect execution conditions on {symbol}.</p>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted">
          When the setup is valid, AI monitors market data, risk math, stop loss, take profit, and trailing stop requirements through existing backend controls.
        </p>
      </div>
      <div className="mt-4 space-y-3">
        <PlanLine label="AI confidence" value={signal ? `${confidence(signal).toFixed(0)}%` : "Waiting"} />
        <PlanLine label="Entry zone" value={guide?.entry_low && guide?.entry_high ? `${money(guide.entry_low)} - ${money(guide.entry_high)}` : "Waiting for chart guide"} />
        <PlanLine label="Hard stop" value={guide?.stop_loss ? money(guide.stop_loss) : "Backend required"} />
        <PlanLine label="Targets" value={guide?.tp1 ? `${money(guide.tp1)} / ${money(guide.tp2)}` : "Adaptive"} />
        <PlanLine label="AI trailing stop" value="Volatility-adaptive" />
      </div>
      <Button className="mt-5 w-full" icon={<CheckCircle2 size={16} />} onClick={onArm}>
        Arm AI Monitoring Plan
      </Button>
      <div className="mt-4 rounded-xl border border-secondary/25 bg-secondary/10 p-3 text-sm text-secondary">
        <LockKeyhole size={16} className="mr-2 inline" />
        AI mode cannot bypass risk-first execution ordering.
      </div>
    </Card>
  );
}

function ToggleButton({ active, onClick, label, icon }: { active: boolean; onClick: () => void; label: string; icon: React.ReactNode }) {
  return (
    <button
      className={active ? "rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-black text-primary" : "rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-bold text-muted"}
      onClick={onClick}
    >
      <span className="inline-flex items-center gap-1.5">{icon}{label}</span>
    </button>
  );
}

function Field({ label, ...props }: { label: string } & ComponentProps<typeof Input>) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-bold uppercase tracking-[0.16em] text-muted">{label}</span>
      <Input className="w-full" {...props} />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="tabular mt-1 font-black">{value}</p>
    </div>
  );
}

function PlanLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.04] px-3 py-3 text-sm">
      <span className="text-muted">{label}</span>
      <span className="tabular text-right font-bold text-text">{value}</span>
    </div>
  );
}

function LineControl({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  return (
    <label className="block">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-bold text-muted">{label}</span>
        <span className="tabular font-black">{money(value)}</span>
      </div>
      <input
        className="price-line-drag w-full"
        type="range"
        min={min}
        max={max}
        step={(max - min) / 180}
        value={value || min}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}

function CorrelationGrid() {
  const rows = [
    ["1m", "Bullish", "72%", "green"],
    ["5m", "Bullish", "68%", "green"],
    ["15m", "Neutral", "54%", "amber"],
    ["1h", "Bear risk", "49%", "red"],
  ] as const;
  return (
    <Card title="Multi-Timeframe AI Grid" eyebrow="Correlation">
      <div className="grid grid-cols-2 gap-3">
        {rows.map(([tf, trend, score, tone]) => (
          <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3" key={tf}>
            <div className="flex items-center justify-between">
              <span className="text-sm font-black">{tf}</span>
              <Badge tone={tone}>{trend}</Badge>
            </div>
            <p className="tabular mt-3 text-xl font-black">{score}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function SmartRoutingPanel({ side, amountPreset, volatility }: { side: Side; amountPreset: number; volatility: number }) {
  const highVolatility = volatility > 4;
  return (
    <Card title="AI Smart Order Routing" eyebrow="Preview only">
      <div className="space-y-3 text-sm">
        <PlanLine label="Route" value={side === "BUY" ? "Binance best ask" : "Binance best bid"} />
        <PlanLine label="Wallet preset" value={`${amountPreset}%`} />
        <PlanLine label="Slippage guard" value={highVolatility ? "Warning required" : "-0.10% protected"} />
        <PlanLine label="Execution status" value="Not submitted" />
      </div>
      <div className={highVolatility ? "mt-4 rounded-xl border border-warning/25 bg-warning/10 p-3 text-sm text-warning" : "mt-4 rounded-xl border border-secondary/25 bg-secondary/10 p-3 text-sm text-secondary"}>
        <Route size={16} className="mr-2 inline" />
        {highVolatility ? "High volatility detected. UI will require explicit confirmation." : "Routing preview is informational until backend execution approval."}
      </div>
    </Card>
  );
}

function ContextSummaryPanel({
  x,
  y,
  symbol,
  signal,
  volatility,
  onClose,
}: {
  x: number;
  y: number;
  symbol: string;
  signal?: AppData["signals"][number];
  volatility: number;
  onClose: () => void;
}) {
  const score = signal ? confidence(signal) : Math.max(44, 72 - volatility * 3);
  return (
    <div
      className="fixed z-50 w-[340px] rounded-2xl border border-secondary/25 bg-surface/95 p-4 shadow-[0_24px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl"
      style={{ left: Math.min(x, window.innerWidth - 360), top: Math.min(y, window.innerHeight - 330) }}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-secondary">Quick ML Summary</p>
          <h3 className="mt-1 text-xl font-black">{symbol}</h3>
        </div>
        <button className="rounded-lg p-1 text-muted hover:bg-white/10" onClick={onClose} aria-label="Close summary">
          <X size={18} />
        </button>
      </div>
      <div className="space-y-3">
        <PlanLine label="Trend" value={signal?.action === "SELL" ? "Bearish pressure" : "Constructive"} />
        <PlanLine label="AI prediction" value={signal?.action ?? "Wait"} />
        <PlanLine label="Risk score" value={`${Math.min(88, Math.max(18, 100 - score)).toFixed(0)} / 100`} />
        <PlanLine label="Volatility" value={`${volatility.toFixed(2)}%`} />
      </div>
      <div className="mt-4 rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
        <Radar size={16} className="mr-2 inline" />
        Right-click summaries are advisory and do not place orders.
      </div>
    </div>
  );
}

function RiskRule({ title, body }: { title: string; body: string }) {
  return (
    <Card className="p-5">
      <ShieldCheck className="mb-4 text-primary" size={22} />
      <p className="font-black">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
    </Card>
  );
}

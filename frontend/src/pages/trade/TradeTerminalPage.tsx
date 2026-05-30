import { AlertTriangle, Bot, CandlestickChart, CheckCircle2, LockKeyhole, MousePointer2, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import type { ComponentProps } from "react";
import { useMemo, useState } from "react";
import { money } from "../../app/selectors";
import { CandleProxy } from "../../components/charts/Charts";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { Tabs } from "../../components/ui/Tabs";
import type { AppData } from "../../hooks/useMarketData";
import type { MarketChart } from "../../services/types";

type TradeMode = "manual" | "ai";
type Side = "BUY" | "SELL";

export function TradeTerminalPage({ data, onToast }: { data: AppData; onToast: (message: string) => void }) {
  const [mode, setMode] = useState<TradeMode>("manual");
  const [side, setSide] = useState<Side>("BUY");
  const guide = data.chart?.execution_guide;

  const symbolChoices = useMemo(() => {
    const fromUniverse = data.universe?.items?.map((item) => item.symbol) ?? [];
    const fromSignals = data.signals.map((item) => item.symbol);
    return Array.from(new Set([data.selectedSymbol, ...fromUniverse, ...fromSignals, "BTCUSDT", "ETHUSDT", "SOLUSDT"])).slice(0, 12);
  }, [data.selectedSymbol, data.signals, data.universe?.items]);

  const stagedPrice = data.chart?.latest_price ?? data.summary.ticker?.find((item) => item.symbol === data.selectedSymbol)?.price ?? 0;

  const stageManual = () => {
    onToast(`Manual ${side} staged for ${data.selectedSymbol}. Execution remains backend-gated.`);
  };

  const armAi = async () => {
    await data.setAssistantMode("FULL_AUTO").catch(() => undefined);
    onToast(`AI plan monitoring ${data.selectedSymbol}. It will wait for backend-approved conditions.`);
  };

  return (
    <div className="space-y-5">
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
          <Tabs
            value={mode}
            onChange={setMode}
            items={[
              { value: "manual", label: "Manual" },
              { value: "ai", label: "AI Trade" },
            ]}
          />
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[1.35fr_0.8fr]">
        <Card
          title={`${data.selectedSymbol} Chart`}
          eyebrow="Market structure"
          action={<Badge tone={data.liveState === "live" ? "green" : "amber"}>{data.liveState}</Badge>}
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {symbolChoices.map((symbol) => (
              <button
                key={symbol}
                onClick={() => data.setSelectedSymbol(symbol)}
                className={data.selectedSymbol === symbol ? "rounded-full bg-primary px-3 py-1.5 text-xs font-black text-black" : "rounded-full border border-white/10 px-3 py-1.5 text-xs font-bold text-muted transition hover:border-secondary/40 hover:text-text"}
              >
                {symbol}
              </button>
            ))}
          </div>
          <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
            <CandleProxy candles={data.chart?.candles ?? []} />
          </div>
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
            onStage={stageManual}
          />
        ) : (
          <AIPlanPanel symbol={data.selectedSymbol} guide={guide} onArm={() => void armAi()} />
        )}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <RiskRule title="BTC/ETH anchor" body="AI waits for market-leader alignment before trusting altcoin setups." />
        <RiskRule title="Liquidity and slippage" body="Thin books, bad depth, or aggressive spread expansion keep decisions advisory." />
        <RiskRule title="Risk survival rule" body="Hard invalidation, 1-2% risk, and trailing stop behavior stay under backend control." />
      </div>
    </div>
  );
}

function ManualPanel({
  symbol,
  side,
  onSide,
  price,
  guide,
  onStage,
}: {
  symbol: string;
  side: Side;
  onSide: (side: Side) => void;
  price: number;
  guide: MarketChart["execution_guide"];
  onStage: () => void;
}) {
  return (
    <Card title="Manual Order Ticket" eyebrow="Human controlled">
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Button variant={side === "BUY" ? "primary" : "secondary"} icon={<TrendingUp size={16} />} onClick={() => onSide("BUY")}>Buy</Button>
        <Button variant={side === "SELL" ? "danger" : "secondary"} icon={<TrendingDown size={16} />} onClick={() => onSide("SELL")}>Sell</Button>
      </div>
      <div className="space-y-3">
        <Field label="Symbol" value={symbol} readOnly />
        <Field label="Reference price" value={price ? String(price) : ""} readOnly />
        <Field label="Quantity" placeholder="Enter quantity" />
        <Field label="Stop loss" defaultValue={guide?.stop_loss ? String(guide.stop_loss) : ""} placeholder="Required" />
        <Field label="Take profit" defaultValue={guide?.tp1 ? String(guide.tp1) : ""} placeholder="Optional" />
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
}: {
  symbol: string;
  guide: MarketChart["execution_guide"];
  onArm: () => void;
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
        <PlanLine label="Entry zone" value={guide?.entry_low && guide?.entry_high ? `${money(guide.entry_low)} - ${money(guide.entry_high)}` : "Waiting for chart guide"} />
        <PlanLine label="Hard stop" value={guide?.stop_loss ? money(guide.stop_loss) : "Backend required"} />
        <PlanLine label="Targets" value={guide?.tp1 ? `${money(guide.tp1)} / ${money(guide.tp2)}` : "Adaptive"} />
        <PlanLine label="Trailing stop" value="Enabled after favorable movement" />
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

function RiskRule({ title, body }: { title: string; body: string }) {
  return (
    <Card className="p-5">
      <ShieldCheck className="mb-4 text-primary" size={22} />
      <p className="font-black">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted">{body}</p>
    </Card>
  );
}

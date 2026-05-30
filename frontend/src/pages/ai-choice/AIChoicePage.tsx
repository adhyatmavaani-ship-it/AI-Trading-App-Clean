import { ArrowRight, Bot, CandlestickChart, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { buildChoices, type Choice, money } from "../../app/selectors";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Modal } from "../../components/ui/Modal";
import type { AppData } from "../../hooks/useMarketData";

export function AIChoicePage({
  data,
  onOpenTrade,
  onToast,
}: {
  data: AppData;
  onOpenTrade: () => void;
  onToast: (message: string) => void;
}) {
  const choices = useMemo(() => buildChoices(data.signals, data.universe, data.summary), [data.signals, data.universe, data.summary]);
  const buys = choices.filter((item) => item.side === "BUY").slice(0, 8);
  const sells = choices.filter((item) => item.side === "SELL").slice(0, 8);
  const [selected, setSelected] = useState<Choice | null>(choices[0] ?? null);

  const openManual = (choice: Choice) => {
    data.setSelectedSymbol(choice.symbol);
    onToast(`Manual mode opened for ${choice.symbol}. AI intent cleared.`);
    onOpenTrade();
  };

  const openAi = async (choice: Choice) => {
    data.setSelectedSymbol(choice.symbol);
    await data.setAssistantMode("FULL_AUTO").catch(() => undefined);
    onToast(`AI trade plan armed for ${choice.symbol}. Backend risk approval remains required.`);
    onOpenTrade();
  };

  return (
    <div className="space-y-5">
      <Card className="p-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <Badge tone="green" className="mb-4">
              <Bot size={14} className="mr-2" /> Crypto-wide AI selection
            </Badge>
            <h2 className="text-3xl font-black">AI Choice</h2>
            <p className="mt-2 max-w-3xl text-muted">
              Separate buy and sell candidates, ranked by signals, liquidity, momentum, volatility, and conservative risk rules.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="BUY" value={buys.length} tone="green" />
            <Stat label="SELL" value={sells.length} tone="red" />
            <Stat label="MODE" value="Guarded" tone="blue" />
          </div>
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <ChoiceColumn title="AI Buy List" subtitle="Long candidates waiting for confirmation" choices={buys} tone="green" onSelect={setSelected} />
        <ChoiceColumn title="AI Sell List" subtitle="Short or exit-pressure candidates" choices={sells} tone="red" onSelect={setSelected} />
      </div>

      <Modal open={Boolean(selected)} title={selected?.symbol ?? "AI Decision"} onClose={() => setSelected(null)}>
        {selected && (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <Badge tone={selected.side === "BUY" ? "green" : "red"}>{selected.side}</Badge>
                <h3 className="mt-3 text-3xl font-black">{selected.symbol}</h3>
                <p className="mt-2 text-muted">{selected.reason}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted">Confidence</p>
                <p className="text-3xl font-black text-primary">{selected.confidence.toFixed(0)}%</p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {[
                ["Market leader", "BTC/ETH alignment required before execution."],
                ["Liquidity", "Order book and slippage must remain acceptable."],
                ["OI/Funding", "Avoid crowded leverage traps."],
                ["Price action", "Wait for reclaim, rejection, or support break."],
                ["Momentum", "VWAP, EMA, RSI, MACD must confirm."],
                ["Risk math", "1-2% risk, hard SL, TP, trailing stop only after approval."],
                ["Social/Whale", "Treat hype as untrusted until confirmed."],
              ].map(([title, body]) => (
                <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3" key={title}>
                  <p className="font-bold">{title}</p>
                  <p className="mt-1 text-sm text-muted">{body}</p>
                </div>
              ))}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Button variant="secondary" icon={<CandlestickChart size={17} />} onClick={() => openManual(selected)}>
                Manual Trade
              </Button>
              <Button icon={<ArrowRight size={17} />} onClick={() => void openAi(selected)}>
                AI Trade Plan
              </Button>
            </div>
            <div className="rounded-xl border border-primary/20 bg-primary/10 p-3 text-sm text-primary">
              <ShieldCheck size={16} className="mr-2 inline" />
              AI Trade Plan does not bypass backend risk validation or broker execution controls.
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

function ChoiceColumn({
  title,
  subtitle,
  choices,
  tone,
  onSelect,
}: {
  title: string;
  subtitle: string;
  choices: Choice[];
  tone: "green" | "red";
  onSelect: (choice: Choice) => void;
}) {
  return (
    <Card title={title} eyebrow={subtitle}>
      <div className="space-y-3">
        {choices.map((choice) => (
          <button
            key={`${choice.side}-${choice.symbol}`}
            onClick={() => onSelect(choice)}
            className="w-full rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-left transition hover:border-primary/30 hover:bg-white/[0.06]"
          >
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-black">{choice.symbol}</p>
                <p className="text-sm text-muted">{money(choice.price)} - {choice.source}</p>
              </div>
              <Badge tone={tone}>{choice.side}</Badge>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <div className="h-1.5 flex-1 rounded-full bg-white/10">
                <div className={tone === "green" ? "h-full rounded-full bg-primary" : "h-full rounded-full bg-danger"} style={{ width: `${choice.confidence}%` }} />
              </div>
              <span className="tabular text-sm font-bold">{choice.confidence.toFixed(0)}%</span>
            </div>
          </button>
        ))}
        {choices.length === 0 && <p className="rounded-xl bg-white/[0.04] p-4 text-muted">AI is waiting for stronger market evidence.</p>}
      </div>
    </Card>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone: "green" | "red" | "blue" }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
      <p className={tone === "green" ? "text-xs font-bold text-primary" : tone === "red" ? "text-xs font-bold text-danger" : "text-xs font-bold text-secondary"}>{label}</p>
      <p className="mt-1 text-xl font-black">{value}</p>
    </div>
  );
}

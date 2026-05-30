import {
  BarChart3,
  Bot,
  Gauge,
  Home,
  LineChart,
  Menu,
  ShieldCheck,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { brand } from "../design/tokens";
import { cn } from "../lib/cn";
import type { AppData } from "../hooks/useMarketData";

export type RouteKey = "landing" | "dashboard" | "ai-choice" | "trade";

const navItems: Array<{ key: RouteKey; label: string; icon: ReactNode }> = [
  { key: "landing", label: "Home", icon: <Home size={18} /> },
  { key: "dashboard", label: "Dashboard", icon: <BarChart3 size={18} /> },
  { key: "ai-choice", label: "AI Choice", icon: <Bot size={18} /> },
  { key: "trade", label: "Trade Terminal", icon: <LineChart size={18} /> },
];

export function DashboardLayout({
  route,
  onRoute,
  data,
  children,
}: {
  route: RouteKey;
  onRoute: (route: RouteKey) => void;
  data: AppData;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const statusTone = data.liveState === "live" ? "bg-primary" : data.liveState === "syncing" ? "bg-warning" : "bg-danger";

  return (
    <div className="min-h-screen bg-bg text-text">
      <div className="fixed inset-y-0 left-0 z-40 hidden w-[280px] border-r border-white/10 bg-surface/80 p-4 backdrop-blur-xl lg:block">
        <Sidebar route={route} onRoute={onRoute} />
      </div>

      <div className="lg:pl-[280px]">
        <header className="sticky top-0 z-30 border-b border-white/10 bg-bg/78 px-4 py-3 backdrop-blur-xl sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <button
              className="rounded-xl border border-white/10 p-2 text-muted lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu size={20} />
            </button>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-secondary">{brand.tagline}</p>
              <h1 className="text-lg font-bold sm:text-xl">{routeLabel(route)}</h1>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <div className="hidden rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-muted sm:block">
                Portfolio <span className="tabular ml-2 font-bold text-text">10000</span>
              </div>
              <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-bold uppercase text-muted">
                <span className={cn("h-2 w-2 rounded-full", statusTone)} />
                {data.liveState === "live" ? "Live" : data.liveState === "syncing" ? "Live Sync" : "Offline"}
              </div>
            </div>
          </div>
        </header>
        <main className="px-4 py-5 sm:px-6 lg:px-8">{children}</main>
      </div>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/70 p-3 backdrop-blur-sm lg:hidden">
          <div className="h-full max-w-[300px] rounded-2xl bg-surface p-4">
            <div className="mb-4 flex justify-end">
              <button className="rounded-lg p-2 text-muted" onClick={() => setOpen(false)} aria-label="Close navigation">
                <X size={20} />
              </button>
            </div>
            <Sidebar
              route={route}
              onRoute={(next) => {
                onRoute(next);
                setOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function Sidebar({ route, onRoute }: { route: RouteKey; onRoute: (route: RouteKey) => void }) {
  return (
    <aside className="flex h-full flex-col">
      <button className="mb-8 flex items-center gap-3 text-left" onClick={() => onRoute("landing")}>
        <div className="grid h-11 w-11 place-items-center rounded-2xl bg-primary text-black shadow-glow">
          <Gauge size={22} />
        </div>
        <div>
          <p className="text-xl font-black tracking-tight">{brand.name}</p>
          <p className="text-xs text-muted">Institutional AI terminal</p>
        </div>
      </button>
      <nav className="space-y-2">
        {navItems.map((item) => (
          <button
            key={item.key}
            onClick={() => onRoute(item.key)}
            className={cn(
              "flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm font-semibold text-muted transition hover:bg-white/[0.07] hover:text-text",
              route === item.key && "bg-primary/10 text-primary ring-1 ring-primary/20",
            )}
          >
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>
      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.04] p-4">
        <div className="mb-3 flex items-center gap-2 text-primary">
          <ShieldCheck size={18} />
          <span className="text-sm font-bold">Risk-first execution</span>
        </div>
        <p className="text-sm leading-6 text-muted">
          No broker execution happens outside the existing backend validation and risk controls.
        </p>
      </div>
    </aside>
  );
}

function routeLabel(route: RouteKey) {
  return {
    landing: "Premium Trading Platform",
    dashboard: "Trading Dashboard",
    "ai-choice": "AI Choice",
    trade: "Execution Terminal",
  }[route];
}

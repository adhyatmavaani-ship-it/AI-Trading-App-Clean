import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MarketCandle } from "../../services/types";

export function PerformanceArea({ data }: { data: Array<{ name: string; value: number }> }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="equity" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#00E676" stopOpacity={0.55} />
            <stop offset="100%" stopColor="#00E676" stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: "#64748B", fontSize: 11 }} />
        <YAxis hide domain={["dataMin - 2", "dataMax + 2"]} />
        <Tooltip
          contentStyle={{ background: "#0F172A", border: "1px solid #1E293B", borderRadius: 12 }}
          labelStyle={{ color: "#E5E7EB" }}
        />
        <Area type="monotone" dataKey="value" stroke="#00E676" fill="url(#equity)" strokeWidth={2.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function ExposureDonut({ value }: { value: number }) {
  const safe = Math.max(0, Math.min(100, value));
  const data = [
    { name: "Risk", value: safe },
    { name: "Free", value: 100 - safe },
  ];
  return (
    <ResponsiveContainer width="100%" height={190}>
      <PieChart>
        <Pie data={data} innerRadius={58} outerRadius={78} dataKey="value" startAngle={90} endAngle={-270}>
          <Cell fill="#00C2FF" />
          <Cell fill="rgba(148,163,184,0.14)" />
        </Pie>
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" fill="#E5E7EB" fontSize={28} fontWeight={800}>
          {safe.toFixed(0)}%
        </text>
      </PieChart>
    </ResponsiveContainer>
  );
}

export function CandleProxy({ candles }: { candles: MarketCandle[] }) {
  const data = candles.slice(-40).map((item, index) => ({
    name: String(index + 1),
    close: item.close,
    volume: item.volume ?? 0,
  }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <XAxis dataKey="name" hide />
        <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
        <Tooltip
          contentStyle={{ background: "#0F172A", border: "1px solid #1E293B", borderRadius: 12 }}
          labelStyle={{ color: "#E5E7EB" }}
        />
        <Bar dataKey="close" radius={[6, 6, 0, 0]}>
          {data.map((item, index) => (
            <Cell key={index} fill={index > 0 && item.close < data[index - 1].close ? "#FF4D4F" : "#00E676"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Sparkline({ values, color = "#00E676" }: { values: number[]; color?: string }) {
  const data = values.map((value, index) => ({ index, value }));
  return (
    <ResponsiveContainer width="100%" height={52}>
      <AreaChart data={data}>
        <Area type="monotone" dataKey="value" stroke={color} fill={color} fillOpacity={0.12} strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

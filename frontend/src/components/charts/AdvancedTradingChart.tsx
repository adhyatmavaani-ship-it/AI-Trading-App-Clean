import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef } from "react";
import type { MarketCandle, Signal } from "../../services/types";

type OrderLines = {
  limit: number;
  stop: number;
  target: number;
};

export function AdvancedTradingChart({
  symbol,
  candles,
  signals,
  showForecast,
  showZones,
  orderLines,
  onContextSummary,
}: {
  symbol: string;
  candles: MarketCandle[];
  signals: Signal[];
  showForecast: boolean;
  showZones: boolean;
  orderLines: OrderLines;
  onContextSummary: (x: number, y: number) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const forecastSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const chartData = useMemo(() => normalizeCandles(candles), [candles]);
  const fallbackData = useMemo(() => buildFallbackCandles(), []);
  const activeData = chartData.length ? chartData : fallbackData;

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94A3B8",
        fontFamily: "Inter, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "rgba(148,163,184,0.14)" },
      timeScale: { borderColor: "rgba(148,163,184,0.14)", timeVisible: true },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#00E676",
      downColor: "#FF4D4F",
      borderUpColor: "#00E676",
      borderDownColor: "#FF4D4F",
      wickUpColor: "#00E676",
      wickDownColor: "#FF4D4F",
    });
    const forecastSeries = chart.addLineSeries({
      color: "#00C2FF",
      lineStyle: LineStyle.Dotted,
      lineWidth: 2,
      priceLineVisible: false,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    forecastSeriesRef.current = forecastSeries;

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      forecastSeriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    candleSeriesRef.current?.setData(activeData);
    chartRef.current?.timeScale().fitContent();
  }, [activeData]);

  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    if (!candleSeries) return;
    candleSeries.setMarkers(
      signals
        .filter((signal) => signal.symbol === symbol && (signal.action === "BUY" || signal.action === "SELL"))
        .slice(0, 8)
        .map((signal, index) => ({
          time: activeData[Math.max(0, activeData.length - 1 - index)]?.time ?? activeData[activeData.length - 1]?.time,
          position: signal.action === "BUY" ? "belowBar" : "aboveBar",
          color: signal.action === "BUY" ? "#00E676" : "#FF4D4F",
          shape: signal.action === "BUY" ? "arrowUp" : "arrowDown",
          text: `AI ${signal.action}`,
        })),
    );
  }, [activeData, signals, symbol]);

  useEffect(() => {
    forecastSeriesRef.current?.setData(showForecast ? buildForecast(activeData) : []);
  }, [activeData, showForecast]);

  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series || activeData.length === 0) return;

    const latest = activeData[activeData.length - 1].close;
    const low = Math.min(...activeData.slice(-34).map((item) => item.low));
    const high = Math.max(...activeData.slice(-34).map((item) => item.high));
    const lines = [
      series.createPriceLine({ price: orderLines.limit || latest, color: "#00C2FF", lineWidth: 2, lineStyle: LineStyle.Solid, title: "LIMIT" }),
      series.createPriceLine({ price: orderLines.stop || latest * 0.99, color: "#FF4D4F", lineWidth: 2, lineStyle: LineStyle.Dashed, title: "SL" }),
      series.createPriceLine({ price: orderLines.target || latest * 1.02, color: "#00E676", lineWidth: 2, lineStyle: LineStyle.Dashed, title: "TP" }),
      ...(showZones
        ? [
            series.createPriceLine({ price: low, color: "rgba(0,230,118,0.75)", lineWidth: 1, lineStyle: LineStyle.LargeDashed, title: "AI SUPPORT" }),
            series.createPriceLine({ price: high, color: "rgba(255,77,79,0.75)", lineWidth: 1, lineStyle: LineStyle.LargeDashed, title: "AI RESIST" }),
          ]
        : []),
    ];

    return () => {
      lines.forEach((line) => series.removePriceLine(line));
    };
  }, [activeData, orderLines.limit, orderLines.stop, orderLines.target, showZones]);

  return (
    <div
      className="relative min-h-[520px] rounded-2xl border border-white/10 bg-[#050914]"
      onContextMenu={(event) => {
        event.preventDefault();
        onContextSummary(event.clientX, event.clientY);
      }}
    >
      <div className="pointer-events-none absolute left-4 top-4 z-10 rounded-xl border border-white/10 bg-black/40 px-3 py-2 backdrop-blur">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-secondary">TradingView Lightweight</p>
        <p className="mt-1 text-sm font-black">{symbol}</p>
      </div>
      <div ref={containerRef} className="h-[520px] w-full" />
    </div>
  );
}

function normalizeCandles(candles: MarketCandle[]): CandlestickData<Time>[] {
  return candles
    .filter((item) => item.timestamp_ms && item.open && item.high && item.low && item.close)
    .map((item) => ({
      time: Math.floor(item.timestamp_ms / 1000) as Time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
    }));
}

function buildFallbackCandles(): CandlestickData<Time>[] {
  const start = Math.floor(Date.now() / 1000) - 60 * 120;
  let price = 100;
  return Array.from({ length: 90 }, (_, index) => {
    const drift = Math.sin(index / 5) * 0.65 + (index > 45 ? 0.28 : -0.04);
    const open = price;
    const close = Math.max(4, open + drift);
    const high = Math.max(open, close) + 1.4;
    const low = Math.min(open, close) - 1.2;
    price = close;
    return { time: (start + index * 60) as Time, open, high, low, close };
  });
}

function buildForecast(data: CandlestickData<Time>[]): LineData<Time>[] {
  if (data.length === 0) return [];
  const latest = data[data.length - 1];
  const previous = data[Math.max(0, data.length - 10)];
  const slope = (latest.close - previous.close) / 10;
  return Array.from({ length: 16 }, (_, index) => ({
    time: ((latest.time as number) + index * 60) as Time,
    value: latest.close + slope * index + Math.sin(index / 2) * Math.abs(slope || latest.close * 0.001),
  }));
}

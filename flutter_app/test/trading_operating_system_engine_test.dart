import 'package:ai_trading_app/core/trading_operating_system_engine.dart';
import 'package:ai_trading_app/models/active_trade.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:ai_trading_app/models/user_pnl.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('trading operating system builds portfolio and orchestration reads', () {
    const engine = TradingOperatingSystemEngine();
    const trades = <ActiveTradeModel>[
      ActiveTradeModel(
        tradeId: 't1',
        symbol: 'BTCUSDT',
        side: 'BUY',
        entry: 100,
        stopLoss: 96,
        takeProfit: 110,
        executedQuantity: 1,
        entryReason: 'AI approved',
        status: 'open',
        regime: 'TRENDING',
        riskFraction: 0.01,
      ),
      ActiveTradeModel(
        tradeId: 't2',
        symbol: 'ETHUSDT',
        side: 'BUY',
        entry: 50,
        stopLoss: 47,
        takeProfit: 60,
        executedQuantity: 2,
        entryReason: 'AI approved',
        status: 'open',
        regime: 'TRENDING',
        riskFraction: 0.01,
      ),
    ];
    const pnl = UserPnLModel(
      userId: 'admin',
      startingEquity: 1000,
      currentEquity: 1000,
      absolutePnl: 12,
      pnlPct: 1.2,
      peakEquity: 1020,
      rollingDrawdown: 0.01,
      protectionState: 'NORMAL',
      capitalMultiplier: 1,
      activeTrades: 2,
      grossExposure: 200,
      openNotional: 200,
    );
    final signals = <SignalModel>[
      _signal('BTCUSDT', 0.82),
      _signal('SOLUSDT', 0.76),
    ];
    const universe = MarketUniverseModel(
      items: <MarketUniverseEntryModel>[
        MarketUniverseEntryModel(
          symbol: 'BTCUSDT',
          price: 100,
          changePct: 2,
          volumeRatio: 2,
          volatilityPct: 3,
          trendPct: 12,
          quoteVolume: 1000000,
          category: 'majors',
        ),
        MarketUniverseEntryModel(
          symbol: 'SOLUSDT',
          price: 10,
          changePct: 4,
          volumeRatio: 3,
          volatilityPct: 5,
          trendPct: 20,
          quoteVolume: 900000,
          category: 'majors',
        ),
      ],
      topGainers: <MarketUniverseEntryModel>[],
      highVolatility: <MarketUniverseEntryModel>[],
      aiPicks: <MarketUniverseEntryModel>[],
    );

    final portfolio = engine.portfolioIntelligence(pnl: pnl, trades: trades);
    final orchestration = engine.multiAssetOrchestration(
      signals: signals,
      trades: trades,
      universe: universe,
    );
    final copilot = engine.copilot(
      portfolio: portfolio,
      orchestration: orchestration,
    );
    final realtime = engine.realtimeOrchestration(
      signalCount: signals.length,
      activeTrades: trades.length,
      chartActive: true,
    );
    final workspace = engine.executionWorkspace(
      portfolio: portfolio,
      signal: signals.first,
    );

    expect(portfolio.sectorExposure, contains('BTC'));
    expect(portfolio.grossExposurePct, greaterThan(0));
    expect(orchestration.globalRank, hasLength(2));
    expect(orchestration.suppressedSymbols, contains('BTCUSDT'));
    expect(copilot.messages, isNotEmpty);
    expect(realtime.priorityLanes.first, 'execution');
    expect(workspace.readinessScore, inInclusiveRange(0, 100));
  });
}

SignalModel _signal(String symbol, double confidence) {
  return SignalModel(
    signalId: 'sig-$symbol',
    symbol: symbol,
    action: 'BUY',
    strategy: 'AI',
    confidence: confidence,
    alphaScore: confidence * 100,
    regime: 'TRENDING',
    price: 100,
    signalVersion: 1,
    publishedAt: DateTime.utc(2026, 5, 14),
    decisionReason: 'Momentum confirmed',
    degradedMode: false,
    requiredTier: 'pro',
    minBalance: 0,
    rejectionReason: null,
    lowConfidence: false,
    quality: 'approved',
    qualityScore: confidence * 100,
    qualityReasons: const <String>['trend alignment'],
    executionAllowed: true,
    marketDataStale: false,
    marketDataSources: const <String, String>{},
  );
}

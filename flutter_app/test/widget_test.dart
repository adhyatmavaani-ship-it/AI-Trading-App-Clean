import 'dart:async';

import 'package:ai_trading_app/core/api_client.dart';
import 'package:ai_trading_app/core/auth_credentials_store.dart';
import 'package:ai_trading_app/core/websocket_service.dart';
import 'package:ai_trading_app/main.dart';
import 'package:ai_trading_app/models/batch.dart';
import 'package:ai_trading_app/models/meta_analytics.dart';
import 'package:ai_trading_app/models/meta_decision.dart';
import 'package:ai_trading_app/models/portfolio_concentration.dart';
import 'package:ai_trading_app/models/public_dashboard.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:ai_trading_app/models/system_health.dart';
import 'package:ai_trading_app/models/trade_timeline.dart';
import 'package:ai_trading_app/models/user_pnl.dart';
import 'package:ai_trading_app/providers/app_providers.dart';
import 'package:ai_trading_app/repositories/trading_repository.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

class MemoryAuthCredentialsStore extends AuthCredentialsStore {
  MemoryAuthCredentialsStore({AuthSession? initialSession})
      : _session = initialSession;

  AuthSession? _session;

  @override
  Future<AuthSession?> loadSession() async => _session;

  @override
  Future<void> saveSession(AuthSession session) async {
    _session = session;
  }

  @override
  Future<void> saveApiKey(
    String apiKey, {
    AuthScheme scheme = AuthScheme.apiKey,
    DateTime? expiresAt,
  }) async {
    final normalized = apiKey.trim();
    if (normalized.isEmpty) {
      _session = null;
      return;
    }
    _session = AuthSession(
      accessToken: normalized,
      scheme: scheme,
      expiresAt: expiresAt,
    );
  }

  @override
  Future<void> clear() async {
    _session = null;
  }
}

class FakeTradingRepository extends TradingRepository {
  FakeTradingRepository()
      : super(
          apiClient: ApiClient(
            credentialsStore: AuthCredentialsStore(),
            baseUrl: 'http://localhost',
          ),
          webSocketService: WebSocketService(
            credentialsStore: AuthCredentialsStore(),
          ),
        );

  @override
  Future<List<SignalModel>> fetchSignals({int limit = 25}) async {
    return <SignalModel>[
      SignalModel(
        signalId: 'sig-1',
        symbol: 'BTCUSDT',
        action: 'BUY',
        strategy: 'AI',
        confidence: 0.82,
        alphaScore: 86,
        regime: 'TRENDING',
        price: 100000,
        signalVersion: 1,
        publishedAt: DateTime.parse('2026-01-01T00:00:00Z'),
        decisionReason: 'Meta approved directional setup.',
        degradedMode: false,
        requiredTier: 'pro',
        minBalance: 25,
        rejectionReason: null,
        lowConfidence: false,
      ),
    ];
  }

  @override
  Stream<SignalModel> watchSignals() => const Stream<SignalModel>.empty();

  @override
  Future<List<BatchModel>> fetchBatches({int limit = 25}) async {
    return const <BatchModel>[];
  }

  @override
  Stream<List<BatchModel>> watchBatches({int limit = 25}) async* {
    yield const <BatchModel>[];
  }

  @override
  Future<SystemHealthModel> fetchSystemHealth() async {
    return const SystemHealthModel(
      tradingMode: 'paper',
      apiStatus: 'ok',
      latencyMsP50: 12,
      latencyMsP95: 28,
      activeTrades: 2,
      errorCount: 0,
      failedOrders: 0,
      partialFills: 0,
      degradedMode: false,
    );
  }

  @override
  Stream<SystemHealthModel> watchSystemHealth() async* {
    yield await fetchSystemHealth();
  }

  @override
  Future<MetaAnalyticsModel> fetchMetaAnalytics() async {
    return const MetaAnalyticsModel(
      blockedTrades: MetaBlockedTradesModel(
        total: 2,
        reasons: <String, int>{'Latency threshold exceeded': 2},
      ),
      strategyPerformance: <String, MetaStrategyPerformanceModel>{
        'AI': MetaStrategyPerformanceModel(
          trades: 8,
          wins: 5,
          losses: 3,
          blocked: 1,
          pnl: 124.5,
        ),
      },
      confidenceDistribution: <String, int>{
        '65_79': 3,
        '80_100': 5,
      },
      learning: MetaLearningModel(
        enabled: true,
        blacklistTotal: 1,
        whitelistTotal: 2,
        regimes: <String, MetaLearningRegimeModel>{
          'TRENDING': MetaLearningRegimeModel(
            trackedPatterns: 3,
            blacklistPatterns: <String>['late_breakout'],
            whitelistPatterns: <String>['trend_continuation'],
            preferredMinAtrPct: 0.5,
            preferredMinTrendGap: 1.2,
          ),
        },
      ),
      updatedAt: '2026-01-01T00:00:00Z',
    );
  }

  @override
  Stream<MetaAnalyticsModel> watchMetaAnalytics() async* {
    yield await fetchMetaAnalytics();
  }

  @override
  Future<PublicPerformanceModel> fetchPublicPerformance() async {
    return PublicPerformanceModel(
      winRate: 0.63,
      totalPnlPct: 18.4,
      totalTrades: 142,
      lastUpdated: DateTime.parse('2026-01-01T00:00:00Z'),
    );
  }

  @override
  Future<List<PublicTradeModel>> fetchPublicTrades({int limit = 20}) async {
    return <PublicTradeModel>[
      const PublicTradeModel(
        symbol: 'BTCUSDT',
        side: 'BUY',
        entry: 100000,
        exit: 103200,
        pnlPct: 3.2,
        status: 'WIN',
      ),
      const PublicTradeModel(
        symbol: 'ETHUSDT',
        side: 'SELL',
        entry: 3200,
        exit: 3260,
        pnlPct: -1.9,
        status: 'LOSS',
      ),
    ].take(limit).toList();
  }

  @override
  Future<List<PublicDailyPointModel>> fetchPublicDaily({int limit = 90}) async {
    return <PublicDailyPointModel>[
      const PublicDailyPointModel(date: '2025-12-29', pnlPct: 0.8),
      const PublicDailyPointModel(date: '2025-12-30', pnlPct: 1.4),
      const PublicDailyPointModel(date: '2025-12-31', pnlPct: -0.2),
      const PublicDailyPointModel(date: '2026-01-01', pnlPct: 3.2),
    ].take(limit).toList();
  }

  @override
  Future<TradeTimelineModel> fetchTradeTimeline(String tradeId) async {
    return TradeTimelineModel(
      tradeId: tradeId,
      currentStatus: 'FILLED',
      events: <TradeTimelineEventModel>[
        TradeTimelineEventModel(
          timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
          stage: 'SIGNAL_ACCEPTED',
          status: 'ACCEPTED',
          description: 'Accepted',
          metadata: const <String, dynamic>{},
        ),
      ],
    );
  }

  @override
  Future<MetaDecisionModel> fetchMetaDecision(String tradeId) async {
    return MetaDecisionModel(
      tradeId: tradeId,
      userId: 'u1',
      symbol: 'BTCUSDT',
      decision: 'APPROVED',
      strategy: 'AI',
      confidence: 0.82,
      signals: const <String, dynamic>{'ai_score': 84},
      conflicts: const <String>[],
      riskAdjustments: const <String, dynamic>{'meta_capital_multiplier': 1.0},
      systemHealthSnapshot: const <String, dynamic>{'healthy': true},
      reason: 'Approved by meta controller.',
    );
  }

  @override
  Future<UserPnLModel> fetchUserPnL(String userId) async {
    return const UserPnLModel(
      userId: 'u1',
      startingEquity: 10000,
      currentEquity: 10125,
      absolutePnl: 125,
      pnlPct: 0.0125,
      peakEquity: 10125,
      rollingDrawdown: 0,
      protectionState: 'NORMAL',
      capitalMultiplier: 1,
      activeTrades: 2,
    );
  }

  @override
  Stream<UserPnLModel> watchUserPnL(String userId) async* {
    yield await fetchUserPnL(userId);
  }

  @override
  Future<PortfolioConcentrationHistoryModel> fetchConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async {
    return const PortfolioConcentrationHistoryModel(
      history: <PortfolioConcentrationSnapshotModel>[
        PortfolioConcentrationSnapshotModel(
          updatedAt: null,
          grossExposurePct: 0.34,
          maxSymbolExposurePct: 0.18,
          maxSideExposurePct: 0.12,
          maxThemeExposurePct: 0.1,
          maxClusterExposurePct: 0.09,
          maxBetaBucketExposurePct: 0.08,
          grossExposureDrift: 0.01,
          clusterConcentrationDrift: 0.02,
          betaBucketConcentrationDrift: 0.01,
          clusterTurnover: 0.05,
          factorSleeveBudgetTurnover: 0.03,
          maxFactorSleeveBudgetGapPct: 0.04,
          severity: 'normal',
          severityReason: null,
          factorRegime: 'TRENDING',
          factorModel: 'demo-model',
          factorUniverseSymbols: <String>['BTCUSDT'],
          factorWeights: <String, double>{'momentum': 0.6},
          factorAttribution: <String, double>{'momentum': 0.12},
          factorSleevePerformance: <String, Map<String, dynamic>>{},
          factorSleeveBudgetTargets: <String, double>{'momentum': 0.5},
          factorSleeveBudgetDeltas: <String, double>{'momentum': 0.1},
          dominantFactorSleeve: 'momentum',
          dominantSymbol: 'BTCUSDT',
          dominantSide: 'LONG',
          dominantTheme: 'macro',
          dominantCluster: 'majors',
          dominantBetaBucket: 'high-beta',
          dominantOverBudgetSleeve: null,
          dominantUnderBudgetSleeve: null,
        ),
      ],
      latest: PortfolioConcentrationSnapshotModel(
        updatedAt: null,
        grossExposurePct: 0.34,
        maxSymbolExposurePct: 0.18,
        maxSideExposurePct: 0.12,
        maxThemeExposurePct: 0.1,
        maxClusterExposurePct: 0.09,
        maxBetaBucketExposurePct: 0.08,
        grossExposureDrift: 0.01,
        clusterConcentrationDrift: 0.02,
        betaBucketConcentrationDrift: 0.01,
        clusterTurnover: 0.05,
        factorSleeveBudgetTurnover: 0.03,
        maxFactorSleeveBudgetGapPct: 0.04,
        severity: 'normal',
        severityReason: null,
        factorRegime: 'TRENDING',
        factorModel: 'demo-model',
        factorUniverseSymbols: <String>['BTCUSDT'],
        factorWeights: <String, double>{'momentum': 0.6},
        factorAttribution: <String, double>{'momentum': 0.12},
        factorSleevePerformance: <String, Map<String, dynamic>>{},
        factorSleeveBudgetTargets: <String, double>{'momentum': 0.5},
        factorSleeveBudgetDeltas: <String, double>{'momentum': 0.1},
        dominantFactorSleeve: 'momentum',
        dominantSymbol: 'BTCUSDT',
        dominantSide: 'LONG',
        dominantTheme: 'macro',
        dominantCluster: 'majors',
        dominantBetaBucket: 'high-beta',
        dominantOverBudgetSleeve: null,
        dominantUnderBudgetSleeve: null,
      ),
    );
  }

  @override
  Stream<PortfolioConcentrationHistoryModel> watchConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async* {
    yield await fetchConcentrationHistory(window: window, limit: limit);
  }
}

void main() {
  testWidgets('default production API key enters the app shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          authCredentialsStoreProvider.overrideWithValue(
            MemoryAuthCredentialsStore(),
          ),
          tradingRepositoryProvider.overrideWithValue(FakeTradingRepository()),
        ],
        child: const TradingApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(TradingApp), findsOneWidget);
    expect(find.text('AI Trading Dashboard'), findsOneWidget);
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Portfolio'), findsWidgets);
  });

  testWidgets('authenticated users enter the app shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: <Override>[
          authCredentialsStoreProvider.overrideWithValue(
            MemoryAuthCredentialsStore(
              initialSession: const AuthSession(accessToken: 'test-token'),
            ),
          ),
          tradingRepositoryProvider.overrideWithValue(FakeTradingRepository()),
        ],
        child: const TradingApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(TradingApp), findsOneWidget);
    expect(find.text('AI Trading Dashboard'), findsOneWidget);
    expect(find.text('Dashboard'), findsWidgets);
    expect(find.text('Portfolio'), findsWidgets);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}

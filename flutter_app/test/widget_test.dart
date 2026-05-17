import 'dart:async';

import 'package:ai_trading_app/core/api_client.dart';
import 'package:ai_trading_app/core/api_exception.dart';
import 'package:ai_trading_app/core/auth_credentials_store.dart';
import 'package:ai_trading_app/core/constants.dart';
import 'package:ai_trading_app/core/error_mapper.dart';
import 'package:ai_trading_app/core/websocket_service.dart';
import 'package:ai_trading_app/features/market/providers/market_providers.dart';
import 'package:ai_trading_app/features/retention/providers/retention_providers.dart';
import 'package:ai_trading_app/main.dart';
import 'package:ai_trading_app/models/activity.dart';
import 'package:ai_trading_app/models/active_trade.dart';
import 'package:ai_trading_app/models/batch.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:ai_trading_app/models/market_summary.dart';
import 'package:ai_trading_app/models/meta_analytics.dart';
import 'package:ai_trading_app/models/meta_decision.dart';
import 'package:ai_trading_app/models/portfolio_concentration.dart';
import 'package:ai_trading_app/models/public_dashboard.dart';
import 'package:ai_trading_app/models/realtime_event.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:ai_trading_app/models/system_health.dart';
import 'package:ai_trading_app/models/trade_timeline.dart';
import 'package:ai_trading_app/models/user_pnl.dart';
import 'package:ai_trading_app/providers/app_providers.dart';
import 'package:ai_trading_app/repositories/trading_repository.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeApiClient extends ApiClient {
  FakeApiClient()
      : super(
          baseUrl: AppConstants.productionApiBaseUrl,
        );

  @override
  Future<Map<String, dynamic>> getHealthStatus() async {
    return <String, dynamic>{
      'status': 'ok',
      'version': 'test-build',
      'deployment_mode': 'PROD:PAPER',
      'build_timestamp': '2026-01-01T00:00:00Z',
      'readiness': <String, dynamic>{
        'ready': true,
        'checks': <String, dynamic>{'redis': 'ready'},
      },
    };
  }

  @override
  Future<Map<String, dynamic>> getRootStatus() {
    return getHealthStatus();
  }
}

class FakeWebSocketService extends WebSocketService {
  FakeWebSocketService()
      : _state = ValueNotifier<WsState>(WsState.connected),
        super(baseUrl: AppConstants.productionSignalsWebSocketUrl);

  final ValueNotifier<WsState> _state;

  @override
  ValueListenable<WsState> get stateListenable => _state;

  @override
  String get baseUrl => AppConstants.productionSignalsWebSocketUrl;

  @override
  Stream<Map<String, dynamic>> connectEvents() =>
      const Stream<Map<String, dynamic>>.empty();

  @override
  Future<Map<String, dynamic>> probeSignals({
    Duration timeout = AppConstants.websocketProbeTimeout,
  }) async {
    return const <String, dynamic>{'type': 'pong'};
  }

  @override
  void reconnectNow() {
    _state.value = WsState.connected;
  }

  @override
  Future<void> dispose() async {
    _state.dispose();
  }
}

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

class FailingOnboardingStorage extends FlutterSecureStorage {
  const FailingOnboardingStorage();

  @override
  Future<String?> read({
    required String key,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    return null;
  }

  @override
  Future<void> write({
    required String key,
    required String? value,
    IOSOptions? iOptions,
    AndroidOptions? aOptions,
    LinuxOptions? lOptions,
    WebOptions? webOptions,
    MacOsOptions? mOptions,
    WindowsOptions? wOptions,
  }) async {
    throw StateError('secure storage unavailable');
  }
}

class FakeTradingRepository extends TradingRepository {
  FakeTradingRepository()
      : super(
          apiClient: ApiClient(
            baseUrl: AppConstants.productionApiBaseUrl,
          ),
          webSocketService: WebSocketService(
            baseUrl: AppConstants.productionSignalsWebSocketUrl,
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
        quality: 'approved',
        qualityScore: 82,
        qualityReasons: const <String>['Meta approved directional setup'],
        executionAllowed: true,
        marketDataStale: false,
        marketDataSources: const <String, String>{'primary': 'scanner'},
      ),
    ];
  }

  @override
  Future<MarketChartModel> fetchMarketCandles({
    required String symbol,
    String interval = '5m',
    int limit = 96,
    String? userId,
  }) async {
    return MarketChartModel(
      symbol: symbol,
      interval: interval,
      latestPrice: 100000,
      changePct: 1.2,
      candles: <MarketCandleModel>[
        MarketCandleModel(
          timestampMs:
              DateTime.parse('2026-01-01T00:00:00Z').millisecondsSinceEpoch,
          open: 99500,
          high: 100500,
          low: 99000,
          close: 100000,
          volume: 1200,
        ),
      ],
      markers: const <TradeMarkerModel>[],
      confidenceIntervals: const <ConfidenceIntervalModel>[],
      confidenceHistory: const <ConfidenceHistoryPointModel>[],
      executionGuide: const ChartExecutionGuideModel(
        side: 'BUY',
        entryLow: 99800,
        entryHigh: 100000,
        stopLoss: 98500,
        tp1: 102000,
        tp2: 104000,
        riskReward: 2.4,
        riskPct: 1.5,
        rewardPct: 3.6,
      ),
    );
  }

  @override
  Future<void> prefetchMarketContext({
    required String symbol,
    required String interval,
    String? userId,
  }) async {}

  @override
  Stream<ChartRealtimeSnapshotModel> watchChartSnapshots({String? symbol}) =>
      const Stream<ChartRealtimeSnapshotModel>.empty();

  @override
  Stream<Map<String, dynamic>> watchRecoveryRequests() =>
      const Stream<Map<String, dynamic>>.empty();

  @override
  Stream<SignalModel> watchSignals() => const Stream<SignalModel>.empty();

  @override
  Future<List<ActivityItemModel>> fetchActivityHistory({int limit = 25}) async {
    return <ActivityItemModel>[
      ActivityItemModel(
        type: 'activity',
        status: 'ready',
        botState: 'SCANNING',
        mode: 'PAPER',
        message: 'BTCUSDT remains the highest quality setup in the scanner.',
        timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
        symbol: 'BTCUSDT',
        readiness: 82,
        confidence: 0.82,
        regime: 'TRENDING',
      ),
    ].take(limit).toList();
  }

  @override
  Stream<ActivityItemModel> watchActivity() =>
      const Stream<ActivityItemModel>.empty();

  @override
  Future<List<ReadinessCardModel>> fetchReadinessBoard({int limit = 8}) async {
    return <ReadinessCardModel>[
      ReadinessCardModel(
        symbol: 'BTCUSDT',
        readiness: 82,
        status: 'ready',
        updatedAt: DateTime.parse('2026-01-01T00:00:00Z'),
        regime: 'TRENDING',
        botState: 'SCANNING',
      ),
    ].take(limit).toList();
  }

  @override
  Future<MarketUniverseModel> fetchMarketUniverse({int limit = 18}) async {
    const btc = MarketUniverseEntryModel(
      symbol: 'BTCUSDT',
      price: 100000,
      changePct: 2.4,
      volumeRatio: 1.8,
      volatilityPct: 3.2,
      trendPct: 1.4,
      quoteVolume: 1200000,
      category: 'major',
    );
    const eth = MarketUniverseEntryModel(
      symbol: 'ETHUSDT',
      price: 3200,
      changePct: 1.3,
      volumeRatio: 1.4,
      volatilityPct: 2.6,
      trendPct: 1.1,
      quoteVolume: 950000,
      category: 'major',
    );
    return const MarketUniverseModel(
      items: <MarketUniverseEntryModel>[btc, eth],
      topGainers: <MarketUniverseEntryModel>[btc, eth],
      highVolatility: <MarketUniverseEntryModel>[btc],
      aiPicks: <MarketUniverseEntryModel>[btc],
    );
  }

  @override
  Future<MarketSummaryModel> fetchMarketSummary({int limit = 18}) async {
    return MarketSummaryModel(
      sentimentScore: 72,
      sentimentLabel: 'BULLISH',
      marketBreadth: 68,
      avgChangePct: 1.7,
      avgVolatilityPct: 2.4,
      participationScore: 74,
      confidenceScore: 81,
      ticker: const <MarketTickerItemModel>[
        MarketTickerItemModel(symbol: 'BTCUSDT', price: 100000, changePct: 2.4),
      ],
      heatmap: const <MarketHeatmapItemModel>[
        MarketHeatmapItemModel(
          symbol: 'BTCUSDT',
          changePct: 2.4,
          intensity: 0.8,
        ),
      ],
      scanner: MarketScannerModel(
        activeSymbols: const <String>['BTCUSDT', 'ETHUSDT'],
        fixedSymbols: const <String>['BTCUSDT'],
        rotatingSymbols: const <String>['ETHUSDT'],
        candidates: const <ScannerCandidateModel>[
          ScannerCandidateModel(
            symbol: 'BTCUSDT',
            price: 100000,
            changePct: 2.4,
            quoteVolume: 1200000,
            volumeRatio: 1.8,
            volumeSpikePct: 28,
            volatilityPct: 3.2,
            potentialScore: 86,
            exchange: 'binance',
          ),
        ],
        rotationStartedAt: DateTime.parse('2026-01-01T00:00:00Z'),
        nextRotationAt: DateTime.parse('2026-01-01T00:15:00Z'),
        secondsUntilRotation: 600,
      ),
      confidenceHistory: <ConfidenceHistoryPointModel>[
        ConfidenceHistoryPointModel(
          timestamp: DateTime.parse('2026-01-01T00:00:00Z'),
          score: 0.78,
          isGhost: false,
          symbol: 'BTCUSDT',
        ),
      ],
    );
  }

  @override
  Future<List<ActiveTradeModel>> fetchActiveTrades(String userId) async {
    return const <ActiveTradeModel>[
      ActiveTradeModel(
        tradeId: 'trade-1',
        symbol: 'BTCUSDT',
        side: 'BUY',
        entry: 100000,
        stopLoss: 98500,
        takeProfit: 103500,
        executedQuantity: 0.01,
        entryReason: 'Meta approved directional setup.',
        status: 'OPEN',
        regime: 'TRENDING',
        riskFraction: 0.01,
      ),
    ];
  }

  @override
  Stream<List<ActiveTradeModel>> watchActiveTrades(String userId) async* {
    yield await fetchActiveTrades(userId);
  }

  @override
  Stream<RealtimeTradeUpdateModel> watchTradeUpdates({String? userId}) =>
      const Stream<RealtimeTradeUpdateModel>.empty();

  @override
  Stream<RealtimePortfolioUpdateModel> watchPortfolioUpdates(
          {String? userId}) =>
      const Stream<RealtimePortfolioUpdateModel>.empty();

  @override
  Stream<DashboardRealtimeSummaryModel> watchDashboardSummaries({
    String? userId,
  }) =>
      const Stream<DashboardRealtimeSummaryModel>.empty();

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

List<Override> _commonOverrides({
  required MemoryAuthCredentialsStore authStore,
}) {
  final fakeRepository = FakeTradingRepository();
  return <Override>[
    authCredentialsStoreProvider.overrideWithValue(authStore),
    apiClientProvider.overrideWithValue(FakeApiClient()),
    webSocketServiceProvider.overrideWithValue(FakeWebSocketService()),
    tradingRepositoryProvider.overrideWithValue(fakeRepository),
    marketUniverseProvider.overrideWith(
      (ref) => Stream<MarketUniverseModel>.fromFuture(
        fakeRepository.fetchMarketUniverse(),
      ),
    ),
    marketSummaryProvider.overrideWith(
      (ref) => Stream<MarketSummaryModel>.fromFuture(
        fakeRepository.fetchMarketSummary(),
      ),
    ),
    onboardingCompletedProvider.overrideWith(
      (ref) => OnboardingCompletedNotifier(initial: true, persist: false),
    ),
  ];
}

void main() {
  test('backend connectivity errors map to non-blocking degraded mode copy',
      () {
    final serverMessage = ErrorMapper.map(
      const ApiException(
        'Internal Server Error',
        statusCode: 500,
        code: 'server_error',
      ),
    );
    final timeoutMessage = ErrorMapper.map(
      const ApiException('timeout', code: 'timeout'),
    );
    final invalidResponseMessage = ErrorMapper.map(
      const ApiException('invalid json', code: 'invalid_response'),
    );
    final riskMessage = ErrorMapper.map(
      const ApiException(
        'blocked',
        code: 'DAILY_LOSS_LIMIT_REACHED',
      ),
    );

    expect(serverMessage, contains('Backend is reconnecting'));
    expect(timeoutMessage, contains('Backend is reconnecting'));
    expect(invalidResponseMessage, contains('Backend is reconnecting'));
    expect(serverMessage.toLowerCase(), isNot(contains('server error')));
    expect(
        ErrorMapper.isRecoverableBackend(
          const ApiException('Internal Server Error', statusCode: 500),
        ),
        isTrue);
    expect(
        ErrorMapper.isRecoverableBackend(
          const ApiException('blocked', code: 'DAILY_LOSS_LIMIT_REACHED'),
        ),
        isFalse);
    expect(riskMessage, contains('Daily loss protection'));
  });

  test('onboarding completion does not block on secure storage failures',
      () async {
    final previousOnError = FlutterError.onError;
    final reportedErrors = <FlutterErrorDetails>[];
    FlutterError.onError = reportedErrors.add;
    addTearDown(() => FlutterError.onError = previousOnError);

    final container = ProviderContainer(
      overrides: <Override>[
        onboardingCompletedProvider.overrideWith(
          (ref) => OnboardingCompletedNotifier(
            storage: const FailingOnboardingStorage(),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await container.read(onboardingCompletedProvider.notifier).markCompleted();

    expect(container.read(onboardingCompletedProvider), isTrue);
    expect(reportedErrors, isNotEmpty);
  });

  testWidgets('default production API key enters the app shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: _commonOverrides(
          authStore: MemoryAuthCredentialsStore(),
        ),
        child: const TradingApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(TradingApp), findsOneWidget);
    expect(find.text('AI Trade Center'), findsOneWidget);
    expect(find.text('AI Trade'), findsWidgets);
    expect(find.text('BEST AI TRADE NOW'), findsOneWidget);
    expect(find.text('Portfolio'), findsWidgets);
  });

  testWidgets('authenticated users enter the app shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: _commonOverrides(
          authStore: MemoryAuthCredentialsStore(
            initialSession: const AuthSession(accessToken: 'test-token'),
          ),
        ),
        child: const TradingApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(TradingApp), findsOneWidget);
    expect(find.text('AI Trade Center'), findsOneWidget);
    expect(find.text('AI Trade'), findsWidgets);
    expect(find.text('BEST AI TRADE NOW'), findsOneWidget);
    expect(find.text('Portfolio'), findsWidgets);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump();
  });
}

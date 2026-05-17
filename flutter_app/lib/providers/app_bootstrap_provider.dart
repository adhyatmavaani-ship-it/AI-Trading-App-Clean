import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/backend_warmup_state.dart';
import '../core/constants.dart';
import '../models/meta_analytics.dart';
import '../models/signal.dart';
import '../models/user_pnl.dart';
import 'app_providers.dart';

class AppBootstrapSnapshot {
  const AppBootstrapSnapshot({
    required this.signals,
    required this.portfolio,
    required this.meta,
  });

  final List<SignalModel> signals;
  final UserPnLModel portfolio;
  final MetaAnalyticsModel meta;
}

class AppBootstrapNotifier extends AsyncNotifier<AppBootstrapSnapshot> {
  @override
  Future<AppBootstrapSnapshot> build() {
    return _loadAppData();
  }

  Future<void> refresh() async {
    state = const AsyncLoading<AppBootstrapSnapshot>();
    state = await AsyncValue.guard(_loadAppData);
  }

  Future<AppBootstrapSnapshot> _loadAppData() async {
    final repository = ref.read(tradingRepositoryProvider);
    markBackendConnecting();

    var degraded = false;
    final signals = await repository.fetchSignals(limit: 5).catchError((_) {
      degraded = true;
      return _fallbackSignals();
    });
    final portfolio = await repository
        .fetchUserPnL(AppConstants.requiredUserId)
        .catchError((_) {
      degraded = true;
      return _fallbackPortfolio();
    });
    final meta = await repository.fetchMetaAnalytics().catchError((_) {
      degraded = true;
      return _fallbackMeta();
    });

    if (degraded) {
      markBackendSlow();
    } else {
      markBackendReady();
    }
    return AppBootstrapSnapshot(
      signals: signals,
      portfolio: portfolio,
      meta: meta,
    );
  }

  List<SignalModel> _fallbackSignals() {
    final now = DateTime.now();
    return <SignalModel>[
      SignalModel(
        signalId: 'local-paper-btc-${now.millisecondsSinceEpoch}',
        symbol: 'BTCUSDT',
        action: 'BUY',
        strategy: 'LOCAL_PAPER_ADVISORY',
        confidence: 0.64,
        alphaScore: 64,
        regime: 'DEGRADED_ADVISORY',
        price: 0,
        signalVersion: 1,
        publishedAt: now,
        decisionReason:
            'Production connection is recovering. Use paper mode while realtime auth reconnects.',
        degradedMode: true,
        requiredTier: 'free',
        minBalance: 0,
        rejectionReason: null,
        lowConfidence: false,
        quality: 'watchlist',
        qualityScore: 64,
        qualityReasons: const <String>[
          'local_advisory_mode',
          'paper_trading_available',
        ],
        executionAllowed: false,
        marketDataStale: true,
        marketDataSources: const <String, String>{'mode': 'local'},
      ),
    ];
  }

  UserPnLModel _fallbackPortfolio() {
    return const UserPnLModel(
      userId: 'paper-local',
      startingEquity: 10000,
      currentEquity: 10000,
      absolutePnl: 0,
      pnlPct: 0,
      peakEquity: 10000,
      rollingDrawdown: 0,
      protectionState: 'PAPER_MODE',
      capitalMultiplier: 1,
      activeTrades: 0,
    );
  }

  MetaAnalyticsModel _fallbackMeta() {
    return const MetaAnalyticsModel(
      blockedTrades: MetaBlockedTradesModel(total: 0, reasons: <String, int>{}),
      strategyPerformance: <String, MetaStrategyPerformanceModel>{},
      confidenceDistribution: <String, int>{},
      learning: MetaLearningModel(
        enabled: false,
        blacklistTotal: 0,
        whitelistTotal: 0,
        regimes: <String, MetaLearningRegimeModel>{},
      ),
    );
  }
}

final appBootstrapProvider =
    AsyncNotifierProvider<AppBootstrapNotifier, AppBootstrapSnapshot>(
  AppBootstrapNotifier.new,
);

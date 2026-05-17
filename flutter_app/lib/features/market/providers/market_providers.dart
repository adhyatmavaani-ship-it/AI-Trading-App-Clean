import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/market_chart.dart';
import '../../../models/market_summary.dart';
import '../../../models/realtime_event.dart';
import '../../../providers/app_providers.dart';
import '../../pnl/providers/pnl_providers.dart';

final selectedMarketSymbolProvider = StateProvider<String>((ref) => 'BTCUSDT');

final selectedMarketIntervalProvider = StateProvider<String>((ref) => '5m');

final marketChartProvider =
    StreamProvider.autoDispose<MarketChartModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  final symbol = ref.watch(selectedMarketSymbolProvider);
  final interval = ref.watch(selectedMarketIntervalProvider);
  final userId = ref.watch(activeUserIdProvider);
  final controller = StreamController<MarketChartModel>();
  Timer? pollTimer;
  StreamSubscription<ChartRealtimeSnapshotModel>? realtimeSubscription;
  StreamSubscription<Map<String, dynamic>>? recoverySubscription;
  MarketChartModel? latest;
  bool refreshInFlight = false;

  Future<void> refresh() async {
    if (refreshInFlight) {
      return;
    }
    refreshInFlight = true;
    try {
      latest = await repository.fetchMarketCandles(
        symbol: symbol,
        interval: interval,
        userId: userId,
      );
      if (!controller.isClosed && latest != null) {
        controller.add(latest!);
      }
      unawaited(
        repository.prefetchMarketContext(
          symbol: symbol,
          interval: interval,
          userId: userId,
        ),
      );
    } catch (error, stackTrace) {
      if (!controller.isClosed) {
        controller.addError(error, stackTrace);
      }
    } finally {
      refreshInFlight = false;
    }
  }

  void ingestRealtime(ChartRealtimeSnapshotModel snapshot) {
    final current = latest;
    if (current == null) {
      unawaited(refresh());
      return;
    }
    if (snapshot.snapshotVersion > 0 &&
        current.snapshotVersion > 0 &&
        snapshot.snapshotVersion < current.snapshotVersion) {
      return;
    }
    final mergedCandles = <MarketCandleModel>[...current.candles];
    final patch = snapshot.latestCandle;
    if (patch != null &&
        snapshot.interval.toLowerCase() == current.interval.toLowerCase()) {
      if (mergedCandles.isNotEmpty &&
          mergedCandles.last.timestampMs == patch.timestampMs) {
        mergedCandles[mergedCandles.length - 1] = patch;
      } else if (patch.timestampMs > 0) {
        mergedCandles.add(patch);
      }
      if (mergedCandles.length > 240) {
        mergedCandles.removeRange(0, mergedCandles.length - 240);
      }
    }

    latest = current.copyWith(
      latestPrice: snapshot.latestPrice == 0
          ? current.latestPrice
          : snapshot.latestPrice,
      changePct:
          snapshot.changePct == 0 ? current.changePct : snapshot.changePct,
      candles: mergedCandles,
      markers: snapshot.markers.isEmpty ? current.markers : snapshot.markers,
      overlays:
          snapshot.overlays.isEmpty ? current.overlays : snapshot.overlays,
      opportunity: snapshot.opportunity,
      marketRegime: snapshot.marketRegime,
      assistantModes: snapshot.assistantModes.isEmpty
          ? current.assistantModes
          : snapshot.assistantModes,
      activeAssistantMode: snapshot.activeAssistantMode,
      executionGuide: snapshot.executionGuide,
      strategyState: snapshot.strategyState,
      aiFeed: snapshot.aiFeed.isEmpty ? current.aiFeed : snapshot.aiFeed,
      trailingStop: snapshot.trailingStop,
      chartEngine: snapshot.chartEngine.isEmpty
          ? current.chartEngine
          : snapshot.chartEngine,
      renderHints: snapshot.renderHints.isEmpty
          ? current.renderHints
          : snapshot.renderHints,
      snapshotVersion: snapshot.snapshotVersion == 0
          ? current.snapshotVersion
          : snapshot.snapshotVersion,
      stateHash: snapshot.stateHash.isEmpty ? current.stateHash : snapshot.stateHash,
      integrityChecksum: snapshot.integrityChecksum.isEmpty
          ? current.integrityChecksum
          : snapshot.integrityChecksum,
    );
    if (!controller.isClosed && latest != null) {
      controller.add(latest!);
    }
  }

  unawaited(refresh());
  realtimeSubscription = repository.watchChartSnapshots(symbol: symbol).listen(
        ingestRealtime,
        onError: controller.addError,
      );
  recoverySubscription = repository.watchRecoveryRequests().listen(
    (event) {
      if ((event['stream'] as String?) == 'chart_snapshot') {
        unawaited(refresh());
      }
    },
    onError: controller.addError,
  );
  pollTimer = Timer.periodic(
    AppConstants.chartRefreshInterval,
    (_) => unawaited(refresh()),
  );

  ref.onDispose(() async {
    pollTimer?.cancel();
    await realtimeSubscription?.cancel();
    await recoverySubscription?.cancel();
    await controller.close();
  });

  yield* controller.stream;
});

final marketUniverseProvider =
    StreamProvider.autoDispose<MarketUniverseModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  yield await repository.fetchMarketUniverse();
  while (true) {
    await Future<void>.delayed(AppConstants.marketSurfaceRefreshInterval);
    yield await repository.fetchMarketUniverse();
  }
});

final marketSummaryProvider =
    StreamProvider.autoDispose<MarketSummaryModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  yield await repository.fetchMarketSummary();
  while (true) {
    await Future<void>.delayed(AppConstants.marketSurfaceRefreshInterval);
    yield await repository.fetchMarketSummary();
  }
});

final assistantModeProvider = FutureProvider.autoDispose<String>((ref) {
  return ref.watch(tradingRepositoryProvider).fetchAssistantMode();
});

final aiTradeFeedProvider =
    StreamProvider.autoDispose<List<AiTradeFeedRealtimeModel>>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  final symbol = ref.watch(selectedMarketSymbolProvider);
  final controller = StreamController<List<AiTradeFeedRealtimeModel>>();
  final items = <AiTradeFeedRealtimeModel>[];
  late final StreamSubscription<AiTradeFeedRealtimeModel> subscription;

  void emit() {
    if (!controller.isClosed) {
      controller.add(List<AiTradeFeedRealtimeModel>.from(items));
    }
  }

  subscription = repository.watchAiTradeFeed(symbol: symbol).listen(
    (event) {
      items.insert(0, event);
      if (items.length > 8) {
        items.removeRange(8, items.length);
      }
      emit();
    },
    onError: controller.addError,
  );

  ref.onDispose(() async {
    await subscription.cancel();
    await controller.close();
  });

  emit();
  yield* controller.stream;
});

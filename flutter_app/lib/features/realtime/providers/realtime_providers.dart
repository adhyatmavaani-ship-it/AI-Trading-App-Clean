import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/realtime_event.dart';
import '../../../providers/app_providers.dart';

final tradeUpdateStreamProvider =
    StreamProvider.autoDispose.family<RealtimeTradeUpdateModel, String>((
  ref,
  userId,
) {
  return ref.watch(tradingRepositoryProvider).watchTradeUpdates(userId: userId);
});

final latestTradeUpdateProvider = Provider.autoDispose
    .family<RealtimeTradeUpdateModel?, String>((ref, userId) {
  return ref.watch(tradeUpdateStreamProvider(userId)).valueOrNull;
});

final dashboardSummaryStreamProvider =
    StreamProvider.autoDispose.family<DashboardRealtimeSummaryModel, String>((
  ref,
  userId,
) {
  return ref
      .watch(tradingRepositoryProvider)
      .watchDashboardSummaries(userId: userId);
});

final latestDashboardSummaryProvider =
    Provider.autoDispose.family<DashboardRealtimeSummaryModel?, String>((
  ref,
  userId,
) {
  return ref.watch(dashboardSummaryStreamProvider(userId)).valueOrNull;
});

final portfolioUpdateStreamProvider =
    StreamProvider.autoDispose.family<RealtimePortfolioUpdateModel, String>((
  ref,
  userId,
) {
  return ref
      .watch(tradingRepositoryProvider)
      .watchPortfolioUpdates(userId: userId);
});

final latestPortfolioUpdateProvider =
    Provider.autoDispose.family<RealtimePortfolioUpdateModel?, String>((
  ref,
  userId,
) {
  return ref.watch(portfolioUpdateStreamProvider(userId)).valueOrNull;
});

final chartOrderActionStreamProvider =
    StreamProvider.autoDispose.family<ChartOrderActionModel, String>((
  ref,
  symbol,
) {
  return ref.watch(tradingRepositoryProvider).watchChartOrderActions(
        symbol: symbol,
      );
});

final chartOrderActionFeedProvider =
    StreamProvider.autoDispose.family<List<ChartOrderActionModel>, String>((
  ref,
  symbol,
) async* {
  final controller = StreamController<List<ChartOrderActionModel>>();
  final actions = <ChartOrderActionModel>[];
  final subscription = ref
      .watch(tradingRepositoryProvider)
      .watchChartOrderActions(symbol: symbol)
      .listen(
    (event) {
      actions.removeWhere((item) =>
          item.actionId == event.actionId ||
          (item.chartOrderId != null &&
              item.chartOrderId == event.chartOrderId));
      actions.insert(0, event);
      if (actions.length > 24) {
        actions.removeRange(24, actions.length);
      }
      if (!controller.isClosed) {
        controller.add(List<ChartOrderActionModel>.unmodifiable(actions));
      }
    },
    onError: controller.addError,
  );

  ref.onDispose(() async {
    await subscription.cancel();
    await controller.close();
  });

  controller.add(const <ChartOrderActionModel>[]);
  yield* controller.stream;
});

final latestChartOrderActionProvider =
    Provider.autoDispose.family<ChartOrderActionModel?, String>((ref, symbol) {
  final actions = ref.watch(chartOrderActionFeedProvider(symbol)).valueOrNull;
  return actions == null || actions.isEmpty ? null : actions.first;
});

final strategyPerformanceUpdateStreamProvider =
    StreamProvider.autoDispose<StrategyPerformanceUpdateModel>((ref) {
  return ref.watch(tradingRepositoryProvider).watchStrategyPerformanceUpdates();
});

final latestStrategyPerformanceUpdateProvider =
    Provider.autoDispose<StrategyPerformanceUpdateModel?>((ref) {
  return ref.watch(strategyPerformanceUpdateStreamProvider).valueOrNull;
});

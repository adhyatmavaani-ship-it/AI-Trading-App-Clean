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

final latestTradeUpdateProvider =
    Provider.autoDispose.family<RealtimeTradeUpdateModel?, String>((ref, userId) {
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

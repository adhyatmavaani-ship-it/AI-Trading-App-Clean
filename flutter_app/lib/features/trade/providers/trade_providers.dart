import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/trade_timeline.dart';
import '../../../providers/app_providers.dart';

final selectedTradeIdProvider = StateProvider<String?>((ref) => null);

final tradeTimelineProvider =
    FutureProvider.family<TradeTimelineModel, String>((ref, tradeId) {
  return ref.watch(tradingRepositoryProvider).fetchTradeTimeline(tradeId);
});

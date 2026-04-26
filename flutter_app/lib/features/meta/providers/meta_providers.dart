import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/meta_analytics.dart';
import '../../../models/meta_decision.dart';
import '../../../providers/app_providers.dart';

final metaDecisionProvider =
    FutureProvider.family<MetaDecisionModel, String>((ref, tradeId) {
  return ref.watch(tradingRepositoryProvider).fetchMetaDecision(tradeId);
});

final metaAnalyticsProvider = StreamProvider<MetaAnalyticsModel>((ref) {
  return ref.watch(tradingRepositoryProvider).watchMetaAnalytics();
});

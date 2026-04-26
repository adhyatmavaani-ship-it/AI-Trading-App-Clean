import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/batch.dart';
import '../../../models/portfolio_concentration.dart';
import '../../../models/system_health.dart';
import '../../../providers/app_providers.dart';

final batchesProvider = StreamProvider<List<BatchModel>>((ref) {
  return ref.watch(tradingRepositoryProvider).watchBatches(limit: 25);
});

final systemHealthProvider = StreamProvider<SystemHealthModel>((ref) {
  return ref.watch(tradingRepositoryProvider).watchSystemHealth();
});

final concentrationWindowProvider = StateProvider<String>((ref) => '24h');

final concentrationHistoryProvider =
    StreamProvider<PortfolioConcentrationHistoryModel>((ref) {
  final window = ref.watch(concentrationWindowProvider);
  return ref
      .watch(tradingRepositoryProvider)
      .watchConcentrationHistory(window: window, limit: 32);
});

final modelStabilityConcentrationHistoryProvider =
    StreamProvider<ModelStabilityConcentrationHistoryModel>((ref) {
  final window = ref.watch(concentrationWindowProvider);
  return ref
      .watch(tradingRepositoryProvider)
      .watchModelStabilityConcentrationHistory(window: window, limit: 32);
});

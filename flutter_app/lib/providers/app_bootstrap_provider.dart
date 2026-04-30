import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/backend_warmup_state.dart';
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

    final signals = await repository.fetchSignals(limit: 5);
    final portfolio = await repository.fetchUserPnL('alice');
    final meta = await repository.fetchMetaAnalytics();

    markBackendReady();
    return AppBootstrapSnapshot(
      signals: signals,
      portfolio: portfolio,
      meta: meta,
    );
  }
}

final appBootstrapProvider =
    AsyncNotifierProvider<AppBootstrapNotifier, AppBootstrapSnapshot>(
  AppBootstrapNotifier.new,
);

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/production_diagnostics.dart';
import '../../../models/system_diagnostics.dart';
import '../../../providers/app_providers.dart';

final exchangeDiagnosticsProvider =
    StreamProvider<SystemDiagnosticsModel>((ref) {
  return ref
      .watch(tradingRepositoryProvider)
      .watchExchangeDiagnostics(sampleSymbol: 'BTCUSDT');
});

final productionDiagnosticsProvider =
    StreamProvider.autoDispose<ProductionDiagnosticsModel>((ref) async* {
  final apiClient = ref.watch(apiClientProvider);
  final repository = ref.watch(tradingRepositoryProvider);

  Future<ProductionDiagnosticsModel> load() async {
    final startedAt = DateTime.now();
    final health = await apiClient.getHealthStatus();
    final diagnostics = await repository.fetchExchangeDiagnostics();
    final readiness =
        (health['readiness'] as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{})
            .cast<String, dynamic>();
    final checks =
        (readiness['checks'] as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{})
            .cast<String, dynamic>();
    return ProductionDiagnosticsModel(
      apiHealthy: (health['status'] as String? ?? '').toLowerCase() == 'ok',
      apiReady: readiness['ready'] as bool? ?? false,
      apiStatus: (health['status'] as String? ?? 'unknown').toUpperCase(),
      latencyMs: DateTime.now().difference(startedAt).inMilliseconds,
      redisState: (checks['redis'] as String? ?? 'unknown').toUpperCase(),
      deploymentMode:
          (health['deployment_mode'] as String? ?? 'unknown').toUpperCase(),
      backendVersion: (health['version'] as String? ?? 'unknown').toString(),
      buildTimestamp:
          (health['build_timestamp'] as String? ?? 'unknown').toString(),
      marketDataMode: diagnostics.resolvedMode.toUpperCase(),
      usingMockData: diagnostics.usingMockData,
      activeExchanges: diagnostics.activeExchanges,
    );
  }

  yield await load();
  while (true) {
    await Future<void>.delayed(AppConstants.realtimeFallbackPollingInterval);
    yield await load();
  }
});

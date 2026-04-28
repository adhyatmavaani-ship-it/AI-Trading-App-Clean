import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth_credentials_store.dart';
import '../../../models/app_settings.dart';
import '../../../providers/app_providers.dart';
import '../../../repositories/trading_repository.dart';

class AppSettingsNotifier extends StateNotifier<AppSettings> {
  AppSettingsNotifier(this._credentialsStore, this._repository)
      : super(const AppSettings()) {
    _loadStoredAuthState();
  }

  final AuthCredentialsStore _credentialsStore;
  final TradingRepository _repository;

  void updateRisk(double value) {
    state = state.copyWith(riskSlider: value);
  }

  void toggleAutoplay(bool value) {
    state = state.copyWith(autoplayEnabled: value);
  }

  void toggleNotifications(bool value) {
    state = state.copyWith(notificationsEnabled: value);
  }

  Future<void> saveApiKey(
    String apiKey, {
    AuthScheme scheme = AuthScheme.apiKey,
  }) async {
    await _credentialsStore.saveApiKey(apiKey, scheme: scheme);
    state = state.copyWith(hasStoredApiKey: apiKey.trim().isNotEmpty);
  }

  Future<void> clearApiKey() async {
    await _credentialsStore.clear();
    state = state.copyWith(hasStoredApiKey: false);
  }

  Future<void> saveRiskLevel(
    String userId,
    String level,
  ) async {
    final payload = await _repository.updateRiskProfile(userId, level: level);
    state = state.copyWith(
      riskLevel: (payload['level'] as String?) ?? level,
    );
  }

  Future<void> loadTradingControls(String userId) async {
    final risk = await _repository.fetchRiskProfile(userId);
    final engine = await _repository.fetchEngineState(userId);
    Map<String, dynamic> admin = const <String, dynamic>{};
    try {
      admin = await _repository.fetchAdminModelState();
    } catch (_) {
      admin = const <String, dynamic>{};
    }
    final guardState = (admin['guard_state'] as Map<String, dynamic>?) ?? const <String, dynamic>{};
    state = state.copyWith(
      riskLevel: (risk['level'] as String?) ?? state.riskLevel,
      engineEnabled: (engine['enabled'] as bool?) ?? state.engineEnabled,
      learningFrozen: (guardState['freeze_enabled'] as bool?) ?? state.learningFrozen,
    );
  }

  Future<void> saveEngineState(
    String userId, {
    required bool enabled,
  }) async {
    final payload = await _repository.updateEngineState(userId, enabled: enabled);
    state = state.copyWith(
      engineEnabled: (payload['enabled'] as bool?) ?? enabled,
    );
  }

  Future<Map<String, dynamic>> triggerMockPriceMove({
    required String symbol,
    required double change,
    String? userId,
    double volumeMultiplier = 3.0,
    bool runMonitor = true,
  }) {
    return _repository.triggerMockPriceMove(
      symbol: symbol,
      change: change,
      userId: userId,
      volumeMultiplier: volumeMultiplier,
      runMonitor: runMonitor,
    );
  }

  Future<Map<String, dynamic>> fetchAdminModelState() async {
    final payload = await _repository.fetchAdminModelState();
    final guardState = (payload['guard_state'] as Map<String, dynamic>?) ?? const <String, dynamic>{};
    state = state.copyWith(
      learningFrozen: (guardState['freeze_enabled'] as bool?) ?? state.learningFrozen,
    );
    return payload;
  }

  Future<Map<String, dynamic>> rollbackAdminModel() async {
    final payload = await _repository.rollbackAdminModel();
    final guardState = (payload['guard_state'] as Map<String, dynamic>?) ?? const <String, dynamic>{};
    state = state.copyWith(
      learningFrozen: (guardState['freeze_enabled'] as bool?) ?? state.learningFrozen,
    );
    return payload;
  }

  Future<Map<String, dynamic>> setLearningFreeze({required bool enabled}) async {
    final payload = await _repository.setAdminModelFreeze(enabled: enabled);
    final guardState = (payload['guard_state'] as Map<String, dynamic>?) ?? const <String, dynamic>{};
    state = state.copyWith(
      learningFrozen: (guardState['freeze_enabled'] as bool?) ?? enabled,
    );
    return payload;
  }

  Future<void> _loadStoredAuthState() async {
    final session = await _credentialsStore.loadSession();
    state = state.copyWith(
      hasStoredApiKey: session != null && session.accessToken.trim().isNotEmpty,
    );
  }
}

final appSettingsProvider =
    StateNotifierProvider<AppSettingsNotifier, AppSettings>((ref) {
  return AppSettingsNotifier(
    ref.watch(authCredentialsStoreProvider),
    ref.watch(tradingRepositoryProvider),
  );
});

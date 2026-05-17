import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../../core/ai_opportunity_engine.dart';
import '../../../core/retention_engine.dart';
import '../../settings/providers/settings_provider.dart';
import '../../signals/providers/signal_providers.dart';

final selectedPlanTierProvider = StateProvider<PlanTier>((ref) {
  return PlanTier.pro;
});

final advancedAiModeProvider = StateProvider<AdvancedAiMode>((ref) {
  return AdvancedAiMode.smart;
});

class OnboardingCompletedNotifier extends StateNotifier<bool> {
  OnboardingCompletedNotifier({
    bool initial = false,
    bool persist = true,
    FlutterSecureStorage? storage,
  })  : _persist = persist,
        _storage = storage ?? _defaultStorage,
        super(initial) {
    if (_persist) {
      _load();
    }
  }

  static const String _key = 'ai_trader_onboarding_completed_v1';
  static const FlutterSecureStorage _defaultStorage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(
      accessibility: KeychainAccessibility.first_unlock,
    ),
  );

  final bool _persist;
  final FlutterSecureStorage _storage;

  Future<void> markCompleted() async {
    state = true;
    if (_persist) {
      try {
        await _storage.write(key: _key, value: 'true');
      } catch (error, stackTrace) {
        _reportStorageError(
          error,
          stackTrace,
          'persisting onboarding completion',
        );
      }
    }
  }

  Future<void> reset() async {
    state = false;
    if (_persist) {
      try {
        await _storage.delete(key: _key);
      } catch (error, stackTrace) {
        _reportStorageError(
          error,
          stackTrace,
          'resetting onboarding completion',
        );
      }
    }
  }

  Future<void> _load() async {
    try {
      final value = await _storage.read(key: _key);
      if (value == 'true') {
        state = true;
      }
    } catch (error, stackTrace) {
      _reportStorageError(
        error,
        stackTrace,
        'loading onboarding completion',
      );
    }
  }

  void _reportStorageError(
    Object error,
    StackTrace stackTrace,
    String context,
  ) {
    FlutterError.reportError(
      FlutterErrorDetails(
        exception: error,
        stack: stackTrace,
        library: 'retention',
        context: ErrorDescription(context),
      ),
    );
  }
}

final onboardingCompletedProvider =
    StateNotifierProvider<OnboardingCompletedNotifier, bool>((ref) {
  return OnboardingCompletedNotifier();
});

class LocalAiMemoryState {
  const LocalAiMemoryState({
    this.preferredAssets = const <String>[],
    this.preferredModes = const <String>[],
    this.favoriteStyle = 'Balanced momentum entries',
    this.viewedSignals = 0,
  });

  final List<String> preferredAssets;
  final List<String> preferredModes;
  final String favoriteStyle;
  final int viewedSignals;

  LocalAiMemoryState copyWith({
    List<String>? preferredAssets,
    List<String>? preferredModes,
    String? favoriteStyle,
    int? viewedSignals,
  }) {
    return LocalAiMemoryState(
      preferredAssets: preferredAssets ?? this.preferredAssets,
      preferredModes: preferredModes ?? this.preferredModes,
      favoriteStyle: favoriteStyle ?? this.favoriteStyle,
      viewedSignals: viewedSignals ?? this.viewedSignals,
    );
  }

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'preferred_assets': preferredAssets,
      'preferred_modes': preferredModes,
      'favorite_style': favoriteStyle,
      'viewed_signals': viewedSignals,
    };
  }

  factory LocalAiMemoryState.fromJson(Map<String, dynamic> json) {
    return LocalAiMemoryState(
      preferredAssets:
          (json['preferred_assets'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(growable: false),
      preferredModes:
          (json['preferred_modes'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(growable: false),
      favoriteStyle:
          json['favorite_style'] as String? ?? 'Balanced momentum entries',
      viewedSignals: (json['viewed_signals'] as num?)?.toInt() ?? 0,
    );
  }
}

class LocalAiMemoryNotifier extends StateNotifier<LocalAiMemoryState> {
  LocalAiMemoryNotifier({
    bool persist = true,
    FlutterSecureStorage? storage,
  })  : _persist = persist,
        _storage = storage ?? const FlutterSecureStorage(),
        super(const LocalAiMemoryState()) {
    if (_persist) {
      _load();
    }
  }

  static const String _key = 'ai_trader_memory_v1';

  final bool _persist;
  final FlutterSecureStorage _storage;

  Future<void> recordAsset(String symbol) async {
    final normalized = symbol.trim().toUpperCase();
    if (normalized.isEmpty) {
      return;
    }
    final next = <String>[
      normalized,
      ...state.preferredAssets.where((item) => item != normalized),
    ].take(8).toList(growable: false);
    state = state.copyWith(
      preferredAssets: next,
      viewedSignals: state.viewedSignals + 1,
    );
    await _save();
  }

  Future<void> recordMode(String mode) async {
    final normalized = mode.trim();
    if (normalized.isEmpty) {
      return;
    }
    final next = <String>[
      normalized,
      ...state.preferredModes.where((item) => item != normalized),
    ].take(5).toList(growable: false);
    state = state.copyWith(
      preferredModes: next,
      favoriteStyle: normalized,
    );
    await _save();
  }

  Future<void> _load() async {
    final raw = await _storage.read(key: _key);
    if (raw == null || raw.isEmpty) {
      return;
    }
    try {
      state = LocalAiMemoryState.fromJson(
        Map<String, dynamic>.from(jsonDecode(raw) as Map),
      );
    } catch (_) {
      state = const LocalAiMemoryState();
    }
  }

  Future<void> _save() async {
    if (!_persist) {
      return;
    }
    await _storage.write(key: _key, value: jsonEncode(state.toJson()));
  }
}

final localAiMemoryProvider =
    StateNotifierProvider<LocalAiMemoryNotifier, LocalAiMemoryState>((ref) {
  return LocalAiMemoryNotifier();
});

final retentionSnapshotProvider = Provider<RetentionSnapshot>((ref) {
  final settings = ref.watch(appSettingsProvider);
  final signals = ref.watch(signalFeedProvider).items;
  final tier = ref.watch(selectedPlanTierProvider);
  return const RetentionEngine().build(
    signals: signals,
    mode: aiTradingModeFromRiskLevel(settings.riskLevel),
    tier: tier,
  );
});

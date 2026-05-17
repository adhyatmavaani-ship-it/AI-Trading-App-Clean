import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_exception.dart';
import '../../../core/auth_credentials_store.dart';
import '../../../core/constants.dart';
import '../../../core/error_mapper.dart';
import '../../../providers/app_bootstrap_provider.dart';
import '../../../providers/app_providers.dart';

class AuthState {
  const AuthState({
    this.isLoading = false,
    this.isSubmitting = false,
    this.isAuthenticated = false,
    this.isDegraded = false,
    this.errorMessage,
    this.session,
  });

  final bool isLoading;
  final bool isSubmitting;
  final bool isAuthenticated;
  final bool isDegraded;
  final String? errorMessage;
  final AuthSession? session;

  AuthState copyWith({
    bool? isLoading,
    bool? isSubmitting,
    bool? isAuthenticated,
    bool? isDegraded,
    String? errorMessage,
    bool clearError = false,
    AuthSession? session,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isDegraded: isDegraded ?? this.isDegraded,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      session: session ?? this.session,
    );
  }
}

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._ref)
      : _credentialsStore = _ref.read(authCredentialsStoreProvider),
        super(
          AuthState(
            isLoading: true,
            isAuthenticated: true,
            isDegraded: AppConstants.defaultApiKey.trim().isEmpty,
          ),
        ) {
    _restoreSession();
  }

  final Ref _ref;
  final AuthCredentialsStore _credentialsStore;

  bool get _embeddedProductionAuthEnabled =>
      AppConstants.hasEmbeddedProductionAuth;

  Future<void> _restoreSession() async {
    final session = await _credentialsStore.loadSession();
    if (session != null) {
      track('auth_legacy_session_cleared');
      await _credentialsStore.clear();
    }
    var healthOk = false;
    if (_embeddedProductionAuthEnabled) {
      try {
        final payload = await _ref.read(apiClientProvider).getHealthStatus();
        healthOk = (payload['status'] as String?)?.trim().isNotEmpty == true;
      } catch (error, stackTrace) {
        logError(error, stackTrace: stackTrace);
      }
    }
    const isAuthenticated = true;
    final isDegraded = !_embeddedProductionAuthEnabled || !healthOk;
    track(
      'auth_restore',
      <String, dynamic>{
        'authenticated': isAuthenticated,
        'degraded': isDegraded,
        'session_scheme': 'required_api_key',
        'health_ok': healthOk,
      },
    );
    state = AuthState(
      isLoading: false,
      isAuthenticated: isAuthenticated,
      isDegraded: isDegraded,
      errorMessage: isDegraded
          ? 'Realtime connection is recovering. Paper trading and AI advisory mode are available.'
          : null,
      session: null,
    );
    if (!isDegraded) {
      _primeAuthenticatedData();
    }
  }

  Future<bool> signIn({
    required String credential,
    required AuthScheme scheme,
  }) async {
    state = state.copyWith(
      isSubmitting: true,
      clearError: true,
      isAuthenticated: true,
    );
    await _credentialsStore.clear();
    track(
      'auth_sign_in_attempt',
      <String, dynamic>{
        'scheme': 'required_api_key',
        'requested_scheme': scheme.name,
      },
    );

    try {
      final rootStatus = await _ref.read(apiClientProvider).getRootStatus();
      final accepted =
          (rootStatus['status'] as String?)?.trim().isNotEmpty == true;
      if (!accepted) {
        throw const ApiException(
          'Credential accepted by storage, but backend did not return a valid status.',
          code: 'invalid_auth_response',
        );
      }
      state = const AuthState(
        isLoading: false,
        isSubmitting: false,
        isAuthenticated: true,
        isDegraded: false,
        session: null,
      );
      track('auth_sign_in_success',
          <String, dynamic>{'scheme': 'required_api_key'});
      _primeAuthenticatedData();
      return true;
    } catch (error) {
      await _credentialsStore.clear();
      track('auth_sign_in_failed',
          <String, dynamic>{'scheme': 'required_api_key'});
      state = AuthState(
        isLoading: false,
        isSubmitting: false,
        isAuthenticated: true,
        isDegraded: true,
        session: null,
        errorMessage: _messageFor(error),
      );
      return false;
    }
  }

  Future<void> signOut() async {
    await _credentialsStore.clear();
    _ref.invalidate(appBootstrapProvider);
    track('auth_sign_out');
    state = AuthState(
      isLoading: false,
      isSubmitting: false,
      isAuthenticated: true,
      isDegraded: !_embeddedProductionAuthEnabled,
      errorMessage: !_embeddedProductionAuthEnabled
          ? 'Paper trading mode is active while production auth reconnects.'
          : null,
    );
    if (_embeddedProductionAuthEnabled) {
      _primeAuthenticatedData();
    }
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, clearError: true);
    await _restoreSession();
  }

  String _messageFor(Object error) {
    if (error is ApiException) {
      return ErrorMapper.map(
        error,
        fallback:
            'Realtime connection is recovering. Paper trading and AI advisory mode are available.',
      );
    }
    return 'Realtime connection is recovering. Paper trading and AI advisory mode are available.';
  }

  void _primeAuthenticatedData() {
    unawaited(_ref.read(appBootstrapProvider.future));
  }
}

final authControllerProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  return AuthController(ref);
});

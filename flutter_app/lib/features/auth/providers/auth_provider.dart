import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_exception.dart';
import '../../../core/auth_credentials_store.dart';
import '../../../core/constants.dart';
import '../../../providers/app_bootstrap_provider.dart';
import '../../../providers/app_providers.dart';

class AuthState {
  const AuthState({
    this.isLoading = false,
    this.isSubmitting = false,
    this.isAuthenticated = false,
    this.errorMessage,
    this.session,
  });

  final bool isLoading;
  final bool isSubmitting;
  final bool isAuthenticated;
  final String? errorMessage;
  final AuthSession? session;

  AuthState copyWith({
    bool? isLoading,
    bool? isSubmitting,
    bool? isAuthenticated,
    String? errorMessage,
    bool clearError = false,
    AuthSession? session,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
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
            isAuthenticated: AppConstants.defaultApiKey.trim().isNotEmpty,
          ),
        ) {
    _restoreSession();
  }

  final Ref _ref;
  final AuthCredentialsStore _credentialsStore;

  Future<void> _restoreSession() async {
    final session = await _credentialsStore.loadSession();
    final isAuthenticated =
        session != null || AppConstants.defaultApiKey.trim().isNotEmpty;
    state = AuthState(
      isLoading: false,
      isAuthenticated: isAuthenticated,
      session: session,
    );
    if (isAuthenticated) {
      _primeAuthenticatedData();
    }
  }

  Future<bool> signIn({
    required String credential,
    required AuthScheme scheme,
  }) async {
    final normalized = credential.trim();
    if (normalized.isEmpty) {
      state = state.copyWith(
        isSubmitting: false,
        isAuthenticated: false,
        errorMessage: 'Enter your API key or bearer token to continue.',
        clearError: true,
        session: null,
      );
      return false;
    }

    final session = AuthSession(accessToken: normalized, scheme: scheme);
    state = state.copyWith(
      isSubmitting: true,
      clearError: true,
      isAuthenticated: false,
    );

    await _credentialsStore.saveSession(session);

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
      state = AuthState(
        isLoading: false,
        isSubmitting: false,
        isAuthenticated: true,
        session: session,
      );
      _primeAuthenticatedData();
      return true;
    } catch (error) {
      await _credentialsStore.clear();
      state = AuthState(
        isLoading: false,
        isSubmitting: false,
        isAuthenticated: false,
        errorMessage: _messageFor(error),
      );
      return false;
    }
  }

  Future<void> signOut() async {
    await _credentialsStore.clear();
    _ref.invalidate(appBootstrapProvider);
    state = const AuthState(
      isLoading: false,
      isSubmitting: false,
      isAuthenticated: false,
    );
  }

  Future<void> refresh() async {
    state = state.copyWith(isLoading: true, clearError: true);
    await _restoreSession();
  }

  String _messageFor(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Unable to verify your credential right now. Check connectivity and try again.';
  }

  void _primeAuthenticatedData() {
    unawaited(_ref.read(appBootstrapProvider.future));
  }
}

final authControllerProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  return AuthController(ref);
});

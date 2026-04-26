import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/auth_credentials_store.dart';
import '../core/websocket_service.dart';
import '../repositories/trading_repository.dart';

final authCredentialsStoreProvider = Provider<AuthCredentialsStore>((ref) {
  return AuthCredentialsStore();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(
    credentialsStore: ref.watch(authCredentialsStoreProvider),
  );
});

final webSocketServiceProvider = Provider<WebSocketService>((ref) {
  final service = WebSocketService(
    credentialsStore: ref.watch(authCredentialsStoreProvider),
  );
  ref.onDispose(() {
    service.dispose();
  });
  return service;
});

final tradingRepositoryProvider = Provider<TradingRepository>((ref) {
  return TradingRepository(
    apiClient: ref.watch(apiClientProvider),
    webSocketService: ref.watch(webSocketServiceProvider),
  );
});

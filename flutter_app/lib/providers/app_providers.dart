import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/auth_credentials_store.dart';
import '../core/error_mapper.dart';
import '../core/trading_updates_socket_service.dart';
import '../core/websocket_service.dart';
import '../repositories/trading_repository.dart';

final authCredentialsStoreProvider = Provider<AuthCredentialsStore>((ref) {
  return AuthCredentialsStore();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  track('provider_init', <String, dynamic>{'provider': 'apiClientProvider'});
  return ApiClient();
});

final webSocketServiceProvider = Provider<WebSocketService>((ref) {
  track(
    'provider_init',
    <String, dynamic>{'provider': 'webSocketServiceProvider'},
  );
  final service = WebSocketService();
  ref.onDispose(() {
    service.dispose();
  });
  return service;
});

final tradingUpdatesSocketServiceProvider =
    Provider<TradingUpdatesSocketService>((ref) {
  track(
    'provider_init',
    <String, dynamic>{'provider': 'tradingUpdatesSocketServiceProvider'},
  );
  final service = TradingUpdatesSocketService();
  ref.onDispose(() {
    service.dispose();
  });
  return service;
});

final tradingRepositoryProvider = Provider<TradingRepository>((ref) {
  return TradingRepository(
    apiClient: ref.watch(apiClientProvider),
    webSocketService: ref.watch(webSocketServiceProvider),
    tradingUpdatesSocketService: ref.watch(tradingUpdatesSocketServiceProvider),
  );
});

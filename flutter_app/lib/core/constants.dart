import 'package:flutter/foundation.dart';

class AppConstants {
  static const String _configuredApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );
  static const String _configuredSignalsWebSocketUrl = String.fromEnvironment(
    'SIGNALS_WS_URL',
    defaultValue: '',
  );
  static const String _configuredMarketWebSocketUrl = String.fromEnvironment(
    'MARKET_WS_URL',
    defaultValue: '',
  );
  static const String productionApiBaseUrl = 'http://69.62.74.7';
  static const String productionSignalsWebSocketUrl =
      'ws://69.62.74.7/ws/signals';
  static const String productionMarketWebSocketUrl =
      'ws://69.62.74.7/ws/market';
  static const String _configuredProductionApiKey = String.fromEnvironment(
    'TRADING_API_KEY',
    defaultValue: '',
  );
  static const String productionUserId = 'admin';

  static String get defaultApiBaseUrl {
    final configured = _configuredApiBaseUrl.trim();
    return configured.isNotEmpty ? configured : productionApiBaseUrl;
  }

  static String get productionApiKey {
    final configured = _configuredProductionApiKey.trim();
    if (configured.isNotEmpty) {
      return configured;
    }
    return kDebugMode ? 'local-dev-token' : '';
  }

  static String get defaultApiKey => productionApiKey;

  static String get requiredApiKey {
    final configured = defaultApiKey.trim();
    if (configured.isNotEmpty) {
      return configured;
    }
    return productionApiKey;
  }

  static bool get hasEmbeddedProductionAuth => requiredApiKey.isNotEmpty;

  static String get requiredUserId {
    final configured = productionUserId.trim();
    return configured.isNotEmpty ? configured : 'admin';
  }

  static String get defaultSignalsWebSocketUrl {
    final configured = _configuredSignalsWebSocketUrl.trim();
    return configured.isNotEmpty ? configured : productionSignalsWebSocketUrl;
  }

  static String get defaultMarketWebSocketUrl {
    final configured = _configuredMarketWebSocketUrl.trim();
    return configured.isNotEmpty ? configured : productionMarketWebSocketUrl;
  }

  static const int maxSignalCacheSize = 100;
  static const Duration pollingInterval = Duration(seconds: 15);
  static const Duration realtimeFallbackPollingInterval = Duration(seconds: 60);
  static const Duration tradeEvaluationPollingInterval = Duration(seconds: 30);
  static const Duration chartRefreshInterval = Duration(seconds: 8);
  static const Duration marketSurfaceRefreshInterval = Duration(seconds: 20);
  static const Duration requestTimeout = Duration(seconds: 20);
  static const int requestRetryAttempts = 3;
  static const Duration requestRetryDelay = Duration(seconds: 2);
  static const Duration websocketConnectTimeout = Duration(seconds: 12);
  static const Duration websocketProbeTimeout = Duration(seconds: 10);
  static const Duration websocketPingInterval = Duration(seconds: 20);
  static const Duration websocketReconnectBaseDelay = Duration(seconds: 2);
  static const Duration websocketReconnectMaxDelay = Duration(seconds: 20);
  static const Duration websocketStaleAfter = Duration(seconds: 45);
  static const Duration websocketIntegrityCheckInterval = Duration(seconds: 10);
}

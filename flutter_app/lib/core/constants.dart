class AppConstants {
  static const String productionApiBaseUrl =
      'https://ai-trading-app-clean.onrender.com';
  static const String productionWsBaseUrl =
      'wss://ai-trading-app-clean.onrender.com/ws';

  static const String productionApiKey = String.fromEnvironment(
    'PRODUCTION_API_KEY',
    defaultValue: 'my-secret-key-123',
  );

  static const String defaultApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: productionApiBaseUrl,
  );

  static const String defaultApiKey = String.fromEnvironment(
    'API_KEY',
    defaultValue: productionApiKey,
  );

  static String get requiredApiKey {
    final configured = defaultApiKey.trim();
    if (configured.isNotEmpty) {
      return configured;
    }
    return productionApiKey;
  }

  static const String localDemoApiKey = String.fromEnvironment(
    'DEMO_API_KEY',
    defaultValue: '',
  );

  static const String _configuredWsBaseUrl = String.fromEnvironment(
    'WS_BASE_URL',
    defaultValue: '',
  );

  static String get defaultWsBaseUrl {
    if (_configuredWsBaseUrl.isNotEmpty) {
      return _configuredWsBaseUrl;
    }
    if (defaultApiBaseUrl == productionApiBaseUrl) {
      return productionWsBaseUrl;
    }
    final uri = Uri.parse(defaultApiBaseUrl);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return uri.replace(scheme: scheme, path: '/ws', query: null).toString();
  }

  static const int maxSignalCacheSize = 100;
  static const Duration pollingInterval = Duration(seconds: 15);
  static const Duration requestTimeout = Duration(seconds: 30);
  static const int requestRetryAttempts = 3;
  static const Duration requestRetryDelay = Duration(seconds: 3);
  static const Duration websocketReconnectDelay = Duration(seconds: 5);
}

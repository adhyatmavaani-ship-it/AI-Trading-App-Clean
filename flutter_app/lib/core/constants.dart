class AppConstants {
  static const String productionApiBaseUrl =
      'https://ai-trading-app-clean.onrender.com';

  static const String defaultApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: productionApiBaseUrl,
  );

  static const String defaultApiKey = String.fromEnvironment(
    'API_KEY',
    defaultValue: '',
  );

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
    final uri = Uri.parse(defaultApiBaseUrl);
    final scheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return uri.replace(scheme: scheme, path: '').toString();
  }

  static const int maxSignalCacheSize = 100;
  static const Duration websocketReconnectBaseDelay = Duration(seconds: 2);
  static const Duration websocketMaxReconnectDelay = Duration(seconds: 30);
  static const Duration pollingInterval = Duration(seconds: 15);
  static const Duration connectTimeout = Duration(seconds: 20);
  static const Duration receiveTimeout = Duration(seconds: 25);
  static const Duration sendTimeout = Duration(seconds: 20);
}

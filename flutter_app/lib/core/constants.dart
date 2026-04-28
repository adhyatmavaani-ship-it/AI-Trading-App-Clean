class AppConstants {
  static const String defaultApiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.84.86.111:8000',
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
    return uri.replace(scheme: scheme).toString();
  }

  static const int maxSignalCacheSize = 100;
  static const Duration websocketReconnectBaseDelay = Duration(seconds: 2);
  static const Duration websocketMaxReconnectDelay = Duration(seconds: 30);
  static const Duration pollingInterval = Duration(seconds: 15);
  static const Duration requestTimeout = Duration(seconds: 60);
}

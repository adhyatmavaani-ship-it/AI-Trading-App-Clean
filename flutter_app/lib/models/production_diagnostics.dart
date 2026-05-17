class ProductionDiagnosticsModel {
  const ProductionDiagnosticsModel({
    required this.apiHealthy,
    required this.apiReady,
    required this.apiStatus,
    required this.latencyMs,
    required this.redisState,
    required this.deploymentMode,
    required this.backendVersion,
    required this.buildTimestamp,
    required this.marketDataMode,
    required this.usingMockData,
    required this.activeExchanges,
  });

  final bool apiHealthy;
  final bool apiReady;
  final String apiStatus;
  final int latencyMs;
  final String redisState;
  final String deploymentMode;
  final String backendVersion;
  final String buildTimestamp;
  final String marketDataMode;
  final bool usingMockData;
  final List<String> activeExchanges;
}

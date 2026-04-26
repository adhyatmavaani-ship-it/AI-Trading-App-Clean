class SystemHealthModel {
  const SystemHealthModel({
    required this.tradingMode,
    required this.apiStatus,
    required this.latencyMsP50,
    required this.latencyMsP95,
    required this.activeTrades,
    required this.errorCount,
    required this.failedOrders,
    required this.partialFills,
    required this.degradedMode,
  });

  final String tradingMode;
  final String apiStatus;
  final double latencyMsP50;
  final double latencyMsP95;
  final int activeTrades;
  final int errorCount;
  final int failedOrders;
  final int partialFills;
  final bool degradedMode;

  factory SystemHealthModel.fromJson(Map<String, dynamic> json) {
    return SystemHealthModel(
      tradingMode: json['trading_mode'] as String? ?? 'paper',
      apiStatus: json['api_status'] as String? ?? 'unknown',
      latencyMsP50: (json['latency_ms_p50'] ?? 0).toDouble(),
      latencyMsP95: (json['latency_ms_p95'] ?? 0).toDouble(),
      activeTrades: (json['active_trades'] as num?)?.toInt() ?? 0,
      errorCount: (json['error_count'] as num?)?.toInt() ?? 0,
      failedOrders: (json['failed_orders'] as num?)?.toInt() ?? 0,
      partialFills: (json['partial_fills'] as num?)?.toInt() ?? 0,
      degradedMode: json['degraded_mode'] as bool? ?? false,
    );
  }
}

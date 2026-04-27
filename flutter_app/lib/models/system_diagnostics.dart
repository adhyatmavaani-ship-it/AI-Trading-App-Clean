class ExchangeStatusModel {
  const ExchangeStatusModel({
    required this.name,
    required this.status,
    required this.lastError,
    required this.lastAttemptAt,
    required this.lastSuccessAt,
  });

  final String name;
  final String status;
  final String? lastError;
  final DateTime? lastAttemptAt;
  final DateTime? lastSuccessAt;

  bool get isHealthy => status == 'active';

  factory ExchangeStatusModel.fromJson(String name, Map<String, dynamic> json) {
    return ExchangeStatusModel(
      name: name,
      status: json['status'] as String? ?? 'unknown',
      lastError: json['lastError'] as String? ?? json['last_error'] as String?,
      lastAttemptAt: DateTime.tryParse(
        json['lastAttemptAt'] as String? ?? json['last_attempt_at'] as String? ?? '',
      ),
      lastSuccessAt: DateTime.tryParse(
        json['lastSuccessAt'] as String? ?? json['last_success_at'] as String? ?? '',
      ),
    );
  }
}

class SystemDiagnosticsModel {
  const SystemDiagnosticsModel({
    required this.configuredMode,
    required this.resolvedMode,
    required this.usingMockData,
    required this.forceExecutionOverrideEnabled,
    required this.forceExecutionOverrideConfidenceFloor,
    required this.configuredExchanges,
    required this.activeExchanges,
    required this.exchangeStatuses,
  });

  final String configuredMode;
  final String resolvedMode;
  final bool usingMockData;
  final bool forceExecutionOverrideEnabled;
  final double forceExecutionOverrideConfidenceFloor;
  final List<String> configuredExchanges;
  final List<String> activeExchanges;
  final List<ExchangeStatusModel> exchangeStatuses;

  factory SystemDiagnosticsModel.fromJson(Map<String, dynamic> json) {
    final marketData = (json['market_data'] as Map<String, dynamic>?) ?? json;
    final statusMap =
        (marketData['exchange_status'] as Map<String, dynamic>?) ?? const {};

    return SystemDiagnosticsModel(
      configuredMode: marketData['configured_mode'] as String? ?? 'unknown',
      resolvedMode: marketData['resolved_mode'] as String? ?? 'unknown',
      usingMockData: marketData['using_mock_data'] as bool? ?? false,
      forceExecutionOverrideEnabled:
          marketData['force_execution_override_enabled'] as bool? ?? false,
      forceExecutionOverrideConfidenceFloor:
          (marketData['force_execution_override_confidence_floor'] ?? 0)
              .toDouble(),
      configuredExchanges: ((marketData['configured_exchanges'] as List?) ??
              const <dynamic>[])
          .map((item) => item.toString())
          .toList(),
      activeExchanges:
          ((marketData['active_exchanges'] as List?) ?? const <dynamic>[])
              .map((item) => item.toString())
              .toList(),
      exchangeStatuses: statusMap.entries
          .map(
            (entry) => ExchangeStatusModel.fromJson(
              entry.key,
              (entry.value as Map?)?.cast<String, dynamic>() ??
                  const <String, dynamic>{},
            ),
          )
          .toList(),
    );
  }
}

class MetaDecisionModel {
  const MetaDecisionModel({
    required this.tradeId,
    required this.userId,
    required this.symbol,
    required this.decision,
    required this.strategy,
    required this.confidence,
    required this.signals,
    required this.conflicts,
    required this.riskAdjustments,
    required this.systemHealthSnapshot,
    required this.reason,
    this.createdAt,
    this.outcome,
  });

  final String tradeId;
  final String userId;
  final String symbol;
  final String decision;
  final String strategy;
  final double confidence;
  final Map<String, dynamic> signals;
  final List<String> conflicts;
  final Map<String, dynamic> riskAdjustments;
  final Map<String, dynamic> systemHealthSnapshot;
  final String reason;
  final String? createdAt;
  final Map<String, dynamic>? outcome;

  bool get isBlocked => decision.toUpperCase() == 'BLOCKED';

  double get normalizedConfidence {
    if (confidence <= 1) {
      return confidence.clamp(0, 1);
    }
    return (confidence / 100).clamp(0, 1);
  }

  factory MetaDecisionModel.fromJson(Map<String, dynamic> json) {
    return MetaDecisionModel(
      tradeId: json['trade_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      symbol: json['symbol'] as String? ?? '',
      decision: json['decision'] as String? ?? 'UNKNOWN',
      strategy: json['strategy'] as String? ?? 'UNKNOWN',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      signals: Map<String, dynamic>.from(
        json['signals'] as Map? ?? const <String, dynamic>{},
      ),
      conflicts: (json['conflicts'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(),
      riskAdjustments: Map<String, dynamic>.from(
        json['risk_adjustments'] as Map? ?? const <String, dynamic>{},
      ),
      systemHealthSnapshot: Map<String, dynamic>.from(
        json['system_health_snapshot'] as Map? ?? const <String, dynamic>{},
      ),
      reason: json['reason'] as String? ?? '',
      createdAt: json['created_at'] as String?,
      outcome: json['outcome'] == null
          ? null
          : Map<String, dynamic>.from(json['outcome'] as Map),
    );
  }
}

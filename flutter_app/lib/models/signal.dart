class SignalModel {
  const SignalModel({
    required this.signalId,
    required this.symbol,
    required this.action,
    required this.strategy,
    required this.confidence,
    required this.alphaScore,
    required this.regime,
    required this.price,
    required this.signalVersion,
    required this.publishedAt,
    required this.decisionReason,
    required this.degradedMode,
    required this.requiredTier,
    required this.minBalance,
    required this.rejectionReason,
    required this.lowConfidence,
  });

  final String signalId;
  final String symbol;
  final String action;
  final String strategy;
  final double confidence;
  final double alphaScore;
  final String regime;
  final double price;
  final int signalVersion;
  final DateTime publishedAt;
  final String decisionReason;
  final bool degradedMode;
  final String requiredTier;
  final double minBalance;
  final String? rejectionReason;
  final bool lowConfidence;

  bool get isForcedPaperTrade => strategy == 'FORCED_PAPER_TRADE';

  bool get isHighPriority => isForcedPaperTrade || alphaScore >= 80;

  factory SignalModel.fromJson(Map<String, dynamic> json) {
    return SignalModel(
      signalId: json['signal_id'] as String? ?? '',
      symbol: json['symbol'] as String? ?? '',
      action: json['action'] as String? ?? 'HOLD',
      strategy: json['strategy'] as String? ?? 'NO_TRADE',
      confidence: (json['confidence'] ?? 0).toDouble(),
      alphaScore: (json['alpha_score'] ?? 0).toDouble(),
      regime: json['regime'] as String? ?? 'UNKNOWN',
      price: (json['price'] ?? 0).toDouble(),
      signalVersion: (json['signal_version'] as num?)?.toInt() ?? 0,
      publishedAt: DateTime.tryParse(json['published_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      decisionReason: json['decision_reason'] as String? ?? '',
      degradedMode: json['degraded_mode'] as bool? ?? false,
      requiredTier: json['required_tier'] as String? ?? 'free',
      minBalance: (json['min_balance'] ?? 0).toDouble(),
      rejectionReason: json['rejection_reason'] as String?,
      lowConfidence: json['low_confidence'] as bool? ?? false,
    );
  }
}

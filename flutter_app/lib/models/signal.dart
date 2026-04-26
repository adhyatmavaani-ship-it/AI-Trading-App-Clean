class SignalModel {
  const SignalModel({
    required this.signalId,
    required this.symbol,
    required this.strategy,
    required this.alphaScore,
    required this.regime,
    required this.price,
    required this.signalVersion,
    required this.publishedAt,
    required this.decisionReason,
    required this.degradedMode,
    required this.requiredTier,
    required this.minBalance,
  });

  final String signalId;
  final String symbol;
  final String strategy;
  final double alphaScore;
  final String regime;
  final double price;
  final int signalVersion;
  final DateTime publishedAt;
  final String decisionReason;
  final bool degradedMode;
  final String requiredTier;
  final double minBalance;

  factory SignalModel.fromJson(Map<String, dynamic> json) {
    return SignalModel(
      signalId: json['signal_id'] as String? ?? '',
      symbol: json['symbol'] as String? ?? '',
      strategy: json['strategy'] as String? ?? 'NO_TRADE',
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
    );
  }
}

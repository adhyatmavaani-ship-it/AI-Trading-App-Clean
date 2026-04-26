class MetaAnalyticsModel {
  const MetaAnalyticsModel({
    required this.blockedTrades,
    required this.strategyPerformance,
    required this.confidenceDistribution,
    this.updatedAt,
  });

  final MetaBlockedTradesModel blockedTrades;
  final Map<String, MetaStrategyPerformanceModel> strategyPerformance;
  final Map<String, int> confidenceDistribution;
  final String? updatedAt;

  int get totalExecutedTrades => strategyPerformance.values.fold(
        0,
        (sum, item) => sum + item.trades,
      );

  int get totalBlockedTrades => blockedTrades.total;

  factory MetaAnalyticsModel.fromJson(Map<String, dynamic> json) {
    final rawStrategyPerformance =
        json['strategy_performance'] as Map? ?? const <String, dynamic>{};
    final strategyPerformance = rawStrategyPerformance.map(
      (key, value) => MapEntry(
        key.toString(),
        MetaStrategyPerformanceModel.fromJson(
          Map<String, dynamic>.from(value as Map? ?? const <String, dynamic>{}),
        ),
      ),
    );
    final rawConfidence =
        json['confidence_distribution'] as Map? ?? const <String, dynamic>{};
    return MetaAnalyticsModel(
      blockedTrades: MetaBlockedTradesModel.fromJson(
        Map<String, dynamic>.from(
          json['blocked_trades'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      strategyPerformance: strategyPerformance,
      confidenceDistribution: rawConfidence.map(
        (key, value) => MapEntry(
          key.toString(),
          (value as num?)?.toInt() ?? 0,
        ),
      ),
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class MetaBlockedTradesModel {
  const MetaBlockedTradesModel({
    required this.total,
    required this.reasons,
  });

  final int total;
  final Map<String, int> reasons;

  factory MetaBlockedTradesModel.fromJson(Map<String, dynamic> json) {
    final rawReasons = json['reasons'] as Map? ?? const <String, dynamic>{};
    return MetaBlockedTradesModel(
      total: (json['total'] as num?)?.toInt() ?? 0,
      reasons: rawReasons.map(
        (key, value) => MapEntry(
          key.toString(),
          (value as num?)?.toInt() ?? 0,
        ),
      ),
    );
  }
}

class MetaStrategyPerformanceModel {
  const MetaStrategyPerformanceModel({
    required this.trades,
    required this.wins,
    required this.losses,
    required this.blocked,
    required this.pnl,
  });

  final int trades;
  final int wins;
  final int losses;
  final int blocked;
  final double pnl;

  double get winRate {
    if (trades == 0) {
      return 0;
    }
    return wins / trades;
  }

  factory MetaStrategyPerformanceModel.fromJson(Map<String, dynamic> json) {
    return MetaStrategyPerformanceModel(
      trades: (json['trades'] as num?)?.toInt() ?? 0,
      wins: (json['wins'] as num?)?.toInt() ?? 0,
      losses: (json['losses'] as num?)?.toInt() ?? 0,
      blocked: (json['blocked'] as num?)?.toInt() ?? 0,
      pnl: (json['pnl'] as num?)?.toDouble() ?? 0,
    );
  }
}

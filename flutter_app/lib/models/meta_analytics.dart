class MetaAnalyticsModel {
  const MetaAnalyticsModel({
    required this.blockedTrades,
    required this.strategyPerformance,
    required this.confidenceDistribution,
    required this.learning,
    this.updatedAt,
  });

  final MetaBlockedTradesModel blockedTrades;
  final Map<String, MetaStrategyPerformanceModel> strategyPerformance;
  final Map<String, int> confidenceDistribution;
  final MetaLearningModel learning;
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
      learning: MetaLearningModel.fromJson(
        Map<String, dynamic>.from(
          json['learning'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class MetaLearningModel {
  const MetaLearningModel({
    required this.enabled,
    required this.blacklistTotal,
    required this.whitelistTotal,
    required this.regimes,
    this.updatedAt,
  });

  final bool enabled;
  final int blacklistTotal;
  final int whitelistTotal;
  final Map<String, MetaLearningRegimeModel> regimes;
  final String? updatedAt;

  int get trackedPatterns =>
      regimes.values.fold(0, (sum, item) => sum + item.trackedPatterns);

  factory MetaLearningModel.fromJson(Map<String, dynamic> json) {
    final rawRegimes = json['regimes'] as Map? ?? const <String, dynamic>{};
    return MetaLearningModel(
      enabled: json['enabled'] as bool? ?? false,
      blacklistTotal: (json['blacklist_total'] as num?)?.toInt() ?? 0,
      whitelistTotal: (json['whitelist_total'] as num?)?.toInt() ?? 0,
      regimes: rawRegimes.map(
        (key, value) => MapEntry(
          key.toString(),
          MetaLearningRegimeModel.fromJson(
            Map<String, dynamic>.from(value as Map? ?? const <String, dynamic>{}),
          ),
        ),
      ),
      updatedAt: json['updated_at'] as String?,
    );
  }
}

class MetaLearningRegimeModel {
  const MetaLearningRegimeModel({
    required this.trackedPatterns,
    required this.blacklistPatterns,
    required this.whitelistPatterns,
    required this.preferredMinAtrPct,
    required this.preferredMinTrendGap,
    this.updatedAt,
  });

  final int trackedPatterns;
  final List<String> blacklistPatterns;
  final List<String> whitelistPatterns;
  final double preferredMinAtrPct;
  final double preferredMinTrendGap;
  final String? updatedAt;

  factory MetaLearningRegimeModel.fromJson(Map<String, dynamic> json) {
    final rawBlacklist = json['blacklist_patterns'] as List? ?? const <dynamic>[];
    final rawWhitelist = json['whitelist_patterns'] as List? ?? const <dynamic>[];
    return MetaLearningRegimeModel(
      trackedPatterns: (json['tracked_patterns'] as num?)?.toInt() ?? 0,
      blacklistPatterns: rawBlacklist.map((item) => item.toString()).toList(),
      whitelistPatterns: rawWhitelist.map((item) => item.toString()).toList(),
      preferredMinAtrPct:
          (json['preferred_min_atr_pct'] as num?)?.toDouble() ?? 0.0,
      preferredMinTrendGap:
          (json['preferred_min_trend_gap'] as num?)?.toDouble() ?? 0.0,
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

class PortfolioConcentrationSnapshotModel {
  const PortfolioConcentrationSnapshotModel({
    required this.updatedAt,
    required this.grossExposurePct,
    required this.maxSymbolExposurePct,
    required this.maxSideExposurePct,
    required this.maxThemeExposurePct,
    required this.maxClusterExposurePct,
    required this.maxBetaBucketExposurePct,
    required this.grossExposureDrift,
    required this.clusterConcentrationDrift,
    required this.betaBucketConcentrationDrift,
    required this.clusterTurnover,
    required this.factorSleeveBudgetTurnover,
    required this.maxFactorSleeveBudgetGapPct,
    required this.severity,
    required this.severityReason,
    required this.factorRegime,
    required this.factorModel,
    required this.factorUniverseSymbols,
    required this.factorWeights,
    required this.factorAttribution,
    required this.factorSleevePerformance,
    required this.factorSleeveBudgetTargets,
    required this.factorSleeveBudgetDeltas,
    required this.dominantFactorSleeve,
    required this.dominantSymbol,
    required this.dominantSide,
    required this.dominantTheme,
    required this.dominantCluster,
    required this.dominantBetaBucket,
    required this.dominantOverBudgetSleeve,
    required this.dominantUnderBudgetSleeve,
  });

  final DateTime? updatedAt;
  final double grossExposurePct;
  final double maxSymbolExposurePct;
  final double maxSideExposurePct;
  final double maxThemeExposurePct;
  final double maxClusterExposurePct;
  final double maxBetaBucketExposurePct;
  final double grossExposureDrift;
  final double clusterConcentrationDrift;
  final double betaBucketConcentrationDrift;
  final double clusterTurnover;
  final double factorSleeveBudgetTurnover;
  final double maxFactorSleeveBudgetGapPct;
  final String severity;
  final String? severityReason;
  final String factorRegime;
  final String factorModel;
  final List<String> factorUniverseSymbols;
  final Map<String, double> factorWeights;
  final Map<String, double> factorAttribution;
  final Map<String, Map<String, dynamic>> factorSleevePerformance;
  final Map<String, double> factorSleeveBudgetTargets;
  final Map<String, double> factorSleeveBudgetDeltas;
  final String? dominantFactorSleeve;
  final String? dominantSymbol;
  final String? dominantSide;
  final String? dominantTheme;
  final String? dominantCluster;
  final String? dominantBetaBucket;
  final String? dominantOverBudgetSleeve;
  final String? dominantUnderBudgetSleeve;

  factory PortfolioConcentrationSnapshotModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return PortfolioConcentrationSnapshotModel(
      updatedAt: json['updated_at'] == null
          ? null
          : DateTime.tryParse(json['updated_at'] as String),
      grossExposurePct: (json['gross_exposure_pct'] ?? 0).toDouble(),
      maxSymbolExposurePct: (json['max_symbol_exposure_pct'] ?? 0).toDouble(),
      maxSideExposurePct: (json['max_side_exposure_pct'] ?? 0).toDouble(),
      maxThemeExposurePct: (json['max_theme_exposure_pct'] ?? 0).toDouble(),
      maxClusterExposurePct:
          (json['max_cluster_exposure_pct'] ?? 0).toDouble(),
      maxBetaBucketExposurePct:
          (json['max_beta_bucket_exposure_pct'] ?? 0).toDouble(),
      grossExposureDrift: (json['gross_exposure_drift'] ?? 0).toDouble(),
      clusterConcentrationDrift:
          (json['cluster_concentration_drift'] ?? 0).toDouble(),
      betaBucketConcentrationDrift:
          (json['beta_bucket_concentration_drift'] ?? 0).toDouble(),
      clusterTurnover: (json['cluster_turnover'] ?? 0).toDouble(),
      factorSleeveBudgetTurnover:
          (json['factor_sleeve_budget_turnover'] ?? 0).toDouble(),
      maxFactorSleeveBudgetGapPct:
          (json['max_factor_sleeve_budget_gap_pct'] ?? 0).toDouble(),
      severity: json['severity'] as String? ?? 'normal',
      severityReason: json['severity_reason'] as String?,
      factorRegime: json['factor_regime'] as String? ?? 'RANGING',
      factorModel:
          json['factor_model'] as String? ??
          'pca_covariance_regime_universe_v1',
      factorUniverseSymbols:
          (json['factor_universe_symbols'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .toList(),
      factorWeights: (json['factor_weights'] as Map<String, dynamic>? ??
              const <String, dynamic>{})
          .map(
        (key, value) => MapEntry<String, double>(key, (value as num).toDouble()),
      ),
      factorAttribution: (json['factor_attribution'] as Map<String, dynamic>? ??
              const <String, dynamic>{})
          .map(
        (key, value) => MapEntry<String, double>(key, (value as num).toDouble()),
      ),
      factorSleeveBudgetTargets:
          (json['factor_sleeve_budget_targets'] as Map<String, dynamic>? ??
                  const <String, dynamic>{})
              .map(
        (key, value) => MapEntry<String, double>(key, (value as num).toDouble()),
      ),
      factorSleeveBudgetDeltas:
          (json['factor_sleeve_budget_deltas'] as Map<String, dynamic>? ??
                  const <String, dynamic>{})
              .map(
        (key, value) => MapEntry<String, double>(key, (value as num).toDouble()),
      ),
      factorSleevePerformance:
          (json['factor_sleeve_performance'] as Map<String, dynamic>? ??
                  const <String, dynamic>{})
              .map(
        (key, value) => MapEntry<String, Map<String, dynamic>>(
          key,
          Map<String, dynamic>.from(value as Map),
        ),
      ),
      dominantFactorSleeve: json['dominant_factor_sleeve'] as String?,
      dominantSymbol: json['dominant_symbol'] as String?,
      dominantSide: json['dominant_side'] as String?,
      dominantTheme: json['dominant_theme'] as String?,
      dominantCluster: json['dominant_cluster'] as String?,
      dominantBetaBucket: json['dominant_beta_bucket'] as String?,
      dominantOverBudgetSleeve: json['dominant_over_budget_sleeve'] as String?,
      dominantUnderBudgetSleeve:
          json['dominant_under_budget_sleeve'] as String?,
    );
  }
}

class PortfolioConcentrationHistoryModel {
  const PortfolioConcentrationHistoryModel({
    required this.latest,
    required this.history,
  });

  final PortfolioConcentrationSnapshotModel latest;
  final List<PortfolioConcentrationSnapshotModel> history;

  factory PortfolioConcentrationHistoryModel.fromJson(
    Map<String, dynamic> json,
  ) {
    final history = json['history'] as List<dynamic>? ?? const <dynamic>[];
    return PortfolioConcentrationHistoryModel(
      latest: PortfolioConcentrationSnapshotModel.fromJson(
        json['latest'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      history: history
          .map(
            (item) => PortfolioConcentrationSnapshotModel.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }
}

class ModelStabilityConcentrationStatusModel {
  const ModelStabilityConcentrationStatusModel({
    required this.activeModelVersion,
    required this.fallbackModelVersion,
    required this.concentrationDriftScore,
    required this.tradingFrequencyMultiplier,
    required this.retrainingTriggered,
    required this.degraded,
  });

  final String activeModelVersion;
  final String? fallbackModelVersion;
  final double concentrationDriftScore;
  final double tradingFrequencyMultiplier;
  final bool retrainingTriggered;
  final bool degraded;

  factory ModelStabilityConcentrationStatusModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return ModelStabilityConcentrationStatusModel(
      activeModelVersion: json['active_model_version'] as String? ?? 'unknown',
      fallbackModelVersion: json['fallback_model_version'] as String?,
      concentrationDriftScore:
          (json['concentration_drift_score'] ?? 0).toDouble(),
      tradingFrequencyMultiplier:
          (json['trading_frequency_multiplier'] ?? 1).toDouble(),
      retrainingTriggered: json['retraining_triggered'] as bool? ?? false,
      degraded: json['degraded'] as bool? ?? false,
    );
  }
}

class ModelStabilityConcentrationHistoryEntryModel {
  const ModelStabilityConcentrationHistoryEntryModel({
    required this.updatedAt,
    required this.score,
    required this.grossExposureDrift,
    required this.clusterConcentrationDrift,
    required this.betaBucketConcentrationDrift,
    required this.clusterTurnover,
    required this.severity,
    required this.severityReason,
  });

  final DateTime? updatedAt;
  final double score;
  final double grossExposureDrift;
  final double clusterConcentrationDrift;
  final double betaBucketConcentrationDrift;
  final double clusterTurnover;
  final String severity;
  final String? severityReason;

  factory ModelStabilityConcentrationHistoryEntryModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return ModelStabilityConcentrationHistoryEntryModel(
      updatedAt: json['updated_at'] == null
          ? null
          : DateTime.tryParse(json['updated_at'] as String),
      score: (json['score'] ?? 0).toDouble(),
      grossExposureDrift: (json['gross_exposure_drift'] ?? 0).toDouble(),
      clusterConcentrationDrift:
          (json['cluster_concentration_drift'] ?? 0).toDouble(),
      betaBucketConcentrationDrift:
          (json['beta_bucket_concentration_drift'] ?? 0).toDouble(),
      clusterTurnover: (json['cluster_turnover'] ?? 0).toDouble(),
      severity: json['severity'] as String? ?? 'normal',
      severityReason: json['severity_reason'] as String?,
    );
  }
}

class ModelStabilityConcentrationHistoryModel {
  const ModelStabilityConcentrationHistoryModel({
    required this.latestStatus,
    required this.latestState,
    required this.history,
  });

  final ModelStabilityConcentrationStatusModel latestStatus;
  final ModelStabilityConcentrationHistoryEntryModel latestState;
  final List<ModelStabilityConcentrationHistoryEntryModel> history;

  factory ModelStabilityConcentrationHistoryModel.fromJson(
    Map<String, dynamic> json,
  ) {
    final history = json['history'] as List<dynamic>? ?? const <dynamic>[];
    return ModelStabilityConcentrationHistoryModel(
      latestStatus: ModelStabilityConcentrationStatusModel.fromJson(
        json['latest_status'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      latestState: ModelStabilityConcentrationHistoryEntryModel.fromJson(
        json['latest_state'] as Map<String, dynamic>? ??
            const <String, dynamic>{},
      ),
      history: history
          .map(
            (item) => ModelStabilityConcentrationHistoryEntryModel.fromJson(
              item as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }
}

class UserPnLModel {
  const UserPnLModel({
    required this.userId,
    required this.startingEquity,
    required this.currentEquity,
    required this.absolutePnl,
    required this.pnlPct,
    required this.peakEquity,
    required this.rollingDrawdown,
    required this.protectionState,
    required this.capitalMultiplier,
    required this.activeTrades,
    this.realizedPnl = 0,
    this.unrealizedPnl = 0,
    this.grossExposure = 0,
    this.openNotional = 0,
    this.profitFactor = 0,
    this.strategyHealthTag = 'Needs Improvement',
    this.drawdownAlert = false,
    this.riskProfileMode = 'normal',
    this.drawdownExplanation = '',
    this.concentrationWarning = '',
    this.largestPositionSymbol = '',
    this.largestPositionPct = 0,
    this.strategyScoreSummary = '',
    this.strategyScores = const <String, StrategyScoreModel>{},
  });

  final String userId;
  final double startingEquity;
  final double currentEquity;
  final double absolutePnl;
  final double pnlPct;
  final double peakEquity;
  final double rollingDrawdown;
  final String protectionState;
  final double capitalMultiplier;
  final int activeTrades;
  final double realizedPnl;
  final double unrealizedPnl;
  final double grossExposure;
  final double openNotional;
  final double profitFactor;
  final String strategyHealthTag;
  final bool drawdownAlert;
  final String riskProfileMode;
  final String drawdownExplanation;
  final String concentrationWarning;
  final String largestPositionSymbol;
  final double largestPositionPct;
  final String strategyScoreSummary;
  final Map<String, StrategyScoreModel> strategyScores;

  factory UserPnLModel.fromJson(Map<String, dynamic> json) {
    return UserPnLModel(
      userId: json['user_id'] as String? ?? '',
      startingEquity: (json['starting_equity'] ?? 0).toDouble(),
      currentEquity: (json['current_equity'] ?? 0).toDouble(),
      absolutePnl: (json['absolute_pnl'] ?? 0).toDouble(),
      pnlPct: (json['pnl_pct'] ?? 0).toDouble(),
      peakEquity: (json['peak_equity'] ?? 0).toDouble(),
      rollingDrawdown: (json['rolling_drawdown'] ?? 0).toDouble(),
      protectionState: json['protection_state'] as String? ?? 'UNKNOWN',
      capitalMultiplier: (json['capital_multiplier'] ?? 0).toDouble(),
      activeTrades: (json['active_trades'] as num?)?.toInt() ?? 0,
      realizedPnl: (json['realized_pnl'] ?? 0).toDouble(),
      unrealizedPnl: (json['unrealized_pnl'] ?? 0).toDouble(),
      grossExposure: (json['gross_exposure'] ?? 0).toDouble(),
      openNotional: (json['open_notional'] ?? 0).toDouble(),
      profitFactor: (json['profit_factor'] ?? 0).toDouble(),
      strategyHealthTag:
          json['strategy_health_tag'] as String? ?? 'Needs Improvement',
      drawdownAlert: json['drawdown_alert'] as bool? ?? false,
      riskProfileMode: json['risk_profile_mode'] as String? ?? 'normal',
      drawdownExplanation: json['drawdown_explanation'] as String? ?? '',
      concentrationWarning: json['concentration_warning'] as String? ?? '',
      largestPositionSymbol: json['largest_position_symbol'] as String? ?? '',
      largestPositionPct: (json['largest_position_pct'] ?? 0).toDouble(),
      strategyScoreSummary: json['strategy_score_summary'] as String? ?? '',
      strategyScores:
          (json['strategy_scores'] as Map? ?? const <String, dynamic>{}).map(
        (key, value) => MapEntry(
          key.toString(),
          StrategyScoreModel.fromJson(
            Map<String, dynamic>.from(
                value as Map? ?? const <String, dynamic>{}),
          ),
        ),
      ),
    );
  }

  UserPnLModel copyWith({
    String? userId,
    double? startingEquity,
    double? currentEquity,
    double? absolutePnl,
    double? pnlPct,
    double? peakEquity,
    double? rollingDrawdown,
    String? protectionState,
    double? capitalMultiplier,
    int? activeTrades,
    double? realizedPnl,
    double? unrealizedPnl,
    double? grossExposure,
    double? openNotional,
    double? profitFactor,
    String? strategyHealthTag,
    bool? drawdownAlert,
    String? riskProfileMode,
    String? drawdownExplanation,
    String? concentrationWarning,
    String? largestPositionSymbol,
    double? largestPositionPct,
    String? strategyScoreSummary,
    Map<String, StrategyScoreModel>? strategyScores,
  }) {
    return UserPnLModel(
      userId: userId ?? this.userId,
      startingEquity: startingEquity ?? this.startingEquity,
      currentEquity: currentEquity ?? this.currentEquity,
      absolutePnl: absolutePnl ?? this.absolutePnl,
      pnlPct: pnlPct ?? this.pnlPct,
      peakEquity: peakEquity ?? this.peakEquity,
      rollingDrawdown: rollingDrawdown ?? this.rollingDrawdown,
      protectionState: protectionState ?? this.protectionState,
      capitalMultiplier: capitalMultiplier ?? this.capitalMultiplier,
      activeTrades: activeTrades ?? this.activeTrades,
      realizedPnl: realizedPnl ?? this.realizedPnl,
      unrealizedPnl: unrealizedPnl ?? this.unrealizedPnl,
      grossExposure: grossExposure ?? this.grossExposure,
      openNotional: openNotional ?? this.openNotional,
      profitFactor: profitFactor ?? this.profitFactor,
      strategyHealthTag: strategyHealthTag ?? this.strategyHealthTag,
      drawdownAlert: drawdownAlert ?? this.drawdownAlert,
      riskProfileMode: riskProfileMode ?? this.riskProfileMode,
      drawdownExplanation: drawdownExplanation ?? this.drawdownExplanation,
      concentrationWarning: concentrationWarning ?? this.concentrationWarning,
      largestPositionSymbol:
          largestPositionSymbol ?? this.largestPositionSymbol,
      largestPositionPct: largestPositionPct ?? this.largestPositionPct,
      strategyScoreSummary: strategyScoreSummary ?? this.strategyScoreSummary,
      strategyScores: strategyScores ?? this.strategyScores,
    );
  }

  List<double> get sparkline {
    final base = startingEquity;
    if (base == 0) {
      return const [0, 0, 0, 0];
    }
    return <double>[
      base,
      base + absolutePnl * 0.35,
      peakEquity,
      currentEquity,
    ];
  }
}

class StrategyScoreModel {
  const StrategyScoreModel({
    required this.trades,
    required this.winRate,
    required this.pnl,
    required this.tag,
  });

  final int trades;
  final double winRate;
  final double pnl;
  final String tag;

  factory StrategyScoreModel.fromJson(Map<String, dynamic> json) {
    return StrategyScoreModel(
      trades: (json['trades'] as num?)?.toInt() ?? 0,
      winRate: (json['win_rate'] as num?)?.toDouble() ?? 0,
      pnl: (json['pnl'] as num?)?.toDouble() ?? 0,
      tag: json['tag'] as String? ?? 'Needs More Data',
    );
  }
}

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

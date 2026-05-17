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

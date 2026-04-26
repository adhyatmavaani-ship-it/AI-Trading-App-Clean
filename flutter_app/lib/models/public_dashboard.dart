class PublicPerformanceModel {
  const PublicPerformanceModel({
    required this.winRate,
    required this.totalPnlPct,
    required this.totalTrades,
    required this.lastUpdated,
  });

  final double winRate;
  final double totalPnlPct;
  final int totalTrades;
  final DateTime lastUpdated;

  factory PublicPerformanceModel.fromJson(Map<String, dynamic> json) {
    return PublicPerformanceModel(
      winRate: (json['win_rate'] as num?)?.toDouble() ?? 0,
      totalPnlPct: (json['total_pnl_pct'] as num?)?.toDouble() ?? 0,
      totalTrades: (json['total_trades'] as num?)?.toInt() ?? 0,
      lastUpdated: DateTime.tryParse(json['last_updated'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
    );
  }
}

class PublicTradeModel {
  const PublicTradeModel({
    required this.symbol,
    required this.side,
    required this.entry,
    required this.exit,
    required this.pnlPct,
    required this.status,
  });

  final String symbol;
  final String side;
  final double entry;
  final double exit;
  final double pnlPct;
  final String status;

  bool get isPositive => pnlPct >= 0;

  factory PublicTradeModel.fromJson(Map<String, dynamic> json) {
    return PublicTradeModel(
      symbol: json['symbol'] as String? ?? '',
      side: json['side'] as String? ?? '',
      entry: (json['entry'] as num?)?.toDouble() ?? 0,
      exit: (json['exit'] as num?)?.toDouble() ?? 0,
      pnlPct: (json['pnl_pct'] as num?)?.toDouble() ?? 0,
      status: json['status'] as String? ?? 'LOSS',
    );
  }
}

class PublicDailyPointModel {
  const PublicDailyPointModel({
    required this.date,
    required this.pnlPct,
  });

  final String date;
  final double pnlPct;

  factory PublicDailyPointModel.fromJson(Map<String, dynamic> json) {
    return PublicDailyPointModel(
      date: json['date'] as String? ?? '',
      pnlPct: (json['pnl_pct'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TrustDashboardModel {
  const TrustDashboardModel({
    required this.performance,
    required this.trades,
    required this.daily,
  });

  final PublicPerformanceModel performance;
  final List<PublicTradeModel> trades;
  final List<PublicDailyPointModel> daily;
}

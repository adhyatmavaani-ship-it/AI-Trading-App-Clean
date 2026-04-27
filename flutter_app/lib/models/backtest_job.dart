class BacktestRunRequestModel {
  const BacktestRunRequestModel({
    required this.symbol,
    required this.days,
    this.timeframe = '5m',
    this.strategy = 'ensemble',
    this.startingBalance = 10000,
    this.riskProfile = 'medium',
  });

  final String symbol;
  final int days;
  final String timeframe;
  final String strategy;
  final double startingBalance;
  final String riskProfile;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'symbol': symbol,
      'days': days,
      'timeframe': timeframe,
      'strategy': strategy,
      'starting_balance': startingBalance,
      'risk_profile': riskProfile,
    };
  }
}

class BacktestCompareRequestModel {
  const BacktestCompareRequestModel({
    required this.symbol,
    required this.days,
    required this.profiles,
    this.timeframe = '5m',
    this.strategy = 'ensemble',
    this.startingBalance = 10000,
  });

  final String symbol;
  final int days;
  final List<String> profiles;
  final String timeframe;
  final String strategy;
  final double startingBalance;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'symbol': symbol,
      'days': days,
      'profiles': profiles,
      'timeframe': timeframe,
      'strategy': strategy,
      'starting_balance': startingBalance,
    };
  }
}

class BacktestJobLogModel {
  const BacktestJobLogModel({
    required this.timestamp,
    required this.message,
  });

  final DateTime timestamp;
  final String message;

  factory BacktestJobLogModel.fromJson(Map<String, dynamic> json) {
    return BacktestJobLogModel(
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.now().toUtc(),
      message: json['message'] as String? ?? '',
    );
  }
}

class BacktestEquityPointModel {
  const BacktestEquityPointModel({
    required this.step,
    required this.equity,
    required this.regime,
  });

  final int step;
  final double equity;
  final String regime;

  factory BacktestEquityPointModel.fromJson(Map<String, dynamic> json) {
    return BacktestEquityPointModel(
      step: (json['step'] as num?)?.toInt() ?? 0,
      equity: (json['equity'] as num?)?.toDouble() ?? 0,
      regime: json['regime'] as String? ?? 'UNKNOWN',
    );
  }
}

class BacktestSummaryModel {
  const BacktestSummaryModel({
    required this.symbol,
    required this.timeframe,
    required this.strategy,
    required this.days,
    required this.startingBalance,
    required this.finalEquity,
    required this.totalProfit,
    required this.roiPct,
    required this.winRate,
    required this.maxDrawdown,
    required this.profitFactor,
    required this.totalTrades,
  });

  final String symbol;
  final String timeframe;
  final String strategy;
  final int days;
  final double startingBalance;
  final double finalEquity;
  final double totalProfit;
  final double roiPct;
  final double winRate;
  final double maxDrawdown;
  final double profitFactor;
  final int totalTrades;

  factory BacktestSummaryModel.fromJson(Map<String, dynamic> json) {
    return BacktestSummaryModel(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '5m',
      strategy: json['strategy'] as String? ?? 'ensemble',
      days: (json['days'] as num?)?.toInt() ?? 0,
      startingBalance: (json['starting_balance'] as num?)?.toDouble() ?? 0,
      finalEquity: (json['final_equity'] as num?)?.toDouble() ?? 0,
      totalProfit: (json['total_profit'] as num?)?.toDouble() ?? 0,
      roiPct: (json['roi_pct'] as num?)?.toDouble() ?? 0,
      winRate: (json['win_rate'] as num?)?.toDouble() ?? 0,
      maxDrawdown: (json['max_drawdown'] as num?)?.toDouble() ?? 0,
      profitFactor: (json['profit_factor'] as num?)?.toDouble() ?? 0,
      totalTrades: (json['total_trades'] as num?)?.toInt() ?? 0,
    );
  }
}

class BacktestJobResultModel {
  const BacktestJobResultModel({
    required this.summary,
    required this.equityCurve,
    required this.trades,
  });

  final BacktestSummaryModel summary;
  final List<BacktestEquityPointModel> equityCurve;
  final List<Map<String, dynamic>> trades;

  factory BacktestJobResultModel.fromJson(Map<String, dynamic> json) {
    return BacktestJobResultModel(
      summary: BacktestSummaryModel.fromJson(
        json['summary'] as Map<String, dynamic>? ?? const {},
      ),
      equityCurve: (json['equity_curve'] as List<dynamic>? ?? const [])
          .map((item) => BacktestEquityPointModel.fromJson(
              item as Map<String, dynamic>))
          .toList(),
      trades: (json['trades'] as List<dynamic>? ?? const [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
    );
  }
}

class BacktestComparisonProfileResultModel {
  const BacktestComparisonProfileResultModel({
    required this.riskProfile,
    required this.summary,
    required this.equityCurve,
    required this.trades,
  });

  final String riskProfile;
  final BacktestSummaryModel summary;
  final List<BacktestEquityPointModel> equityCurve;
  final List<Map<String, dynamic>> trades;

  factory BacktestComparisonProfileResultModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return BacktestComparisonProfileResultModel(
      riskProfile: json['risk_profile'] as String? ?? 'medium',
      summary: BacktestSummaryModel.fromJson(
        json['summary'] as Map<String, dynamic>? ?? const {},
      ),
      equityCurve: (json['equity_curve'] as List<dynamic>? ?? const [])
          .map((item) => BacktestEquityPointModel.fromJson(
              item as Map<String, dynamic>))
          .toList(),
      trades: (json['trades'] as List<dynamic>? ?? const [])
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList(),
    );
  }
}

class BacktestJobStatusModel {
  const BacktestJobStatusModel({
    required this.jobId,
    required this.userId,
    required this.status,
    required this.progressPct,
    required this.currentStage,
    required this.tradesFound,
    required this.netProfit,
    required this.logs,
    required this.comparisonProfiles,
    this.error,
    this.result,
  });

  final String jobId;
  final String userId;
  final String status;
  final double progressPct;
  final String currentStage;
  final int tradesFound;
  final double netProfit;
  final String? error;
  final List<BacktestJobLogModel> logs;
  final BacktestJobResultModel? result;
  final List<BacktestComparisonProfileResultModel> comparisonProfiles;

  bool get isTerminal => status == 'COMPLETED' || status == 'FAILED';

  factory BacktestJobStatusModel.fromJson(Map<String, dynamic> json) {
    return BacktestJobStatusModel(
      jobId: json['job_id'] as String? ?? '',
      userId: json['user_id'] as String? ?? '',
      status: json['status'] as String? ?? 'QUEUED',
      progressPct: (json['progress_pct'] as num?)?.toDouble() ?? 0,
      currentStage: json['current_stage'] as String? ?? 'queued',
      tradesFound: (json['trades_found'] as num?)?.toInt() ?? 0,
      netProfit: (json['net_profit'] as num?)?.toDouble() ?? 0,
      error: json['error'] as String?,
      logs: (json['logs'] as List<dynamic>? ?? const [])
          .map((item) => BacktestJobLogModel.fromJson(
              item as Map<String, dynamic>))
          .toList(),
      result: json['result'] is Map<String, dynamic>
          ? BacktestJobResultModel.fromJson(
              json['result'] as Map<String, dynamic>)
          : null,
      comparisonProfiles:
          (json['comparison_profiles'] as List<dynamic>? ?? const [])
              .map((item) => BacktestComparisonProfileResultModel.fromJson(
                  item as Map<String, dynamic>))
              .toList(),
    );
  }
}

class DashboardData {
  final double balance;
  final double profit;
  final int trades;
  final String aiReason;
  final double confidence;
  final String riskLevel;

  const DashboardData({
    required this.balance,
    required this.profit,
    required this.trades,
    required this.aiReason,
    required this.confidence,
    required this.riskLevel,
  });
}

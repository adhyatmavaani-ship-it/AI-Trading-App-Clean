class ActiveTradeModel {
  const ActiveTradeModel({
    required this.tradeId,
    required this.symbol,
    required this.side,
    required this.entry,
    required this.stopLoss,
    required this.takeProfit,
    required this.executedQuantity,
    required this.entryReason,
    required this.status,
    required this.regime,
    required this.riskFraction,
  });

  final String tradeId;
  final String symbol;
  final String side;
  final double entry;
  final double stopLoss;
  final double takeProfit;
  final double executedQuantity;
  final String entryReason;
  final String status;
  final String regime;
  final double riskFraction;

  factory ActiveTradeModel.fromJson(Map<String, dynamic> json) {
    return ActiveTradeModel(
      tradeId: json['trade_id'] as String? ?? '',
      symbol: json['symbol'] as String? ?? '',
      side: json['side'] as String? ?? '',
      entry: (json['entry'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      takeProfit: (json['take_profit'] ?? 0).toDouble(),
      executedQuantity: (json['executed_quantity'] ?? 0).toDouble(),
      entryReason: json['entry_reason'] as String? ?? '',
      status: json['status'] as String? ?? '',
      regime: json['regime'] as String? ?? '',
      riskFraction: (json['risk_fraction'] ?? 0).toDouble(),
    );
  }
}

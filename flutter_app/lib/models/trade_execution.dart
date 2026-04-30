class TradeExecutionRequestModel {
  const TradeExecutionRequestModel({
    required this.userId,
    required this.symbol,
    required this.side,
    required this.confidence,
    required this.reason,
    this.quantity,
    this.orderType = 'MARKET',
    this.limitPrice,
    this.expectedReturn,
    this.expectedRisk,
    this.featureSnapshot = const <String, double>{},
    this.requestedNotional,
    this.signalId,
    this.strategy = '',
    this.macroBiasMultiplier,
    this.macroBiasRegime,
  });

  final String userId;
  final String symbol;
  final String side;
  final double confidence;
  final String reason;
  final double? quantity;
  final String orderType;
  final double? limitPrice;
  final double? expectedReturn;
  final double? expectedRisk;
  final Map<String, double> featureSnapshot;
  final double? requestedNotional;
  final String? signalId;
  final String strategy;
  final double? macroBiasMultiplier;
  final String? macroBiasRegime;

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'user_id': userId,
      'symbol': symbol,
      'side': side,
      if (quantity != null) 'quantity': quantity,
      'order_type': orderType,
      if (limitPrice != null) 'limit_price': limitPrice,
      'confidence': confidence,
      'reason': reason,
      if (expectedReturn != null) 'expected_return': expectedReturn,
      if (expectedRisk != null) 'expected_risk': expectedRisk,
      'feature_snapshot': featureSnapshot,
      if (requestedNotional != null) 'requested_notional': requestedNotional,
      if (signalId != null) 'signal_id': signalId,
      'strategy': strategy,
      if (macroBiasMultiplier != null)
        'macro_bias_multiplier': macroBiasMultiplier,
      if (macroBiasRegime != null) 'macro_bias_regime': macroBiasRegime,
    };
  }
}

class TradeExecutionResponseModel {
  const TradeExecutionResponseModel({
    required this.tradeId,
    required this.status,
    required this.tradingMode,
    required this.symbol,
    required this.side,
    required this.executedPrice,
    required this.executedQuantity,
    required this.stopLoss,
    required this.trailingStopPct,
    required this.takeProfit,
    required this.feePaid,
    required this.slippageBps,
    required this.filledRatio,
    required this.explanation,
    required this.alphaScore,
  });

  final String tradeId;
  final String status;
  final String tradingMode;
  final String symbol;
  final String side;
  final double executedPrice;
  final double executedQuantity;
  final double stopLoss;
  final double trailingStopPct;
  final double takeProfit;
  final double feePaid;
  final double slippageBps;
  final double filledRatio;
  final String explanation;
  final double alphaScore;

  factory TradeExecutionResponseModel.fromJson(Map<String, dynamic> json) {
    return TradeExecutionResponseModel(
      tradeId: json['trade_id'] as String? ?? '',
      status: json['status'] as String? ?? '',
      tradingMode: json['trading_mode'] as String? ?? 'paper',
      symbol: json['symbol'] as String? ?? '',
      side: json['side'] as String? ?? '',
      executedPrice: (json['executed_price'] as num?)?.toDouble() ?? 0,
      executedQuantity: (json['executed_quantity'] as num?)?.toDouble() ?? 0,
      stopLoss: (json['stop_loss'] as num?)?.toDouble() ?? 0,
      trailingStopPct:
          (json['trailing_stop_pct'] as num?)?.toDouble() ?? 0,
      takeProfit: (json['take_profit'] as num?)?.toDouble() ?? 0,
      feePaid: (json['fee_paid'] as num?)?.toDouble() ?? 0,
      slippageBps: (json['slippage_bps'] as num?)?.toDouble() ?? 0,
      filledRatio: (json['filled_ratio'] as num?)?.toDouble() ?? 0,
      explanation: json['explanation'] as String? ?? '',
      alphaScore: (json['alpha_score'] as num?)?.toDouble() ?? 0,
    );
  }
}

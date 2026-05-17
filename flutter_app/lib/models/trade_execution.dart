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

class TradeEvaluationSnapshotModel {
  const TradeEvaluationSnapshotModel({
    required this.price,
    required this.regime,
    required this.featureSnapshot,
  });

  final double price;
  final String regime;
  final Map<String, double> featureSnapshot;

  factory TradeEvaluationSnapshotModel.fromJson(Map<String, dynamic> json) {
    final rawFeatures =
        json['features'] as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{};
    return TradeEvaluationSnapshotModel(
      price: (json['price'] as num?)?.toDouble() ?? 0,
      regime: json['regime'] as String? ?? 'UNKNOWN',
      featureSnapshot: rawFeatures.map(
        (key, value) => MapEntry(
          key.toString(),
          value is num ? value.toDouble() : 0,
        ),
      ),
    );
  }
}

class TradeEvaluationInferenceModel {
  const TradeEvaluationInferenceModel({
    required this.decision,
    required this.confidenceScore,
    required this.tradeProbability,
    required this.expectedReturn,
    required this.expectedRisk,
    required this.reason,
  });

  final String decision;
  final double confidenceScore;
  final double tradeProbability;
  final double expectedReturn;
  final double expectedRisk;
  final String reason;

  factory TradeEvaluationInferenceModel.fromJson(Map<String, dynamic> json) {
    return TradeEvaluationInferenceModel(
      decision: json['decision'] as String? ?? 'HOLD',
      confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0,
      tradeProbability: (json['trade_probability'] as num?)?.toDouble() ?? 0,
      expectedReturn: (json['expected_return'] as num?)?.toDouble() ?? 0,
      expectedRisk: (json['expected_risk'] as num?)?.toDouble() ?? 0,
      reason: json['reason'] as String? ?? '',
    );
  }
}

class TradeEvaluationAlphaDecisionModel {
  const TradeEvaluationAlphaDecisionModel({
    required this.finalScore,
    required this.allowTrade,
    required this.expectedReturn,
    required this.netExpectedReturn,
    required this.riskScore,
    required this.executionCostTotal,
  });

  final double finalScore;
  final bool allowTrade;
  final double expectedReturn;
  final double netExpectedReturn;
  final double riskScore;
  final double executionCostTotal;

  factory TradeEvaluationAlphaDecisionModel.fromJson(
    Map<String, dynamic> json,
  ) {
    return TradeEvaluationAlphaDecisionModel(
      finalScore: (json['final_score'] as num?)?.toDouble() ?? 0,
      allowTrade: json['allow_trade'] as bool? ?? false,
      expectedReturn: (json['expected_return'] as num?)?.toDouble() ?? 0,
      netExpectedReturn: (json['net_expected_return'] as num?)?.toDouble() ?? 0,
      riskScore: (json['risk_score'] as num?)?.toDouble() ?? 0,
      executionCostTotal:
          (json['execution_cost_total'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TradeEvaluationModel {
  const TradeEvaluationModel({
    required this.symbol,
    required this.strategy,
    required this.timeframe,
    required this.riskBudget,
    required this.rolloutCapitalFraction,
    required this.snapshot,
    required this.inference,
    required this.alphaDecision,
  });

  final String symbol;
  final String strategy;
  final String timeframe;
  final double riskBudget;
  final double rolloutCapitalFraction;
  final TradeEvaluationSnapshotModel snapshot;
  final TradeEvaluationInferenceModel inference;
  final TradeEvaluationAlphaDecisionModel alphaDecision;

  bool get allowTrade => alphaDecision.allowTrade;
  String get approvedSide => inference.decision.toUpperCase();
  double get confidenceScore => inference.confidenceScore;
  String get reason => inference.reason;
  double get alphaScore => alphaDecision.finalScore;

  factory TradeEvaluationModel.fromJson(Map<String, dynamic> json) {
    return TradeEvaluationModel(
      symbol: json['symbol'] as String? ?? '',
      strategy: json['strategy'] as String? ?? 'NO_TRADE',
      timeframe: json['timeframe'] as String? ?? 'multi',
      riskBudget: (json['risk_budget'] as num?)?.toDouble() ?? 0,
      rolloutCapitalFraction:
          (json['rollout_capital_fraction'] as num?)?.toDouble() ?? 0,
      snapshot: TradeEvaluationSnapshotModel.fromJson(
        (json['snapshot'] as Map<String, dynamic>?) ?? const <String, dynamic>{},
      ),
      inference: TradeEvaluationInferenceModel.fromJson(
        (json['inference'] as Map<String, dynamic>?) ??
            const <String, dynamic>{},
      ),
      alphaDecision: TradeEvaluationAlphaDecisionModel.fromJson(
        (json['alpha_decision'] as Map<String, dynamic>?) ??
            const <String, dynamic>{},
      ),
    );
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

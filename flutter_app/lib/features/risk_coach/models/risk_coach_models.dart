class RiskCoachCandle {
  const RiskCoachCandle({
    required this.timestampMs,
    required this.open,
    required this.high,
    required this.low,
    required this.close,
    required this.volume,
  });

  final int timestampMs;
  final double open;
  final double high;
  final double low;
  final double close;
  final double volume;

  factory RiskCoachCandle.fromJson(Map<String, dynamic> json) {
    return RiskCoachCandle(
      timestampMs: (json['t'] as num?)?.toInt() ?? 0,
      open: (json['o'] as num?)?.toDouble() ?? 0,
      high: (json['h'] as num?)?.toDouble() ?? 0,
      low: (json['l'] as num?)?.toDouble() ?? 0,
      close: (json['c'] as num?)?.toDouble() ?? 0,
      volume: (json['v'] as num?)?.toDouble() ?? 0,
    );
  }
}

class RiskCoachStreamEvent {
  const RiskCoachStreamEvent({
    required this.stream,
    required this.data,
  });

  final String stream;
  final RiskCoachCandle data;

  factory RiskCoachStreamEvent.fromJson(Map<String, dynamic> json) {
    return RiskCoachStreamEvent(
      stream: json['stream'] as String? ?? 'btcusdt@kline_1m',
      data: RiskCoachCandle.fromJson(
        Map<String, dynamic>.from(json['data'] as Map? ?? const <String, dynamic>{}),
      ),
    );
  }
}

class RiskCoachOhlcResponse {
  const RiskCoachOhlcResponse({
    required this.symbol,
    required this.interval,
    required this.stream,
    required this.candles,
    required this.source,
    required this.educationalOnly,
  });

  final String symbol;
  final String interval;
  final String stream;
  final List<RiskCoachCandle> candles;
  final String source;
  final String educationalOnly;

  factory RiskCoachOhlcResponse.fromJson(Map<String, dynamic> json) {
    return RiskCoachOhlcResponse(
      symbol: json['symbol'] as String? ?? 'BTCUSDT',
      interval: json['interval'] as String? ?? '1m',
      stream: json['stream'] as String? ?? 'btcusdt@kline_1m',
      candles: (json['candles'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => RiskCoachCandle.fromJson(Map<String, dynamic>.from(item as Map)))
          .toList(),
      source: json['source'] as String? ?? 'unknown',
      educationalOnly: json['educational_only'] as String? ??
          'Educational only. Not financial advice. No guaranteed profits.',
    );
  }
}

class RiskPlan {
  const RiskPlan({
    required this.allowed,
    required this.blockers,
    required this.warnings,
    required this.positionSize,
    required this.notional,
    required this.effectiveRr,
    required this.expectedValue,
    required this.heatmapIntensity,
    required this.heatmapState,
    required this.educationalOnly,
  });

  final bool allowed;
  final List<String> blockers;
  final List<String> warnings;
  final double positionSize;
  final double notional;
  final double effectiveRr;
  final double expectedValue;
  final double heatmapIntensity;
  final String heatmapState;
  final String educationalOnly;

  factory RiskPlan.fromJson(Map<String, dynamic> json) {
    return RiskPlan(
      allowed: json['allowed'] as bool? ?? false,
      blockers: (json['blockers'] as List<dynamic>? ?? const <dynamic>[]).map((item) => item.toString()).toList(),
      warnings: (json['warnings'] as List<dynamic>? ?? const <dynamic>[]).map((item) => item.toString()).toList(),
      positionSize: (json['position_size'] as num?)?.toDouble() ?? 0,
      notional: (json['notional'] as num?)?.toDouble() ?? 0,
      effectiveRr: (json['effective_rr'] as num?)?.toDouble() ?? 0,
      expectedValue: (json['expected_value'] as num?)?.toDouble() ?? 0,
      heatmapIntensity: (json['heatmap_intensity'] as num?)?.toDouble() ?? 0,
      heatmapState: json['heatmap_state'] as String? ?? 'neutral',
      educationalOnly: json['educational_only'] as String? ??
          'Educational only. Not financial advice. No guaranteed profits.',
    );
  }
}

class HeatmapZoneModel {
  const HeatmapZoneModel({
    required this.startPrice,
    required this.endPrice,
    required this.intensity,
    required this.state,
    required this.expectedValue,
  });

  final double startPrice;
  final double endPrice;
  final double intensity;
  final String state;
  final double expectedValue;

  factory HeatmapZoneModel.fromJson(Map<String, dynamic> json) {
    return HeatmapZoneModel(
      startPrice: (json['start_price'] as num?)?.toDouble() ?? 0,
      endPrice: (json['end_price'] as num?)?.toDouble() ?? 0,
      intensity: (json['intensity'] as num?)?.toDouble() ?? 0,
      state: json['state'] as String? ?? 'neutral',
      expectedValue: (json['expected_value'] as num?)?.toDouble() ?? 0,
    );
  }
}

class RiskCoachTrade {
  const RiskCoachTrade({
    required this.tradeId,
    required this.symbol,
    required this.side,
    required this.state,
    required this.entry,
    required this.stopLoss,
    required this.takeProfit,
    required this.pWin,
    required this.reliability,
    required this.rr,
    required this.positionSize,
    required this.createdAt,
  });

  final String tradeId;
  final String symbol;
  final String side;
  final String state;
  final double entry;
  final double stopLoss;
  final double takeProfit;
  final double pWin;
  final double reliability;
  final double rr;
  final double positionSize;
  final int createdAt;

  factory RiskCoachTrade.fromJson(Map<String, dynamic> json) {
    return RiskCoachTrade(
      tradeId: json['trade_id'] as String? ?? '',
      symbol: json['symbol'] as String? ?? 'BTCUSDT',
      side: json['side'] as String? ?? 'long',
      state: json['state'] as String? ?? 'idle',
      entry: (json['entry'] as num?)?.toDouble() ?? 0,
      stopLoss: (json['stop_loss'] as num?)?.toDouble() ?? 0,
      takeProfit: (json['take_profit'] as num?)?.toDouble() ?? 0,
      pWin: (json['p_win'] as num?)?.toDouble() ?? 0,
      reliability: (json['reliability'] as num?)?.toDouble() ?? 0,
      rr: (json['rr'] as num?)?.toDouble() ?? 0,
      positionSize: (json['position_size'] as num?)?.toDouble() ?? 0,
      createdAt: (json['created_at'] as num?)?.toInt() ?? 0,
    );
  }

  RiskCoachTrade copyWith({
    String? state,
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) {
    return RiskCoachTrade(
      tradeId: tradeId,
      symbol: symbol,
      side: side,
      state: state ?? this.state,
      entry: entry ?? this.entry,
      stopLoss: stopLoss ?? this.stopLoss,
      takeProfit: takeProfit ?? this.takeProfit,
      pWin: pWin,
      reliability: reliability,
      rr: rr,
      positionSize: positionSize,
      createdAt: createdAt,
    );
  }
}

class PostMortemInsightModel {
  const PostMortemInsightModel({
    required this.code,
    required this.severity,
    required this.message,
  });

  final String code;
  final String severity;
  final String message;

  factory PostMortemInsightModel.fromJson(Map<String, dynamic> json) {
    return PostMortemInsightModel(
      code: json['code'] as String? ?? '',
      severity: json['severity'] as String? ?? 'info',
      message: json['message'] as String? ?? '',
    );
  }
}

class PostMortemReportModel {
  const PostMortemReportModel({
    required this.trade,
    required this.mfeR,
    required this.maeR,
    required this.realizedRr,
    required this.insights,
  });

  final RiskCoachTrade trade;
  final double mfeR;
  final double maeR;
  final double realizedRr;
  final List<PostMortemInsightModel> insights;

  factory PostMortemReportModel.fromJson(Map<String, dynamic> json) {
    return PostMortemReportModel(
      trade: RiskCoachTrade.fromJson(Map<String, dynamic>.from(json['trade'] as Map? ?? const <String, dynamic>{})),
      mfeR: (json['mfe_r'] as num?)?.toDouble() ?? 0,
      maeR: (json['mae_r'] as num?)?.toDouble() ?? 0,
      realizedRr: (json['realized_rr'] as num?)?.toDouble() ?? 0,
      insights: (json['insights'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => PostMortemInsightModel.fromJson(Map<String, dynamic>.from(item as Map)))
          .toList(),
    );
  }
}

class RiskSignalMarker {
  const RiskSignalMarker({
    required this.tradeId,
    required this.timestampMs,
    required this.price,
    required this.side,
    required this.kind,
    required this.isActive,
  });

  final String tradeId;
  final int timestampMs;
  final double price;
  final String side;
  final String kind;
  final bool isActive;
}

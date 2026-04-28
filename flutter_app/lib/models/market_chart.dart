class MarketCandleModel {
  const MarketCandleModel({
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

  factory MarketCandleModel.fromJson(Map<String, dynamic> json) {
    return MarketCandleModel(
      timestampMs: (json['timestamp'] as num?)?.toInt() ?? 0,
      open: (json['open'] as num?)?.toDouble() ?? 0,
      high: (json['high'] as num?)?.toDouble() ?? 0,
      low: (json['low'] as num?)?.toDouble() ?? 0,
      close: (json['close'] as num?)?.toDouble() ?? 0,
      volume: (json['volume'] as num?)?.toDouble() ?? 0,
    );
  }
}

class TradeMarkerModel {
  const TradeMarkerModel({
    required this.type,
    required this.markerType,
    required this.markerStyle,
    required this.side,
    required this.price,
    required this.timestamp,
    required this.confidenceScore,
    this.tradeId,
    this.exitReason,
    this.readinessScore,
    this.reason,
    this.message,
    this.intent,
  });

  final String type;
  final String markerType;
  final String markerStyle;
  final String side;
  final double price;
  final DateTime timestamp;
  final double confidenceScore;
  final String? tradeId;
  final String? exitReason;
  final double? readinessScore;
  final String? reason;
  final String? message;
  final String? intent;

  factory TradeMarkerModel.fromJson(Map<String, dynamic> json) {
    return TradeMarkerModel(
      type: json['type'] as String? ?? 'entry',
      markerType: json['marker_type'] as String? ?? 'ENTRY',
      markerStyle: json['marker_style'] as String? ?? 'filled',
      side: json['side'] as String? ?? 'BUY',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      timestamp: _parseMarkerTimestamp(json['timestamp']),
      confidenceScore:
          (json['confidence_score'] as num?)?.toDouble() ?? 0,
      tradeId: json['trade_id'] as String?,
      exitReason: json['exit_reason'] as String?,
      readinessScore: (json['readiness_score'] as num?)?.toDouble(),
      reason: json['reason'] as String?,
      message: json['message'] as String?,
      intent: json['intent'] as String?,
    );
  }
}

DateTime _parseMarkerTimestamp(dynamic raw) {
  if (raw is num) {
    final value = raw.toDouble();
    final milliseconds = value.abs() >= 1000000000000
        ? value.round()
        : (value * 1000).round();
    return DateTime.fromMillisecondsSinceEpoch(milliseconds, isUtc: true);
  }
  if (raw is String) {
    return DateTime.tryParse(raw) ?? DateTime.fromMillisecondsSinceEpoch(0);
  }
  return DateTime.fromMillisecondsSinceEpoch(0);
}
class MarketChartModel {
  const MarketChartModel({
    required this.symbol,
    required this.interval,
    required this.latestPrice,
    required this.changePct,
    required this.candles,
    required this.markers,
  });

  final String symbol;
  final String interval;
  final double latestPrice;
  final double changePct;
  final List<MarketCandleModel> candles;
  final List<TradeMarkerModel> markers;

  factory MarketChartModel.fromJson(Map<String, dynamic> json) {
    final candles = (json['candles'] as List<dynamic>? ?? const [])
        .map((item) => MarketCandleModel.fromJson(item as Map<String, dynamic>))
        .toList();
    final markers = (json['markers'] as List<dynamic>? ?? const [])
        .map((item) => TradeMarkerModel.fromJson(item as Map<String, dynamic>))
        .toList();
    return MarketChartModel(
      symbol: json['symbol'] as String? ?? 'BTCUSDT',
      interval: json['interval'] as String? ?? '5m',
      latestPrice: (json['latest_price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      candles: candles,
      markers: markers,
    );
  }
}

class MarketUniverseEntryModel {
  const MarketUniverseEntryModel({
    required this.symbol,
    required this.price,
    required this.changePct,
    required this.volumeRatio,
    required this.volatilityPct,
    required this.trendPct,
    required this.quoteVolume,
    required this.category,
  });

  final String symbol;
  final double price;
  final double changePct;
  final double volumeRatio;
  final double volatilityPct;
  final double trendPct;
  final double quoteVolume;
  final String category;

  factory MarketUniverseEntryModel.fromJson(Map<String, dynamic> json) {
    return MarketUniverseEntryModel(
      symbol: json['symbol'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      volumeRatio: (json['volume_ratio'] as num?)?.toDouble() ?? 0,
      volatilityPct: (json['volatility_pct'] as num?)?.toDouble() ?? 0,
      trendPct: (json['trend_pct'] as num?)?.toDouble() ?? 0,
      quoteVolume: (json['quote_volume'] as num?)?.toDouble() ?? 0,
      category: json['category'] as String? ?? 'watch',
    );
  }
}

class MarketUniverseModel {
  const MarketUniverseModel({
    required this.items,
    required this.topGainers,
    required this.highVolatility,
    required this.aiPicks,
  });

  final List<MarketUniverseEntryModel> items;
  final List<MarketUniverseEntryModel> topGainers;
  final List<MarketUniverseEntryModel> highVolatility;
  final List<MarketUniverseEntryModel> aiPicks;

  factory MarketUniverseModel.fromJson(Map<String, dynamic> json) {
    List<MarketUniverseEntryModel> parseEntries(dynamic raw) {
      return (raw as List<dynamic>? ?? const [])
          .map(
            (item) =>
                MarketUniverseEntryModel.fromJson(item as Map<String, dynamic>),
          )
          .toList();
    }

    final categories = json['categories'] as Map<String, dynamic>? ?? const {};
    return MarketUniverseModel(
      items: parseEntries(json['items']),
      topGainers: parseEntries(categories['top_gainers']),
      highVolatility: parseEntries(categories['high_volatility']),
      aiPicks: parseEntries(categories['ai_picks']),
    );
  }
}

class MarketTickerItemModel {
  const MarketTickerItemModel({
    required this.symbol,
    required this.price,
    required this.changePct,
  });

  final String symbol;
  final double price;
  final double changePct;

  factory MarketTickerItemModel.fromJson(Map<String, dynamic> json) {
    return MarketTickerItemModel(
      symbol: json['symbol'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
    );
  }
}

class MarketHeatmapItemModel {
  const MarketHeatmapItemModel({
    required this.symbol,
    required this.changePct,
    required this.intensity,
  });

  final String symbol;
  final double changePct;
  final double intensity;

  factory MarketHeatmapItemModel.fromJson(Map<String, dynamic> json) {
    return MarketHeatmapItemModel(
      symbol: json['symbol'] as String? ?? '',
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      intensity: (json['intensity'] as num?)?.toDouble() ?? 0,
    );
  }
}

class MarketSummaryModel {
  const MarketSummaryModel({
    required this.sentimentScore,
    required this.sentimentLabel,
    required this.marketBreadth,
    required this.avgChangePct,
    required this.avgVolatilityPct,
    required this.participationScore,
    required this.confidenceScore,
    required this.ticker,
    required this.heatmap,
  });

  final double sentimentScore;
  final String sentimentLabel;
  final double marketBreadth;
  final double avgChangePct;
  final double avgVolatilityPct;
  final double participationScore;
  final double confidenceScore;
  final List<MarketTickerItemModel> ticker;
  final List<MarketHeatmapItemModel> heatmap;

  factory MarketSummaryModel.fromJson(Map<String, dynamic> json) {
    final ticker = (json['ticker'] as List<dynamic>? ?? const [])
        .map(
          (item) =>
              MarketTickerItemModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
    final heatmap = (json['heatmap'] as List<dynamic>? ?? const [])
        .map(
          (item) =>
              MarketHeatmapItemModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
    return MarketSummaryModel(
      sentimentScore: (json['sentiment_score'] as num?)?.toDouble() ?? 0,
      sentimentLabel: json['sentiment_label'] as String? ?? 'NEUTRAL',
      marketBreadth: (json['market_breadth'] as num?)?.toDouble() ?? 0,
      avgChangePct: (json['avg_change_pct'] as num?)?.toDouble() ?? 0,
      avgVolatilityPct:
          (json['avg_volatility_pct'] as num?)?.toDouble() ?? 0,
      participationScore:
          (json['participation_score'] as num?)?.toDouble() ?? 0,
      confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0,
      ticker: ticker,
      heatmap: heatmap,
    );
  }
}

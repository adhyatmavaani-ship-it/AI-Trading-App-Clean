import 'activity.dart';

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

class ScannerCandidateModel {
  const ScannerCandidateModel({
    required this.symbol,
    required this.price,
    required this.changePct,
    required this.quoteVolume,
    required this.volumeRatio,
    required this.volumeSpikePct,
    required this.volatilityPct,
    required this.potentialScore,
    required this.exchange,
  });

  final String symbol;
  final double price;
  final double changePct;
  final double quoteVolume;
  final double volumeRatio;
  final double volumeSpikePct;
  final double volatilityPct;
  final double potentialScore;
  final String exchange;

  bool get isHot => volumeSpikePct > 20;

  factory ScannerCandidateModel.fromJson(Map<String, dynamic> json) {
    return ScannerCandidateModel(
      symbol: json['symbol'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      quoteVolume: (json['quote_volume'] as num?)?.toDouble() ?? 0,
      volumeRatio: (json['volume_ratio'] as num?)?.toDouble() ?? 0,
      volumeSpikePct: (json['volume_spike_pct'] as num?)?.toDouble() ?? 0,
      volatilityPct: (json['volatility_pct'] as num?)?.toDouble() ?? 0,
      potentialScore: (json['potential_score'] as num?)?.toDouble() ?? 0,
      exchange: json['exchange'] as String? ?? '',
    );
  }
}

class MarketScannerModel {
  const MarketScannerModel({
    required this.activeSymbols,
    required this.fixedSymbols,
    required this.rotatingSymbols,
    required this.candidates,
    required this.rotationStartedAt,
    required this.nextRotationAt,
    required this.secondsUntilRotation,
  });

  final List<String> activeSymbols;
  final List<String> fixedSymbols;
  final List<String> rotatingSymbols;
  final List<ScannerCandidateModel> candidates;
  final DateTime? rotationStartedAt;
  final DateTime? nextRotationAt;
  final int secondsUntilRotation;

  bool get hasScannerData => candidates.isNotEmpty || activeSymbols.isNotEmpty;

  double get averagePotentialScore {
    if (candidates.isEmpty) {
      return 0;
    }
    final total = candidates
        .take(10)
        .fold<double>(0, (sum, item) => sum + item.potentialScore);
    return total / candidates.take(10).length;
  }

  factory MarketScannerModel.fromJson(Map<String, dynamic> json) {
    List<String> parseSymbols(dynamic raw) {
      return (raw as List<dynamic>? ?? const [])
          .map((item) => item.toString())
          .where((item) => item.trim().isNotEmpty)
          .toList();
    }

    final candidates = (json['candidates'] as List<dynamic>? ?? const [])
        .map(
          (item) => ScannerCandidateModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
    return MarketScannerModel(
      activeSymbols: parseSymbols(json['active_symbols']),
      fixedSymbols: parseSymbols(json['fixed_symbols']),
      rotatingSymbols: parseSymbols(json['rotating_symbols']),
      candidates: candidates,
      rotationStartedAt: _parseNullableDateTime(json['rotation_started_at']),
      nextRotationAt: _parseNullableDateTime(json['next_rotation_at']),
      secondsUntilRotation: (json['seconds_until_rotation'] as num?)?.toInt() ?? 0,
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
    required this.scanner,
    required this.confidenceHistory,
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
  final MarketScannerModel scanner;
  final List<ConfidenceHistoryPointModel> confidenceHistory;

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
    final confidenceHistory =
        (json['confidence_history'] as List<dynamic>? ?? const [])
            .whereType<Map>()
            .map((item) => ConfidenceHistoryPointModel.fromJson(Map<String, dynamic>.from(item)))
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
      scanner: MarketScannerModel.fromJson(
        json['scanner'] as Map<String, dynamic>? ?? const <String, dynamic>{},
      ),
      confidenceHistory: confidenceHistory,
    );
  }
}

DateTime? _parseNullableDateTime(dynamic raw) {
  if (raw == null) {
    return null;
  }
  if (raw is String && raw.trim().isEmpty) {
    return null;
  }
  return DateTime.tryParse(raw.toString());
}

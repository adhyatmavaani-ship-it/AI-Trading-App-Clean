import 'activity.dart';

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

  MarketCandleModel copyWith({
    int? timestampMs,
    double? open,
    double? high,
    double? low,
    double? close,
    double? volume,
  }) {
    return MarketCandleModel(
      timestampMs: timestampMs ?? this.timestampMs,
      open: open ?? this.open,
      high: high ?? this.high,
      low: low ?? this.low,
      close: close ?? this.close,
      volume: volume ?? this.volume,
    );
  }

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
    this.confluenceBreakdown = const <String, String>{},
    this.confluenceAligned,
    this.confluenceTotal,
    this.riskFlags = const <String, dynamic>{},
    this.logicTags = const <String>[],
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
  final Map<String, String> confluenceBreakdown;
  final int? confluenceAligned;
  final int? confluenceTotal;
  final Map<String, dynamic> riskFlags;
  final List<String> logicTags;

  factory TradeMarkerModel.fromJson(Map<String, dynamic> json) {
    return TradeMarkerModel(
      type: json['type'] as String? ?? 'entry',
      markerType: json['marker_type'] as String? ?? 'ENTRY',
      markerStyle: json['marker_style'] as String? ?? 'filled',
      side: json['side'] as String? ?? 'BUY',
      price: (json['price'] as num?)?.toDouble() ?? 0,
      timestamp: _parseMarkerTimestamp(json['timestamp']),
      confidenceScore: (json['confidence_score'] as num?)?.toDouble() ?? 0,
      tradeId: json['trade_id'] as String?,
      exitReason: json['exit_reason'] as String?,
      readinessScore: (json['readiness_score'] as num?)?.toDouble(),
      reason: json['reason'] as String?,
      message: json['message'] as String?,
      intent: json['intent'] as String?,
      confluenceBreakdown: _markerStringMap(json['confluence_breakdown']),
      confluenceAligned: (json['confluence_aligned'] as num?)?.toInt(),
      confluenceTotal: (json['confluence_total'] as num?)?.toInt(),
      riskFlags: _markerDynamicMap(json['risk_flags']),
      logicTags: _markerStringList(json['logic_tags']),
    );
  }
}

DateTime _parseMarkerTimestamp(dynamic raw) {
  if (raw is num) {
    final value = raw.toDouble();
    final milliseconds =
        value.abs() >= 1000000000000 ? value.round() : (value * 1000).round();
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
    required this.confidenceIntervals,
    required this.confidenceHistory,
    this.overlays = const <MarketOverlayModel>[],
    this.opportunity = const OpportunityScoreModel(),
    this.marketRegime = const MarketRegimeSnapshotModel(),
    this.assistantModes = const <String>[],
    this.activeAssistantMode = 'ASSISTED',
    this.executionGuide = const ChartExecutionGuideModel(),
    this.strategyState = const StrategyStateModel(),
    this.aiFeed = const <AiFeedItemModel>[],
    this.trailingStop = const TrailingStopModel(),
    this.chartEngine = 'custom_canvas_pro',
    this.renderHints = const <String, dynamic>{},
    this.liquidityHeatmap = const LiquidityHeatmapModel(),
    this.orderbookDepth = const OrderbookDepthModel(),
    this.autonomousAssistant = const AutonomousAssistantModel(),
    this.renderProfile = const ChartRenderProfileModel(),
    this.snapshotVersion = 0,
    this.stateHash = '',
    this.integrityChecksum = '',
  });

  final String symbol;
  final String interval;
  final double latestPrice;
  final double changePct;
  final List<MarketCandleModel> candles;
  final List<TradeMarkerModel> markers;
  final List<ConfidenceIntervalModel> confidenceIntervals;
  final List<ConfidenceHistoryPointModel> confidenceHistory;
  final List<MarketOverlayModel> overlays;
  final OpportunityScoreModel opportunity;
  final MarketRegimeSnapshotModel marketRegime;
  final List<String> assistantModes;
  final String activeAssistantMode;
  final ChartExecutionGuideModel executionGuide;
  final StrategyStateModel strategyState;
  final List<AiFeedItemModel> aiFeed;
  final TrailingStopModel trailingStop;
  final String chartEngine;
  final Map<String, dynamic> renderHints;
  final LiquidityHeatmapModel liquidityHeatmap;
  final OrderbookDepthModel orderbookDepth;
  final AutonomousAssistantModel autonomousAssistant;
  final ChartRenderProfileModel renderProfile;
  final int snapshotVersion;
  final String stateHash;
  final String integrityChecksum;

  factory MarketChartModel.fromJson(Map<String, dynamic> json) {
    final candles = (json['candles'] as List<dynamic>? ?? const [])
        .map((item) => MarketCandleModel.fromJson(item as Map<String, dynamic>))
        .toList();
    final markers = (json['markers'] as List<dynamic>? ?? const [])
        .map((item) => TradeMarkerModel.fromJson(item as Map<String, dynamic>))
        .toList();
    final confidenceIntervals =
        (json['confidence_intervals'] as List<dynamic>? ?? const [])
            .map(
              (item) => ConfidenceIntervalModel.fromJson(
                item as Map<String, dynamic>,
              ),
            )
            .toList();
    final confidenceHistory =
        (json['confidence_history'] as List<dynamic>? ?? const [])
            .whereType<Map>()
            .map((item) => ConfidenceHistoryPointModel.fromJson(
                Map<String, dynamic>.from(item)))
            .toList();
    return MarketChartModel(
      symbol: json['symbol'] as String? ?? 'BTCUSDT',
      interval: json['interval'] as String? ?? '5m',
      latestPrice: (json['latest_price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      candles: candles,
      markers: markers,
      confidenceIntervals: confidenceIntervals,
      confidenceHistory: confidenceHistory,
      overlays: (json['overlays'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              MarketOverlayModel.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      opportunity: OpportunityScoreModel.fromJson(
        Map<String, dynamic>.from(
          json['opportunity'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      marketRegime: MarketRegimeSnapshotModel.fromJson(
        Map<String, dynamic>.from(
          json['market_regime'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      assistantModes:
          (json['assistant_modes'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(),
      activeAssistantMode:
          json['active_assistant_mode'] as String? ?? 'ASSISTED',
      executionGuide: ChartExecutionGuideModel.fromJson(
        Map<String, dynamic>.from(
          json['execution_guide'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      strategyState: StrategyStateModel.fromJson(
        Map<String, dynamic>.from(
          json['strategy_state'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      aiFeed: (json['ai_feed'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              AiFeedItemModel.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      trailingStop: TrailingStopModel.fromJson(
        Map<String, dynamic>.from(
          json['trailing_stop'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      chartEngine: json['chart_engine'] as String? ?? 'custom_canvas_pro',
      renderHints: Map<String, dynamic>.from(
        json['render_hints'] as Map? ?? const <String, dynamic>{},
      ),
      liquidityHeatmap: LiquidityHeatmapModel.fromJson(
        Map<String, dynamic>.from(
          json['liquidity_heatmap'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      orderbookDepth: OrderbookDepthModel.fromJson(
        Map<String, dynamic>.from(
          json['orderbook_depth'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      autonomousAssistant: AutonomousAssistantModel.fromJson(
        Map<String, dynamic>.from(
          json['autonomous_assistant'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      renderProfile: ChartRenderProfileModel.fromJson(
        Map<String, dynamic>.from(
          (json['render_hints'] as Map? ??
                  const <String, dynamic>{})['render_profile'] as Map? ??
              const <String, dynamic>{},
        ),
      ),
      snapshotVersion: (json['snapshot_version'] as num?)?.toInt() ?? 0,
      stateHash: json['state_hash'] as String? ?? '',
      integrityChecksum: json['integrity_checksum'] as String? ?? '',
    );
  }

  MarketChartModel copyWith({
    String? symbol,
    String? interval,
    double? latestPrice,
    double? changePct,
    List<MarketCandleModel>? candles,
    List<TradeMarkerModel>? markers,
    List<ConfidenceIntervalModel>? confidenceIntervals,
    List<ConfidenceHistoryPointModel>? confidenceHistory,
    List<MarketOverlayModel>? overlays,
    OpportunityScoreModel? opportunity,
    MarketRegimeSnapshotModel? marketRegime,
    List<String>? assistantModes,
    String? activeAssistantMode,
    ChartExecutionGuideModel? executionGuide,
    StrategyStateModel? strategyState,
    List<AiFeedItemModel>? aiFeed,
    TrailingStopModel? trailingStop,
    String? chartEngine,
    Map<String, dynamic>? renderHints,
    LiquidityHeatmapModel? liquidityHeatmap,
    OrderbookDepthModel? orderbookDepth,
    AutonomousAssistantModel? autonomousAssistant,
    ChartRenderProfileModel? renderProfile,
    int? snapshotVersion,
    String? stateHash,
    String? integrityChecksum,
  }) {
    return MarketChartModel(
      symbol: symbol ?? this.symbol,
      interval: interval ?? this.interval,
      latestPrice: latestPrice ?? this.latestPrice,
      changePct: changePct ?? this.changePct,
      candles: candles ?? this.candles,
      markers: markers ?? this.markers,
      confidenceIntervals: confidenceIntervals ?? this.confidenceIntervals,
      confidenceHistory: confidenceHistory ?? this.confidenceHistory,
      overlays: overlays ?? this.overlays,
      opportunity: opportunity ?? this.opportunity,
      marketRegime: marketRegime ?? this.marketRegime,
      assistantModes: assistantModes ?? this.assistantModes,
      activeAssistantMode: activeAssistantMode ?? this.activeAssistantMode,
      executionGuide: executionGuide ?? this.executionGuide,
      strategyState: strategyState ?? this.strategyState,
      aiFeed: aiFeed ?? this.aiFeed,
      trailingStop: trailingStop ?? this.trailingStop,
      chartEngine: chartEngine ?? this.chartEngine,
      renderHints: renderHints ?? this.renderHints,
      liquidityHeatmap: liquidityHeatmap ?? this.liquidityHeatmap,
      orderbookDepth: orderbookDepth ?? this.orderbookDepth,
      autonomousAssistant: autonomousAssistant ?? this.autonomousAssistant,
      renderProfile: renderProfile ?? this.renderProfile,
      snapshotVersion: snapshotVersion ?? this.snapshotVersion,
      stateHash: stateHash ?? this.stateHash,
      integrityChecksum: integrityChecksum ?? this.integrityChecksum,
    );
  }
}

class ChartRenderProfileModel {
  const ChartRenderProfileModel({
    this.mode = 'PRO',
    this.targetFps = 60,
    this.pressure = 0,
    this.maxOverlays = 40,
    this.maxDomLevels = 16,
    this.shaderQuality = 'full',
    this.thermalSafe = false,
  });

  final String mode;
  final int targetFps;
  final double pressure;
  final int maxOverlays;
  final int maxDomLevels;
  final String shaderQuality;
  final bool thermalSafe;

  factory ChartRenderProfileModel.fromJson(Map<String, dynamic> json) {
    return ChartRenderProfileModel(
      mode: json['mode'] as String? ?? 'PRO',
      targetFps: (json['target_fps'] as num?)?.toInt() ?? 60,
      pressure: (json['pressure'] as num?)?.toDouble() ?? 0,
      maxOverlays: (json['max_overlays'] as num?)?.toInt() ?? 40,
      maxDomLevels: (json['max_dom_levels'] as num?)?.toInt() ?? 16,
      shaderQuality: json['shader_quality'] as String? ?? 'full',
      thermalSafe: json['thermal_safe'] == true,
    );
  }
}

class OrderbookDepthModel {
  const OrderbookDepthModel({
    this.sequenceId = 0,
    this.pressureScore = 0,
    this.imbalanceProbability = 0,
    this.hiddenLiquidityScore = 0,
    this.exhaustionWarning = false,
    this.liquidityLadder = const <OrderbookLevelModel>[],
  });

  final int sequenceId;
  final double pressureScore;
  final double imbalanceProbability;
  final double hiddenLiquidityScore;
  final bool exhaustionWarning;
  final List<OrderbookLevelModel> liquidityLadder;

  factory OrderbookDepthModel.fromJson(Map<String, dynamic> json) {
    return OrderbookDepthModel(
      sequenceId: (json['sequence_id'] as num?)?.toInt() ?? 0,
      pressureScore: (json['pressure_score'] as num?)?.toDouble() ?? 0,
      imbalanceProbability:
          (json['imbalance_probability'] as num?)?.toDouble() ?? 0,
      hiddenLiquidityScore:
          (json['hidden_liquidity_score'] as num?)?.toDouble() ?? 0,
      exhaustionWarning: json['exhaustion_warning'] == true,
      liquidityLadder:
          (json['liquidity_ladder'] as List<dynamic>? ?? const <dynamic>[])
              .whereType<Map>()
              .map((item) =>
                  OrderbookLevelModel.fromJson(Map<String, dynamic>.from(item)))
              .toList(growable: false),
    );
  }
}

class OrderbookLevelModel {
  const OrderbookLevelModel({
    required this.level,
    required this.bidPrice,
    required this.bidSize,
    required this.askPrice,
    required this.askSize,
    required this.imbalance,
    required this.intensity,
  });

  final int level;
  final double bidPrice;
  final double bidSize;
  final double askPrice;
  final double askSize;
  final double imbalance;
  final double intensity;

  factory OrderbookLevelModel.fromJson(Map<String, dynamic> json) {
    return OrderbookLevelModel(
      level: (json['level'] as num?)?.toInt() ?? 0,
      bidPrice: (json['bid_price'] as num?)?.toDouble() ?? 0,
      bidSize: (json['bid_size'] as num?)?.toDouble() ?? 0,
      askPrice: (json['ask_price'] as num?)?.toDouble() ?? 0,
      askSize: (json['ask_size'] as num?)?.toDouble() ?? 0,
      imbalance: (json['imbalance'] as num?)?.toDouble() ?? 0,
      intensity: (json['intensity'] as num?)?.toDouble() ?? 0,
    );
  }
}

class AutonomousAssistantModel {
  const AutonomousAssistantModel({
    this.summary = '',
    this.voiceAlert = '',
    this.recommendations = const <String>[],
    this.replaySafe = true,
  });

  final String summary;
  final String voiceAlert;
  final List<String> recommendations;
  final bool replaySafe;

  factory AutonomousAssistantModel.fromJson(Map<String, dynamic> json) {
    return AutonomousAssistantModel(
      summary: json['summary'] as String? ?? '',
      voiceAlert: json['voice_alert'] as String? ?? '',
      recommendations:
          (json['recommendations'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(growable: false),
      replaySafe: json['replay_safe'] != false,
    );
  }
}

class LiquidityHeatmapModel {
  const LiquidityHeatmapModel({
    this.pressureScore = 0,
    this.nearestWall = '',
    this.zones = const <Map<String, dynamic>>[],
    this.heatmapZones = const <LiquidityHeatmapZoneModel>[],
  });

  final double pressureScore;
  final String nearestWall;
  final List<Map<String, dynamic>> zones;
  final List<LiquidityHeatmapZoneModel> heatmapZones;

  factory LiquidityHeatmapModel.fromJson(Map<String, dynamic> json) {
    return LiquidityHeatmapModel(
      pressureScore: (json['pressure_score'] as num?)?.toDouble() ?? 0,
      nearestWall: json['nearest_wall'] as String? ?? '',
      zones: (json['zones'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) => Map<String, dynamic>.from(item))
          .toList(growable: false),
      heatmapZones:
          (json['heatmap_zones'] as List<dynamic>? ?? const <dynamic>[])
              .whereType<Map>()
              .map((item) => LiquidityHeatmapZoneModel.fromJson(
                  Map<String, dynamic>.from(item)))
              .toList(growable: false),
    );
  }
}

class LiquidityHeatmapZoneModel {
  const LiquidityHeatmapZoneModel({
    required this.side,
    required this.label,
    required this.startTs,
    required this.endTs,
    required this.low,
    required this.high,
    required this.intensity,
    required this.opacity,
  });

  final String side;
  final String label;
  final int startTs;
  final int endTs;
  final double low;
  final double high;
  final double intensity;
  final double opacity;

  factory LiquidityHeatmapZoneModel.fromJson(Map<String, dynamic> json) {
    return LiquidityHeatmapZoneModel(
      side: json['side'] as String? ?? '',
      label: json['label'] as String? ?? '',
      startTs: (json['start_ts'] as num?)?.toInt() ?? 0,
      endTs: (json['end_ts'] as num?)?.toInt() ?? 0,
      low: (json['low'] as num?)?.toDouble() ?? 0,
      high: (json['high'] as num?)?.toDouble() ?? 0,
      intensity: (json['intensity'] as num?)?.toDouble() ?? 0,
      opacity: (json['opacity'] as num?)?.toDouble() ?? 0.12,
    );
  }
}

class MarketOverlayModel {
  const MarketOverlayModel({
    required this.zoneType,
    required this.label,
    required this.startTs,
    required this.endTs,
    required this.low,
    required this.high,
    required this.confidence,
    required this.side,
    required this.style,
    this.priority = 0,
    this.expiresAt,
  });

  final String zoneType;
  final String label;
  final int startTs;
  final int endTs;
  final double low;
  final double high;
  final double confidence;
  final String side;
  final String style;
  final int priority;
  final DateTime? expiresAt;

  factory MarketOverlayModel.fromJson(Map<String, dynamic> json) {
    return MarketOverlayModel(
      zoneType: json['zone_type'] as String? ?? '',
      label: json['label'] as String? ?? '',
      startTs: (json['start_ts'] as num?)?.toInt() ?? 0,
      endTs: (json['end_ts'] as num?)?.toInt() ?? 0,
      low: (json['low'] as num?)?.toDouble() ?? 0,
      high: (json['high'] as num?)?.toDouble() ?? 0,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      side: json['side'] as String? ?? '',
      style: json['style'] as String? ?? 'neutral',
      priority: (json['priority'] as num?)?.toInt() ?? 0,
      expiresAt: DateTime.tryParse(json['expires_at'] as String? ?? ''),
    );
  }
}

class OpportunityScoreModel {
  const OpportunityScoreModel({
    this.confidence = 0,
    this.expectedRr = 0,
    this.momentumScore = 0,
    this.volatilityScore = 0,
    this.whalePressure = 0,
    this.trendStrength = 0,
    this.scalpScore = 0,
  });

  final double confidence;
  final double expectedRr;
  final double momentumScore;
  final double volatilityScore;
  final double whalePressure;
  final double trendStrength;
  final double scalpScore;

  factory OpportunityScoreModel.fromJson(Map<String, dynamic> json) {
    return OpportunityScoreModel(
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      expectedRr: (json['expected_rr'] as num?)?.toDouble() ?? 0,
      momentumScore: (json['momentum_score'] as num?)?.toDouble() ?? 0,
      volatilityScore: (json['volatility_score'] as num?)?.toDouble() ?? 0,
      whalePressure: (json['whale_pressure'] as num?)?.toDouble() ?? 0,
      trendStrength: (json['trend_strength'] as num?)?.toDouble() ?? 0,
      scalpScore: (json['scalp_score'] as num?)?.toDouble() ?? 0,
    );
  }
}

class MarketRegimeSnapshotModel {
  const MarketRegimeSnapshotModel({
    this.state = 'RANGING',
    this.confidence = 0,
    this.summary = '',
  });

  final String state;
  final double confidence;
  final String summary;

  factory MarketRegimeSnapshotModel.fromJson(Map<String, dynamic> json) {
    return MarketRegimeSnapshotModel(
      state: json['state'] as String? ?? 'RANGING',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0,
      summary: json['summary'] as String? ?? '',
    );
  }
}

class ChartGuidePointModel {
  const ChartGuidePointModel({
    required this.label,
    required this.price,
  });

  final String label;
  final double price;

  factory ChartGuidePointModel.fromJson(Map<String, dynamic> json) {
    return ChartGuidePointModel(
      label: json['label'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0,
    );
  }
}

class ChartExecutionGuideModel {
  const ChartExecutionGuideModel({
    this.side = 'BUY',
    this.entryLow = 0,
    this.entryHigh = 0,
    this.stopLoss = 0,
    this.tp1 = 0,
    this.tp2 = 0,
    this.trailingStopPath = const <ChartGuidePointModel>[],
    this.riskReward = 0,
    this.riskPct = 0,
    this.rewardPct = 0,
  });

  final String side;
  final double entryLow;
  final double entryHigh;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final List<ChartGuidePointModel> trailingStopPath;
  final double riskReward;
  final double riskPct;
  final double rewardPct;

  factory ChartExecutionGuideModel.fromJson(Map<String, dynamic> json) {
    final entryZone = Map<String, dynamic>.from(
      json['entry_zone'] as Map? ?? const <String, dynamic>{},
    );
    final riskVisualization = Map<String, dynamic>.from(
      json['risk_visualization'] as Map? ?? const <String, dynamic>{},
    );
    return ChartExecutionGuideModel(
      side: json['side'] as String? ?? 'BUY',
      entryLow: (entryZone['low'] as num?)?.toDouble() ?? 0,
      entryHigh: (entryZone['high'] as num?)?.toDouble() ?? 0,
      stopLoss: (json['stop_loss'] as num?)?.toDouble() ?? 0,
      tp1: (json['tp1'] as num?)?.toDouble() ?? 0,
      tp2: (json['tp2'] as num?)?.toDouble() ?? 0,
      trailingStopPath: (json['trailing_stop_path'] as List<dynamic>? ??
              const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              ChartGuidePointModel.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      riskReward: (json['risk_reward'] as num?)?.toDouble() ?? 0,
      riskPct: (riskVisualization['risk_pct'] as num?)?.toDouble() ?? 0,
      rewardPct: (riskVisualization['reward_pct'] as num?)?.toDouble() ?? 0,
    );
  }
}

class StrategyMicroModel {
  const StrategyMicroModel({
    required this.name,
    required this.score,
    required this.state,
  });

  final String name;
  final double score;
  final String state;

  factory StrategyMicroModel.fromJson(Map<String, dynamic> json) {
    return StrategyMicroModel(
      name: json['name'] as String? ?? '',
      score: (json['score'] as num?)?.toDouble() ?? 0,
      state: json['state'] as String? ?? 'WATCH',
    );
  }
}

class StrategyStateModel {
  const StrategyStateModel({
    this.activeStrategy = 'ADAPTIVE_SCALP_ENGINE',
    this.activeTimeframe = '5m',
    this.learnsFromSuccessfulTrades = false,
    this.currentWinRate = 0,
    this.promotedStrategies = const <String>[],
    this.microStrategies = const <StrategyMicroModel>[],
    this.bestRegime = 'RANGING',
  });

  final String activeStrategy;
  final String activeTimeframe;
  final bool learnsFromSuccessfulTrades;
  final double currentWinRate;
  final List<String> promotedStrategies;
  final List<StrategyMicroModel> microStrategies;
  final String bestRegime;

  factory StrategyStateModel.fromJson(Map<String, dynamic> json) {
    return StrategyStateModel(
      activeStrategy:
          json['active_strategy'] as String? ?? 'ADAPTIVE_SCALP_ENGINE',
      activeTimeframe: json['active_timeframe'] as String? ?? '5m',
      learnsFromSuccessfulTrades:
          json['learns_from_successful_trades'] as bool? ?? false,
      currentWinRate: (json['current_win_rate'] as num?)?.toDouble() ?? 0,
      promotedStrategies:
          (json['promoted_strategies'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(),
      microStrategies:
          (json['micro_strategies'] as List<dynamic>? ?? const <dynamic>[])
              .whereType<Map>()
              .map((item) =>
                  StrategyMicroModel.fromJson(Map<String, dynamic>.from(item)))
              .toList(),
      bestRegime: json['best_regime'] as String? ?? 'RANGING',
    );
  }
}

class AiFeedItemModel {
  const AiFeedItemModel({
    required this.title,
    required this.detail,
    required this.severity,
    required this.timestamp,
  });

  final String title;
  final String detail;
  final String severity;
  final DateTime timestamp;

  factory AiFeedItemModel.fromJson(Map<String, dynamic> json) {
    return AiFeedItemModel(
      title: json['title'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      severity: json['severity'] as String? ?? 'low',
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
    );
  }
}

class TrailingStopModel {
  const TrailingStopModel({
    this.mode = 'ATR_TRAIL',
    this.currentStop = 0,
    this.projectedStop = 0,
    this.path = const <ChartGuidePointModel>[],
  });

  final String mode;
  final double currentStop;
  final double projectedStop;
  final List<ChartGuidePointModel> path;

  factory TrailingStopModel.fromJson(Map<String, dynamic> json) {
    return TrailingStopModel(
      mode: json['mode'] as String? ?? 'ATR_TRAIL',
      currentStop: (json['current_stop'] as num?)?.toDouble() ?? 0,
      projectedStop: (json['projected_stop'] as num?)?.toDouble() ?? 0,
      path: (json['path'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              ChartGuidePointModel.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
    );
  }
}

class ConfidenceIntervalModel {
  const ConfidenceIntervalModel({
    required this.startTs,
    required this.endTs,
    required this.score,
    required this.zoneType,
  });

  final int startTs;
  final int endTs;
  final double score;
  final String zoneType;

  factory ConfidenceIntervalModel.fromJson(Map<String, dynamic> json) {
    return ConfidenceIntervalModel(
      startTs: (json['start_ts'] as num?)?.toInt() ?? 0,
      endTs: (json['end_ts'] as num?)?.toInt() ?? 0,
      score: (json['score'] as num?)?.toDouble() ?? 0,
      zoneType: json['zone_type'] as String? ?? 'SOFT_CONVICTION',
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
    this.potentialScore = 0,
    this.sparkline = const <double>[],
  });

  final String symbol;
  final double price;
  final double changePct;
  final double volumeRatio;
  final double volatilityPct;
  final double trendPct;
  final double quoteVolume;
  final String category;
  final double potentialScore;
  final List<double> sparkline;

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
      potentialScore: (json['potential_score'] as num?)?.toDouble() ?? 0,
      sparkline: (json['sparkline'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<num>()
          .map((item) => item.toDouble())
          .toList(),
    );
  }
}

Map<String, String> _markerStringMap(dynamic raw) {
  final source = raw as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{};
  return source.map((key, value) => MapEntry(key.toString(), value.toString()));
}

Map<String, dynamic> _markerDynamicMap(dynamic raw) {
  final source = raw as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{};
  return source.map((key, value) => MapEntry(key.toString(), value));
}

List<String> _markerStringList(dynamic raw) {
  return (raw as List<dynamic>? ?? const <dynamic>[])
      .map((item) => item.toString())
      .where((item) => item.trim().isNotEmpty)
      .toList();
}

class MarketUniverseModel {
  const MarketUniverseModel({
    required this.items,
    required this.topGainers,
    required this.topLosers,
    required this.highVolatility,
    required this.aiPicks,
  });

  final List<MarketUniverseEntryModel> items;
  final List<MarketUniverseEntryModel> topGainers;
  final List<MarketUniverseEntryModel> topLosers;
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
      topLosers: parseEntries(categories['top_losers']),
      highVolatility: parseEntries(categories['high_volatility']),
      aiPicks: parseEntries(categories['ai_picks']),
    );
  }
}

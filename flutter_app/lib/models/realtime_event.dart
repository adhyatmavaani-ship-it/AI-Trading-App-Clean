import 'market_chart.dart';

class RealtimeTradeUpdateModel {
  const RealtimeTradeUpdateModel({
    required this.timestamp,
    required this.userId,
    required this.symbol,
    required this.side,
    required this.status,
    required this.reason,
    this.tradeId,
    this.errorCode,
    this.details = const <String, dynamic>{},
  });

  final DateTime timestamp;
  final String userId;
  final String symbol;
  final String side;
  final String status;
  final String reason;
  final String? tradeId;
  final String? errorCode;
  final Map<String, dynamic> details;

  bool matchesUser(String userId) =>
      this.userId.isEmpty || this.userId == userId;

  factory RealtimeTradeUpdateModel.fromJson(Map<String, dynamic> json) {
    return RealtimeTradeUpdateModel(
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      userId: json['user_id'] as String? ?? '',
      tradeId: json['trade_id'] as String?,
      symbol: json['symbol'] as String? ?? '',
      side: json['side'] as String? ?? '',
      status: json['status'] as String? ?? '',
      reason: json['reason'] as String? ?? '',
      errorCode: json['error_code'] as String?,
      details: Map<String, dynamic>.from(
        json['details'] as Map? ?? const <String, dynamic>{},
      ),
    );
  }
}

class PortfolioRealtimeSummaryModel {
  const PortfolioRealtimeSummaryModel({
    required this.userId,
    required this.currentEquity,
    required this.peakEquity,
    required this.rollingDrawdown,
    required this.protectionState,
    required this.activeTrades,
    required this.realizedPnl,
    required this.unrealizedPnl,
    required this.grossExposure,
    required this.grossExposurePct,
    required this.openNotional,
  });

  final String userId;
  final double currentEquity;
  final double peakEquity;
  final double rollingDrawdown;
  final String protectionState;
  final int activeTrades;
  final double realizedPnl;
  final double unrealizedPnl;
  final double grossExposure;
  final double grossExposurePct;
  final double openNotional;

  bool matchesUser(String userId) =>
      this.userId.isEmpty || this.userId == userId;

  factory PortfolioRealtimeSummaryModel.fromJson(Map<String, dynamic> json) {
    return PortfolioRealtimeSummaryModel(
      userId: json['user_id'] as String? ?? '',
      currentEquity: (json['current_equity'] as num?)?.toDouble() ?? 0,
      peakEquity: (json['peak_equity'] as num?)?.toDouble() ?? 0,
      rollingDrawdown: (json['rolling_drawdown'] as num?)?.toDouble() ?? 0,
      protectionState: json['protection_state'] as String? ?? 'UNKNOWN',
      activeTrades: (json['active_trades'] as num?)?.toInt() ?? 0,
      realizedPnl: (json['realized_pnl'] as num?)?.toDouble() ?? 0,
      unrealizedPnl: (json['unrealized_pnl'] as num?)?.toDouble() ?? 0,
      grossExposure: (json['gross_exposure'] as num?)?.toDouble() ?? 0,
      grossExposurePct: (json['gross_exposure_pct'] as num?)?.toDouble() ?? 0,
      openNotional: (json['open_notional'] as num?)?.toDouble() ?? 0,
    );
  }
}

class RealtimePortfolioUpdateModel {
  const RealtimePortfolioUpdateModel({
    required this.timestamp,
    required this.reason,
    required this.summary,
  });

  final DateTime timestamp;
  final String reason;
  final PortfolioRealtimeSummaryModel summary;

  bool matchesUser(String userId) => summary.matchesUser(userId);

  factory RealtimePortfolioUpdateModel.fromJson(Map<String, dynamic> json) {
    return RealtimePortfolioUpdateModel(
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      reason: json['reason'] as String? ?? '',
      summary: PortfolioRealtimeSummaryModel.fromJson(
        Map<String, dynamic>.from(
          json['summary'] as Map? ?? const <String, dynamic>{},
        ),
      ),
    );
  }
}

class DashboardRealtimeSummaryModel {
  const DashboardRealtimeSummaryModel({
    required this.timestamp,
    required this.reason,
    required this.userId,
    required this.symbol,
    required this.activeTrades,
    required this.currentEquity,
    required this.rollingDrawdown,
    required this.protectionState,
    required this.degradedMode,
    required this.executionLatencyMs,
    required this.executionSlippageBps,
  });

  final DateTime timestamp;
  final String reason;
  final String userId;
  final String? symbol;
  final int activeTrades;
  final double currentEquity;
  final double rollingDrawdown;
  final String protectionState;
  final bool degradedMode;
  final double executionLatencyMs;
  final double executionSlippageBps;

  bool matchesUser(String userId) =>
      this.userId.isEmpty || this.userId == userId;

  factory DashboardRealtimeSummaryModel.fromJson(Map<String, dynamic> json) {
    final summary = Map<String, dynamic>.from(
      json['summary'] as Map? ?? const <String, dynamic>{},
    );
    return DashboardRealtimeSummaryModel(
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      reason: json['reason'] as String? ?? '',
      userId: summary['user_id'] as String? ?? '',
      symbol: summary['symbol'] as String?,
      activeTrades: (summary['active_trades'] as num?)?.toInt() ?? 0,
      currentEquity: (summary['current_equity'] as num?)?.toDouble() ?? 0,
      rollingDrawdown: (summary['rolling_drawdown'] as num?)?.toDouble() ?? 0,
      protectionState: summary['protection_state'] as String? ?? 'UNKNOWN',
      degradedMode: summary['degraded_mode'] as bool? ?? false,
      executionLatencyMs:
          (summary['execution_latency_ms'] as num?)?.toDouble() ?? 0,
      executionSlippageBps:
          (summary['execution_slippage_bps'] as num?)?.toDouble() ?? 0,
    );
  }
}

class AiTradeFeedRealtimeModel {
  const AiTradeFeedRealtimeModel({
    required this.symbol,
    required this.interval,
    required this.title,
    required this.detail,
    required this.severity,
    required this.marketRegime,
    required this.opportunity,
  });

  final String symbol;
  final String interval;
  final String title;
  final String detail;
  final String severity;
  final MarketRegimeSnapshotModel marketRegime;
  final OpportunityScoreModel opportunity;

  factory AiTradeFeedRealtimeModel.fromJson(Map<String, dynamic> json) {
    return AiTradeFeedRealtimeModel(
      symbol: json['symbol'] as String? ?? '',
      interval: json['interval'] as String? ?? '',
      title: json['title'] as String? ?? '',
      detail: json['detail'] as String? ?? '',
      severity: json['severity'] as String? ?? 'low',
      marketRegime: MarketRegimeSnapshotModel.fromJson(
        Map<String, dynamic>.from(
          json['market_regime'] as Map? ?? const <String, dynamic>{},
        ),
      ),
      opportunity: OpportunityScoreModel.fromJson(
        Map<String, dynamic>.from(
          json['opportunity'] as Map? ?? const <String, dynamic>{},
        ),
      ),
    );
  }
}

class ChartRealtimeSnapshotModel {
  const ChartRealtimeSnapshotModel({
    required this.symbol,
    required this.interval,
    required this.latestPrice,
    required this.changePct,
    required this.assistantModes,
    required this.activeAssistantMode,
    required this.opportunity,
    required this.marketRegime,
    required this.executionGuide,
    required this.strategyState,
    required this.aiFeed,
    required this.overlays,
    required this.markers,
    required this.trailingStop,
    required this.chartEngine,
    required this.renderHints,
    this.snapshotVersion = 0,
    this.stateHash = '',
    this.integrityChecksum = '',
    this.latestCandle,
  });

  final String symbol;
  final String interval;
  final double latestPrice;
  final double changePct;
  final List<String> assistantModes;
  final String activeAssistantMode;
  final OpportunityScoreModel opportunity;
  final MarketRegimeSnapshotModel marketRegime;
  final ChartExecutionGuideModel executionGuide;
  final StrategyStateModel strategyState;
  final List<AiFeedItemModel> aiFeed;
  final List<MarketOverlayModel> overlays;
  final List<TradeMarkerModel> markers;
  final TrailingStopModel trailingStop;
  final String chartEngine;
  final Map<String, dynamic> renderHints;
  final int snapshotVersion;
  final String stateHash;
  final String integrityChecksum;
  final MarketCandleModel? latestCandle;

  factory ChartRealtimeSnapshotModel.fromJson(Map<String, dynamic> json) {
    return ChartRealtimeSnapshotModel(
      symbol: json['symbol'] as String? ?? '',
      interval: json['interval'] as String? ?? '',
      latestPrice: (json['latest_price'] as num?)?.toDouble() ?? 0,
      changePct: (json['change_pct'] as num?)?.toDouble() ?? 0,
      assistantModes:
          (json['assistant_modes'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .where((item) => item.trim().isNotEmpty)
              .toList(),
      activeAssistantMode:
          json['active_assistant_mode'] as String? ?? 'ASSISTED',
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
      overlays: (json['overlays'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              MarketOverlayModel.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      markers: (json['markers'] as List<dynamic>? ?? const <dynamic>[])
          .whereType<Map>()
          .map((item) =>
              TradeMarkerModel.fromJson(Map<String, dynamic>.from(item)))
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
      snapshotVersion: (json['snapshot_version'] as num?)?.toInt() ?? 0,
      stateHash: json['state_hash'] as String? ?? '',
      integrityChecksum: json['integrity_checksum'] as String? ?? '',
      latestCandle: json['latest_candle'] is Map
          ? MarketCandleModel.fromJson(
              Map<String, dynamic>.from(json['latest_candle'] as Map),
            )
          : null,
    );
  }
}

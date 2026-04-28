class ActivityItemModel {
  const ActivityItemModel({
    required this.type,
    required this.status,
    required this.botState,
    required this.mode,
    required this.message,
    required this.timestamp,
    this.symbol,
    this.nextScan,
    this.confidence,
    this.action,
    this.intent,
    this.confidenceBuilding,
    this.readiness,
    this.reason,
    this.confidenceMeter,
    this.strictTradeScore,
    this.regime,
    this.confluenceBreakdown = const <String, String>{},
    this.confluenceAligned,
    this.confluenceTotal,
    this.riskFlags = const <String, dynamic>{},
    this.logicTags = const <String>[],
  });

  final String type;
  final String status;
  final String botState;
  final String mode;
  final String message;
  final DateTime timestamp;
  final String? symbol;
  final String? nextScan;
  final double? confidence;
  final String? action;
  final String? intent;
  final bool? confidenceBuilding;
  final double? readiness;
  final String? reason;
  final double? confidenceMeter;
  final double? strictTradeScore;
  final String? regime;
  final Map<String, String> confluenceBreakdown;
  final int? confluenceAligned;
  final int? confluenceTotal;
  final Map<String, dynamic> riskFlags;
  final List<String> logicTags;

  factory ActivityItemModel.fromJson(Map<String, dynamic> json) {
    return ActivityItemModel(
      type: json['type'] as String? ?? 'activity',
      status: json['status'] as String? ?? 'scanning',
      botState: json['bot_state'] as String? ?? 'WAITING',
      mode: json['mode'] as String? ?? 'LOW',
      message: json['message'] as String? ?? '',
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      symbol: json['symbol'] as String?,
      nextScan: json['next_scan'] as String?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      action: json['action'] as String?,
      intent: json['intent'] as String?,
      confidenceBuilding: json['confidence_building'] as bool?,
      readiness: (json['readiness'] as num?)?.toDouble(),
      reason: json['reason'] as String?,
      confidenceMeter: (json['confidence_meter'] as num?)?.toDouble(),
      strictTradeScore: (json['strict_trade_score'] as num?)?.toDouble(),
      regime: json['regime'] as String?,
      confluenceBreakdown: _stringMap(json['confluence_breakdown']),
      confluenceAligned: (json['confluence_aligned'] as num?)?.toInt(),
      confluenceTotal: (json['confluence_total'] as num?)?.toInt(),
      riskFlags: _dynamicMap(json['risk_flags']),
      logicTags: _stringList(json['logic_tags']),
    );
  }

  String get dedupeKey {
    return [
      timestamp.toIso8601String(),
      symbol ?? '',
      status,
      message,
    ].join('|');
  }
}

class ReadinessCardModel {
  const ReadinessCardModel({
    required this.symbol,
    required this.readiness,
    required this.status,
    required this.updatedAt,
    this.intent,
    this.confidenceBuilding,
    this.confidence,
    this.reason,
    this.message,
    this.regime,
    this.botState,
    this.confidenceMeter,
    this.strictTradeScore,
    this.confluenceBreakdown = const <String, String>{},
    this.confluenceAligned,
    this.confluenceTotal,
    this.riskFlags = const <String, dynamic>{},
    this.logicTags = const <String>[],
  });

  final String symbol;
  final double readiness;
  final String status;
  final DateTime updatedAt;
  final String? intent;
  final bool? confidenceBuilding;
  final double? confidence;
  final String? reason;
  final String? message;
  final String? regime;
  final String? botState;
  final double? confidenceMeter;
  final double? strictTradeScore;
  final Map<String, String> confluenceBreakdown;
  final int? confluenceAligned;
  final int? confluenceTotal;
  final Map<String, dynamic> riskFlags;
  final List<String> logicTags;

  factory ReadinessCardModel.fromJson(Map<String, dynamic> json) {
    return ReadinessCardModel(
      symbol: json['symbol'] as String? ?? '',
      readiness: (json['readiness'] as num?)?.toDouble() ?? 0,
      status: json['status'] as String? ?? 'scanning',
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      intent: json['intent'] as String?,
      confidenceBuilding: json['confidence_building'] as bool?,
      confidence: (json['confidence'] as num?)?.toDouble(),
      reason: json['reason'] as String?,
      message: json['message'] as String?,
      regime: json['regime'] as String?,
      botState: json['bot_state'] as String?,
      confidenceMeter: (json['confidence_meter'] as num?)?.toDouble(),
      strictTradeScore: (json['strict_trade_score'] as num?)?.toDouble(),
      confluenceBreakdown: _stringMap(json['confluence_breakdown']),
      confluenceAligned: (json['confluence_aligned'] as num?)?.toInt(),
      confluenceTotal: (json['confluence_total'] as num?)?.toInt(),
      riskFlags: _dynamicMap(json['risk_flags']),
      logicTags: _stringList(json['logic_tags']),
    );
  }

  factory ReadinessCardModel.fromActivity(ActivityItemModel item) {
    return ReadinessCardModel(
      symbol: item.symbol ?? '',
      readiness: item.readiness ?? 0,
      status: item.status,
      updatedAt: item.timestamp,
      intent: item.intent,
      confidenceBuilding: item.confidenceBuilding,
      confidence: item.confidence,
      reason: item.reason,
      message: item.message,
      regime: item.regime,
      botState: item.botState,
      confidenceMeter: item.confidenceMeter,
      strictTradeScore: item.strictTradeScore,
      confluenceBreakdown: item.confluenceBreakdown,
      confluenceAligned: item.confluenceAligned,
      confluenceTotal: item.confluenceTotal,
      riskFlags: item.riskFlags,
      logicTags: item.logicTags,
    );
  }
}

Map<String, String> _stringMap(dynamic raw) {
  final source = raw as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{};
  return source.map((key, value) => MapEntry(key.toString(), value.toString()));
}

Map<String, dynamic> _dynamicMap(dynamic raw) {
  final source = raw as Map<dynamic, dynamic>? ?? const <dynamic, dynamic>{};
  return source.map((key, value) => MapEntry(key.toString(), value));
}

List<String> _stringList(dynamic raw) {
  return (raw as List<dynamic>? ?? const <dynamic>[])
      .map((item) => item.toString())
      .where((item) => item.trim().isNotEmpty)
      .toList();
}

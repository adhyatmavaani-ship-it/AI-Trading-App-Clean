class TradeTimelineModel {
  const TradeTimelineModel({
    required this.tradeId,
    required this.currentStatus,
    required this.events,
  });

  final String tradeId;
  final String currentStatus;
  final List<TradeTimelineEventModel> events;

  factory TradeTimelineModel.fromJson(Map<String, dynamic> json) {
    final rawEvents = json['events'] as List<dynamic>? ?? const [];
    return TradeTimelineModel(
      tradeId: json['trade_id'] as String? ?? '',
      currentStatus: json['current_status'] as String? ?? 'UNKNOWN',
      events: rawEvents
          .map(
            (event) => TradeTimelineEventModel.fromJson(
              event as Map<String, dynamic>,
            ),
          )
          .toList(),
    );
  }
}

class TradeTimelineEventModel {
  const TradeTimelineEventModel({
    required this.timestamp,
    required this.stage,
    required this.status,
    required this.description,
    required this.metadata,
  });

  final DateTime timestamp;
  final String stage;
  final String status;
  final String description;
  final Map<String, dynamic> metadata;

  factory TradeTimelineEventModel.fromJson(Map<String, dynamic> json) {
    return TradeTimelineEventModel(
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
      stage: json['stage'] as String? ?? 'UNKNOWN',
      status: json['status'] as String? ?? 'UNKNOWN',
      description: json['description'] as String? ?? '',
      metadata: Map<String, dynamic>.from(
        json['metadata'] as Map? ?? const <String, dynamic>{},
      ),
    );
  }
}

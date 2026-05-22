class ProCopilotRequestModel {
  const ProCopilotRequestModel({
    required this.prompt,
    this.symbol = 'BTCUSDT',
    this.timeframe,
    this.sessionId,
  });

  final String prompt;
  final String symbol;
  final String? timeframe;
  final String? sessionId;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'prompt': prompt,
        'symbol': symbol,
        if (timeframe != null) 'timeframe': timeframe,
        if (sessionId != null) 'session_id': sessionId,
      };
}

class ProCopilotResponseModel {
  const ProCopilotResponseModel({
    required this.symbol,
    required this.timeframe,
    required this.sessionId,
    required this.answer,
    required this.facts,
    required this.confidence,
    required this.dataSource,
  });

  final String symbol;
  final String timeframe;
  final String sessionId;
  final String answer;
  final Map<String, dynamic> facts;
  final double confidence;
  final String dataSource;

  factory ProCopilotResponseModel.fromJson(Map<String, dynamic> json) {
    return ProCopilotResponseModel(
      symbol: json['symbol'] as String? ?? '',
      timeframe: json['timeframe'] as String? ?? '',
      sessionId: json['session_id'] as String? ?? '',
      answer: json['answer'] as String? ?? '',
      facts: _map(json['facts']),
      confidence: _double(json['confidence']),
      dataSource: json['data_source'] as String? ?? '',
    );
  }
}

class ProScannerCriterionModel {
  const ProScannerCriterionModel({
    required this.field,
    required this.operator,
    required this.value,
  });

  final String field;
  final String operator;
  final Object value;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'field': field,
        'operator': operator,
        'value': value,
      };
}

class ProScannerRunRequestModel {
  const ProScannerRunRequestModel({
    required this.criteria,
    this.symbols,
    this.timeframe = '1h',
    this.webhookUrl,
    this.limit = 30,
  });

  final List<ProScannerCriterionModel> criteria;
  final List<String>? symbols;
  final String timeframe;
  final String? webhookUrl;
  final int limit;

  Map<String, dynamic> toJson() => <String, dynamic>{
        if (symbols != null) 'symbols': symbols,
        'timeframe': timeframe,
        'criteria': criteria.map((item) => item.toJson()).toList(),
        if (webhookUrl != null) 'webhook_url': webhookUrl,
        'limit': limit,
      };
}

class ProScannerResponseModel {
  const ProScannerResponseModel({
    required this.timeframe,
    required this.matchCount,
    required this.matches,
    required this.notificationEvent,
  });

  final String timeframe;
  final int matchCount;
  final List<Map<String, dynamic>> matches;
  final Map<String, dynamic> notificationEvent;

  factory ProScannerResponseModel.fromJson(Map<String, dynamic> json) {
    return ProScannerResponseModel(
      timeframe: json['timeframe'] as String? ?? '',
      matchCount: (json['match_count'] as num?)?.toInt() ?? 0,
      matches: _listOfMaps(json['matches']),
      notificationEvent: _map(json['notification_event']),
    );
  }
}

class StrategyPublishRequestModel {
  const StrategyPublishRequestModel({
    required this.name,
    required this.evidenceType,
    required this.metrics,
    this.description = '',
    this.style = 'trend_following',
    this.markets = const <String>['CRYPTO'],
  });

  final String name;
  final String description;
  final String style;
  final List<String> markets;
  final String evidenceType;
  final Map<String, num> metrics;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'name': name,
        'description': description,
        'style': style,
        'markets': markets,
        'evidence_type': evidenceType,
        'metrics': metrics,
      };
}

class StrategyMarketplaceResponseModel {
  const StrategyMarketplaceResponseModel({
    required this.count,
    required this.items,
  });

  final int count;
  final List<Map<String, dynamic>> items;

  factory StrategyMarketplaceResponseModel.fromJson(Map<String, dynamic> json) {
    return StrategyMarketplaceResponseModel(
      count: (json['count'] as num?)?.toInt() ?? 0,
      items: _listOfMaps(json['items']),
    );
  }
}

class StrategyWeightsResponseModel {
  const StrategyWeightsResponseModel({
    required this.regime,
    required this.weights,
  });

  final String regime;
  final List<Map<String, dynamic>> weights;

  factory StrategyWeightsResponseModel.fromJson(Map<String, dynamic> json) {
    return StrategyWeightsResponseModel(
      regime: json['regime'] as String? ?? '',
      weights: _listOfMaps(json['weights']),
    );
  }
}

class JournalReportRequestModel {
  const JournalReportRequestModel({required this.trade});

  final Map<String, dynamic> trade;

  Map<String, dynamic> toJson() => <String, dynamic>{'trade': trade};
}

class JournalReportResponseModel {
  const JournalReportResponseModel({
    required this.symbol,
    required this.result,
    required this.pnl,
    required this.holdMinutes,
    required this.psychologyTags,
    required this.analysis,
    required this.snapshotImage,
  });

  final String symbol;
  final String result;
  final double pnl;
  final double holdMinutes;
  final List<String> psychologyTags;
  final String analysis;
  final Map<String, dynamic> snapshotImage;

  factory JournalReportResponseModel.fromJson(Map<String, dynamic> json) {
    return JournalReportResponseModel(
      symbol: json['symbol'] as String? ?? '',
      result: json['result'] as String? ?? '',
      pnl: _double(json['pnl']),
      holdMinutes: _double(json['hold_minutes']),
      psychologyTags: (json['psychology_tags'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(growable: false),
      analysis: json['analysis'] as String? ?? '',
      snapshotImage: _map(json['snapshot_image']),
    );
  }
}

double _double(dynamic value) => (value as num?)?.toDouble() ?? 0;

Map<String, dynamic> _map(dynamic value) {
  return Map<String, dynamic>.from(value as Map? ?? const <String, dynamic>{});
}

List<Map<String, dynamic>> _listOfMaps(dynamic value) {
  return (value as List<dynamic>? ?? const <dynamic>[])
      .map((item) => _map(item))
      .toList(growable: false);
}

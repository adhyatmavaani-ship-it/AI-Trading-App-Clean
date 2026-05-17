import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../features/risk_coach/models/risk_coach_models.dart';
import '../models/active_trade.dart';
import '../models/activity.dart';
import '../models/backtest_job.dart';
import '../models/batch.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/infrastructure_snapshot.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/portfolio_concentration.dart';
import '../models/public_dashboard.dart';
import '../models/signal.dart';
import '../models/system_diagnostics.dart';
import '../models/system_health.dart';
import '../models/trade_execution.dart';
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';
import 'api_exception.dart';
import 'backend_warmup_state.dart';
import 'constants.dart';
import 'error_mapper.dart';

class ApiClient {
  ApiClient({
    String? baseUrl,
    http.Client? httpClient,
  })  : _httpClient = httpClient ?? http.Client(),
        _baseUrl =
            _normalizeBaseUrl(baseUrl ?? AppConstants.defaultApiBaseUrl) {
    debugPrint('[API BASE URL] $_baseUrl');
    track('api_base_url_resolved', <String, dynamic>{'url': _baseUrl});
  }

  final http.Client _httpClient;
  final String _baseUrl;

  String get baseUrl => _baseUrl;

  static String _normalizeBaseUrl(String value) {
    return value.trim().replaceFirst(RegExp(r'/+$'), '');
  }

  void warmUpServer() {
    unawaited(
      getHealthStatus().then((_) {
        markBackendReady();
      }).catchError((_) {
        markBackendSlow();
      }),
    );
  }

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final payload = await _requestJson(
      'GET',
      path,
      queryParameters: queryParameters,
    );
    return _requireMap(payload, path: path);
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) async {
    final payload = await _requestJson(
      'POST',
      path,
      queryParameters: queryParameters,
      data: data,
    );
    return _requireMap(payload, path: path);
  }

  Future<Map<String, dynamic>> getHealthStatus() {
    return getJson('/v1/health');
  }

  Future<Map<String, dynamic>> getRootStatus() {
    return getJson('/v1/health');
  }

  Future<TradeExecutionResponseModel> executeTrade(
    TradeExecutionRequestModel request,
  ) async {
    final payload = await postJson(
      '/v1/trading/execute',
      data: request.toJson(),
    );
    return TradeExecutionResponseModel.fromJson(payload);
  }

  Future<TradeEvaluationModel> getTradeEvaluation(String symbol) async {
    final payload = await postJson('/v1/trading/evaluate/$symbol');
    return TradeEvaluationModel.fromJson(payload);
  }

  Future<List<SignalModel>> getSignals({int limit = 25}) async {
    final payload = await getJson(
      '/v1/signals/live',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireList(payload['items'], path: '/v1/signals/live.items');
    return items
        .map((item) => SignalModel.fromJson(_mapItem(item, '/v1/signals/live')))
        .toList();
  }

  Future<ActivityItemModel?> getLiveActivity() async {
    final payload = await getJson('/v1/activity/live');
    if (payload.isEmpty) {
      return null;
    }
    return ActivityItemModel.fromJson(payload);
  }

  Future<List<ActivityItemModel>> getActivityHistory({int limit = 25}) async {
    final payload = await getJson(
      '/v1/activity/history',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireList(payload['items'], path: '/v1/activity/history.items');
    return items
        .map(
          (item) => ActivityItemModel.fromJson(
            _mapItem(item, '/v1/activity/history'),
          ),
        )
        .toList();
  }

  Future<List<ReadinessCardModel>> getActivityReadiness({
    int limit = 8,
  }) async {
    final payload = await getJson(
      '/v1/activity/readiness',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireList(payload['items'], path: '/v1/activity/readiness.items');
    return items
        .map(
          (item) => ReadinessCardModel.fromJson(
            _mapItem(item, '/v1/activity/readiness'),
          ),
        )
        .toList();
  }

  Future<MarketChartModel> getMarketCandles({
    required String symbol,
    String interval = '5m',
    int limit = 96,
    String? userId,
  }) async {
    final payload = await getJson(
      '/v1/market/candles',
      queryParameters: <String, dynamic>{
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
        'user_id': userId ?? AppConstants.requiredUserId,
      },
    );
    return MarketChartModel.fromJson(payload);
  }

  Future<MarketUniverseModel> getMarketUniverse({int limit = 18}) async {
    final payload = await getJson(
      '/v1/market/universe',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    return MarketUniverseModel.fromJson(payload);
  }

  Future<MarketSummaryModel> getMarketSummary({int limit = 18}) async {
    final payload = await postJson(
      '/v1/market/summary',
      data: <String, dynamic>{'limit': limit},
    );
    return MarketSummaryModel.fromJson(payload);
  }

  Future<String> getAssistantMode() async {
    final payload = await getJson('/v1/market/assistant-mode');
    return payload['mode'] as String? ?? 'ASSISTED';
  }

  Future<String> setAssistantMode(String mode) async {
    final payload = await postJson(
      '/v1/market/assistant-mode',
      data: <String, dynamic>{'mode': mode},
    );
    return payload['mode'] as String? ?? mode;
  }

  Future<RiskCoachOhlcResponse> getRiskCoachOhlc({
    String symbol = 'BTCUSDT',
    String interval = '1m',
    int limit = 200,
  }) async {
    final payload = await getJson(
      '/v1/market/ohlc',
      queryParameters: <String, dynamic>{
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
      },
    );
    return RiskCoachOhlcResponse.fromJson(payload);
  }

  Future<RiskPlan> evaluateRiskCoachPlan({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) async {
    final payload = await postJson(
      '/v1/risk-coach/evaluate',
      data: <String, dynamic>{
        'account_equity': 10000,
        'risk_amount': 100,
        'entry': entry,
        'stop_loss': stopLoss,
        'take_profit': takeProfit,
        'confidence': 0.61,
        'reliability': 0.74,
      },
    );
    return RiskPlan.fromJson(payload);
  }

  Future<HeatmapZoneModel> getRiskCoachHeatmap({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) async {
    final payload = await postJson(
      '/v1/risk-coach/heatmap',
      data: <String, dynamic>{
        'account_equity': 10000,
        'risk_amount': 100,
        'entry': entry,
        'stop_loss': stopLoss,
        'take_profit': takeProfit,
        'confidence': 0.61,
        'reliability': 0.74,
      },
    );
    return HeatmapZoneModel.fromJson(
      _requireMap(payload['zone'], path: '/v1/risk-coach/heatmap.zone'),
    );
  }

  Future<RiskCoachTrade> createRiskCoachTrade({
    required double entry,
    required double stopLoss,
    required double takeProfit,
    required double pWin,
    required double reliability,
  }) async {
    final payload = await postJson(
      '/v1/risk-coach/trades',
      data: <String, dynamic>{
        'account_equity': 10000,
        'risk_amount': 100,
        'entry': entry,
        'stop_loss': stopLoss,
        'take_profit': takeProfit,
        'p_win': pWin,
        'reliability': reliability,
      },
    );
    return RiskCoachTrade.fromJson(
      _requireMap(payload['trade'], path: '/v1/risk-coach/trades.trade'),
    );
  }

  Future<RiskCoachTrade> patchRiskCoachTrade({
    required String tradeId,
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) async {
    final payload = await _patchJson(
      '/v1/risk-coach/trades/$tradeId',
      data: <String, dynamic>{
        if (entry != null) 'entry': entry,
        if (stopLoss != null) 'stop_loss': stopLoss,
        if (takeProfit != null) 'take_profit': takeProfit,
      },
    );
    return RiskCoachTrade.fromJson(
      _requireMap(
        payload['trade'],
        path: '/v1/risk-coach/trades/$tradeId.trade',
      ),
    );
  }

  Future<PostMortemReportModel> closeRiskCoachTrade({
    required String tradeId,
    required double exitPrice,
  }) async {
    final payload = await postJson(
      '/v1/risk-coach/trades/$tradeId/close',
      data: <String, dynamic>{'exit_price': exitPrice},
    );
    return PostMortemReportModel.fromJson(payload);
  }

  Future<Map<String, dynamic>> panicCloseRiskCoachTrades({
    List<String> tradeIds = const <String>[],
  }) {
    return postJson(
      '/v1/risk-coach/panic-close',
      data: <String, dynamic>{'trade_ids': tradeIds},
    );
  }

  Future<Map<String, dynamic>> getRiskProfile(String userId) {
    return getJson(
      '/v1/risk/profile',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
  }

  Future<Map<String, dynamic>> updateRiskProfile(
    String userId, {
    required String level,
  }) {
    return postJson(
      '/v1/risk/profile',
      queryParameters: <String, dynamic>{
        'user_id': userId,
        'level': level,
      },
    );
  }

  Future<Map<String, dynamic>> getEngineState(String userId) {
    return getJson(
      '/v1/engine/state',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
  }

  Future<Map<String, dynamic>> updateEngineState(
    String userId, {
    required bool enabled,
  }) {
    return postJson(
      '/v1/engine/state',
      queryParameters: <String, dynamic>{
        'user_id': userId,
        'enabled': enabled,
      },
    );
  }

  Future<Map<String, dynamic>> getAdminModelState() {
    return getJson('/v1/admin/model/state');
  }

  Future<Map<String, dynamic>> rollbackAdminModel() {
    return postJson('/v1/admin/model/rollback');
  }

  Future<Map<String, dynamic>> setAdminModelFreeze({
    required bool enabled,
  }) {
    return postJson(
      '/v1/admin/model/freeze',
      queryParameters: <String, dynamic>{'enabled': enabled},
    );
  }

  Future<SystemDiagnosticsModel> getExchangeDiagnostics({
    String sampleSymbol = 'BTCUSDT',
  }) async {
    final payload = await getJson(
      '/v1/diag/exchange',
      queryParameters: <String, dynamic>{'sample_symbol': sampleSymbol},
    );
    return SystemDiagnosticsModel.fromJson(payload);
  }

  Future<List<ActiveTradeModel>> getActiveTrades(String userId) async {
    final payload = await getJson(
      '/v1/trades/active',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    final items =
        _requireList(payload['items'], path: '/v1/trades/active.items');
    return items
        .map(
          (item) =>
              ActiveTradeModel.fromJson(_mapItem(item, '/v1/trades/active')),
        )
        .toList();
  }

  Future<Map<String, dynamic>> triggerMockPriceMove({
    required String symbol,
    required double change,
    String? userId,
    double volumeMultiplier = 3.0,
    bool runMonitor = true,
  }) {
    return postJson(
      '/v1/test/mock-price-move',
      data: <String, dynamic>{
        'symbol': symbol,
        'change': change,
        if (userId != null && userId.trim().isNotEmpty) 'user_id': userId,
        'volume_multiplier': volumeMultiplier,
        'run_monitor': runMonitor,
      },
    );
  }

  Future<List<BatchModel>> getBatches({int limit = 25}) async {
    final payload = await getJson(
      '/v1/vom/batches',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items = _requireList(payload['items'], path: '/v1/vom/batches.items');
    return items
        .map((item) => BatchModel.fromJson(_mapItem(item, '/v1/vom/batches')))
        .toList();
  }

  Future<BacktestJobStatusModel> runBacktest(
    BacktestRunRequestModel request,
  ) async {
    final payload = await postJson('/v1/backtest/run', data: request.toJson());
    return BacktestJobStatusModel.fromJson(payload);
  }

  Future<BacktestJobStatusModel> getBacktestStatus(String jobId) async {
    final payload = await getJson('/v1/backtest/status/$jobId');
    return BacktestJobStatusModel.fromJson(payload);
  }

  Future<BacktestJobStatusModel> compareBacktest(
    BacktestCompareRequestModel request,
  ) async {
    final payload = await postJson(
      '/v1/backtest/compare',
      data: request.toJson(),
    );
    return BacktestJobStatusModel.fromJson(payload);
  }

  Future<String> exportBacktestCsv(String jobId) {
    return _requestText('GET', '/v1/backtest/export/$jobId');
  }

  Future<UserPnLModel> getUserPnL(String userId) async {
    final payload = await getJson(
      '/v1/user/pnl',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return UserPnLModel.fromJson(payload);
  }

  Future<TradeTimelineModel> getTradeTimeline(String tradeId) async {
    final payload = await getJson('/v1/trade/$tradeId/timeline');
    return TradeTimelineModel.fromJson(payload);
  }

  Future<SystemHealthModel> getSystemHealth() async {
    final payload = await getJson('/v1/monitoring/system');
    return SystemHealthModel.fromJson(payload);
  }

  Future<InfrastructureSnapshotModel> getInfrastructureSnapshot() async {
    final payload = await getJson('/v1/monitoring/infrastructure/realtime');
    return InfrastructureSnapshotModel.fromJson(payload);
  }

  Future<PortfolioConcentrationHistoryModel> getConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async {
    final payload = await getJson(
      '/v1/monitoring/concentration',
      queryParameters: <String, dynamic>{
        'window': window,
        'limit': limit,
      },
    );
    return PortfolioConcentrationHistoryModel.fromJson(payload);
  }

  Future<ModelStabilityConcentrationHistoryModel>
      getModelStabilityConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async {
    final payload = await getJson(
      '/v1/monitoring/model-stability/concentration',
      queryParameters: <String, dynamic>{
        'window': window,
        'limit': limit,
      },
    );
    return ModelStabilityConcentrationHistoryModel.fromJson(payload);
  }

  Future<MetaDecisionModel> getMetaDecision(String tradeId) async {
    final payload = await getJson('/v1/meta/decision/$tradeId');
    return MetaDecisionModel.fromJson(payload);
  }

  Future<MetaAnalyticsModel> getMetaAnalytics() async {
    final payload = await getJson('/v1/meta/analytics');
    return MetaAnalyticsModel.fromJson(payload);
  }

  Future<PublicPerformanceModel> getPublicPerformance() async {
    final payload = await getJson('/v1/public/performance');
    return PublicPerformanceModel.fromJson(payload);
  }

  Future<List<PublicTradeModel>> getPublicTrades({int limit = 20}) async {
    final payload = await getJson(
      '/v1/public/trades',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireList(payload['items'], path: '/v1/public/trades.items');
    return items
        .map(
          (item) =>
              PublicTradeModel.fromJson(_mapItem(item, '/v1/public/trades')),
        )
        .toList();
  }

  Future<List<PublicDailyPointModel>> getPublicDaily({int limit = 90}) async {
    final payload = await getJson(
      '/v1/public/daily',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireList(payload['items'], path: '/v1/public/daily.items');
    return items
        .map(
          (item) => PublicDailyPointModel.fromJson(
              _mapItem(item, '/v1/public/daily')),
        )
        .toList();
  }

  Future<Map<String, dynamic>> _patchJson(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) async {
    final payload = await _requestJson(
      'PATCH',
      path,
      queryParameters: queryParameters,
      data: data,
    );
    return _requireMap(payload, path: path);
  }

  Future<Object?> _requestJson(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Object? data,
  }) async {
    final response = await _send(
      method,
      path,
      queryParameters: queryParameters,
      data: data,
    );
    if (response.body.trim().isEmpty) {
      return const <String, dynamic>{};
    }
    try {
      return jsonDecode(response.body);
    } on FormatException {
      throw ApiException(
        'Backend returned an invalid response format for $path.',
        code: 'invalid_response',
        method: method,
        uri: response.uri.toString(),
        details: <String, dynamic>{'body': response.body},
      );
    }
  }

  Future<String> _requestText(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Object? data,
  }) async {
    final response = await _send(
      method,
      path,
      queryParameters: queryParameters,
      data: data,
    );
    return response.body;
  }

  Future<_ApiRawResponse> _send(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Object? data,
  }) async {
    markBackendConnecting();
    ApiException? lastError;
    for (var attempt = 1;
        attempt <= AppConstants.requestRetryAttempts;
        attempt++) {
      if (attempt > 1) {
        markBackendRetrying();
        await Future<void>.delayed(AppConstants.requestRetryDelay);
      }
      try {
        final response = await _dispatch(
          method,
          path,
          queryParameters: queryParameters,
          data: data,
        );
        _throwForStatus(response, method: method);
        markBackendReady();
        return response;
      } on ApiException catch (error, stackTrace) {
        lastError = error;
        logError(error.toJson(), stackTrace: stackTrace);
        if (attempt >= AppConstants.requestRetryAttempts ||
            !_shouldRetry(error)) {
          markBackendSlow();
          rethrow;
        }
        if (attempt == 1) {
          markBackendWaking();
        } else {
          markBackendRetrying();
        }
        track(
          'api_retry',
          <String, dynamic>{
            'attempt': attempt,
            'method': method,
            'path': path,
            'code': error.code,
            'status_code': error.statusCode,
          },
        );
      }
    }
    markBackendSlow();
    throw lastError ??
        const ApiException(
          'Unexpected network failure. Please try again.',
          code: 'network_error',
        );
  }

  Future<_ApiRawResponse> _dispatch(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Object? data,
  }) async {
    final uri = _buildUri(path, queryParameters: queryParameters);
    final headers = await _buildHeaders();
    final body = data == null ? null : jsonEncode(data);
    final requestStartedAt = DateTime.now();
    _logRequest(method, uri, headers);
    http.Response response;
    try {
      response = await _sendHttpRequest(
        method,
        uri,
        headers: headers,
        body: body,
      ).timeout(AppConstants.requestTimeout);
    } on TimeoutException {
      _logFailure(method, uri, 'timeout', requestStartedAt);
      throw ApiException(
        'Request timed out while contacting the nginx proxy or trading backend.',
        code: 'timeout',
        method: method,
        uri: uri.toString(),
        retryable: true,
      );
    } on SocketException {
      _logFailure(method, uri, 'socket_error', requestStartedAt);
      throw ApiException(
        'No internet connection or the nginx endpoint is unreachable right now.',
        code: 'socket_error',
        method: method,
        uri: uri.toString(),
        retryable: true,
      );
    } on http.ClientException catch (error) {
      _logFailure(method, uri, 'network_error', requestStartedAt);
      throw ApiException(
        'Unable to reach the nginx proxy in front of the trading backend. Check mobile internet and try again.',
        code: 'network_error',
        method: method,
        uri: uri.toString(),
        retryable: true,
        details: <String, dynamic>{'error': error.message},
      );
    }

    final raw = _ApiRawResponse(
      uri: uri,
      statusCode: response.statusCode,
      body: response.body,
      headers: response.headers,
    );
    _logResponse(method, uri, raw.statusCode, requestStartedAt);
    return raw;
  }

  Future<http.Response> _sendHttpRequest(
    String method,
    Uri uri, {
    required Map<String, String> headers,
    String? body,
  }) {
    switch (method.toUpperCase()) {
      case 'GET':
        return _httpClient.get(uri, headers: headers);
      case 'POST':
        return _httpClient.post(uri, headers: headers, body: body);
      case 'PATCH':
        return _httpClient.patch(uri, headers: headers, body: body);
      default:
        throw ApiException(
          'Unsupported HTTP method $method.',
          code: 'invalid_request',
          method: method,
          uri: uri.toString(),
        );
    }
  }

  Uri _buildUri(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) {
    final base = Uri.parse(_baseUrl);
    final resolved = base.resolve(path.startsWith('/') ? path : '/$path');
    final query = <String, String>{};
    for (final entry in queryParameters?.entries ?? const Iterable.empty()) {
      final value = entry.value;
      if (value == null) {
        continue;
      }
      query[entry.key] = value.toString();
    }
    return resolved.replace(
      queryParameters: query.isEmpty ? null : query,
    );
  }

  Future<Map<String, String>> _buildHeaders() async {
    final apiKey = AppConstants.requiredApiKey.trim();
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      'X-Client-Platform': 'flutter',
      'X-App-Environment': const String.fromEnvironment(
        'APP_ENV',
        defaultValue: 'mobile',
      ),
    };
    if (apiKey.isNotEmpty) {
      headers['X-API-Key'] = apiKey;
    }
    debugPrint('[API AUTH] required_api_key');
    return headers;
  }

  bool _shouldRetry(ApiException error) {
    return error.retryable || error.isTimeout || error.isSocketError;
  }

  void _logRequest(String method, Uri uri, Map<String, String> headers) {
    debugPrint('[API REQUEST] $method $uri');
    final hasApiKey = (headers['X-API-Key'] ?? '').trim().isNotEmpty;
    debugPrint(
      '[API AUTH HEADER] X-API-Key=${hasApiKey ? 'present' : 'missing'}',
    );
  }

  void _logResponse(
    String method,
    Uri uri,
    int statusCode,
    DateTime startedAt,
  ) {
    debugPrint('[API RESPONSE] $method $uri');
    debugPrint('[API STATUS] $statusCode');
    debugPrint(
      '[API LATENCY_MS] ${DateTime.now().difference(startedAt).inMilliseconds}',
    );
  }

  void _logFailure(
    String method,
    Uri uri,
    String status,
    DateTime startedAt,
  ) {
    debugPrint('[API RESPONSE] $method $uri');
    debugPrint('[API STATUS] $status');
    debugPrint(
      '[API LATENCY_MS] ${DateTime.now().difference(startedAt).inMilliseconds}',
    );
  }

  void _throwForStatus(
    _ApiRawResponse response, {
    required String method,
  }) {
    final statusCode = response.statusCode;
    if (statusCode >= 200 && statusCode < 300) {
      return;
    }
    final backendError = _extractBackendError(response.body);
    if (statusCode == 401) {
      debugPrint('[API AUTH RESPONSE] ${response.body}');
      throw ApiException(
        backendError?.message ??
            'Realtime connection is reconnecting. Paper trading and charts remain available.',
        statusCode: statusCode,
        code: backendError?.code ?? 'unauthorized',
        method: method,
        uri: response.uri.toString(),
        details:
            backendError?.details ?? <String, dynamic>{'body': response.body},
      );
    }
    if (statusCode == 403) {
      debugPrint('[API AUTH RESPONSE] ${response.body}');
      throw ApiException(
        backendError?.message ??
            'Live execution is temporarily locked. Paper trading and AI advisory mode are still available.',
        statusCode: statusCode,
        code: backendError?.code ?? 'forbidden',
        method: method,
        uri: response.uri.toString(),
        details:
            backendError?.details ?? <String, dynamic>{'body': response.body},
      );
    }
    if (statusCode == 451) {
      throw ApiException(
        'The requested market data is unavailable in this region or from this provider right now.',
        statusCode: statusCode,
        code: 'region_restricted',
        method: method,
        uri: response.uri.toString(),
      );
    }
    if (statusCode == 502 || statusCode == 503 || statusCode == 504) {
      throw ApiException(
        'Nginx could not reach the trading backend right now. Please retry in a moment.',
        statusCode: statusCode,
        code: 'server_unavailable',
        method: method,
        uri: response.uri.toString(),
        retryable: true,
        details: <String, dynamic>{'body': response.body},
      );
    }
    if (statusCode >= 500) {
      throw ApiException(
        backendError?.message ??
            'Trading backend is temporarily unavailable. Please retry in a moment.',
        statusCode: statusCode,
        code: backendError?.code ?? 'server_error',
        method: method,
        uri: response.uri.toString(),
        retryable: true,
        details:
            backendError?.details ?? <String, dynamic>{'body': response.body},
      );
    }
    throw ApiException(
      backendError?.message ??
          (statusCode >= 400 && statusCode < 500
              ? 'The request could not be completed. Please review your input and try again.'
              : 'The request failed. Please try again.'),
      statusCode: statusCode,
      code: backendError?.code ?? 'http_error',
      method: method,
      uri: response.uri.toString(),
      details:
          backendError?.details ?? <String, dynamic>{'body': response.body},
    );
  }

  _BackendError? _extractBackendError(String body) {
    if (body.trim().isEmpty) {
      return null;
    }
    try {
      final decoded = jsonDecode(body);
      if (decoded is! Map) {
        return null;
      }
      final root = Map<String, dynamic>.from(decoded);
      final detail = root['detail'];
      if (detail is Map) {
        final detailMap = Map<String, dynamic>.from(detail);
        return _BackendError(
          code: detailMap['error_code']?.toString(),
          message: detailMap['message']?.toString(),
          details: detailMap,
        );
      }
      if (root['message'] != null) {
        return _BackendError(
          code: root['error_code']?.toString(),
          message: root['message']?.toString(),
          details: root,
        );
      }
    } catch (_) {
      return null;
    }
    return null;
  }

  Map<String, dynamic> _requireMap(
    Object? value, {
    required String path,
  }) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }
    throw ApiException(
      'Backend returned an invalid response format for $path.',
      code: 'invalid_response',
      details: <String, dynamic>{'type': value.runtimeType.toString()},
    );
  }

  List<dynamic> _requireList(
    Object? value, {
    required String path,
  }) {
    if (value is List<dynamic>) {
      return value;
    }
    throw ApiException(
      'Backend returned an invalid response format for $path.',
      code: 'invalid_response',
      details: <String, dynamic>{'type': value.runtimeType.toString()},
    );
  }

  Map<String, dynamic> _mapItem(Object? value, String path) {
    return _requireMap(value, path: path);
  }
}

class _ApiRawResponse {
  const _ApiRawResponse({
    required this.uri,
    required this.statusCode,
    required this.body,
    required this.headers,
  });

  final Uri uri;
  final int statusCode;
  final String body;
  final Map<String, String> headers;
}

class _BackendError {
  const _BackendError({
    required this.code,
    required this.message,
    required this.details,
  });

  final String? code;
  final String? message;
  final Map<String, dynamic>? details;
}

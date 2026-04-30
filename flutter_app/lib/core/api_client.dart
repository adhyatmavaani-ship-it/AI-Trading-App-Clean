import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:dio/dio.dart';

import '../models/batch.dart';
import '../models/backtest_job.dart';
import '../models/activity.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/portfolio_concentration.dart';
import '../models/public_dashboard.dart';
import '../models/signal.dart';
import '../models/active_trade.dart';
import '../models/system_diagnostics.dart';
import '../models/system_health.dart';
import '../models/trade_execution.dart';
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';
import '../features/risk_coach/models/risk_coach_models.dart';
import 'api_exception.dart';
import 'auth_credentials_store.dart';
import 'backend_warmup_state.dart';
import 'constants.dart';
import 'retry.dart';

class ApiClient {
  ApiClient({
    required AuthCredentialsStore credentialsStore,
    Future<AuthSession?> Function(AuthSession currentSession)? tokenRefresher,
    String? baseUrl,
  })  : _credentialsStore = credentialsStore,
        _tokenRefresher = tokenRefresher,
        _dio = Dio(
          BaseOptions(
            baseUrl:
                _normalizeBaseUrl(baseUrl ?? AppConstants.defaultApiBaseUrl),
            connectTimeout: AppConstants.connectTimeout,
            receiveTimeout: AppConstants.receiveTimeout,
            sendTimeout: AppConstants.sendTimeout,
            headers: const <String, String>{
              'X-API-Key': AppConstants.defaultApiKey,
              'Accept': 'application/json',
            },
          ),
        ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          options.headers['X-Client-Platform'] = 'flutter';
          options.headers['X-App-Environment'] = const String.fromEnvironment(
            'APP_ENV',
            defaultValue: 'mobile',
          );
          if (AppConstants.defaultApiKey.trim().isEmpty) {
            options.headers.remove('X-API-Key');
          }
          final session = await _credentialsStore.loadSession();
          if (session != null && session.accessToken.trim().isNotEmpty) {
            _attachAuthHeaders(options, session);
          } else {
            _attachLocalDemoAuth(options);
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          if (_shouldRefresh(error)) {
            final refreshed = await _refreshSession();
            if (refreshed != null) {
              try {
                final retryResponse = await _retryRequest(
                  error.requestOptions,
                  refreshed,
                );
                handler.resolve(retryResponse);
                return;
              } on DioException catch (retryError) {
                handler.next(retryError);
                return;
              }
            }
          }

          handler.next(
            _normalizeDioException(error),
          );
        },
      ),
    );
    if (kDebugMode) {
      _dio.interceptors.add(
        LogInterceptor(
          requestBody: false,
          responseBody: false,
          requestHeader: false,
        ),
      );
    }
  }

  final Dio _dio;
  final AuthCredentialsStore _credentialsStore;
  final Future<AuthSession?> Function(AuthSession currentSession)?
      _tokenRefresher;

  String get baseUrl => _dio.options.baseUrl;

  static String _normalizeBaseUrl(String value) {
    return value.trim().replaceFirst(RegExp(r'\/+$'), '');
  }

  void _attachLocalDemoAuth(RequestOptions options) {
    final baseUri = Uri.tryParse(options.baseUrl);
    final demoApiKey = AppConstants.localDemoApiKey.trim();
    final isLocalhost = baseUri != null &&
        (baseUri.host == '127.0.0.1' || baseUri.host == 'localhost');
    if (!isLocalhost || demoApiKey.isEmpty) {
      return;
    }
    options.headers['X-API-Key'] = demoApiKey;
  }

  void warmUpServer() {
    unawaited(
      _sendWithWakeRetry<dynamic>('GET', '/health').then((_) {
        markBackendReady();
      }).catchError((_) {
        markBackendSlow();
      }),
    );
  }

  Future<Map<String, dynamic>> getHealthStatus() async {
    final response = await _sendWithWakeRetry<dynamic>('GET', '/health');
    return _requireMap(response.data, path: '/health');
  }

  Future<Map<String, dynamic>> getRootStatus() async {
    final response = await _sendWithWakeRetry<dynamic>('GET', '/');
    return _requireMap(response.data, path: '/');
  }

  Future<TradeExecutionResponseModel> executeTrade(
    TradeExecutionRequestModel request,
  ) async {
    final response = await _dio.post<dynamic>(
      '/v1/trading/execute',
      data: request.toJson(),
    );
    return TradeExecutionResponseModel.fromJson(
      _requireMap(response.data, path: '/v1/trading/execute'),
    );
  }

  Future<List<SignalModel>> getSignals({int limit = 25}) async {
    final response = await _getWithRetry(
      '/v1/signals/live',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/signals/live')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map((item) => SignalModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<ActivityItemModel?> getLiveActivity() async {
    final response = await _getWithRetry('/v1/activity/live');
    final data = _requireMap(response.data, path: '/v1/activity/live');
    if (data.isEmpty) {
      return null;
    }
    return ActivityItemModel.fromJson(data);
  }

  Future<List<ActivityItemModel>> getActivityHistory({int limit = 25}) async {
    final response = await _getWithRetry(
      '/v1/activity/history',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/activity/history')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map(
          (item) => ActivityItemModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<List<ReadinessCardModel>> getActivityReadiness({int limit = 8}) async {
    final response = await _getWithRetry(
      '/v1/activity/readiness',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/activity/readiness')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map(
          (item) => ReadinessCardModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<MarketChartModel> getMarketCandles({
    required String symbol,
    String interval = '5m',
    int limit = 96,
    String userId = 'alice',
  }) async {
    final response = await _getWithRetry(
      '/v1/market/candles',
      queryParameters: <String, dynamic>{
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
        'user_id': userId,
      },
    );
    return MarketChartModel.fromJson(
      _requireMap(response.data, path: '/v1/market/candles'),
    );
  }

  Future<MarketUniverseModel> getMarketUniverse({int limit = 18}) async {
    final response = await _getWithRetry(
      '/v1/market/universe',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    return MarketUniverseModel.fromJson(
      _requireMap(response.data, path: '/v1/market/universe'),
    );
  }

  Future<MarketSummaryModel> getMarketSummary({int limit = 18}) async {
    final response = await _sendWithWakeRetry<dynamic>(
      'POST',
      '/v1/market/summary',
      data: <String, dynamic>{'limit': limit},
    );
    return MarketSummaryModel.fromJson(
      _requireMap(response.data, path: '/v1/market/summary'),
    );
  }

  Future<RiskCoachOhlcResponse> getRiskCoachOhlc({
    String symbol = 'BTCUSDT',
    String interval = '1m',
    int limit = 200,
  }) async {
    final response = await _getWithRetry(
      '/v1/market/ohlc',
      queryParameters: <String, dynamic>{
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
      },
    );
    return RiskCoachOhlcResponse.fromJson(
      _requireMap(response.data, path: '/v1/market/ohlc'),
    );
  }

  Future<RiskPlan> evaluateRiskCoachPlan({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) async {
    final response = await _dio.post<dynamic>(
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
    return RiskPlan.fromJson(
      _requireMap(response.data, path: '/v1/risk-coach/evaluate'),
    );
  }

  Future<HeatmapZoneModel> getRiskCoachHeatmap({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) async {
    final response = await _dio.post<dynamic>(
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
    final body = _requireMap(response.data, path: '/v1/risk-coach/heatmap');
    return HeatmapZoneModel.fromJson(
      Map<String, dynamic>.from(body['zone'] as Map? ?? const <String, dynamic>{}),
    );
  }

  Future<RiskCoachTrade> createRiskCoachTrade({
    required double entry,
    required double stopLoss,
    required double takeProfit,
    required double pWin,
    required double reliability,
  }) async {
    final response = await _dio.post<dynamic>(
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
    final body = _requireMap(response.data, path: '/v1/risk-coach/trades');
    return RiskCoachTrade.fromJson(
      Map<String, dynamic>.from(body['trade'] as Map? ?? const <String, dynamic>{}),
    );
  }

  Future<RiskCoachTrade> patchRiskCoachTrade({
    required String tradeId,
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) async {
    final response = await _dio.patch<dynamic>(
      '/v1/risk-coach/trades/$tradeId',
      data: <String, dynamic>{
        if (entry != null) 'entry': entry,
        if (stopLoss != null) 'stop_loss': stopLoss,
        if (takeProfit != null) 'take_profit': takeProfit,
      },
    );
    final body = _requireMap(response.data, path: '/v1/risk-coach/trades/$tradeId');
    return RiskCoachTrade.fromJson(
      Map<String, dynamic>.from(body['trade'] as Map? ?? const <String, dynamic>{}),
    );
  }

  Future<PostMortemReportModel> closeRiskCoachTrade({
    required String tradeId,
    required double exitPrice,
  }) async {
    final response = await _dio.post<dynamic>(
      '/v1/risk-coach/trades/$tradeId/close',
      data: <String, dynamic>{'exit_price': exitPrice},
    );
    return PostMortemReportModel.fromJson(
      _requireMap(response.data, path: '/v1/risk-coach/trades/$tradeId/close'),
    );
  }

  Future<Map<String, dynamic>> panicCloseRiskCoachTrades({
    List<String> tradeIds = const <String>[],
  }) async {
    final response = await _dio.post<dynamic>(
      '/v1/risk-coach/panic-close',
      data: <String, dynamic>{'trade_ids': tradeIds},
    );
    return _requireMap(response.data, path: '/v1/risk-coach/panic-close');
  }

  Future<Map<String, dynamic>> getRiskProfile(String userId) async {
    final response = await _getWithRetry(
      '/v1/risk/profile',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return _requireMap(response.data, path: '/v1/risk/profile');
  }

  Future<Map<String, dynamic>> updateRiskProfile(
    String userId, {
    required String level,
  }) async {
    final response = await _dio.post<dynamic>(
      '/v1/risk/profile',
      queryParameters: <String, dynamic>{
        'user_id': userId,
        'level': level,
      },
    );
    return _requireMap(response.data, path: '/v1/risk/profile');
  }

  Future<Map<String, dynamic>> getEngineState(String userId) async {
    final response = await _getWithRetry(
      '/v1/engine/state',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return _requireMap(response.data, path: '/v1/engine/state');
  }

  Future<Map<String, dynamic>> updateEngineState(
    String userId, {
    required bool enabled,
  }) async {
    final response = await _dio.post<dynamic>(
      '/v1/engine/state',
      queryParameters: <String, dynamic>{
        'user_id': userId,
        'enabled': enabled,
      },
    );
    return _requireMap(response.data, path: '/v1/engine/state');
  }

  Future<Map<String, dynamic>> getAdminModelState() async {
    final response = await _getWithRetry('/v1/admin/model/state');
    return _requireMap(response.data, path: '/v1/admin/model/state');
  }

  Future<Map<String, dynamic>> rollbackAdminModel() async {
    final response = await _dio.post<dynamic>('/v1/admin/model/rollback');
    return _requireMap(response.data, path: '/v1/admin/model/rollback');
  }

  Future<Map<String, dynamic>> setAdminModelFreeze(
      {required bool enabled}) async {
    final response = await _dio.post<dynamic>(
      '/v1/admin/model/freeze',
      queryParameters: <String, dynamic>{'enabled': enabled},
    );
    return _requireMap(response.data, path: '/v1/admin/model/freeze');
  }

  Future<SystemDiagnosticsModel> getExchangeDiagnostics({
    String sampleSymbol = 'BTCUSDT',
  }) async {
    final response = await _getWithRetry(
      '/v1/diag/exchange',
      queryParameters: <String, dynamic>{'sample_symbol': sampleSymbol},
    );
    return SystemDiagnosticsModel.fromJson(
      _requireMap(response.data, path: '/v1/diag/exchange'),
    );
  }

  Future<List<ActiveTradeModel>> getActiveTrades(String userId) async {
    final response = await _getWithRetry(
      '/v1/trades/active',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    final items =
        _requireMap(response.data, path: '/v1/trades/active')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map(
          (item) => ActiveTradeModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<Map<String, dynamic>> triggerMockPriceMove({
    required String symbol,
    required double change,
    String? userId,
    double volumeMultiplier = 3.0,
    bool runMonitor = true,
  }) async {
    final response = await _dio.post<dynamic>(
      '/v1/test/mock-price-move',
      data: <String, dynamic>{
        'symbol': symbol,
        'change': change,
        if (userId != null && userId.trim().isNotEmpty) 'user_id': userId,
        'volume_multiplier': volumeMultiplier,
        'run_monitor': runMonitor,
      },
    );
    return _requireMap(response.data, path: '/v1/test/mock-price-move');
  }

  Future<List<BatchModel>> getBatches({int limit = 25}) async {
    final response = await _getWithRetry(
      '/v1/vom/batches',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/vom/batches')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map((item) => BatchModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<BacktestJobStatusModel> runBacktest(
    BacktestRunRequestModel request,
  ) async {
    final response = await _dio.post<dynamic>(
      '/v1/backtest/run',
      data: request.toJson(),
    );
    return BacktestJobStatusModel.fromJson(
      _requireMap(response.data, path: '/v1/backtest/run'),
    );
  }

  Future<BacktestJobStatusModel> getBacktestStatus(String jobId) async {
    final response = await _getWithRetry('/v1/backtest/status/$jobId');
    return BacktestJobStatusModel.fromJson(
      _requireMap(response.data, path: '/v1/backtest/status/$jobId'),
    );
  }

  Future<BacktestJobStatusModel> compareBacktest(
    BacktestCompareRequestModel request,
  ) async {
    final response = await _dio.post<dynamic>(
      '/v1/backtest/compare',
      data: request.toJson(),
    );
    return BacktestJobStatusModel.fromJson(
      _requireMap(response.data, path: '/v1/backtest/compare'),
    );
  }

  Future<String> exportBacktestCsv(String jobId) async {
    final response = await _dio.get<String>(
      '/v1/backtest/export/$jobId',
      options: Options(responseType: ResponseType.plain),
    );
    return response.data ?? '';
  }

  Future<UserPnLModel> getUserPnL(String userId) async {
    final response = await _getWithRetry(
      '/v1/user/pnl',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return UserPnLModel.fromJson(
      _requireMap(response.data, path: '/v1/user/pnl'),
    );
  }

  Future<TradeTimelineModel> getTradeTimeline(String tradeId) async {
    final response = await _getWithRetry('/v1/trade/$tradeId/timeline');
    return TradeTimelineModel.fromJson(
      _requireMap(response.data, path: '/v1/trade/$tradeId/timeline'),
    );
  }

  Future<SystemHealthModel> getSystemHealth() async {
    final response = await _getWithRetry('/v1/monitoring/system');
    return SystemHealthModel.fromJson(
      _requireMap(response.data, path: '/v1/monitoring/system'),
    );
  }

  Future<PortfolioConcentrationHistoryModel> getConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async {
    final response = await _getWithRetry(
      '/v1/monitoring/concentration',
      queryParameters: <String, dynamic>{
        'window': window,
        'limit': limit,
      },
    );
    return PortfolioConcentrationHistoryModel.fromJson(
      _requireMap(response.data, path: '/v1/monitoring/concentration'),
    );
  }

  Future<ModelStabilityConcentrationHistoryModel>
      getModelStabilityConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async {
    final response = await _getWithRetry(
      '/v1/monitoring/model-stability/concentration',
      queryParameters: <String, dynamic>{
        'window': window,
        'limit': limit,
      },
    );
    return ModelStabilityConcentrationHistoryModel.fromJson(
      _requireMap(
        response.data,
        path: '/v1/monitoring/model-stability/concentration',
      ),
    );
  }

  Future<MetaDecisionModel> getMetaDecision(String tradeId) async {
    final response = await _getWithRetry('/v1/meta/decision/$tradeId');
    return MetaDecisionModel.fromJson(
      _requireMap(response.data, path: '/v1/meta/decision/$tradeId'),
    );
  }

  Future<MetaAnalyticsModel> getMetaAnalytics() async {
    final response = await _getWithRetry('/v1/meta/analytics');
    return MetaAnalyticsModel.fromJson(
      _requireMap(response.data, path: '/v1/meta/analytics'),
    );
  }

  Future<PublicPerformanceModel> getPublicPerformance() async {
    final response = await _getWithRetry('/v1/public/performance');
    return PublicPerformanceModel.fromJson(
      _requireMap(response.data, path: '/v1/public/performance'),
    );
  }

  Future<List<PublicTradeModel>> getPublicTrades({int limit = 20}) async {
    final response = await _getWithRetry(
      '/v1/public/trades',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/public/trades')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map(
          (item) => PublicTradeModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<List<PublicDailyPointModel>> getPublicDaily({int limit = 90}) async {
    final response = await _getWithRetry(
      '/v1/public/daily',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items =
        _requireMap(response.data, path: '/v1/public/daily')['items']
            as List<dynamic>? ??
        const [];
    return items
        .map(
          (item) =>
              PublicDailyPointModel.fromJson(item as Map<String, dynamic>),
        )
        .toList();
  }

  Future<Response<dynamic>> _getWithRetry(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) {
    return _sendWithWakeRetry<dynamic>(
      'GET',
      path,
      queryParameters: queryParameters,
    );
  }

  Future<Response<T>> _sendWithWakeRetry<T>(
    String method,
    String path, {
    Map<String, dynamic>? queryParameters,
    Object? data,
  }) async {
    markBackendConnecting();
    try {
      final response = await _dio.request<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: Options(method: method),
      );
      markBackendReady();
      return response;
    } on DioException catch (error) {
      if (!_isWakeRetryCandidate(error)) {
        markBackendSlow();
        rethrow;
      }
      markBackendWaking();
      await Future<void>.delayed(const Duration(seconds: 3));
      try {
        final retryResponse = await retry<Response<T>>(
          () => _dio.request<T>(
            path,
            data: data,
            queryParameters: queryParameters,
            options: Options(method: method),
          ),
          shouldRetry: (error) =>
              error is DioException && _isWakeRetryCandidate(error),
        );
        markBackendReady();
        return retryResponse;
      } on DioException {
        markBackendSlow();
        rethrow;
      }
    }
  }

  Map<String, dynamic> _requireMap(
    Object? value, {
    required String path,
  }) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    throw ApiException(
      'Backend returned an invalid response format for $path.',
      code: 'invalid_response',
    );
  }

  DioException _normalizeDioException(DioException error) {
    final apiException = _toApiException(error);
    return DioException(
      requestOptions: error.requestOptions,
      response: error.response,
      type: error.type,
      error: apiException,
      message: apiException.message,
    );
  }

  ApiException _toApiException(DioException error) {
    final statusCode = error.response?.statusCode;
    final lowerLevelError = error.error;
    if (statusCode != null) {
      if (statusCode == 401) {
        return const ApiException(
          'Authentication failed. Check the production API key configured in the app.',
          statusCode: 401,
          code: 'unauthorized',
        );
      }
      if (statusCode == 403) {
        return const ApiException(
          'Access denied by the trading backend. Check API credentials or account permissions.',
          statusCode: 403,
          code: 'forbidden',
        );
      }
      if (statusCode >= 500) {
        return ApiException(
          'Trading backend is temporarily unavailable. Please retry in a moment.',
          statusCode: statusCode,
          code: 'server_error',
        );
      }
      if (statusCode == 451) {
        return const ApiException(
          'The requested market data is unavailable in this region or from this provider right now.',
          statusCode: 451,
          code: 'region_restricted',
        );
      }
      return ApiException(
        statusCode >= 400 && statusCode < 500
            ? 'The request could not be completed. Please review your input and try again.'
            : 'The request failed. Please try again.',
        statusCode: statusCode,
        code: 'http_error',
      );
    }
    if (lowerLevelError is SocketException) {
      return const ApiException(
        'No internet connection or the server is unreachable right now.',
        code: 'socket_error',
      );
    }
    if (error.type == DioExceptionType.connectionError) {
      return const ApiException(
        'Unable to reach the trading backend. Check mobile internet and try again.',
        code: 'socket_error',
      );
    }
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return const ApiException(
        'Request timed out while contacting the trading backend.',
        code: 'timeout',
      );
    }
    return const ApiException(
      'Unexpected network failure. Please try again.',
      code: 'network_error',
    );
  }

  bool _isWakeRetryCandidate(DioException error) {
    return error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout;
  }

  void _attachAuthHeaders(RequestOptions options, AuthSession session) {
    options.headers.remove('X-API-Key');
    options.headers.remove('Authorization');
    switch (session.scheme) {
      case AuthScheme.apiKey:
        options.headers['X-API-Key'] = session.accessToken;
        break;
      case AuthScheme.bearer:
        options.headers['Authorization'] = 'Bearer ${session.accessToken}';
        break;
    }
  }

  bool _shouldRefresh(DioException error) {
    return error.response?.statusCode == 401 &&
        error.requestOptions.extra['auth_retry'] != true &&
        _tokenRefresher != null;
  }

  Future<AuthSession?> _refreshSession() async {
    final tokenRefresher = _tokenRefresher;
    if (tokenRefresher == null) {
      return null;
    }
    final currentSession = await _credentialsStore.loadSession();
    if (currentSession == null || !currentSession.hasRefreshToken) {
      return null;
    }
    final refreshedSession = await tokenRefresher(currentSession);
    if (refreshedSession == null ||
        refreshedSession.accessToken.trim().isEmpty) {
      await _credentialsStore.clear();
      return null;
    }
    await _credentialsStore.saveSession(refreshedSession);
    return refreshedSession;
  }

  Future<Response<dynamic>> _retryRequest(
    RequestOptions requestOptions,
    AuthSession session,
  ) {
    final headers = Map<String, dynamic>.from(requestOptions.headers);
    final extra = Map<String, dynamic>.from(requestOptions.extra);
    extra['auth_retry'] = true;
    final requestCopy = RequestOptions(
      path: requestOptions.path,
      method: requestOptions.method,
      baseUrl: requestOptions.baseUrl,
      headers: headers,
      extra: extra,
    );
    _attachAuthHeaders(requestCopy, session);
    final retryOptions = Options(
      method: requestOptions.method,
      headers: requestCopy.headers,
      responseType: requestOptions.responseType,
      contentType: requestOptions.contentType,
      sendTimeout: requestOptions.sendTimeout,
      receiveTimeout: requestOptions.receiveTimeout,
      extra: extra,
      followRedirects: requestOptions.followRedirects,
      listFormat: requestOptions.listFormat,
      maxRedirects: requestOptions.maxRedirects,
      persistentConnection: requestOptions.persistentConnection,
      receiveDataWhenStatusError: requestOptions.receiveDataWhenStatusError,
      requestEncoder: requestOptions.requestEncoder,
      responseDecoder: requestOptions.responseDecoder,
      validateStatus: requestOptions.validateStatus,
    );

    return _dio.request<dynamic>(
      requestOptions.path,
      data: requestOptions.data,
      queryParameters: requestOptions.queryParameters,
      options: retryOptions,
      cancelToken: requestOptions.cancelToken,
    );
  }
}

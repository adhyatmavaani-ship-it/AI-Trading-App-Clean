import 'dart:async';

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
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';
import 'auth_credentials_store.dart';
import 'backend_warmup_state.dart';
import 'constants.dart';

class ApiClient {
  ApiClient({
    required AuthCredentialsStore credentialsStore,
    Future<AuthSession?> Function(AuthSession currentSession)? tokenRefresher,
    String? baseUrl,
  })  : _credentialsStore = credentialsStore,
        _tokenRefresher = tokenRefresher,
        _dio = Dio(
          BaseOptions(
            baseUrl: baseUrl ?? AppConstants.defaultApiBaseUrl,
            connectTimeout: AppConstants.requestTimeout,
            receiveTimeout: AppConstants.requestTimeout,
            sendTimeout: AppConstants.requestTimeout,
            headers: const <String, String>{
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
            DioException(
              requestOptions: error.requestOptions,
              response: error.response,
              type: error.type,
              error: _buildReadableError(error),
              message: _buildReadableError(error),
            ),
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

  void _attachLocalDemoAuth(RequestOptions options) {
    final baseUri = Uri.tryParse(options.baseUrl);
    final demoApiKey = AppConstants.localDemoApiKey.trim();
    final isLocalhost = baseUri != null &&
        (baseUri.host == '127.0.0.1' ||
            baseUri.host == 'localhost');
    if (!isLocalhost || demoApiKey.isEmpty) {
      return;
    }
    options.headers['X-API-Key'] = demoApiKey;
  }

  void warmUpServer() {
    unawaited(
      _dio.get<dynamic>('/health/ping').then((_) {
        markBackendReady();
      }).catchError((_) {
        if (backendWarmupState.value != BackendWarmupState.ready) {
          markBackendWaking();
        }
      }),
    );
  }

  Future<List<SignalModel>> getSignals({int limit = 25}) async {
    final response = await _getWithRetry(
      '/v1/signals/live',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items = response.data['items'] as List<dynamic>? ?? const [];
    return items
        .map((item) => SignalModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<ActivityItemModel?> getLiveActivity() async {
    final response = await _getWithRetry('/v1/activity/live');
    final data = response.data as Map<String, dynamic>;
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
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
    return MarketChartModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MarketUniverseModel> getMarketUniverse({int limit = 18}) async {
    final response = await _getWithRetry(
      '/v1/market/universe',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    return MarketUniverseModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MarketSummaryModel> getMarketSummary({int limit = 18}) async {
    final response = await _sendWithWakeRetry<dynamic>(
      'POST',
      '/v1/market/summary',
      data: <String, dynamic>{'limit': limit},
    );
    return MarketSummaryModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> getRiskProfile(String userId) async {
    final response = await _getWithRetry(
      '/v1/risk/profile',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
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
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getEngineState(String userId) async {
    final response = await _getWithRetry(
      '/v1/engine/state',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
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
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getAdminModelState() async {
    final response = await _getWithRetry('/v1/admin/model/state');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> rollbackAdminModel() async {
    final response = await _dio.post<dynamic>('/v1/admin/model/rollback');
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> setAdminModelFreeze({required bool enabled}) async {
    final response = await _dio.post<dynamic>(
      '/v1/admin/model/freeze',
      queryParameters: <String, dynamic>{'enabled': enabled},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<SystemDiagnosticsModel> getExchangeDiagnostics({
    String sampleSymbol = 'BTCUSDT',
  }) async {
    final response = await _getWithRetry(
      '/v1/diag/exchange',
      queryParameters: <String, dynamic>{'sample_symbol': sampleSymbol},
    );
    return SystemDiagnosticsModel.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<List<ActiveTradeModel>> getActiveTrades(String userId) async {
    final response = await _getWithRetry(
      '/v1/trades/active',
      queryParameters: <String, dynamic>{'user_id': userId},
    );
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
    return response.data as Map<String, dynamic>;
  }

  Future<List<BatchModel>> getBatches({int limit = 25}) async {
    final response = await _getWithRetry(
      '/v1/vom/batches',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
      response.data as Map<String, dynamic>,
    );
  }

  Future<BacktestJobStatusModel> getBacktestStatus(String jobId) async {
    final response = await _getWithRetry('/v1/backtest/status/$jobId');
    return BacktestJobStatusModel.fromJson(
      response.data as Map<String, dynamic>,
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
      response.data as Map<String, dynamic>,
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
    return UserPnLModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<TradeTimelineModel> getTradeTimeline(String tradeId) async {
    final response = await _getWithRetry('/v1/trade/$tradeId/timeline');
    return TradeTimelineModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<SystemHealthModel> getSystemHealth() async {
    final response = await _getWithRetry('/v1/monitoring/system');
    return SystemHealthModel.fromJson(response.data as Map<String, dynamic>);
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
      response.data as Map<String, dynamic>,
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
      response.data as Map<String, dynamic>,
    );
  }

  Future<MetaDecisionModel> getMetaDecision(String tradeId) async {
    final response = await _getWithRetry('/v1/meta/decision/$tradeId');
    return MetaDecisionModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<MetaAnalyticsModel> getMetaAnalytics() async {
    final response = await _getWithRetry('/v1/meta/analytics');
    return MetaAnalyticsModel.fromJson(response.data as Map<String, dynamic>);
  }

  Future<PublicPerformanceModel> getPublicPerformance() async {
    final response = await _getWithRetry('/v1/public/performance');
    return PublicPerformanceModel.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  Future<List<PublicTradeModel>> getPublicTrades({int limit = 20}) async {
    final response = await _getWithRetry(
      '/v1/public/trades',
      queryParameters: <String, dynamic>{'limit': limit},
    );
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
    final items = response.data['items'] as List<dynamic>? ?? const [];
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
        rethrow;
      }
      markBackendWaking();
      await Future<void>.delayed(const Duration(seconds: 5));
      final retryResponse = await _dio.request<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: Options(method: method),
      );
      markBackendReady();
      return retryResponse;
    }
  }

  String _buildReadableError(DioException error) {
    final statusCode = error.response?.statusCode;
    final detail = error.response?.data;
    if (statusCode != null) {
      if (statusCode == 403) {
        return 'Access denied by the trading backend. Check API credentials or account permissions.';
      }
      if (statusCode == 451) {
        return 'The requested market data is unavailable in this region or from this provider right now.';
      }
      return 'Request failed ($statusCode): $detail';
    }
    if (error.type == DioExceptionType.connectionError) {
      if (backendWarmupState.value == BackendWarmupState.waking) {
        return 'Waking up AI Engine... The backend is resuming from cold start. Please wait a few seconds.';
      }
      return 'Unable to reach the trading backend. Check the deployed API URL and network access.';
    }
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      if (backendWarmupState.value == BackendWarmupState.waking) {
        return 'Waking up AI Engine... The backend is resuming from cold start. Please wait a few seconds.';
      }
      return 'The trading backend timed out after a wake retry. Please try again.';
    }
    return error.message ?? 'Unexpected network failure';
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

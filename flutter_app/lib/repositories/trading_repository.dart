import 'dart:async';

import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/websocket_service.dart';
import '../models/active_trade.dart';
import '../models/activity.dart';
import '../models/batch.dart';
import '../models/backtest_job.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/market_chart.dart';
import '../models/portfolio_concentration.dart';
import '../models/public_dashboard.dart';
import '../models/signal.dart';
import '../models/system_diagnostics.dart';
import '../models/system_health.dart';
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';

class TradingRepository {
  TradingRepository({
    required ApiClient apiClient,
    required WebSocketService webSocketService,
  })  : _apiClient = apiClient,
        _webSocketService = webSocketService;

  final ApiClient _apiClient;
  final WebSocketService _webSocketService;

  Future<List<SignalModel>> fetchSignals({int limit = 25}) {
    return _apiClient.getSignals(limit: limit);
  }

  Stream<SignalModel> watchSignals() {
    return _webSocketService.connectSignals();
  }

  Future<ActivityItemModel?> fetchLiveActivity() {
    return _apiClient.getLiveActivity();
  }

  Future<List<ActivityItemModel>> fetchActivityHistory({int limit = 25}) {
    return _apiClient.getActivityHistory(limit: limit);
  }

  Future<List<ReadinessCardModel>> fetchReadinessBoard({int limit = 8}) {
    return _apiClient.getActivityReadiness(limit: limit);
  }

  Future<MarketChartModel> fetchMarketCandles({
    required String symbol,
    String interval = '5m',
    int limit = 96,
    String userId = 'alice',
  }) {
    return _apiClient.getMarketCandles(
      symbol: symbol,
      interval: interval,
      limit: limit,
      userId: userId,
    );
  }

  Future<MarketUniverseModel> fetchMarketUniverse({int limit = 18}) {
    return _apiClient.getMarketUniverse(limit: limit);
  }

  Future<Map<String, dynamic>> fetchRiskProfile(String userId) {
    return _apiClient.getRiskProfile(userId);
  }

  Future<Map<String, dynamic>> updateRiskProfile(
    String userId, {
    required String level,
  }) {
    return _apiClient.updateRiskProfile(userId, level: level);
  }

  Future<Map<String, dynamic>> fetchEngineState(String userId) {
    return _apiClient.getEngineState(userId);
  }

  Future<Map<String, dynamic>> updateEngineState(
    String userId, {
    required bool enabled,
  }) {
    return _apiClient.updateEngineState(userId, enabled: enabled);
  }

  Future<SystemDiagnosticsModel> fetchExchangeDiagnostics({
    String sampleSymbol = 'BTCUSDT',
  }) {
    return _apiClient.getExchangeDiagnostics(sampleSymbol: sampleSymbol);
  }

  Stream<SystemDiagnosticsModel> watchExchangeDiagnostics({
    String sampleSymbol = 'BTCUSDT',
  }) async* {
    yield await fetchExchangeDiagnostics(sampleSymbol: sampleSymbol);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchExchangeDiagnostics(sampleSymbol: sampleSymbol);
    }
  }

  Future<List<ActiveTradeModel>> fetchActiveTrades(String userId) {
    return _apiClient.getActiveTrades(userId);
  }

  Future<Map<String, dynamic>> triggerMockPriceMove({
    required String symbol,
    required double change,
    String? userId,
    double volumeMultiplier = 3.0,
    bool runMonitor = true,
  }) {
    return _apiClient.triggerMockPriceMove(
      symbol: symbol,
      change: change,
      userId: userId,
      volumeMultiplier: volumeMultiplier,
      runMonitor: runMonitor,
    );
  }

  Stream<List<ActiveTradeModel>> watchActiveTrades(String userId) async* {
    yield await fetchActiveTrades(userId);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchActiveTrades(userId);
    }
  }

  Stream<ActivityItemModel> watchActivity() {
    return _webSocketService.connectActivity();
  }

  Stream<List<ActivityItemModel>> watchActivityHistory(
      {int limit = 25}) async* {
    yield await fetchActivityHistory(limit: limit);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchActivityHistory(limit: limit);
    }
  }

  Stream<List<ReadinessCardModel>> watchReadinessBoard({int limit = 8}) async* {
    yield await fetchReadinessBoard(limit: limit);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchReadinessBoard(limit: limit);
    }
  }

  Future<List<BatchModel>> fetchBatches({int limit = 25}) {
    return _apiClient.getBatches(limit: limit);
  }

  Future<BacktestJobStatusModel> runBacktest(
    BacktestRunRequestModel request,
  ) {
    return _apiClient.runBacktest(request);
  }

  Future<BacktestJobStatusModel> compareBacktest(
    BacktestCompareRequestModel request,
  ) {
    return _apiClient.compareBacktest(request);
  }

  Future<BacktestJobStatusModel> fetchBacktestStatus(String jobId) {
    return _apiClient.getBacktestStatus(jobId);
  }

  Future<String> exportBacktestCsv(String jobId) {
    return _apiClient.exportBacktestCsv(jobId);
  }

  Stream<BacktestJobStatusModel> watchBacktestStatus(String jobId) async* {
    while (true) {
      final status = await fetchBacktestStatus(jobId);
      yield status;
      if (status.isTerminal) {
        break;
      }
      await Future<void>.delayed(AppConstants.pollingInterval);
    }
  }

  Stream<List<BatchModel>> watchBatches({int limit = 25}) async* {
    yield await fetchBatches(limit: limit);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchBatches(limit: limit);
    }
  }

  Future<UserPnLModel> fetchUserPnL(String userId) {
    return _apiClient.getUserPnL(userId);
  }

  Stream<UserPnLModel> watchUserPnL(String userId) async* {
    yield await fetchUserPnL(userId);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchUserPnL(userId);
    }
  }

  Future<TradeTimelineModel> fetchTradeTimeline(String tradeId) {
    return _apiClient.getTradeTimeline(tradeId);
  }

  Future<SystemHealthModel> fetchSystemHealth() {
    return _apiClient.getSystemHealth();
  }

  Future<PortfolioConcentrationHistoryModel> fetchConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) {
    return _apiClient.getConcentrationHistory(window: window, limit: limit);
  }

  Future<ModelStabilityConcentrationHistoryModel>
      fetchModelStabilityConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) {
    return _apiClient.getModelStabilityConcentrationHistory(
      window: window,
      limit: limit,
    );
  }

  Future<MetaDecisionModel> fetchMetaDecision(String tradeId) {
    return _apiClient.getMetaDecision(tradeId);
  }

  Future<MetaAnalyticsModel> fetchMetaAnalytics() {
    return _apiClient.getMetaAnalytics();
  }

  Future<PublicPerformanceModel> fetchPublicPerformance() {
    return _apiClient.getPublicPerformance();
  }

  Future<List<PublicTradeModel>> fetchPublicTrades({int limit = 20}) {
    return _apiClient.getPublicTrades(limit: limit);
  }

  Future<List<PublicDailyPointModel>> fetchPublicDaily({int limit = 90}) {
    return _apiClient.getPublicDaily(limit: limit);
  }

  Future<TrustDashboardModel> fetchTrustDashboard({
    int tradeLimit = 12,
    int dailyLimit = 30,
  }) async {
    final performance = await fetchPublicPerformance();
    final trades = await fetchPublicTrades(limit: tradeLimit);
    final daily = await fetchPublicDaily(limit: dailyLimit);
    return TrustDashboardModel(
      performance: performance,
      trades: trades,
      daily: daily,
    );
  }

  Stream<MetaAnalyticsModel> watchMetaAnalytics() async* {
    yield await fetchMetaAnalytics();
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchMetaAnalytics();
    }
  }

  Stream<SystemHealthModel> watchSystemHealth() async* {
    yield await fetchSystemHealth();
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchSystemHealth();
    }
  }

  Stream<PortfolioConcentrationHistoryModel> watchConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async* {
    yield await fetchConcentrationHistory(window: window, limit: limit);
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchConcentrationHistory(window: window, limit: limit);
    }
  }

  Stream<ModelStabilityConcentrationHistoryModel>
      watchModelStabilityConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) async* {
    yield await fetchModelStabilityConcentrationHistory(
      window: window,
      limit: limit,
    );
    while (true) {
      await Future<void>.delayed(AppConstants.pollingInterval);
      yield await fetchModelStabilityConcentrationHistory(
        window: window,
        limit: limit,
      );
    }
  }
}

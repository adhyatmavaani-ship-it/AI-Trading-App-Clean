import 'dart:async';

import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/websocket_service.dart';
import '../models/batch.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/portfolio_concentration.dart';
import '../models/public_dashboard.dart';
import '../models/signal.dart';
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

  Future<List<BatchModel>> fetchBatches({int limit = 25}) {
    return _apiClient.getBatches(limit: limit);
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

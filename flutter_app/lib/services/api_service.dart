import '../core/api_client.dart';
import '../core/auth_credentials_store.dart';
import '../models/batch.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/portfolio_concentration.dart';
import '../models/signal.dart';
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';

class ApiService {
  ApiService({ApiClient? apiClient})
      : _apiClient = apiClient ??
            ApiClient(credentialsStore: AuthCredentialsStore());

  final ApiClient _apiClient;

  Future<List<SignalModel>> getSignals({int limit = 25}) {
    return _apiClient.getSignals(limit: limit);
  }

  Future<List<BatchModel>> getBatches({int limit = 25}) {
    return _apiClient.getBatches(limit: limit);
  }

  Future<UserPnLModel> getUserPnL(String userId) {
    return _apiClient.getUserPnL(userId);
  }

  Future<TradeTimelineModel> getTradeTimeline(String tradeId) {
    return _apiClient.getTradeTimeline(tradeId);
  }

  Future<MetaDecisionModel> getMetaDecision(String tradeId) {
    return _apiClient.getMetaDecision(tradeId);
  }

  Future<MetaAnalyticsModel> getMetaAnalytics() {
    return _apiClient.getMetaAnalytics();
  }

  Future<PortfolioConcentrationHistoryModel> getConcentrationHistory({
    String window = '24h',
    int limit = 24,
  }) {
    return _apiClient.getConcentrationHistory(window: window, limit: limit);
  }
}

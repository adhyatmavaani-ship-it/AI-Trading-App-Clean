import 'dart:async';

import '../core/api_client.dart';
import '../core/constants.dart';
import '../core/trading_updates_socket_service.dart';
import '../core/websocket_service.dart';
import '../models/active_trade.dart';
import '../models/activity.dart';
import '../models/batch.dart';
import '../models/backtest_job.dart';
import '../models/infrastructure_snapshot.dart';
import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/portfolio_concentration.dart';
import '../models/public_dashboard.dart';
import '../models/realtime_event.dart';
import '../models/signal.dart';
import '../models/system_diagnostics.dart';
import '../models/system_health.dart';
import '../models/trade_execution.dart';
import '../models/trade_timeline.dart';
import '../models/user_pnl.dart';
import '../features/risk_coach/models/risk_coach_models.dart';

class TradingRepository {
  TradingRepository({
    required ApiClient apiClient,
    required WebSocketService webSocketService,
    TradingUpdatesSocketService? tradingUpdatesSocketService,
  })  : _apiClient = apiClient,
        _webSocketService = webSocketService,
        _tradingUpdatesSocketService =
            tradingUpdatesSocketService ?? TradingUpdatesSocketService();

  final ApiClient _apiClient;
  final WebSocketService _webSocketService;
  final TradingUpdatesSocketService _tradingUpdatesSocketService;

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
    String? userId,
  }) {
    return _apiClient.getMarketCandles(
      symbol: symbol,
      interval: interval,
      limit: limit,
      userId: userId ?? AppConstants.requiredUserId,
    );
  }

  Future<void> prefetchMarketContext({
    required String symbol,
    required String interval,
    String? userId,
  }) async {
    final neighbors = _neighborIntervals(interval);
    if (neighbors.isEmpty) {
      return;
    }
    try {
      await Future.wait(
        neighbors.map(
          (neighbor) => _apiClient.getMarketCandles(
            symbol: symbol,
            interval: neighbor,
            limit: 96,
            userId: userId ?? AppConstants.requiredUserId,
          ),
        ),
        eagerError: false,
      );
    } catch (_) {
      // Prefetch is opportunistic; foreground chart fetch remains authoritative.
    }
  }

  Future<RiskCoachOhlcResponse> fetchRiskCoachOhlc() {
    return _apiClient.getRiskCoachOhlc();
  }

  Stream<RiskCoachStreamEvent> watchRiskCoachMarket() {
    return _webSocketService.connectRiskCoachMarket();
  }

  Future<RiskPlan> evaluateRiskCoachPlan({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) {
    return _apiClient.evaluateRiskCoachPlan(
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
    );
  }

  Future<HeatmapZoneModel> fetchRiskCoachHeatmap({
    required double entry,
    required double stopLoss,
    required double takeProfit,
  }) {
    return _apiClient.getRiskCoachHeatmap(
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
    );
  }

  Future<RiskCoachTrade> createRiskCoachTrade({
    required double entry,
    required double stopLoss,
    required double takeProfit,
    required double pWin,
    required double reliability,
  }) {
    return _apiClient.createRiskCoachTrade(
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      pWin: pWin,
      reliability: reliability,
    );
  }

  Future<RiskCoachTrade> patchRiskCoachTrade({
    required String tradeId,
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) {
    return _apiClient.patchRiskCoachTrade(
      tradeId: tradeId,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
    );
  }

  Future<PostMortemReportModel> closeRiskCoachTrade({
    required String tradeId,
    required double exitPrice,
  }) {
    return _apiClient.closeRiskCoachTrade(
      tradeId: tradeId,
      exitPrice: exitPrice,
    );
  }

  Future<Map<String, dynamic>> panicCloseRiskCoachTrades({
    List<String> tradeIds = const <String>[],
  }) {
    return _apiClient.panicCloseRiskCoachTrades(tradeIds: tradeIds);
  }

  Future<MarketUniverseModel> fetchMarketUniverse({int limit = 18}) {
    return _apiClient.getMarketUniverse(limit: limit);
  }

  Future<MarketSummaryModel> fetchMarketSummary({int limit = 18}) {
    return _apiClient.getMarketSummary(limit: limit);
  }

  Future<String> fetchAssistantMode() {
    return _apiClient.getAssistantMode();
  }

  Future<String> setAssistantMode(String mode) {
    return _apiClient.setAssistantMode(mode);
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

  Future<Map<String, dynamic>> fetchAdminModelState() {
    return _apiClient.getAdminModelState();
  }

  Future<Map<String, dynamic>> rollbackAdminModel() {
    return _apiClient.rollbackAdminModel();
  }

  Future<Map<String, dynamic>> setAdminModelFreeze({required bool enabled}) {
    return _apiClient.setAdminModelFreeze(enabled: enabled);
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
    final controller = StreamController<List<ActiveTradeModel>>();
    Timer? fallbackTimer;
    Timer? debounceTimer;
    StreamSubscription<RealtimeTradeUpdateModel>? tradeSubscription;
    List<ActiveTradeModel> latestTrades = const <ActiveTradeModel>[];
    bool refreshInFlight = false;

    Future<void> refresh() async {
      if (refreshInFlight) {
        return;
      }
      refreshInFlight = true;
      try {
        latestTrades = await fetchActiveTrades(userId);
        if (!controller.isClosed) {
          controller.add(latestTrades);
        }
      } catch (error, stackTrace) {
        if (!controller.isClosed) {
          if (latestTrades.isEmpty) {
            controller.addError(error, stackTrace);
          } else {
            controller.add(latestTrades);
          }
        }
      } finally {
        refreshInFlight = false;
      }
    }

    void scheduleRefresh() {
      debounceTimer?.cancel();
      debounceTimer = Timer(const Duration(milliseconds: 350), () {
        unawaited(refresh());
      });
    }

    unawaited(refresh());
    tradeSubscription = watchTradeUpdates(userId: userId).listen(
      (event) {
        if (event.status.toUpperCase() == 'REJECTED' && latestTrades.isEmpty) {
          return;
        }
        scheduleRefresh();
      },
      onError: (Object error, StackTrace stackTrace) {
        if (controller.isClosed) {
          return;
        }
        if (latestTrades.isEmpty) {
          controller.addError(error, stackTrace);
        } else {
          controller.add(latestTrades);
        }
      },
    );
    fallbackTimer = Timer.periodic(
      AppConstants.realtimeFallbackPollingInterval,
      (_) => unawaited(refresh()),
    );

    controller.onCancel = () async {
      fallbackTimer?.cancel();
      debounceTimer?.cancel();
      await tradeSubscription?.cancel();
    };
    yield* controller.stream;
  }

  Stream<ActivityItemModel> watchActivity() {
    return _webSocketService.connectActivity();
  }

  Stream<RealtimeTradeUpdateModel> watchTradeUpdates({String? userId}) {
    final targetUserId = userId?.trim();
    return _webSocketService.connectTradeUpdates().where(
          (event) => targetUserId == null || event.matchesUser(targetUserId),
        );
  }

  Stream<RealtimePortfolioUpdateModel> watchPortfolioUpdates({
    String? userId,
  }) {
    final targetUserId = userId?.trim();
    return _webSocketService.connectPortfolioUpdates().where(
          (event) => targetUserId == null || event.matchesUser(targetUserId),
        );
  }

  Stream<DashboardRealtimeSummaryModel> watchDashboardSummaries({
    String? userId,
  }) {
    final targetUserId = userId?.trim();
    return _webSocketService.connectDashboardSummaries().where(
          (event) => targetUserId == null || event.matchesUser(targetUserId),
        );
  }

  Stream<ChartRealtimeSnapshotModel> watchChartSnapshots({
    String? symbol,
  }) {
    final normalized = symbol?.trim().toUpperCase();
    return _webSocketService.connectChartSnapshots().where(
          (event) =>
              normalized == null || event.symbol.toUpperCase() == normalized,
        );
  }

  Stream<AiTradeFeedRealtimeModel> watchAiTradeFeed({
    String? symbol,
  }) {
    final normalized = symbol?.trim().toUpperCase();
    return _webSocketService.connectAiTradeFeed().where(
          (event) =>
              normalized == null || event.symbol.toUpperCase() == normalized,
        );
  }

  Stream<Map<String, dynamic>> watchRecoveryRequests() {
    return _webSocketService.connectEvents().where(
          (event) =>
              event['type'] == 'replay_response' &&
              event['recovery'] == 'snapshot_required',
        );
  }

  Stream<ChartOrderActionModel> watchChartOrderActions({String? symbol}) {
    final normalized = symbol?.trim();
    return _tradingUpdatesSocketService.connectChartOrderActions().where(
          (event) =>
              normalized == null ||
              normalized.isEmpty ||
              event.matchesSymbol(normalized),
        );
  }

  Stream<StrategyPerformanceUpdateModel> watchStrategyPerformanceUpdates() {
    return _tradingUpdatesSocketService.connectStrategyPerformanceUpdates();
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

  List<String> _neighborIntervals(String interval) {
    const ladder = <String>['1m', '3m', '5m', '15m', '1h'];
    final normalized = interval.trim().toLowerCase();
    final index = ladder.indexOf(normalized);
    if (index < 0) {
      return const <String>[];
    }
    final neighbors = <String>{};
    if (index > 0) {
      neighbors.add(ladder[index - 1]);
    }
    if (index < ladder.length - 1) {
      neighbors.add(ladder[index + 1]);
    }
    return neighbors.toList(growable: false);
  }

  Future<List<BatchModel>> fetchBatches({int limit = 25}) {
    return _apiClient.getBatches(limit: limit);
  }

  Future<TradeExecutionResponseModel> executeTrade(
    TradeExecutionRequestModel request,
  ) {
    return _apiClient.executeTrade(request);
  }

  Future<TradeEvaluationModel> fetchTradeEvaluation(String symbol) {
    return _apiClient.getTradeEvaluation(symbol);
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
    final controller = StreamController<UserPnLModel>();
    Timer? fallbackTimer;
    Timer? debounceTimer;
    StreamSubscription<RealtimePortfolioUpdateModel>? portfolioSubscription;
    StreamSubscription<RealtimeTradeUpdateModel>? tradeSubscription;
    UserPnLModel? latest;
    bool refreshInFlight = false;

    Future<void> refresh() async {
      if (refreshInFlight) {
        return;
      }
      refreshInFlight = true;
      try {
        latest = await fetchUserPnL(userId);
        if (!controller.isClosed && latest != null) {
          controller.add(latest!);
        }
      } catch (error, stackTrace) {
        if (!controller.isClosed) {
          controller.addError(error, stackTrace);
        }
      } finally {
        refreshInFlight = false;
      }
    }

    void scheduleRefresh() {
      debounceTimer?.cancel();
      debounceTimer = Timer(const Duration(milliseconds: 350), () {
        unawaited(refresh());
      });
    }

    unawaited(refresh());
    portfolioSubscription = watchPortfolioUpdates(userId: userId).listen(
      (event) {
        final current = latest;
        if (current == null) {
          scheduleRefresh();
          return;
        }
        final summary = event.summary;
        final startingEquity = current.startingEquity == 0
            ? summary.currentEquity
            : current.startingEquity;
        final absolutePnl = summary.currentEquity - startingEquity;
        latest = current.copyWith(
          currentEquity: summary.currentEquity,
          peakEquity: summary.peakEquity,
          rollingDrawdown: summary.rollingDrawdown,
          protectionState: summary.protectionState,
          activeTrades: summary.activeTrades,
          absolutePnl: absolutePnl,
          pnlPct: startingEquity == 0 ? 0 : absolutePnl / startingEquity,
          realizedPnl: summary.realizedPnl,
          unrealizedPnl: summary.unrealizedPnl,
          grossExposure: summary.grossExposure,
          openNotional: summary.openNotional,
        );
        if (!controller.isClosed && latest != null) {
          controller.add(latest!);
        }
      },
      onError: controller.addError,
    );
    tradeSubscription = watchTradeUpdates(userId: userId).listen(
      (event) {
        final status = event.status.toUpperCase();
        if (status == 'REJECTED') {
          return;
        }
        scheduleRefresh();
      },
      onError: controller.addError,
    );
    fallbackTimer = Timer.periodic(
      AppConstants.realtimeFallbackPollingInterval,
      (_) => unawaited(refresh()),
    );

    controller.onCancel = () async {
      fallbackTimer?.cancel();
      debounceTimer?.cancel();
      await portfolioSubscription?.cancel();
      await tradeSubscription?.cancel();
    };
    yield* controller.stream;
  }

  Future<TradeTimelineModel> fetchTradeTimeline(String tradeId) {
    return _apiClient.getTradeTimeline(tradeId);
  }

  Future<SystemHealthModel> fetchSystemHealth() {
    return _apiClient.getSystemHealth();
  }

  Future<InfrastructureSnapshotModel> fetchInfrastructureSnapshot() {
    return _apiClient.getInfrastructureSnapshot();
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

  Stream<InfrastructureSnapshotModel> watchInfrastructureSnapshot() async* {
    yield await fetchInfrastructureSnapshot();
    while (true) {
      await Future<void>.delayed(AppConstants.websocketIntegrityCheckInterval);
      yield await fetchInfrastructureSnapshot();
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

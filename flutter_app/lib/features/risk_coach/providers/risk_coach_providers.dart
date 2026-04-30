import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers/app_providers.dart';
import '../controllers/execution_controller.dart';
import '../controllers/signal_manager.dart';
import '../models/risk_coach_models.dart';


final riskCoachExecutionControllerProvider =
    StateNotifierProvider.autoDispose<ExecutionController, ExecutionDraft>((ref) {
  return ExecutionController(ref.watch(tradingRepositoryProvider));
});


class RiskCoachTerminalState {
  const RiskCoachTerminalState({
    required this.symbol,
    required this.interval,
    required this.candles,
    required this.source,
    required this.connectionState,
    required this.disclaimer,
    required this.heatmap,
    required this.riskPlan,
    required this.trade,
    required this.postMortem,
    required this.signalManager,
    required this.isLoading,
    required this.isOffline,
  });

  final String symbol;
  final String interval;
  final List<RiskCoachCandle> candles;
  final String source;
  final String connectionState;
  final String disclaimer;
  final HeatmapZoneModel? heatmap;
  final RiskPlan? riskPlan;
  final RiskCoachTrade? trade;
  final PostMortemReportModel? postMortem;
  final SignalManager signalManager;
  final bool isLoading;
  final bool isOffline;

  factory RiskCoachTerminalState.initial() {
    return RiskCoachTerminalState(
      symbol: 'BTCUSDT',
      interval: '1m',
      candles: const <RiskCoachCandle>[],
      source: 'bootstrap',
      connectionState: 'connecting',
      disclaimer: 'Educational only. Not financial advice. No guaranteed profits.',
      heatmap: null,
      riskPlan: null,
      trade: null,
      postMortem: null,
      signalManager: SignalManager(),
      isLoading: true,
      isOffline: false,
    );
  }

  RiskCoachTerminalState copyWith({
    String? symbol,
    String? interval,
    List<RiskCoachCandle>? candles,
    String? source,
    String? connectionState,
    String? disclaimer,
    HeatmapZoneModel? heatmap,
    RiskPlan? riskPlan,
    RiskCoachTrade? trade,
    PostMortemReportModel? postMortem,
    SignalManager? signalManager,
    bool? isLoading,
    bool? isOffline,
  }) {
    return RiskCoachTerminalState(
      symbol: symbol ?? this.symbol,
      interval: interval ?? this.interval,
      candles: candles ?? this.candles,
      source: source ?? this.source,
      connectionState: connectionState ?? this.connectionState,
      disclaimer: disclaimer ?? this.disclaimer,
      heatmap: heatmap ?? this.heatmap,
      riskPlan: riskPlan ?? this.riskPlan,
      trade: trade ?? this.trade,
      postMortem: postMortem ?? this.postMortem,
      signalManager: signalManager ?? this.signalManager,
      isLoading: isLoading ?? this.isLoading,
      isOffline: isOffline ?? this.isOffline,
    );
  }
}


class RiskCoachTerminalController extends StateNotifier<RiskCoachTerminalState> {
  RiskCoachTerminalController(this._ref) : super(RiskCoachTerminalState.initial()) {
    unawaited(_bootstrap());
  }

  final Ref _ref;
  StreamSubscription<RiskCoachStreamEvent>? _marketSubscription;

  Future<void> _bootstrap() async {
    final repository = _ref.read(tradingRepositoryProvider);
    try {
      final ohlc = await repository.fetchRiskCoachOhlc();
      final last = ohlc.candles.last.close;
      final plan = await repository.evaluateRiskCoachPlan(
        entry: last,
        stopLoss: last * 0.992,
        takeProfit: last * 1.018,
      );
      final heatmap = await repository.fetchRiskCoachHeatmap(
        entry: last,
        stopLoss: last * 0.992,
        takeProfit: last * 1.018,
      );
      state = state.copyWith(
        candles: ohlc.candles,
        source: ohlc.source,
        disclaimer: ohlc.educationalOnly,
        riskPlan: plan,
        heatmap: heatmap,
        connectionState: 'connected',
        isLoading: false,
      );
      await _marketSubscription?.cancel();
      _marketSubscription = repository.watchRiskCoachMarket().listen(
        _applyDelta,
        onError: (_) {
          state = state.copyWith(connectionState: 'offline', isOffline: true);
        },
      );
    } catch (_) {
      state = state.copyWith(connectionState: 'offline', isOffline: true, isLoading: false);
    }
  }

  void _applyDelta(RiskCoachStreamEvent event) {
    final next = List<RiskCoachCandle>.from(state.candles);
    if (next.isNotEmpty && next.last.timestampMs == event.data.timestampMs) {
      next[next.length - 1] = event.data;
    } else {
      next.add(event.data);
      if (next.length > 200) {
        next.removeAt(0);
      }
    }
    state = state.copyWith(candles: next, connectionState: 'connected', isOffline: false);
  }

  Future<void> createPracticeTrade() async {
    if (state.candles.isEmpty) {
      return;
    }
    final last = state.candles.last.close;
    final trade = await _ref.read(tradingRepositoryProvider).createRiskCoachTrade(
          entry: last,
          stopLoss: last * 0.992,
          takeProfit: last * 1.018,
          pWin: 0.61,
          reliability: 0.74,
        );
    final manager = SignalManager(
      markers: <RiskSignalMarker>[
        RiskSignalMarker(
          tradeId: trade.tradeId,
          timestampMs: state.candles.last.timestampMs,
          price: trade.entry,
          side: trade.side,
          kind: 'entry',
          isActive: true,
        ),
      ],
    );
    state = state.copyWith(trade: trade, signalManager: manager);
    _ref.read(riskCoachExecutionControllerProvider.notifier).bindTrade(trade);
  }

  Future<void> closeTrade() async {
    final trade = state.trade;
    if (trade == null || state.candles.isEmpty) {
      return;
    }
    final report = await _ref.read(tradingRepositoryProvider).closeRiskCoachTrade(
          tradeId: trade.tradeId,
          exitPrice: state.candles.last.close,
        );
    state = state.copyWith(postMortem: report, trade: report.trade);
    _ref.read(riskCoachExecutionControllerProvider.notifier).bindTrade(report.trade);
  }

  Future<void> panicClose() async {
    final trade = state.trade;
    if (trade == null) {
      return;
    }
    await _ref.read(tradingRepositoryProvider).panicCloseRiskCoachTrades(
          tradeIds: <String>[trade.tradeId],
        );
    await closeTrade();
  }

  @override
  void dispose() {
    unawaited(_marketSubscription?.cancel());
    super.dispose();
  }
}


final riskCoachTerminalProvider =
    StateNotifierProvider.autoDispose<RiskCoachTerminalController, RiskCoachTerminalState>((ref) {
  return RiskCoachTerminalController(ref);
});

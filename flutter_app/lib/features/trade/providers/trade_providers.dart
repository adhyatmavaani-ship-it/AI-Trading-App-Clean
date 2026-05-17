import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../core/error_mapper.dart';
import '../../../models/active_trade.dart';
import '../../../models/signal.dart';
import '../../../models/trade_execution.dart';
import '../../../models/trade_timeline.dart';
import '../../../providers/app_providers.dart';
import '../../market/providers/market_providers.dart';
import '../../pnl/providers/pnl_providers.dart';
import '../../signals/providers/signal_providers.dart';

final selectedTradeIdProvider = StateProvider<String?>((ref) => null);

final tradeTimelineProvider = FutureProvider.autoDispose
    .family<TradeTimelineModel, String>((ref, tradeId) {
  return ref.watch(tradingRepositoryProvider).fetchTradeTimeline(tradeId);
});

class TradeIntent {
  const TradeIntent({
    required this.symbol,
    this.side,
    this.signalId,
    this.confidence,
    this.strategy,
    this.reason,
    this.price,
    this.rejectionReason,
    this.lowConfidence = false,
  });

  final String symbol;
  final String? side;
  final String? signalId;
  final double? confidence;
  final String? strategy;
  final String? reason;
  final double? price;
  final String? rejectionReason;
  final bool lowConfidence;

  factory TradeIntent.fromSignal(SignalModel signal) {
    return TradeIntent(
      symbol: signal.symbol,
      side: signal.action.toUpperCase(),
      signalId: signal.signalId,
      confidence: signal.confidence,
      strategy: signal.strategy,
      reason: signal.decisionReason,
      price: signal.price,
      rejectionReason: signal.rejectionReason,
      lowConfidence: signal.lowConfidence,
    );
  }
}

final selectedTradeIntentProvider = StateProvider<TradeIntent?>((ref) => null);

class LocalPaperPosition {
  const LocalPaperPosition({
    required this.tradeId,
    required this.symbol,
    required this.side,
    required this.entry,
    required this.quantity,
    required this.notional,
    required this.stopLoss,
    required this.takeProfit,
    required this.openedAt,
    required this.reason,
    required this.currentPrice,
    required this.lastMarkedAt,
    this.marketDataSource = 'entry',
  });

  final String tradeId;
  final String symbol;
  final String side;
  final double entry;
  final double quantity;
  final double notional;
  final double stopLoss;
  final double takeProfit;
  final DateTime openedAt;
  final String reason;
  final double currentPrice;
  final DateTime lastMarkedAt;
  final String marketDataSource;

  double get unrealizedPnl {
    final direction = side == 'SELL' ? -1.0 : 1.0;
    return (currentPrice - entry) * quantity * direction;
  }

  double get simulatedPnl => unrealizedPnl;

  double get currentValue => notional + unrealizedPnl;

  double get pnlPct => notional <= 0 ? 0 : unrealizedPnl / notional;

  bool get takeProfitHit {
    if (side == 'SELL') {
      return currentPrice <= takeProfit;
    }
    return currentPrice >= takeProfit;
  }

  bool get stopLossHit {
    if (side == 'SELL') {
      return currentPrice >= stopLoss;
    }
    return currentPrice <= stopLoss;
  }

  LocalPaperPosition copyWith({
    double? currentPrice,
    DateTime? lastMarkedAt,
    String? marketDataSource,
  }) {
    return LocalPaperPosition(
      tradeId: tradeId,
      symbol: symbol,
      side: side,
      entry: entry,
      quantity: quantity,
      notional: notional,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      openedAt: openedAt,
      reason: reason,
      currentPrice: currentPrice ?? this.currentPrice,
      lastMarkedAt: lastMarkedAt ?? this.lastMarkedAt,
      marketDataSource: marketDataSource ?? this.marketDataSource,
    );
  }

  ActiveTradeModel toActiveTrade() {
    return ActiveTradeModel(
      tradeId: tradeId,
      symbol: symbol,
      side: side,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      executedQuantity: quantity,
      entryReason: reason,
      status: 'PAPER_OPEN',
      regime: 'LOCAL_PAPER',
      riskFraction: notional / 10000,
    );
  }
}

class LocalPaperPortfolioState {
  const LocalPaperPortfolioState({
    this.startingBalance = 10000,
    this.cashBalance = 10000,
    this.positions = const <LocalPaperPosition>[],
    this.realizedPnl = 0,
  });

  final double startingBalance;
  final double cashBalance;
  final List<LocalPaperPosition> positions;
  final double realizedPnl;

  double get openNotional => positions.fold<double>(
        0,
        (sum, item) => sum + item.notional,
      );

  double get unrealizedPnl => positions.fold<double>(
        0,
        (sum, item) => sum + item.simulatedPnl,
      );

  double get currentPositionValue => positions.fold<double>(
        0,
        (sum, item) => sum + item.currentValue,
      );

  double get equity => cashBalance + currentPositionValue;

  double get pnlPct =>
      startingBalance <= 0 ? 0 : ((equity - startingBalance) / startingBalance);

  LocalPaperPortfolioState copyWith({
    double? cashBalance,
    List<LocalPaperPosition>? positions,
    double? realizedPnl,
  }) {
    return LocalPaperPortfolioState(
      startingBalance: startingBalance,
      cashBalance: cashBalance ?? this.cashBalance,
      positions: positions ?? this.positions,
      realizedPnl: realizedPnl ?? this.realizedPnl,
    );
  }
}

class LocalPaperTradingController
    extends StateNotifier<LocalPaperPortfolioState> {
  LocalPaperTradingController() : super(const LocalPaperPortfolioState());

  LocalPaperPosition execute({
    required String symbol,
    required String side,
    required double notional,
    required double price,
    required String reason,
  }) {
    final safeNotional = notional.clamp(10, state.cashBalance).toDouble();
    final safePrice = (price > 0 ? price : 100.0).toDouble();
    final normalizedSide = side.toUpperCase() == 'SELL' ? 'SELL' : 'BUY';
    final stop =
        normalizedSide == 'SELL' ? safePrice * 1.015 : safePrice * 0.985;
    final takeProfit =
        normalizedSide == 'SELL' ? safePrice * 0.97 : safePrice * 1.03;
    final now = DateTime.now();
    final position = LocalPaperPosition(
      tradeId: 'paper-${DateTime.now().microsecondsSinceEpoch}',
      symbol: symbol,
      side: normalizedSide,
      entry: safePrice,
      quantity: safeNotional / safePrice,
      notional: safeNotional,
      stopLoss: stop,
      takeProfit: takeProfit,
      openedAt: now,
      reason: reason,
      currentPrice: safePrice,
      lastMarkedAt: now,
      marketDataSource: 'entry',
    );
    state = state.copyWith(
      cashBalance: state.cashBalance - safeNotional,
      positions: <LocalPaperPosition>[position, ...state.positions],
    );
    return position;
  }

  void markToMarket({
    required String symbol,
    required double price,
    required String source,
  }) {
    final safePrice = (price.isFinite && price > 0 ? price : 0).toDouble();
    if (safePrice <= 0 || state.positions.isEmpty) {
      return;
    }
    final normalizedSymbol = symbol.trim().toUpperCase();
    var changed = false;
    var nextCash = state.cashBalance;
    var nextRealized = state.realizedPnl;
    final nextPositions = <LocalPaperPosition>[];
    final now = DateTime.now();

    for (final position in state.positions) {
      if (position.symbol != normalizedSymbol) {
        nextPositions.add(position);
        continue;
      }
      if ((position.currentPrice - safePrice).abs() < 0.00000001 &&
          position.marketDataSource == source) {
        nextPositions.add(position);
        continue;
      }
      changed = true;
      final marked = position.copyWith(
        currentPrice: safePrice,
        lastMarkedAt: now,
        marketDataSource: source,
      );
      if (marked.takeProfitHit || marked.stopLossHit) {
        nextCash += marked.currentValue;
        nextRealized += marked.unrealizedPnl;
      } else {
        nextPositions.add(marked);
      }
    }

    if (!changed) {
      return;
    }
    state = state.copyWith(
      cashBalance: nextCash,
      positions: nextPositions,
      realizedPnl: nextRealized,
    );
  }

  void markMarketPrices(Map<String, double> prices, {required String source}) {
    for (final entry in prices.entries) {
      markToMarket(symbol: entry.key, price: entry.value, source: source);
    }
  }

  void close(String tradeId) {
    LocalPaperPosition? position;
    for (final item in state.positions) {
      if (item.tradeId == tradeId) {
        position = item;
        break;
      }
    }
    if (position == null) {
      return;
    }
    final remaining = state.positions
        .where((item) => item.tradeId != tradeId)
        .toList(growable: false);
    state = state.copyWith(
      cashBalance: state.cashBalance + position.currentValue,
      realizedPnl: state.realizedPnl + position.unrealizedPnl,
      positions: remaining,
    );
  }
}

final localPaperTradingProvider = StateNotifierProvider<
    LocalPaperTradingController, LocalPaperPortfolioState>(
  (ref) => LocalPaperTradingController(),
);

final resolvedTradeIntentProvider = Provider<TradeIntent?>((ref) {
  final selectedSymbol = ref.watch(selectedMarketSymbolProvider);
  final explicitIntent = ref.watch(selectedTradeIntentProvider);
  if (explicitIntent != null && explicitIntent.symbol == selectedSymbol) {
    return explicitIntent;
  }

  final signals = ref.watch(signalFeedProvider).items;
  for (final signal in signals) {
    if (signal.symbol == selectedSymbol) {
      return TradeIntent.fromSignal(signal);
    }
  }
  return null;
});

final tradeEvaluationProvider =
    StreamProvider.autoDispose<TradeEvaluationModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  final symbol = ref.watch(selectedMarketSymbolProvider);
  yield await repository.fetchTradeEvaluation(symbol);
  while (true) {
    await Future<void>.delayed(AppConstants.tradeEvaluationPollingInterval);
    yield await repository.fetchTradeEvaluation(symbol);
  }
});

class TradeExecutionState {
  const TradeExecutionState({
    this.side = 'BUY',
    this.amount = 100,
    this.isSubmitting = false,
    this.errorMessage,
    this.lastResponse,
  });

  final String side;
  final double amount;
  final bool isSubmitting;
  final String? errorMessage;
  final TradeExecutionResponseModel? lastResponse;

  TradeExecutionState copyWith({
    String? side,
    double? amount,
    bool? isSubmitting,
    String? errorMessage,
    bool clearError = false,
    TradeExecutionResponseModel? lastResponse,
    bool clearLastResponse = false,
  }) {
    return TradeExecutionState(
      side: side ?? this.side,
      amount: amount ?? this.amount,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      lastResponse:
          clearLastResponse ? null : (lastResponse ?? this.lastResponse),
    );
  }
}

class TradeExecutionController extends StateNotifier<TradeExecutionState> {
  TradeExecutionController(this._ref) : super(const TradeExecutionState());

  final Ref _ref;

  void applyIntent(TradeIntent? intent) {
    final nextSide = intent?.side;
    if (nextSide == null || nextSide == state.side) {
      return;
    }
    state = state.copyWith(
      side: nextSide,
      clearError: true,
    );
  }

  void setSide(String side) {
    state = state.copyWith(side: side.toUpperCase(), clearError: true);
  }

  void setAmount(double amount) {
    state = state.copyWith(amount: amount, clearError: true);
  }

  void clearFeedback() {
    state = state.copyWith(
      clearError: true,
      clearLastResponse: true,
    );
  }

  Future<TradeExecutionResponseModel?> execute({
    required String userId,
    required String symbol,
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
  }) async {
    final notional = state.amount;
    if (notional <= 0) {
      state = state.copyWith(
        errorMessage: 'Enter a valid trade amount before submitting.',
        clearLastResponse: true,
      );
      return null;
    }

    if (evaluation == null) {
      state = state.copyWith(
        errorMessage:
            'Waiting for backend trade approval. Let the symbol evaluation finish before submitting.',
        clearLastResponse: true,
      );
      return null;
    }

    if (!evaluation.allowTrade) {
      state = state.copyWith(
        errorMessage: evaluation.reason.isNotEmpty
            ? evaluation.reason
            : 'The backend meta and risk engines blocked this trade.',
        clearLastResponse: true,
      );
      return null;
    }

    if (evaluation.approvedSide != state.side) {
      state = state.copyWith(
        errorMessage:
            'Backend approved ${evaluation.approvedSide} for $symbol. Switch side to match the validated trade direction.',
        clearLastResponse: true,
      );
      return null;
    }

    state = state.copyWith(
      isSubmitting: true,
      clearError: true,
      clearLastResponse: true,
    );

    final request = TradeExecutionRequestModel(
      userId: userId,
      symbol: symbol,
      side: state.side,
      confidence: evaluation.confidenceScore,
      reason: evaluation.reason.isNotEmpty
          ? evaluation.reason
          : ((intent?.reason?.trim().isNotEmpty ?? false)
              ? intent!.reason!.trim()
              : 'Manual ${state.side} request submitted from the production trade terminal.'),
      requestedNotional: notional,
      expectedReturn: evaluation.inference.expectedReturn,
      expectedRisk: evaluation.inference.expectedRisk,
      signalId: intent?.signalId,
      strategy: evaluation.strategy.trim().isNotEmpty
          ? evaluation.strategy.trim()
          : ((intent?.strategy?.trim().isNotEmpty ?? false)
              ? intent!.strategy!.trim()
              : 'MANUAL_TERMINAL'),
      featureSnapshot: <String, double>{
        ...evaluation.snapshot.featureSnapshot,
        'mobile_terminal': 1.0,
        'manual_request': intent == null ? 1.0 : 0.0,
        'signal_confidence': evaluation.confidenceScore,
        'selected_price': evaluation.snapshot.price,
        'low_confidence_signal': intent?.lowConfidence == true ? 1.0 : 0.0,
        'ui_requested_notional': notional,
        'approved_alpha_score': evaluation.alphaScore,
        'approved_rollout_fraction': evaluation.rolloutCapitalFraction,
      },
    );

    try {
      final response =
          await _ref.read(tradingRepositoryProvider).executeTrade(request);
      _ref.invalidate(userPnLProvider(userId));
      _ref.invalidate(activeTradesProvider(userId));
      _ref.invalidate(initialSignalsProvider);
      _ref.invalidate(tradeEvaluationProvider);
      state = state.copyWith(
        isSubmitting: false,
        lastResponse: response,
        clearError: true,
      );
      return response;
    } catch (error) {
      state = state.copyWith(
        isSubmitting: false,
        errorMessage: ErrorMapper.map(
          error,
          fallback:
              'Trade execution failed. The backend rejected or could not process the order.',
        ),
      );
      return null;
    }
  }
}

final tradeExecutionControllerProvider =
    StateNotifierProvider<TradeExecutionController, TradeExecutionState>((ref) {
  final controller = TradeExecutionController(ref);
  ref.listen<TradeIntent?>(resolvedTradeIntentProvider, (previous, next) {
    controller.applyIntent(next);
  });
  return controller;
});

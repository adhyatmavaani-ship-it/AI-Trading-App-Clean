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

class LocalPaperClosedTrade {
  const LocalPaperClosedTrade({
    required this.tradeId,
    required this.symbol,
    required this.side,
    required this.entry,
    required this.exitPrice,
    required this.quantity,
    required this.realizedPnl,
    required this.riskReward,
    required this.result,
    required this.aiAnalysis,
    required this.lessonTags,
    required this.closedAt,
    this.acknowledgedLessons = const <String>{},
  });

  final String tradeId;
  final String symbol;
  final String side;
  final double entry;
  final double exitPrice;
  final double quantity;
  final double realizedPnl;
  final double riskReward;
  final String result;
  final String aiAnalysis;
  final List<String> lessonTags;
  final DateTime closedAt;
  final Set<String> acknowledgedLessons;

  bool get won => realizedPnl > 0;
  bool get acknowledged => acknowledgedLessons.isNotEmpty;

  LocalPaperClosedTrade copyWith({Set<String>? acknowledgedLessons}) {
    return LocalPaperClosedTrade(
      tradeId: tradeId,
      symbol: symbol,
      side: side,
      entry: entry,
      exitPrice: exitPrice,
      quantity: quantity,
      realizedPnl: realizedPnl,
      riskReward: riskReward,
      result: result,
      aiAnalysis: aiAnalysis,
      lessonTags: lessonTags,
      closedAt: closedAt,
      acknowledgedLessons: acknowledgedLessons ?? this.acknowledgedLessons,
    );
  }
}

class LocalPaperPortfolioState {
  const LocalPaperPortfolioState({
    this.startingBalance = 10000,
    this.cashBalance = 10000,
    this.positions = const <LocalPaperPosition>[],
    this.realizedPnl = 0,
    this.closedTrades = const <LocalPaperClosedTrade>[],
  });

  final double startingBalance;
  final double cashBalance;
  final List<LocalPaperPosition> positions;
  final double realizedPnl;
  final List<LocalPaperClosedTrade> closedTrades;

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

  int get closedTradeCount => closedTrades.length;

  int get winningTradeCount => closedTrades.where((trade) => trade.won).length;

  int get consecutiveLosses {
    var count = 0;
    for (final trade in closedTrades) {
      if (trade.won) {
        break;
      }
      count += 1;
    }
    return count;
  }

  double get winRate =>
      closedTradeCount == 0 ? 0 : winningTradeCount / closedTradeCount;

  double get averageRiskReward => closedTrades.isEmpty
      ? 0
      : closedTrades.fold<double>(
            0,
            (sum, trade) => sum + trade.riskReward,
          ) /
          closedTrades.length;

  bool get liveUnlocked =>
      closedTradeCount >= 10 && winRate > 0.45 && averageRiskReward >= 1.5;

  String get licenseStatus =>
      liveUnlocked ? 'Live Trade Ready' : 'Learning Mode';

  LocalPaperPortfolioState copyWith({
    double? cashBalance,
    List<LocalPaperPosition>? positions,
    double? realizedPnl,
    List<LocalPaperClosedTrade>? closedTrades,
  }) {
    return LocalPaperPortfolioState(
      startingBalance: startingBalance,
      cashBalance: cashBalance ?? this.cashBalance,
      positions: positions ?? this.positions,
      realizedPnl: realizedPnl ?? this.realizedPnl,
      closedTrades: closedTrades ?? this.closedTrades,
    );
  }
}

class RiskShieldPreview {
  const RiskShieldPreview({
    required this.approved,
    required this.reason,
    required this.reasonCode,
    required this.autoQuantity,
    required this.maxNotional,
    required this.riskAmount,
    required this.riskReward,
    required this.entry,
    required this.stopLoss,
    required this.takeProfit,
    required this.dailyLoss,
  });

  final bool approved;
  final String reason;
  final String reasonCode;
  final double autoQuantity;
  final double maxNotional;
  final double riskAmount;
  final double riskReward;
  final double entry;
  final double stopLoss;
  final double takeProfit;
  final double dailyLoss;
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

  LocalPaperPosition mirrorBackendFill({
    required TradeExecutionResponseModel response,
    required String reason,
  }) {
    final notional = response.executedPrice * response.executedQuantity;
    final safeNotional = notional.clamp(0, state.cashBalance).toDouble();
    final now = DateTime.now();
    final position = LocalPaperPosition(
      tradeId: response.tradeId,
      symbol: response.symbol,
      side: response.side,
      entry: response.executedPrice,
      quantity: response.executedQuantity,
      notional: safeNotional,
      stopLoss: response.stopLoss,
      takeProfit: response.takeProfit,
      openedAt: now,
      reason: reason,
      currentPrice: response.executedPrice,
      lastMarkedAt: now,
      marketDataSource: 'backend_paper_fill',
    );
    state = state.copyWith(
      cashBalance: state.cashBalance - safeNotional,
      positions: <LocalPaperPosition>[
        position,
        ...state.positions.where((item) => item.tradeId != response.tradeId),
      ],
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
    final nextClosed = <LocalPaperClosedTrade>[];
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
        nextClosed.add(
          _postMortemFor(
            position: marked,
            exitPrice: safePrice,
            reason: marked.takeProfitHit ? 'TARGET HIT' : 'STOP-LOSS HIT',
          ),
        );
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
      closedTrades: nextClosed.isEmpty
          ? state.closedTrades
          : <LocalPaperClosedTrade>[
              ...nextClosed,
              ...state.closedTrades,
            ],
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
      closedTrades: <LocalPaperClosedTrade>[
        _postMortemFor(
          position: position,
          exitPrice: position.currentPrice,
          reason: position.unrealizedPnl >= 0 ? 'MANUAL PROFIT' : 'MANUAL LOSS',
        ),
        ...state.closedTrades,
      ],
    );
  }

  void acknowledgeLesson({
    required String tradeId,
    required String lesson,
    required bool acknowledged,
  }) {
    state = state.copyWith(
      closedTrades: state.closedTrades.map((trade) {
        if (trade.tradeId != tradeId) {
          return trade;
        }
        final lessons = Set<String>.from(trade.acknowledgedLessons);
        if (acknowledged) {
          lessons.add(lesson);
        } else {
          lessons.remove(lesson);
        }
        return trade.copyWith(acknowledgedLessons: lessons);
      }).toList(growable: false),
    );
  }

  LocalPaperClosedTrade _postMortemFor({
    required LocalPaperPosition position,
    required double exitPrice,
    required String reason,
  }) {
    final risk = (position.entry - position.stopLoss).abs();
    final reward = (position.takeProfit - position.entry).abs();
    final riskReward = risk <= 0 ? 0.0 : reward / risk;
    final tags = <String>[
      if (position.unrealizedPnl < 0) 'Rule Violation',
      if (riskReward < 1.5) 'Poor Risk-Reward',
      if (position.reason.toLowerCase().contains('wait')) 'FOMO Entry',
    ];
    if (tags.isEmpty) {
      tags.add(position.unrealizedPnl >= 0 ? 'Plan Followed' : 'Review Entry');
    }
    final analysis = position.unrealizedPnl < 0
        ? 'Trade failed because price hit the protected stop before target. Review whether entry was late, volume was weak, or AI had asked to wait.'
        : 'Trade worked because the target was reached before invalidation. Keep the same bracket discipline instead of increasing size manually.';
    return LocalPaperClosedTrade(
      tradeId: position.tradeId,
      symbol: position.symbol,
      side: position.side,
      entry: position.entry,
      exitPrice: exitPrice,
      quantity: position.quantity,
      realizedPnl: position.unrealizedPnl,
      riskReward: riskReward,
      result: reason,
      aiAnalysis: analysis,
      lessonTags: tags,
      closedAt: DateTime.now(),
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
  TradeEvaluationModel? latest;
  while (true) {
    try {
      latest = await repository.fetchTradeEvaluation(symbol);
      yield latest;
    } catch (error, stackTrace) {
      if (latest == null) {
        Error.throwWithStackTrace(error, stackTrace);
      }
      yield latest;
    }
    await Future<void>.delayed(AppConstants.tradeEvaluationPollingInterval);
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

  Future<TradeExecutionResponseModel?> executePaperSandbox({
    required String userId,
    required String symbol,
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
    required LocalPaperPortfolioState paperState,
    required RiskShieldPreview riskShield,
    double? selectedPrice,
  }) async {
    final notional = state.amount;
    if (notional <= 0) {
      state = state.copyWith(
        errorMessage: 'Enter a valid paper amount before submitting.',
        clearLastResponse: true,
      );
      return null;
    }
    if (!riskShield.approved) {
      state = state.copyWith(
        errorMessage: riskShield.reason,
        clearLastResponse: true,
      );
      return null;
    }

    final side = _paperSide(intent: intent, evaluation: evaluation);
    final confidence = _paperConfidence(intent: intent, evaluation: evaluation);
    final probability = evaluation?.inference.tradeProbability ?? confidence;
    final reason = evaluation?.reason.trim().isNotEmpty == true
        ? evaluation!.reason.trim()
        : ((intent?.reason?.trim().isNotEmpty ?? false)
            ? intent!.reason!.trim()
            : 'Paper sandbox request submitted from the mobile AI guide.');
    final strategy = evaluation?.strategy.trim().isNotEmpty == true
        ? evaluation!.strategy.trim()
        : ((intent?.strategy?.trim().isNotEmpty ?? false)
            ? intent!.strategy!.trim()
            : 'PAPER_SANDBOX');
    final featureSnapshot = <String, double>{
      ...?evaluation?.snapshot.featureSnapshot,
      'mobile_terminal': 1.0,
      'paper_sandbox_request': 1.0,
      'manual_request': 0.0,
      'signal_confidence': confidence,
      'trade_success_probability': probability,
      'raw_trade_success_probability': probability,
      'ui_requested_notional': notional,
      if (selectedPrice != null && selectedPrice > 0)
        'selected_price': selectedPrice,
      'shield_required': 1.0,
      'shield_account_balance': paperState.equity,
      'shield_daily_realized_pnl':
          paperState.realizedPnl < 0 ? paperState.realizedPnl : 0.0,
      'shield_consecutive_losses': paperState.consecutiveLosses.toDouble(),
      'shield_closed_trades': paperState.closedTradeCount.toDouble(),
      'shield_winning_trades': paperState.winningTradeCount.toDouble(),
      'shield_average_risk_reward': paperState.averageRiskReward,
      'shield_entry_price': riskShield.entry,
      'shield_stop_loss': riskShield.stopLoss,
      'shield_take_profit': riskShield.takeProfit,
      'shield_auto_quantity': riskShield.autoQuantity,
      'shield_max_notional': riskShield.maxNotional,
      if (evaluation != null) 'approved_alpha_score': evaluation.alphaScore,
      if (intent?.lowConfidence == true) 'low_confidence_signal': 1.0,
    };

    state = state.copyWith(
      side: side,
      isSubmitting: true,
      clearError: true,
      clearLastResponse: true,
    );

    final request = TradeExecutionRequestModel(
      userId: userId,
      symbol: symbol,
      side: side,
      confidence: confidence,
      reason: reason,
      requestedNotional: notional,
      expectedReturn: evaluation?.inference.expectedReturn,
      expectedRisk: evaluation?.inference.expectedRisk,
      signalId: intent?.signalId,
      strategy: strategy,
      featureSnapshot: featureSnapshot,
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
              'Paper trade was rejected by the backend sandbox. The ledger was not changed.',
        ),
      );
      return null;
    }
  }

  String _paperSide({
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
  }) {
    final approvedSide = evaluation?.approvedSide.toUpperCase();
    if (approvedSide == 'BUY' || approvedSide == 'SELL') {
      return approvedSide!;
    }
    final intentSide = intent?.side?.toUpperCase();
    if (intentSide == 'BUY' || intentSide == 'SELL') {
      return intentSide!;
    }
    return state.side.toUpperCase() == 'SELL' ? 'SELL' : 'BUY';
  }

  double _paperConfidence({
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
  }) {
    final confidence =
        evaluation?.confidenceScore ?? intent?.confidence ?? 0.55;
    return confidence.clamp(0.0, 1.0).toDouble();
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

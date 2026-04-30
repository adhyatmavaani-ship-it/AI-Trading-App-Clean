import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../repositories/trading_repository.dart';
import '../models/risk_coach_models.dart';


class ExecutionDraft {
  const ExecutionDraft({
    required this.trade,
    required this.status,
    this.errorMessage,
  });

  final RiskCoachTrade? trade;
  final String status;
  final String? errorMessage;

  ExecutionDraft copyWith({
    RiskCoachTrade? trade,
    String? status,
    String? errorMessage,
  }) {
    return ExecutionDraft(
      trade: trade ?? this.trade,
      status: status ?? this.status,
      errorMessage: errorMessage,
    );
  }
}


class ExecutionController extends StateNotifier<ExecutionDraft> {
  ExecutionController(this._repository)
      : super(const ExecutionDraft(trade: null, status: 'idle'));

  final TradingRepository _repository;

  void bindTrade(RiskCoachTrade? trade) {
    state = state.copyWith(trade: trade, status: trade == null ? 'idle' : trade.state);
  }

  Future<void> updateLevels({
    required String tradeId,
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) async {
    final previous = state.trade;
    if (previous == null) {
      return;
    }
    final optimistic = previous.copyWith(
      state: 'pending',
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
    );
    state = state.copyWith(trade: optimistic, status: 'pending', errorMessage: null);
    try {
      final patched = await _repository.patchRiskCoachTrade(
        tradeId: tradeId,
        entry: entry,
        stopLoss: stopLoss,
        takeProfit: takeProfit,
      );
      state = state.copyWith(trade: patched, status: 'confirmed');
    } catch (_) {
      state = state.copyWith(
        trade: previous.copyWith(state: 'failed'),
        status: 'failed',
        errorMessage: 'Rollback applied after sync failure.',
      );
    }
  }
}

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/active_trade.dart';
import '../../../models/user_pnl.dart';
import '../../../providers/app_providers.dart';

final userPnLProvider =
    StreamProvider.autoDispose.family<UserPnLModel, String>((ref, userId) {
  return ref.watch(tradingRepositoryProvider).watchUserPnL(userId);
});

final activeUserIdProvider =
    StateProvider<String>((ref) => AppConstants.requiredUserId);

final activeTradesProvider =
    StreamProvider.autoDispose.family<List<ActiveTradeModel>, String>((ref, userId) {
  return ref.watch(tradingRepositoryProvider).watchActiveTrades(userId);
});

final equityCurveProvider =
    StreamProvider.autoDispose.family<List<UserPnLModel>, String>((ref, userId) async* {
  final history = <UserPnLModel>[];
  await for (final snapshot
      in ref.watch(tradingRepositoryProvider).watchUserPnL(userId)) {
    history.add(snapshot);
    if (history.length > 30) {
      history.removeAt(0);
    }
    yield List<UserPnLModel>.unmodifiable(history);
  }
});

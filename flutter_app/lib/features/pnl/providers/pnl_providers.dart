import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/user_pnl.dart';
import '../../../providers/app_providers.dart';

final userPnLProvider =
    StreamProvider.family<UserPnLModel, String>((ref, userId) {
  return ref.watch(tradingRepositoryProvider).watchUserPnL(userId);
});

final activeUserIdProvider = StateProvider<String>((ref) => 'system');

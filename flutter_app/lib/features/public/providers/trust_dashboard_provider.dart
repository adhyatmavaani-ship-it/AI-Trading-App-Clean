import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/public_dashboard.dart';
import '../../../providers/app_providers.dart';

final trustDashboardProvider =
    StreamProvider<TrustDashboardModel>((ref) async* {
  yield await ref.watch(tradingRepositoryProvider).fetchTrustDashboard();
  while (true) {
    await Future<void>.delayed(AppConstants.pollingInterval);
    yield await ref.watch(tradingRepositoryProvider).fetchTrustDashboard();
  }
});

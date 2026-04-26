import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/public_dashboard.dart';
import '../../../providers/app_providers.dart';

final trustDashboardProvider = FutureProvider<TrustDashboardModel>((ref) async {
  return ref.watch(tradingRepositoryProvider).fetchTrustDashboard();
});

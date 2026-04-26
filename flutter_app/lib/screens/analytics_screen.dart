import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/meta/providers/meta_providers.dart';
import '../widgets/meta_widgets.dart';
import '../widgets/state_widgets.dart';

class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final analyticsAsync = ref.watch(metaAnalyticsProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(metaAnalyticsProvider);
      },
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: <Widget>[
          analyticsAsync.when(
            loading: () => const SizedBox(
              height: 220,
              child: LoadingState(label: 'Loading meta analytics'),
            ),
            error: (error, _) => ErrorState(message: error.toString()),
            data: (analytics) => Column(
              children: <Widget>[
                BlockedVsExecutedCard(analytics: analytics),
                const SizedBox(height: 20),
                StrategyPerformanceCard(analytics: analytics),
                const SizedBox(height: 20),
                ConfidenceDistributionCard(
                  distribution: analytics.confidenceDistribution,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

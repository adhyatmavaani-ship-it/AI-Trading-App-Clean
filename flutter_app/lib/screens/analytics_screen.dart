import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_presenter.dart';
import '../features/meta/providers/meta_providers.dart';
import '../providers/app_bootstrap_provider.dart';
import '../widgets/meta_widgets.dart';
import '../widgets/state_widgets.dart';

class AnalyticsScreen extends ConsumerWidget {
  const AnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final bootstrapAsync = ref.watch(appBootstrapProvider);
    final analyticsAsync = ref.watch(metaAnalyticsProvider);
    if (bootstrapAsync.isLoading && !analyticsAsync.hasValue) {
      return const LoadingState();
    }
    if (bootstrapAsync.hasError && !analyticsAsync.hasValue) {
      return ErrorState(
        message: userMessageForError(bootstrapAsync.error),
        onRetry: () => ref.read(appBootstrapProvider.notifier).refresh(),
      );
    }
    return RefreshIndicator(
      onRefresh: () async {
        ref.read(appBootstrapProvider.notifier).refresh();
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
            error: (error, _) => ErrorState(
              message: userMessageForError(error),
              onRetry: () {
                ref.read(appBootstrapProvider.notifier).refresh();
                ref.invalidate(metaAnalyticsProvider);
              },
            ),
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

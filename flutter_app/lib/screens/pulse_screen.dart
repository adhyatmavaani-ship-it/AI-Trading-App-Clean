import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/meta/providers/meta_providers.dart';
import '../features/monitoring/providers/monitoring_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../models/portfolio_concentration.dart';
import '../models/signal.dart';
import '../widgets/batch_tile.dart';
import '../widgets/metric_card.dart';
import '../widgets/meta_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/signal_tile.dart';
import '../widgets/state_widgets.dart';

class PulseScreen extends ConsumerStatefulWidget {
  const PulseScreen({super.key});

  @override
  ConsumerState<PulseScreen> createState() => _PulseScreenState();
}

class _PulseScreenState extends ConsumerState<PulseScreen> {
  ProviderSubscription<AsyncValue<List<SignalModel>>>? _initialSubscription;
  ProviderSubscription<AsyncValue<SignalModel>>? _streamSubscription;

  @override
  void initState() {
    super.initState();
    _initialSubscription =
        ref.listenManual(initialSignalsProvider, (previous, next) {
      next.whenData((signals) {
        ref.read(signalFeedProvider.notifier).hydrate(signals);
      });
      next.whenOrNull(error: (error, _) {
        ref.read(signalFeedProvider.notifier).setError(error);
      });
    });
    _streamSubscription =
        ref.listenManual(signalStreamProvider, (previous, next) {
      next.whenData((signal) {
        ref.read(signalFeedProvider.notifier).ingest(signal);
      });
      next.whenOrNull(error: (error, _) {
        ref.read(signalFeedProvider.notifier).setError(error);
      });
    });
  }

  @override
  void dispose() {
    _initialSubscription?.close();
    _streamSubscription?.close();
    super.dispose();
  }

  List<Widget> _concentrationBadges(
    BuildContext context,
    PortfolioConcentrationSnapshotModel latest,
  ) {
    final badges = <Widget>[];
    if (latest.severity == 'alert') {
      badges.add(
        Chip(
          avatar: const Icon(
            Icons.warning_amber_rounded,
            size: 16,
            color: Color(0xFFFFD28A),
          ),
          label: const Text('Concentration Alert'),
          backgroundColor: const Color(0xFF4A2A14),
          side: const BorderSide(color: Color(0xFF7C5223)),
          labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: const Color(0xFFFFD28A),
              ),
        ),
      );
    } else if (latest.severity == 'softening') {
      badges.add(
        Chip(
          avatar: const Icon(
            Icons.tune_rounded,
            size: 16,
            color: Color(0xFF8DE2C8),
          ),
          label: const Text('Softening Active'),
          backgroundColor: const Color(0xFF13313A),
          side: const BorderSide(color: Color(0xFF1F424D)),
          labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: const Color(0xFF8DE2C8),
              ),
        ),
      );
    }
    badges.add(
      Chip(
        label: Text('Regime ${latest.factorRegime}'),
        backgroundColor: const Color(0xFF153540),
      ),
    );
    return badges;
  }

  List<Widget> _modelStabilityBadges(
    BuildContext context,
    ModelStabilityConcentrationHistoryEntryModel latestState,
  ) {
    final badges = <Widget>[];
    if (latestState.severity == 'alert') {
      badges.add(
        Chip(
          avatar: const Icon(
            Icons.warning_amber_rounded,
            size: 16,
            color: Color(0xFFFFD28A),
          ),
          label: const Text('Throttle Alert'),
          backgroundColor: const Color(0xFF4A2A14),
          side: const BorderSide(color: Color(0xFF7C5223)),
          labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: const Color(0xFFFFD28A),
              ),
        ),
      );
    } else if (latestState.severity == 'softening') {
      badges.add(
        Chip(
          avatar: const Icon(
            Icons.tune_rounded,
            size: 16,
            color: Color(0xFF8DE2C8),
          ),
          label: const Text('Throttle Softening'),
          backgroundColor: const Color(0xFF13313A),
          side: const BorderSide(color: Color(0xFF1F424D)),
          labelStyle: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: const Color(0xFF8DE2C8),
              ),
        ),
      );
    }
    return badges;
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(signalFeedProvider);
    final batchesAsync = ref.watch(batchesProvider);
    final healthAsync = ref.watch(systemHealthProvider);
    final concentrationWindow = ref.watch(concentrationWindowProvider);
    final concentrationAsync = ref.watch(concentrationHistoryProvider);
    final modelStabilityConcentrationAsync =
        ref.watch(modelStabilityConcentrationHistoryProvider);
    final metaAnalyticsAsync = ref.watch(metaAnalyticsProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(initialSignalsProvider);
        ref.invalidate(batchesProvider);
        ref.invalidate(systemHealthProvider);
        ref.invalidate(concentrationHistoryProvider);
      },
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: <Widget>[
          healthAsync.when(
            data: (health) => Wrap(
              spacing: 12,
              runSpacing: 12,
              children: <Widget>[
                MetricCard(
                  label: 'Mode',
                  value: health.tradingMode.toUpperCase(),
                  icon: Icons.memory_rounded,
                ),
                MetricCard(
                  label: 'Latency P95',
                  value: '${health.latencyMsP95.toStringAsFixed(0)} ms',
                  icon: Icons.speed_rounded,
                ),
                MetricCard(
                  label: 'Active Trades',
                  value: health.activeTrades.toString(),
                  icon: Icons.account_tree_outlined,
                ),
                MetricCard(
                  label: 'Failures',
                  value: health.failedOrders.toString(),
                  icon: Icons.warning_amber_rounded,
                ),
              ],
            ),
            loading: () => const SizedBox(
              height: 120,
              child: LoadingState(label: 'Loading platform health'),
            ),
            error: (error, _) => ErrorState(message: error.toString()),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Portfolio Concentration',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SegmentedButton<String>(
                  segments: const <ButtonSegment<String>>[
                    ButtonSegment<String>(value: '1h', label: Text('1h')),
                    ButtonSegment<String>(value: '24h', label: Text('24h')),
                    ButtonSegment<String>(value: '7d', label: Text('7d')),
                  ],
                  selected: <String>{concentrationWindow},
                  onSelectionChanged: (selection) {
                    ref.read(concentrationWindowProvider.notifier).state =
                        selection.first;
                  },
                ),
                const SizedBox(height: 16),
                concentrationAsync.when(
                  data: (concentration) {
                    final latest = concentration.latest;
                    final badges = _concentrationBadges(context, latest);
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: badges,
                        ),
                        const SizedBox(height: 16),
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          children: <Widget>[
                            MetricCard(
                              label: 'Gross Drift',
                              value:
                                  '${(latest.grossExposureDrift * 100).toStringAsFixed(1)}%',
                              icon: Icons.show_chart_rounded,
                            ),
                            MetricCard(
                              label: 'Cluster Drift',
                              value:
                                  '${(latest.clusterConcentrationDrift * 100).toStringAsFixed(1)}%',
                              icon: Icons.hub_outlined,
                            ),
                            MetricCard(
                              label: 'Turnover',
                              value:
                                  '${(latest.clusterTurnover * 100).toStringAsFixed(1)}%',
                              icon: Icons.sync_alt_rounded,
                            ),
                            MetricCard(
                              label: 'Budget Gap',
                              value:
                                  '${(latest.maxFactorSleeveBudgetGapPct * 100).toStringAsFixed(1)}%',
                              icon: Icons.compare_arrows_rounded,
                            ),
                            MetricCard(
                              label: 'Budget Turnover',
                              value:
                                  '${(latest.factorSleeveBudgetTurnover * 100).toStringAsFixed(1)}%',
                              icon: Icons.autorenew_rounded,
                            ),
                            MetricCard(
                              label: 'Factor Model',
                              value:
                                  '${latest.factorRegime} - ${latest.factorModel}',
                              icon: Icons.insights_rounded,
                            ),
                          ],
                        ),
                        if (latest.severityReason != null) ...<Widget>[
                          const SizedBox(height: 12),
                          Text(
                            latest.severityReason!,
                            style: Theme.of(context).textTheme.bodyMedium
                                ?.copyWith(color: const Color(0xFF9CB3C8)),
                          ),
                        ],
                        const SizedBox(height: 16),
                        Text(
                          'Factor Weights',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: latest.factorWeights.entries
                              .map(
                                (entry) => Chip(
                                  label: Text(
                                    '${entry.key} ${(entry.value * 100).toStringAsFixed(0)}%',
                                  ),
                                  backgroundColor: const Color(0xFF153540),
                                ),
                              )
                              .toList(),
                        ),
                        if (latest.factorUniverseSymbols.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Active Factor Universe',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: latest.factorUniverseSymbols
                                .map(
                                  (symbol) => Chip(
                                    label: Text(symbol),
                                    backgroundColor: const Color(0xFF1A2432),
                                  ),
                                )
                                .toList(),
                          ),
                        ],
                        if (latest.factorAttribution.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Factor Attribution',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: latest.factorAttribution.entries
                                .map(
                                  (entry) => Chip(
                                    label: Text(
                                      '${entry.key} ${(entry.value * 100).toStringAsFixed(0)}%',
                                    ),
                                    backgroundColor: const Color(0xFF1B3042),
                                  ),
                                )
                                .toList(),
                          ),
                          if (latest.dominantFactorSleeve != null) ...<Widget>[
                            const SizedBox(height: 8),
                            Text(
                              'Dominant sleeve: ${latest.dominantFactorSleeve}',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(color: const Color(0xFF9CB3C8)),
                            ),
                          ],
                        ],
                        if (latest.factorSleeveBudgetTargets.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Sleeve Budget Rotation',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          if (latest.dominantOverBudgetSleeve != null ||
                              latest.dominantUnderBudgetSleeve != null) ...<Widget>[
                            const SizedBox(height: 8),
                            Text(
                              'Over budget: ${latest.dominantOverBudgetSleeve ?? '-'}  |  '
                              'Under budget: ${latest.dominantUnderBudgetSleeve ?? '-'}',
                              style: Theme.of(context).textTheme.bodyMedium
                                  ?.copyWith(color: const Color(0xFF9CB3C8)),
                            ),
                          ],
                          const SizedBox(height: 8),
                          Column(
                            children: latest.factorSleeveBudgetTargets.entries.map((entry) {
                              final actualShare =
                                  latest.factorAttribution[entry.key] ?? 0.0;
                              final delta =
                                  latest.factorSleeveBudgetDeltas[entry.key] ?? 0.0;
                              final targetShare = entry.value;
                              final isPositive = delta >= 0;
                              return ListTile(
                                dense: true,
                                contentPadding: EdgeInsets.zero,
                                title: Text(entry.key),
                                subtitle: Text(
                                  'Target ${(targetShare * 100).toStringAsFixed(1)}%  |  '
                                  'Actual ${(actualShare * 100).toStringAsFixed(1)}%',
                                ),
                                trailing: Text(
                                  '${isPositive ? '+' : ''}${(delta * 100).toStringAsFixed(1)}%',
                                  style: TextStyle(
                                    color: isPositive
                                        ? const Color(0xFF8DE2C8)
                                        : const Color(0xFFFFB3A7),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              );
                            }).toList(),
                          ),
                        ],
                        if (latest.factorSleevePerformance.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Sleeve Performance',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: latest.factorSleevePerformance.entries.map((entry) {
                              final pnl =
                                  (entry.value['realized_pnl'] as num?)?.toDouble() ??
                                      0.0;
                              final wins =
                                  (entry.value['wins'] as num?)?.toInt() ?? 0;
                              final losses =
                                  (entry.value['losses'] as num?)?.toInt() ?? 0;
                              return Chip(
                                label: Text(
                                  '${entry.key} ${pnl >= 0 ? '+' : ''}${pnl.toStringAsFixed(2)} | $wins/$losses',
                                ),
                                backgroundColor: pnl >= 0
                                    ? const Color(0xFF173A2F)
                                    : const Color(0xFF402020),
                              );
                            }).toList(),
                          ),
                        ],
                        const SizedBox(height: 16),
                        Text(
                          'Recent Drift History',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        if (concentration.history.isEmpty)
                          const EmptyState(
                            title: 'No concentration history yet',
                            subtitle:
                                'Snapshots will appear here once monitoring has collected drift samples.',
                          )
                        else
                          Column(
                            children: concentration.history.reversed
                                .take(6)
                                .map(
                                  (snapshot) => ListTile(
                                    dense: true,
                                    contentPadding: EdgeInsets.zero,
                                    title: Text(
                                      snapshot.updatedAt?.toLocal().toString() ??
                                          'Unknown time',
                                    ),
                                    subtitle: Text(
                                      'Gross ${(snapshot.grossExposureDrift * 100).toStringAsFixed(1)}%  |  '
                                      'Cluster ${(snapshot.clusterConcentrationDrift * 100).toStringAsFixed(1)}%  |  '
                                      'Turnover ${(snapshot.clusterTurnover * 100).toStringAsFixed(1)}%',
                                    ),
                                    trailing: Text(
                                      snapshot.dominantFactorSleeve ??
                                          snapshot.dominantCluster ??
                                          '-',
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                      ],
                    );
                  },
                  loading: () => const LoadingState(
                    label: 'Loading concentration history',
                  ),
                  error: (error, _) => ErrorState(message: error.toString()),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Model Stability Throttling',
            child: modelStabilityConcentrationAsync.when(
              data: (stability) {
                final latestStatus = stability.latestStatus;
                final latestState = stability.latestState;
                final throttlingBadges =
                    _modelStabilityBadges(context, latestState);
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    if (throttlingBadges.isNotEmpty) ...<Widget>[
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: throttlingBadges,
                      ),
                      const SizedBox(height: 16),
                    ],
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: <Widget>[
                        MetricCard(
                          label: 'Drift Score',
                          value:
                              '${(latestStatus.concentrationDriftScore * 100).toStringAsFixed(1)}%',
                          icon: Icons.auto_graph_rounded,
                        ),
                        MetricCard(
                          label: 'Trading Multiplier',
                          value: latestStatus.tradingFrequencyMultiplier
                              .toStringAsFixed(2),
                          icon: Icons.tune_rounded,
                        ),
                        MetricCard(
                          label: 'Model',
                          value: latestStatus.activeModelVersion,
                          icon: Icons.memory_rounded,
                        ),
                        MetricCard(
                          label: 'Fallback',
                          value: latestStatus.degraded ? 'Active' : 'Standby',
                          icon: Icons.shield_outlined,
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    if (latestState.severityReason != null) ...<Widget>[
                      Text(
                        latestState.severityReason!,
                        style: Theme.of(context).textTheme.bodyMedium
                            ?.copyWith(color: const Color(0xFF9CB3C8)),
                      ),
                      const SizedBox(height: 16),
                    ],
                    Text(
                      'Recent Throttling Drift',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    if (stability.history.isEmpty)
                      const EmptyState(
                        title: 'No model throttling history yet',
                        subtitle:
                            'The model stability service will start recording concentration throttling snapshots during live monitoring.',
                      )
                    else
                      Column(
                        children: stability.history.reversed
                            .take(6)
                            .map(
                              (entry) => ListTile(
                                dense: true,
                                contentPadding: EdgeInsets.zero,
                                title: Text(
                                  entry.updatedAt?.toLocal().toString() ??
                                      'Unknown time',
                                ),
                                subtitle: Text(
                                  'Score ${(entry.score * 100).toStringAsFixed(1)}%  |  '
                                  'Cluster ${(entry.clusterConcentrationDrift * 100).toStringAsFixed(1)}%  |  '
                                  'Turnover ${(entry.clusterTurnover * 100).toStringAsFixed(1)}%',
                                ),
                                trailing: Text(entry.severity.toUpperCase()),
                              ),
                            )
                            .toList(),
                      ),
                    if (stability.history.isNotEmpty &&
                        latestState.updatedAt != null) ...<Widget>[
                      const SizedBox(height: 8),
                      Text(
                        'Latest model response at ${latestState.updatedAt!.toLocal()}',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: const Color(0xFF9CB3C8),
                            ),
                      ),
                    ],
                  ],
                );
              },
              loading: () => const LoadingState(
                label: 'Loading model throttling history',
              ),
              error: (error, _) => ErrorState(message: error.toString()),
            ),
          ),
          const SizedBox(height: 20),
          metaAnalyticsAsync.when(
            data: (analytics) => MetaPulseSummaryCard(analytics: analytics),
            loading: () => const SectionCard(
              title: 'Meta Pulse',
              child: LoadingState(label: 'Loading meta pulse'),
            ),
            error: (error, _) => SectionCard(
              title: 'Meta Pulse',
              child: ErrorState(message: error.toString()),
            ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Live Signals',
            trailing: Chip(
              label: Text('${feed.items.length} cached'),
              backgroundColor: const Color(0xFF153540),
            ),
            child: feed.items.isEmpty
                ? const EmptyState(
                    title: 'No live signals yet',
                    subtitle:
                        'Signals will appear here as soon as the websocket receives updates.',
                  )
                : Column(
                    children: feed.items
                        .map(
                          (signal) => SignalTile(
                            signal: signal,
                            onTap: () => ref
                                .read(selectedTradeIdProvider.notifier)
                                .state = signal.signalId,
                          ),
                        )
                        .toList(),
                  ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'VOM Batches',
            child: batchesAsync.when(
              data: (batches) {
                if (batches.isEmpty) {
                  return const EmptyState(
                    title: 'No active VOM batches',
                    subtitle:
                        'Aggregated execution batches will appear here automatically.',
                  );
                }
                return Column(
                  children:
                      batches.map((batch) => BatchTile(batch: batch)).toList(),
                );
              },
              loading: () =>
                  const LoadingState(label: 'Syncing virtual batches'),
              error: (error, _) => ErrorState(message: error.toString()),
            ),
          ),
        ],
      ),
    );
  }
}

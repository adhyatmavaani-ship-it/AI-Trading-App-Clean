import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'dart:async';

import '../core/trading_palette.dart';
import '../features/activity/providers/activity_providers.dart';
import '../features/meta/providers/meta_providers.dart';
import '../features/monitoring/providers/monitoring_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../models/activity.dart';
import '../models/portfolio_concentration.dart';
import '../models/signal.dart';
import '../widgets/activity_feed_tile.dart';
import '../widgets/batch_tile.dart';
import '../widgets/bot_state_banner.dart';
import '../widgets/metric_card.dart';
import '../widgets/market_chart_panel.dart';
import '../widgets/market_sentiment_gauge.dart';
import '../widgets/meta_widgets.dart';
import '../widgets/readiness_tile.dart';
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
  ProviderSubscription<AsyncValue<List<ActivityItemModel>>>?
      _initialActivitySubscription;
  ProviderSubscription<AsyncValue<List<ReadinessCardModel>>>?
      _initialReadinessSubscription;
  ProviderSubscription<AsyncValue<ActivityItemModel>>?
      _activityStreamSubscription;
  Timer? _autoRefreshTimer;

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
    _initialActivitySubscription =
        ref.listenManual(initialActivityHistoryProvider, (previous, next) {
      next.whenData((items) {
        ref.read(activityFeedProvider.notifier).hydrate(items);
      });
      next.whenOrNull(error: (error, _) {
        ref.read(activityFeedProvider.notifier).setError(error);
      });
    });
    _initialReadinessSubscription =
        ref.listenManual(initialReadinessBoardProvider, (previous, next) {
      next.whenData((items) {
        ref.read(readinessBoardProvider.notifier).hydrate(items);
      });
    });
    _activityStreamSubscription =
        ref.listenManual(activityStreamProvider, (previous, next) {
      next.whenData((activity) {
        ref.read(activityFeedProvider.notifier).ingest(activity);
        ref.read(readinessBoardProvider.notifier).ingest(activity);
      });
      next.whenOrNull(error: (error, _) {
        ref.read(activityFeedProvider.notifier).setError(error);
      });
    });
    _autoRefreshTimer = Timer.periodic(
      const Duration(seconds: 15),
      (_) => _triggerAutoRefresh(),
    );
  }

  @override
  void dispose() {
    _initialSubscription?.close();
    _streamSubscription?.close();
    _initialActivitySubscription?.close();
    _initialReadinessSubscription?.close();
    _activityStreamSubscription?.close();
    _autoRefreshTimer?.cancel();
    super.dispose();
  }

  void _triggerAutoRefresh() {
    if (!mounted) {
      return;
    }
    ref.invalidate(initialSignalsProvider);
    ref.invalidate(initialActivityHistoryProvider);
    ref.invalidate(initialReadinessBoardProvider);
    ref.invalidate(batchesProvider);
    ref.invalidate(systemHealthProvider);
    ref.invalidate(concentrationHistoryProvider);
    ref.invalidate(modelStabilityConcentrationHistoryProvider);
    ref.invalidate(metaAnalyticsProvider);
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
    final activityFeed = ref.watch(activityFeedProvider);
    final readinessBoard = ref.watch(readinessBoardProvider);
    final batchesAsync = ref.watch(batchesProvider);
    final healthAsync = ref.watch(systemHealthProvider);
    final concentrationWindow = ref.watch(concentrationWindowProvider);
    final concentrationAsync = ref.watch(concentrationHistoryProvider);
    final modelStabilityConcentrationAsync =
        ref.watch(modelStabilityConcentrationHistoryProvider);
    final metaAnalyticsAsync = ref.watch(metaAnalyticsProvider);
    final latestActivity = activityFeed.latest;

    return RefreshIndicator(
      onRefresh: () async {
        _triggerAutoRefresh();
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
          if (activityFeed.latest != null)
            BotStateBanner(activity: activityFeed.latest!)
          else
            const SectionCard(
              title: 'Bot State',
              child: EmptyState(
                title: 'Waiting for activity',
                subtitle:
                    'The perception engine will publish scanning intent here once the backend starts evaluating symbols.',
              ),
            ),
          const SizedBox(height: 20),
          const MarketSentimentGauge(),
          const SizedBox(height: 20),
          _AmbientMoodShell(
            activity: latestActivity,
            child: MarketChartPanel(latestActivity: latestActivity),
          ),
          const SizedBox(height: 20),
          _LogicFeedCard(
            latestActivity: latestActivity,
            readinessBoard: readinessBoard,
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Trade Readiness Board',
            trailing: Chip(
              label: Text('${readinessBoard.length} tracked'),
              backgroundColor: const Color(0xFF153540),
            ),
            child: readinessBoard.isEmpty
                ? const EmptyState(
                    title: 'No readiness board yet',
                    subtitle:
                        'Symbols will appear here as the engine scans and scores setup quality.',
                  )
                : SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: readinessBoard
                          .map(
                            (card) => Padding(
                              padding: const EdgeInsets.only(right: 12),
                              child: ReadinessTile(card: card),
                            ),
                          )
                          .toList(),
                    ),
                  ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Live Activity Feed',
            trailing: Chip(
              label: Text('${activityFeed.items.length} events'),
              backgroundColor: const Color(0xFF153540),
            ),
            child: activityFeed.items.isEmpty
                ? const EmptyState(
                    title: 'No activity yet',
                    subtitle:
                        'Scanning, rejections, almost-trades, and executions will appear here in real time.',
                  )
                : Column(
                    children: activityFeed.items
                        .take(10)
                        .map((item) => ActivityFeedTile(activity: item))
                        .toList(),
                  ),
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
                            style: Theme.of(context)
                                .textTheme
                                .bodyMedium
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
                        if (latest
                            .factorUniverseSymbols.isNotEmpty) ...<Widget>[
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
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(color: const Color(0xFF9CB3C8)),
                            ),
                          ],
                        ],
                        if (latest
                            .factorSleeveBudgetTargets.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Sleeve Budget Rotation',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          if (latest.dominantOverBudgetSleeve != null ||
                              latest.dominantUnderBudgetSleeve !=
                                  null) ...<Widget>[
                            const SizedBox(height: 8),
                            Text(
                              'Over budget: ${latest.dominantOverBudgetSleeve ?? '-'}  |  '
                              'Under budget: ${latest.dominantUnderBudgetSleeve ?? '-'}',
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(color: const Color(0xFF9CB3C8)),
                            ),
                          ],
                          const SizedBox(height: 8),
                          Column(
                            children: latest.factorSleeveBudgetTargets.entries
                                .map((entry) {
                              final actualShare =
                                  latest.factorAttribution[entry.key] ?? 0.0;
                              final delta =
                                  latest.factorSleeveBudgetDeltas[entry.key] ??
                                      0.0;
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
                        if (latest
                            .factorSleevePerformance.isNotEmpty) ...<Widget>[
                          const SizedBox(height: 16),
                          Text(
                            'Sleeve Performance',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: latest.factorSleevePerformance.entries
                                .map((entry) {
                              final pnl = (entry.value['realized_pnl'] as num?)
                                      ?.toDouble() ??
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
                                      snapshot.updatedAt
                                              ?.toLocal()
                                              .toString() ??
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
                        style: Theme.of(context)
                            .textTheme
                            .bodyMedium
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

class _AmbientMoodShell extends StatelessWidget {
  const _AmbientMoodShell({
    required this.activity,
    required this.child,
  });

  final ActivityItemModel? activity;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final mood = _activityMood(activity);
    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      padding: const EdgeInsets.all(2),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(30),
        gradient: RadialGradient(
          colors: <Color>[
            mood.withOpacity(0.18),
            mood.withOpacity(0.06),
            Colors.transparent,
          ],
          center: const Alignment(-0.15, -0.4),
          radius: 1.15,
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: mood.withOpacity(0.14),
            blurRadius: 32,
            spreadRadius: 2,
          ),
        ],
      ),
      child: child,
    );
  }
}

class _LogicFeedCard extends StatelessWidget {
  const _LogicFeedCard({
    required this.latestActivity,
    required this.readinessBoard,
  });

  final ActivityItemModel? latestActivity;
  final List<ReadinessCardModel> readinessBoard;

  @override
  Widget build(BuildContext context) {
    final topCards = readinessBoard.take(3).toList();
    return SectionCard(
      title: 'AI Logic Feed',
      trailing: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0x2214FFB8),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: const Color(0x4414FFB8)),
        ),
        child: const Text(
          'AI Eyes',
          style: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (latestActivity != null)
            _LogicHeadline(activity: latestActivity!)
          else
            const EmptyState(
              title: 'Waiting for AI context',
              subtitle:
                  'Scanning intent, confidence drift, and setup reasons will appear here once the engine starts narrating the market.',
            ),
          if (topCards.isNotEmpty) ...<Widget>[
            const SizedBox(height: 16),
            Text(
              'What AI is noticing',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 10),
            Column(
              children: topCards
                  .map((card) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _LogicFeedItem(card: card),
                      ))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class _LogicHeadline extends StatelessWidget {
  const _LogicHeadline({required this.activity});

  final ActivityItemModel activity;

  @override
  Widget build(BuildContext context) {
    final accent = _activityMood(activity);
    final confidence = (activity.confidenceMeter ??
            activity.confidence ??
            ((activity.readiness ?? 0) / 100))
        .clamp(0.0, 1.0);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          colors: <Color>[
            accent.withOpacity(0.22),
            TradingPalette.panelSoft,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _LogicChip(label: activity.status.toUpperCase(), accent: accent),
              if ((activity.symbol ?? '').isNotEmpty)
                _LogicChip(label: activity.symbol!, accent: TradingPalette.electricBlue),
              if ((activity.regime ?? '').isNotEmpty)
                _LogicChip(label: activity.regime!, accent: TradingPalette.amber),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            activity.intent?.isNotEmpty == true ? activity.intent! : activity.message,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            activity.reason?.isNotEmpty == true
                ? activity.reason!
                : 'AI is aligning structure, momentum, and participation before committing.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: confidence,
              minHeight: 7,
              backgroundColor: TradingPalette.panelBorder,
              valueColor: AlwaysStoppedAnimation<Color>(accent),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Confidence ${(confidence * 100).toStringAsFixed(0)}%  •  Readiness ${(activity.readiness ?? 0).toStringAsFixed(0)}%',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: accent,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _LogicFeedItem extends StatelessWidget {
  const _LogicFeedItem({required this.card});

  final ReadinessCardModel card;

  @override
  Widget build(BuildContext context) {
    final accent = _readinessAccent(card);
    final confidence = (card.confidenceMeter ??
            card.confidence ??
            (card.readiness / 100))
        .clamp(0.0, 1.0);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: accent.withOpacity(0.28)),
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: accent.withOpacity(0.14),
              border: Border.all(color: accent.withOpacity(0.35)),
            ),
            child: Center(
              child: Text(
                card.symbol.replaceAll('USDT', ''),
                style: const TextStyle(
                  color: TradingPalette.textPrimary,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  card.intent?.isNotEmpty == true ? card.intent! : card.message ?? card.status,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: TradingPalette.textPrimary,
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  card.reason?.isNotEmpty == true
                      ? card.reason!
                      : 'Readiness is building across the latest scan.',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.textMuted,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Text(
                '${card.readiness.toStringAsFixed(0)}%',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: accent,
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 4),
              SizedBox(
                width: 52,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: confidence,
                    minHeight: 6,
                    backgroundColor: TradingPalette.panelBorder,
                    valueColor: AlwaysStoppedAnimation<Color>(accent),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _LogicChip extends StatelessWidget {
  const _LogicChip({
    required this.label,
    required this.accent,
  });

  final String label;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: accent,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

Color _activityMood(ActivityItemModel? activity) {
  final status = (activity?.status ?? '').toLowerCase();
  final confidence =
      activity?.confidenceMeter ?? activity?.confidence ?? ((activity?.readiness ?? 0) / 100);
  if (status.contains('almost') || confidence >= 0.75) {
    return TradingPalette.neonGreen;
  }
  if (status.contains('waiting')) {
    return TradingPalette.amber;
  }
  if (status.contains('rejected')) {
    return TradingPalette.neonRed;
  }
  return TradingPalette.electricBlue;
}

Color _readinessAccent(ReadinessCardModel card) {
  if (card.readiness >= 75) {
    return TradingPalette.neonGreen;
  }
  if (card.readiness >= 50) {
    return TradingPalette.amber;
  }
  return TradingPalette.electricBlue;
}

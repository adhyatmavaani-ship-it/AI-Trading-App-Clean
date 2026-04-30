import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_mapper.dart';
import '../core/error_presenter.dart';
import '../core/trading_palette.dart';
import '../features/activity/providers/activity_providers.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../models/activity.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import '../models/user_pnl.dart';
import '../providers/app_bootstrap_provider.dart';
import '../widgets/ai_explanation_panel.dart';
import '../widgets/ai_signal_card.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pulse_wrapper.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({
    super.key,
    required this.onOpenTrade,
    required this.onOpenSignals,
  });

  final ValueChanged<String> onOpenTrade;
  final VoidCallback onOpenSignals;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(activeUserIdProvider);
    final settings = ref.watch(appSettingsProvider);
    final settingsController = ref.read(appSettingsProvider.notifier);
    final pnlAsync = ref.watch(userPnLProvider(userId));
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final marketSummaryAsync = ref.watch(marketSummaryProvider);
    final marketUniverseAsync = ref.watch(marketUniverseProvider);
    final signalFeed = ref.watch(signalFeedProvider);
    final initialSignalsAsync = ref.watch(initialSignalsProvider);
    final activityFeed = ref.watch(activityFeedProvider);
    final initialActivityAsync = ref.watch(initialActivityHistoryProvider);

    final activeSignal = signalFeed.items.isNotEmpty
        ? signalFeed.items.first
        : initialSignalsAsync.valueOrNull?.firstOrNull;
    final newsItems = activityFeed.items.isNotEmpty
        ? activityFeed.items
        : (initialActivityAsync.valueOrNull ?? const <ActivityItemModel>[]);

    return RefreshIndicator(
      onRefresh: () async => _refresh(ref, userId),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1200;
          final tablet = constraints.maxWidth >= 760;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
            children: <Widget>[
              if (signalFeed.lastError != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: _InlineWarningBanner(
                    message: ErrorMapper.typeOf(signalFeed.lastError) ==
                            AppErrorType.network
                        ? 'Offline mode. Showing last known signals.'
                        : userMessageForError(signalFeed.lastError),
                  ),
                ),
              if (desktop)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(
                      flex: 7,
                      child: _buildBalanceColumn(
                        context,
                        pnlAsync,
                        activeTradesAsync,
                        onOpenTrade,
                      ),
                    ),
                    const SizedBox(width: 18),
                    Expanded(
                      flex: 5,
                      child: _buildSignalColumn(
                        context,
                        activeSignal,
                        onOpenTrade,
                        onOpenSignals,
                        settings.engineEnabled,
                        () => settingsController.saveEngineState(
                          userId,
                          enabled: !settings.engineEnabled,
                        ),
                      ),
                    ),
                  ],
                )
              else ...<Widget>[
                _buildBalanceColumn(
                  context,
                  pnlAsync,
                  activeTradesAsync,
                  onOpenTrade,
                ),
                const SizedBox(height: 18),
                _buildSignalColumn(
                  context,
                  activeSignal,
                  onOpenTrade,
                  onOpenSignals,
                  settings.engineEnabled,
                  () => settingsController.saveEngineState(
                    userId,
                    enabled: !settings.engineEnabled,
                  ),
                ),
              ],
              const SizedBox(height: 18),
              tablet
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: _buildSentimentPanel(marketSummaryAsync),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                          child: _buildTopMoversPanel(marketUniverseAsync),
                        ),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        _buildSentimentPanel(marketSummaryAsync),
                        const SizedBox(height: 18),
                        _buildTopMoversPanel(marketUniverseAsync),
                      ],
                    ),
              const SizedBox(height: 18),
              tablet
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: _buildActiveTradesPanel(
                            activeTradesAsync,
                            onOpenTrade,
                          ),
                        ),
                        const SizedBox(width: 18),
                        Expanded(child: _buildNewsPanel(newsItems)),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        _buildActiveTradesPanel(activeTradesAsync, onOpenTrade),
                        const SizedBox(height: 18),
                        _buildNewsPanel(newsItems),
                      ],
                    ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _refresh(WidgetRef ref, String userId) async {
    ref.read(appBootstrapProvider.notifier).refresh();
    ref.invalidate(userPnLProvider(userId));
    ref.invalidate(activeTradesProvider(userId));
    ref.invalidate(marketSummaryProvider);
    ref.invalidate(marketUniverseProvider);
    ref.invalidate(initialSignalsProvider);
    ref.invalidate(initialActivityHistoryProvider);
  }

  Widget _buildBalanceColumn(
    BuildContext context,
    AsyncValue<UserPnLModel> pnlAsync,
    AsyncValue<List<ActiveTradeModel>> activeTradesAsync,
    ValueChanged<String> onOpenTrade,
  ) {
    return Column(
      children: <Widget>[
        pnlAsync.when(
          data: (pnl) => _BalanceHeroCard(pnl: pnl),
          loading: () => const SectionCard(
            title: 'Balance Overview',
            subtitle: 'Loading live balance, today PnL, and equity graph.',
            child: LoadingState(label: 'Loading balance'),
          ),
          error: (error, _) => ErrorState(message: userMessageForError(error)),
        ),
        const SizedBox(height: 18),
        activeTradesAsync.when(
          data: (trades) => _QuickStatsRow(
            totalTrades: trades.length,
            riskExposure: trades.fold<double>(
              0,
              (sum, item) => sum + item.riskFraction,
            ),
          ),
          loading: () => const SizedBox(height: 110, child: LoadingState()),
          error: (error, _) => ErrorState(message: userMessageForError(error)),
        ),
      ],
    );
  }

  Widget _buildSignalColumn(
    BuildContext context,
    SignalModel? signal,
    ValueChanged<String> onOpenTrade,
    VoidCallback onOpenSignals,
    bool autoModeEnabled,
    VoidCallback onToggleAutoMode,
  ) {
    return SectionCard(
      title: 'AI Signal Deck',
      subtitle: 'Live websocket signal feed with confidence and reasons.',
      trailing: const LivePulseIndicator(),
      glowColor: TradingPalette.violet,
      child: signal == null
          ? const EmptyState(
              title: 'No live signal yet',
              subtitle:
                  'The AI engine is connected. New BUY or SELL opportunities will surface here automatically.',
            )
          : Column(
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: GradientActionButton(
                        label: autoModeEnabled
                            ? 'AI Trading Running'
                            : 'Start AI Trading',
                        icon: autoModeEnabled
                            ? Icons.pause_circle_outline_rounded
                            : Icons.play_circle_fill_rounded,
                        onPressed: onToggleAutoMode,
                        expanded: true,
                      ),
                    ),
                    const SizedBox(width: 12),
                    TextButton(
                      onPressed: onOpenSignals,
                      child: const Text('Open feed'),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 360),
                  transitionBuilder: (child, animation) {
                    return FadeTransition(
                      opacity: animation,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0.08, 0),
                          end: Offset.zero,
                        ).animate(animation),
                        child: child,
                      ),
                    );
                  },
                  child: KeyedSubtree(
                    key: ValueKey<String>(signal.signalId),
                    child: PulseWrapper(
                      child: AiSignalCard(
                        signal: signal,
                        onExecute: () => onOpenTrade(signal.symbol),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                AiExplanationPanel(signal: signal),
              ],
            ),
    );
  }

  Widget _buildSentimentPanel(AsyncValue<MarketSummaryModel> marketSummaryAsync) {
    return SectionCard(
      title: 'Market Sentiment',
      subtitle: 'Breadth, confidence, scanner pulse, and AI mood.',
      trailing: const StatusBadge(label: 'SCANNER'),
      glowColor: TradingPalette.electricBlue,
      child: marketSummaryAsync.when(
        data: (summary) => _MarketSentimentContent(summary: summary),
        loading: () => const LoadingState(label: 'Loading market summary'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildTopMoversPanel(
      AsyncValue<MarketUniverseModel> marketUniverseAsync) {
    return SectionCard(
      title: 'Top Gainers',
      subtitle: 'High momentum assets from the live market universe.',
      trailing: const StatusBadge(label: 'MOMENTUM'),
      glowColor: TradingPalette.neonGreen,
      child: marketUniverseAsync.when(
        data: (universe) {
          final movers = universe.topGainers.isNotEmpty
              ? universe.topGainers
              : universe.items.take(6).toList();
          if (movers.isEmpty) {
            return const EmptyState(
              title: 'No movers yet',
              subtitle: 'The market scanner has not published ranked gainers yet.',
            );
          }
          return Column(
            children: movers
                .take(6)
                .map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Row(
                      children: <Widget>[
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                item.symbol,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Vol ${item.volumeRatio.toStringAsFixed(2)}x  •  ${item.category}',
                                style: const TextStyle(
                                  color: TradingPalette.textFaint,
                                ),
                              ),
                            ],
                          ),
                        ),
                        Text(
                          '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
                          style: const TextStyle(
                            color: TradingPalette.neonGreen,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
                .toList(),
          );
        },
        loading: () => const LoadingState(label: 'Loading movers'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildActiveTradesPanel(
    AsyncValue<List<ActiveTradeModel>> activeTradesAsync,
    ValueChanged<String> onOpenTrade,
  ) {
    return SectionCard(
      title: 'Active Trades',
      subtitle: 'Open positions with live risk and target levels.',
      glowColor: TradingPalette.violet,
      child: activeTradesAsync.when(
        data: (trades) {
          if (trades.isEmpty) {
            return const EmptyState(
              title: 'No active trades',
              subtitle:
                  'When the AI desk opens new trades, they will appear here with SL, TP, and risk allocation.',
            );
          }
          return Column(
            children: trades
                .map(
                  (trade) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: InkWell(
                      onTap: () => onOpenTrade(trade.symbol),
                      borderRadius: BorderRadius.circular(18),
                      child: Ink(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: TradingPalette.overlay,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: TradingPalette.panelBorder),
                        ),
                        child: Row(
                          children: <Widget>[
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: trade.side.toUpperCase() == 'BUY'
                                    ? TradingPalette.neonGreen.withOpacity(0.14)
                                    : TradingPalette.neonRed.withOpacity(0.14),
                              ),
                              child: Icon(
                                trade.side.toUpperCase() == 'BUY'
                                    ? Icons.arrow_upward_rounded
                                    : Icons.arrow_downward_rounded,
                                color: trade.side.toUpperCase() == 'BUY'
                                    ? TradingPalette.neonGreen
                                    : TradingPalette.neonRed,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    '${trade.symbol} • ${trade.side}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Entry ${trade.entry.toStringAsFixed(4)}  •  TP ${trade.takeProfit.toStringAsFixed(4)}  •  SL ${trade.stopLoss.toStringAsFixed(4)}',
                                    style: const TextStyle(
                                      color: TradingPalette.textFaint,
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
                                  '${(trade.riskFraction * 100).toStringAsFixed(1)}%',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  trade.status,
                                  style: const TextStyle(
                                    color: TradingPalette.textFaint,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                )
                .toList(),
          );
        },
        loading: () => const LoadingState(label: 'Loading active trades'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildNewsPanel(List<ActivityItemModel> newsItems) {
    return SectionCard(
      title: 'AI News Feed',
      subtitle: 'Operator-grade live feed from the AI scanner and execution brain.',
      glowColor: TradingPalette.electricBlue,
      child: newsItems.isEmpty
          ? const EmptyState(
              title: 'No live feed yet',
              subtitle:
                  'Scanner activity, risk events, and AI reasoning updates will stream here once the backend publishes events.',
            )
          : Column(
              children: newsItems
                  .take(6)
                  .map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: TradingPalette.overlay,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: TradingPalette.panelBorder),
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Container(
                              width: 10,
                              height: 10,
                              margin: const EdgeInsets.only(top: 4),
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: _activityColor(item),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    item.symbol == null || item.symbol!.isEmpty
                                        ? item.botState
                                        : '${item.symbol} • ${item.botState}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    item.message,
                                    style: const TextStyle(
                                      color: TradingPalette.textMuted,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    _timeAgo(item.timestamp),
                                    style: const TextStyle(
                                      color: TradingPalette.textFaint,
                                      fontSize: 12,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
    );
  }
}

class _BalanceHeroCard extends StatelessWidget {
  const _BalanceHeroCard({required this.pnl});

  final UserPnLModel pnl;

  @override
  Widget build(BuildContext context) {
    final positive = pnl.absolutePnl >= 0;
    final accent = positive ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final chartValues = pnl.sparkline;
    final spots = chartValues
        .asMap()
        .entries
        .map((entry) => FlSpot(entry.key.toDouble(), entry.value))
        .toList();
    final minY = chartValues.reduce((a, b) => a < b ? a : b);
    final maxY = chartValues.reduce((a, b) => a > b ? a : b);

    return GlassPanel(
      glowColor: accent,
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Total Balance',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '\$${pnl.currentEquity.toStringAsFixed(2)}',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
              const Spacer(),
              StatusBadge(
                label: positive
                    ? '+${pnl.pnlPct.toStringAsFixed(2)}%'
                    : '${pnl.pnlPct.toStringAsFixed(2)}%',
                color: accent,
              ),
            ],
          ),
          const SizedBox(height: 18),
          SizedBox(
            height: 180,
            child: LineChart(
              LineChartData(
                minY: minY * 0.995,
                maxY: maxY * 1.005,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (_) => FlLine(
                    color: TradingPalette.glassHighlight.withOpacity(0.05),
                    strokeWidth: 1,
                  ),
                ),
                borderData: FlBorderData(show: false),
                titlesData: const FlTitlesData(
                  topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  bottomTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                lineBarsData: <LineChartBarData>[
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    color: accent,
                    barWidth: 3,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: <Color>[
                          accent.withOpacity(0.24),
                          Colors.transparent,
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _InfoPill(
                label: 'Today PnL',
                value: '\$${pnl.absolutePnl.toStringAsFixed(2)}',
              ),
              _InfoPill(
                label: 'Peak Equity',
                value: '\$${pnl.peakEquity.toStringAsFixed(2)}',
              ),
              _InfoPill(
                label: 'Protection',
                value: pnl.protectionState,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _QuickStatsRow extends StatelessWidget {
  const _QuickStatsRow({
    required this.totalTrades,
    required this.riskExposure,
  });

  final int totalTrades;
  final double riskExposure;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: _MiniMetricCard(
            label: 'Open Trades',
            value: totalTrades.toString(),
            icon: Icons.stacked_line_chart_rounded,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _MiniMetricCard(
            label: 'Risk Exposure',
            value: '${(riskExposure * 100).toStringAsFixed(1)}%',
            icon: Icons.security_rounded,
          ),
        ),
        const SizedBox(width: 12),
        const Expanded(
          child: _MiniMetricCard(
            label: 'Latency',
            value: 'Live',
            icon: Icons.speed_rounded,
          ),
        ),
      ],
    );
  }
}

class _MiniMetricCard extends StatelessWidget {
  const _MiniMetricCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.violet,
      padding: const EdgeInsets.all(16),
      child: Row(
        children: <Widget>[
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: TradingPalette.violet.withOpacity(0.14),
            ),
            child: Icon(icon, color: TradingPalette.violet, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(label, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MarketSentimentContent extends StatelessWidget {
  const _MarketSentimentContent({required this.summary});

  final MarketSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    final progress = (summary.sentimentScore / 100).clamp(0.0, 1.0);
    final color = summary.sentimentScore >= 65
        ? TradingPalette.neonGreen
        : summary.sentimentScore <= 40
            ? TradingPalette.neonRed
            : TradingPalette.electricBlue;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                summary.sentimentLabel,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w800,
                    ),
              ),
            ),
            Text(
              '${summary.sentimentScore.toStringAsFixed(0)}/100',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 10,
            backgroundColor: TradingPalette.panelBorder,
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _InfoPill(
              label: 'Breadth',
              value: '${summary.marketBreadth.toStringAsFixed(1)}%',
            ),
            _InfoPill(
              label: 'Avg Change',
              value: '${summary.avgChangePct.toStringAsFixed(2)}%',
            ),
            _InfoPill(
              label: 'Confidence',
              value: '${summary.confidenceScore.toStringAsFixed(0)}%',
            ),
              _InfoPill(
                label: 'Scanner Avg',
                value: summary.scanner.averagePotentialScore.toStringAsFixed(0),
              ),
          ],
        ),
      ],
    );
  }
}

class _InfoPill extends StatelessWidget {
  const _InfoPill({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _InlineWarningBanner extends StatelessWidget {
  const _InlineWarningBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.amber,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(Icons.warning_amber_rounded, color: TradingPalette.amber),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

Color _activityColor(ActivityItemModel item) {
  final text = item.status.toLowerCase();
  if (text.contains('reject') || text.contains('error')) {
    return TradingPalette.neonRed;
  }
  if (text.contains('execute') || text.contains('ready')) {
    return TradingPalette.neonGreen;
  }
  return TradingPalette.electricBlue;
}

String _timeAgo(DateTime timestamp) {
  final diff = DateTime.now().difference(timestamp.toLocal());
  if (diff.inMinutes < 1) {
    return 'just now';
  }
  if (diff.inHours < 1) {
    return '${diff.inMinutes}m ago';
  }
  return '${diff.inHours}h ago';
}

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

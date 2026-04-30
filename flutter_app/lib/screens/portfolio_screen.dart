import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_presenter.dart';
import '../core/trading_palette.dart';
import '../features/monitoring/providers/monitoring_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../models/active_trade.dart';
import '../models/portfolio_concentration.dart';
import '../models/user_pnl.dart';
import '../widgets/glass_panel.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';

class PortfolioScreen extends ConsumerWidget {
  const PortfolioScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(activeUserIdProvider);
    final pnlAsync = ref.watch(userPnLProvider(userId));
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final concentrationAsync = ref.watch(concentrationHistoryProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(userPnLProvider(userId));
        ref.invalidate(activeTradesProvider(userId));
        ref.invalidate(concentrationHistoryProvider);
      },
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 980;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
            children: <Widget>[
              pnlAsync.when(
                data: (pnl) => _PortfolioHero(pnl: pnl),
                loading: () => const LoadingState(label: 'Loading portfolio'),
                error: (error, _) =>
                    ErrorState(message: userMessageForError(error)),
              ),
              const SizedBox(height: 18),
              desktop
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: _buildAllocationPanel(activeTradesAsync),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                          child: _buildConcentrationPanel(concentrationAsync),
                        ),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        _buildAllocationPanel(activeTradesAsync),
                        const SizedBox(height: 18),
                        _buildConcentrationPanel(concentrationAsync),
                      ],
                    ),
              const SizedBox(height: 18),
              _buildHoldingsPanel(activeTradesAsync),
            ],
          );
        },
      ),
    );
  }

  Widget _buildAllocationPanel(AsyncValue<List<ActiveTradeModel>> activeTradesAsync) {
    return SectionCard(
      title: 'Allocation',
      subtitle: 'Live holding mix across open positions.',
      trailing: const StatusBadge(label: 'PIE'),
      glowColor: TradingPalette.violet,
      child: activeTradesAsync.when(
        data: (trades) {
          if (trades.isEmpty) {
            return const EmptyState(
              title: 'No holdings',
              subtitle: 'Open positions will appear here with live allocation share.',
            );
          }
          final total = trades.fold<double>(
            0,
            (sum, trade) => sum + (trade.entry * trade.executedQuantity),
          );
          final colors = <Color>[
            TradingPalette.violet,
            TradingPalette.electricBlue,
            TradingPalette.neonGreen,
            TradingPalette.amber,
            TradingPalette.neonRed,
          ];
          return Column(
            children: <Widget>[
              SizedBox(
                height: 220,
                child: PieChart(
                  PieChartData(
                    centerSpaceRadius: 56,
                    sectionsSpace: 3,
                    sections: trades.asMap().entries.map((entry) {
                      final index = entry.key;
                      final trade = entry.value;
                      final value = trade.entry * trade.executedQuantity;
                      final pct = total == 0 ? 0.0 : value / total;
                      return PieChartSectionData(
                        color: colors[index % colors.length],
                        value: value,
                        radius: 28,
                        title: '${(pct * 100).toStringAsFixed(0)}%',
                        titleStyle: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 12,
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: trades.asMap().entries.map((entry) {
                  final color = colors[entry.key % colors.length];
                  final trade = entry.value;
                  return Row(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: color,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(trade.symbol),
                    ],
                  );
                }).toList(),
              ),
            ],
          );
        },
        loading: () => const LoadingState(label: 'Loading holdings mix'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildConcentrationPanel(
    AsyncValue<PortfolioConcentrationHistoryModel> concentrationAsync,
  ) {
    return SectionCard(
      title: 'Risk Breakdown',
      subtitle: 'Concentration drift, turnover, and factor sleeve stress.',
      trailing: const StatusBadge(label: 'RISK'),
      glowColor: TradingPalette.electricBlue,
      child: concentrationAsync.when(
        data: (history) {
          final latest = history.latest;
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _RiskBreakdownChip(
                label: 'Gross Drift',
                value: '${(latest.grossExposureDrift * 100).toStringAsFixed(1)}%',
              ),
              _RiskBreakdownChip(
                label: 'Cluster Drift',
                value:
                    '${(latest.clusterConcentrationDrift * 100).toStringAsFixed(1)}%',
              ),
              _RiskBreakdownChip(
                label: 'Budget Turnover',
                value:
                    '${(latest.factorSleeveBudgetTurnover * 100).toStringAsFixed(1)}%',
              ),
              _RiskBreakdownChip(
                label: 'Regime',
                value: latest.factorRegime,
              ),
            ],
          );
        },
        loading: () => const LoadingState(label: 'Loading risk breakdown'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildHoldingsPanel(AsyncValue<List<ActiveTradeModel>> activeTradesAsync) {
    return SectionCard(
      title: 'Holdings',
      subtitle: 'Position-by-position exposure with execution context.',
      trailing: const StatusBadge(label: 'LIVE'),
      glowColor: TradingPalette.neonGreen,
      child: activeTradesAsync.when(
        data: (trades) {
          if (trades.isEmpty) {
            return const EmptyState(
              title: 'No open positions',
              subtitle: 'Portfolio holdings will populate here once trades execute.',
            );
          }
          return Column(
            children: trades
                .map(
                  (trade) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: GlassPanel(
                      glowColor: trade.side == 'BUY'
                          ? TradingPalette.neonGreen
                          : TradingPalette.neonRed,
                      padding: const EdgeInsets.all(16),
                      child: Row(
                        children: <Widget>[
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
                                const SizedBox(height: 6),
                                Text(
                                  'Qty ${trade.executedQuantity.toStringAsFixed(6)}  •  Entry ${trade.entry.toStringAsFixed(4)}',
                                  style: const TextStyle(
                                    color: TradingPalette.textMuted,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  trade.entryReason,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
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
                              const SizedBox(height: 6),
                              Text(
                                trade.regime,
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
                )
                .toList(),
          );
        },
        loading: () => const LoadingState(label: 'Loading holdings'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }
}

class _PortfolioHero extends StatelessWidget {
  const _PortfolioHero({required this.pnl});

  final UserPnLModel pnl;

  @override
  Widget build(BuildContext context) {
    final positive = pnl.absolutePnl >= 0;
    return GlassPanel(
      glowColor: positive ? TradingPalette.neonGreen : TradingPalette.neonRed,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Portfolio Overview',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              StatusBadge(
                label: positive
                    ? '+${pnl.pnlPct.toStringAsFixed(2)}%'
                    : '${pnl.pnlPct.toStringAsFixed(2)}%',
                color: positive
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _PortfolioMetric(label: 'Current Equity', value: '\$${pnl.currentEquity.toStringAsFixed(2)}'),
              _PortfolioMetric(label: 'Absolute PnL', value: '\$${pnl.absolutePnl.toStringAsFixed(2)}'),
              _PortfolioMetric(label: 'Drawdown', value: '${(pnl.rollingDrawdown * 100).toStringAsFixed(2)}%'),
              _PortfolioMetric(label: 'Protection', value: pnl.protectionState),
            ],
          ),
        ],
      ),
    );
  }
}

class _PortfolioMetric extends StatelessWidget {
  const _PortfolioMetric({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
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
          Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}

class _RiskBreakdownChip extends StatelessWidget {
  const _RiskBreakdownChip({
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
        borderRadius: BorderRadius.circular(14),
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

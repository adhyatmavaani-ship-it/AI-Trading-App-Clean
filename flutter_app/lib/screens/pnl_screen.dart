import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/pnl/providers/pnl_providers.dart';
import '../models/active_trade.dart';
import '../models/user_pnl.dart';
import '../widgets/metric_card.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';

class PnlScreen extends ConsumerWidget {
  const PnlScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(activeUserIdProvider);
    final pnlAsync = ref.watch(userPnLProvider(userId));
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final equityCurveAsync = ref.watch(equityCurveProvider(userId));

    return pnlAsync.when(
      loading: () => const LoadingState(label: 'Loading portfolio'),
      error: (error, _) => ErrorState(message: error.toString()),
      data: (pnl) => ListView(
        padding: const EdgeInsets.all(20),
        children: <Widget>[
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              MetricCard(
                label: 'Current Equity',
                value: '\$${pnl.currentEquity.toStringAsFixed(2)}',
                icon: Icons.account_balance_wallet_outlined,
              ),
              MetricCard(
                label: 'PnL',
                value: '\$${pnl.absolutePnl.toStringAsFixed(2)}',
                icon: Icons.trending_up_rounded,
              ),
              MetricCard(
                label: 'Drawdown',
                value: '${(pnl.rollingDrawdown * 100).toStringAsFixed(2)}%',
                icon: Icons.shield_outlined,
              ),
              MetricCard(
                label: 'Active Trades',
                value: pnl.activeTrades.toString(),
                icon: Icons.stacked_line_chart_rounded,
              ),
            ],
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Profit Curve',
            child: equityCurveAsync.when(
              data: (history) {
                final points = history.isEmpty ? <UserPnLModel>[pnl] : history;
                final spots = points
                    .asMap()
                    .entries
                    .map((entry) => FlSpot(
                          entry.key.toDouble(),
                          entry.value.currentEquity,
                        ))
                    .toList();
                final minY = points
                    .map((entry) => entry.currentEquity)
                    .reduce((a, b) => a < b ? a : b);
                final maxY = points
                    .map((entry) => entry.currentEquity)
                    .reduce((a, b) => a > b ? a : b);
                final curveColor = pnl.absolutePnl >= 0
                    ? const Color(0xFF66E0B4)
                    : const Color(0xFFFF8E72);
                return SizedBox(
                  height: 260,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'Live equity curve from backend polling',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: LineChart(
                          LineChartData(
                            minY: minY == maxY ? minY - 1 : minY * 0.999,
                            maxY: minY == maxY ? maxY + 1 : maxY * 1.001,
                            gridData: FlGridData(
                              show: true,
                              drawVerticalLine: false,
                              horizontalInterval:
                                  ((maxY - minY).abs() / 3).clamp(0.25, 5000),
                              getDrawingHorizontalLine: (_) => const FlLine(
                                color: Color(0xFF17343D),
                                strokeWidth: 1,
                              ),
                            ),
                            titlesData: FlTitlesData(
                              topTitles: const AxisTitles(
                                sideTitles: SideTitles(showTitles: false),
                              ),
                              rightTitles: const AxisTitles(
                                sideTitles: SideTitles(showTitles: false),
                              ),
                              leftTitles: AxisTitles(
                                sideTitles: SideTitles(
                                  showTitles: true,
                                  reservedSize: 52,
                                  getTitlesWidget: (value, meta) => Text(
                                    value.toStringAsFixed(0),
                                    style:
                                        Theme.of(context).textTheme.labelSmall,
                                  ),
                                ),
                              ),
                              bottomTitles: AxisTitles(
                                sideTitles: SideTitles(
                                  showTitles: true,
                                  interval: spots.length > 6
                                      ? (spots.length / 3)
                                      : 1,
                                  getTitlesWidget: (value, meta) {
                                    return Text(
                                      value.toInt() == spots.length - 1
                                          ? 'Now'
                                          : 'T${value.toInt() + 1}',
                                      style: Theme.of(context)
                                          .textTheme
                                          .labelSmall,
                                    );
                                  },
                                ),
                              ),
                            ),
                            borderData: FlBorderData(show: false),
                            lineTouchData: LineTouchData(
                              touchTooltipData: LineTouchTooltipData(
                                getTooltipItems: (spots) => spots
                                    .map(
                                      (spot) => LineTooltipItem(
                                        '\$${spot.y.toStringAsFixed(2)}',
                                        Theme.of(context)
                                            .textTheme
                                            .labelMedium!
                                            .copyWith(color: Colors.white),
                                      ),
                                    )
                                    .toList(),
                              ),
                            ),
                            lineBarsData: <LineChartBarData>[
                              LineChartBarData(
                                isCurved: true,
                                barWidth: 3,
                                color: curveColor,
                                dotData: FlDotData(
                                  show: spots.length <= 2,
                                ),
                                belowBarData: BarAreaData(
                                  show: true,
                                  gradient: LinearGradient(
                                    colors: <Color>[
                                      // ignore: deprecated_member_use
                                      curveColor.withOpacity(0.28),
                                      Colors.transparent,
                                    ],
                                    begin: Alignment.topCenter,
                                    end: Alignment.bottomCenter,
                                  ),
                                ),
                                spots: spots,
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
              loading: () => SizedBox(
                height: 240,
                child: Center(
                  child: Text(
                    'Building live equity history...',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              ),
              error: (error, _) => ErrorState(message: error.toString()),
            ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Daily Stats',
            child: Column(
              children: <Widget>[
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Protection State'),
                  trailing: Text(pnl.protectionState),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Capital Multiplier'),
                  trailing: Text(
                      '${(pnl.capitalMultiplier * 100).toStringAsFixed(0)}%'),
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Peak Equity'),
                  trailing: Text('\$${pnl.peakEquity.toStringAsFixed(2)}'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Active Positions',
            child: activeTradesAsync.when(
              data: (trades) {
                if (trades.isEmpty) {
                  return const EmptyState(
                    title: 'No active positions',
                    subtitle:
                        'Open paper or live trades will appear here automatically.',
                  );
                }
                return Column(
                  children: trades
                      .map((trade) => _ActiveTradeTile(trade: trade))
                      .toList(),
                );
              },
              loading: () =>
                  const LoadingState(label: 'Loading active positions'),
              error: (error, _) => ErrorState(message: error.toString()),
            ),
          ),
        ],
      ),
    );
  }
}

class _ActiveTradeTile extends StatelessWidget {
  const _ActiveTradeTile({required this.trade});

  final ActiveTradeModel trade;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text('${trade.symbol} ${trade.side}'),
      subtitle: Text(
        'Entry ${trade.entry.toStringAsFixed(4)}  |  SL ${trade.stopLoss.toStringAsFixed(4)}'
        '  |  Qty ${trade.executedQuantity.toStringAsFixed(6)}',
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: <Widget>[
          Text(
            '${(trade.riskFraction * 100).toStringAsFixed(2)}%',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          Text(
            trade.status,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

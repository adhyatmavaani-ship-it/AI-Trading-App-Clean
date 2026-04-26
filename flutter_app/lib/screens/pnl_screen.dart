import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/pnl/providers/pnl_providers.dart';
import '../widgets/metric_card.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';

class PnlScreen extends ConsumerWidget {
  const PnlScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(activeUserIdProvider);
    final pnlAsync = ref.watch(userPnLProvider(userId));

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
            child: SizedBox(
              height: 240,
              child: LineChart(
                LineChartData(
                  gridData: const FlGridData(show: false),
                  titlesData: const FlTitlesData(show: false),
                  borderData: FlBorderData(show: false),
                  lineBarsData: <LineChartBarData>[
                    LineChartBarData(
                      isCurved: true,
                      barWidth: 3,
                      color: const Color(0xFF66E0B4),
                      dotData: const FlDotData(show: false),
                      belowBarData: BarAreaData(
                        show: true,
                        gradient: LinearGradient(
                          colors: <Color>[
                            const Color(0xFF66E0B4).withOpacity(0.25),
                            Colors.transparent,
                          ],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ),
                      ),
                      spots: pnl.sparkline
                          .asMap()
                          .entries
                          .map((entry) =>
                              FlSpot(entry.key.toDouble(), entry.value))
                          .toList(),
                    ),
                  ],
                ),
              ),
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
        ],
      ),
    );
  }
}

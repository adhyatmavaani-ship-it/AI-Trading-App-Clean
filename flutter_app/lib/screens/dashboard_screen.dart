import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/public/providers/trust_dashboard_provider.dart';
import '../models/public_dashboard.dart';
import '../services/share_card_service.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/trust_share_card.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dashboardAsync = ref.watch(trustDashboardProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(trustDashboardProvider);
      },
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: <Widget>[
          dashboardAsync.when(
            loading: () => const SizedBox(
              height: 420,
              child: LoadingState(label: 'Loading trust dashboard'),
            ),
            error: (error, _) => ErrorState(
              message: error.toString(),
              onRetry: () => ref.invalidate(trustDashboardProvider),
            ),
            data: (dashboard) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _PerformanceHero(
                  performance: dashboard.performance,
                  onShare: () => _openShareSheet(
                    context,
                    performance: dashboard.performance,
                  ),
                ),
                const SizedBox(height: 20),
                SectionCard(
                  title: 'Daily Performance',
                  child: _DailyPerformanceChart(points: dashboard.daily),
                ),
                const SizedBox(height: 20),
                SectionCard(
                  title: 'Recent Closed Trades',
                  trailing:
                      _HeaderChip(label: '${dashboard.trades.length} shown'),
                  child: dashboard.trades.isEmpty
                      ? const EmptyState(
                          title: 'No closed trades yet',
                          subtitle:
                              'Closed trade proofs will appear here automatically.',
                        )
                      : Column(
                          children: dashboard.trades
                              .map((trade) => _PublicTradeTile(trade: trade))
                              .toList(),
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openShareSheet(
    BuildContext context, {
    required PublicPerformanceModel performance,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF0B171D),
      isScrollControlled: true,
      builder: (context) {
        return _ShareSheet(performance: performance);
      },
    );
  }
}

class _ShareSheet extends StatefulWidget {
  const _ShareSheet({required this.performance});

  final PublicPerformanceModel performance;

  @override
  State<_ShareSheet> createState() => _ShareSheetState();
}

class _ShareSheetState extends State<_ShareSheet> {
  final GlobalKey _cardKey = GlobalKey();
  final ShareCardService _shareCardService = const ShareCardService();
  bool _isSharing = false;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                const Expanded(
                  child: Text(
                    'Share Performance Card',
                    style: TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Optimized for WhatsApp, Instagram, and Telegram via the native share sheet.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: const Color(0xFF9CB3C8),
                  ),
            ),
            const SizedBox(height: 18),
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 320),
                child: RepaintBoundary(
                  key: _cardKey,
                  child: TrustShareCard(
                    performance: widget.performance,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: <Widget>[
                _TargetChip(
                  label: 'WhatsApp',
                  icon: Icons.chat_bubble_outline,
                  onTap: _isSharing ? null : () => _share(target: 'WhatsApp'),
                ),
                _TargetChip(
                  label: 'Instagram',
                  icon: Icons.camera_alt_outlined,
                  onTap: _isSharing ? null : () => _share(target: 'Instagram'),
                ),
                _TargetChip(
                  label: 'Telegram',
                  icon: Icons.send_outlined,
                  onTap: _isSharing ? null : () => _share(target: 'Telegram'),
                ),
              ],
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: _isSharing ? null : () => _share(),
                icon: _isSharing
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.ios_share_rounded),
                label: Text(_isSharing ? 'Preparing card...' : 'Share Image'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _share({String? target}) async {
    final boundary =
        _cardKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
    if (boundary == null) {
      return;
    }
    setState(() {
      _isSharing = true;
    });
    try {
      final pct = _formatPct(widget.performance.totalPnlPct);
      final winRate = (widget.performance.winRate * 100).toStringAsFixed(0);
      final intro = target == null
          ? 'AI Profit Today: $pct'
          : 'AI Profit Today: $pct\nReady to post on $target';
      await _shareCardService.sharePerformanceCard(
        boundary: boundary,
        message:
            '$intro\nWin Rate: $winRate%\nShared from AI Crypto Pulse.',
      );
      if (mounted) {
        Navigator.of(context).pop();
      }
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Unable to share card: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSharing = false;
        });
      }
    }
  }
}

class _PerformanceHero extends StatelessWidget {
  const _PerformanceHero({
    required this.performance,
    required this.onShare,
  });

  final PublicPerformanceModel performance;
  final VoidCallback onShare;

  @override
  Widget build(BuildContext context) {
    final pnlColor = performance.totalPnlPct >= 0
        ? const Color(0xFF7CE7A0)
        : const Color(0xFFFF8A80);
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF0E1D24),
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: const Color(0xFF1B3741)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Expanded(
                child: Text(
                  'Trust Dashboard',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              IconButton.filledTonal(
                onPressed: onShare,
                icon: const Icon(Icons.ios_share_rounded),
                tooltip: 'Share performance card',
              ),
              const SizedBox(width: 8),
              _HeaderChip(label: _formatTimestamp(performance.lastUpdated)),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            _formatPct(performance.totalPnlPct),
            style: TextStyle(
              fontSize: 38,
              fontWeight: FontWeight.w800,
              color: pnlColor,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Today PnL',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF9CB3C8),
                ),
          ),
          const SizedBox(height: 20),
          Row(
            children: <Widget>[
              Expanded(
                child: _SummaryMetric(
                  label: 'Win Rate',
                  value: '${(performance.winRate * 100).toStringAsFixed(1)}%',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _SummaryMetric(
                  label: 'Total Profit',
                  value: _formatPct(performance.totalPnlPct),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _SummaryMetric(
                  label: 'Closed Trades',
                  value: performance.totalTrades.toString(),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF11262E),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: const Color(0xFF8AA4B3),
                ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _DailyPerformanceChart extends StatelessWidget {
  const _DailyPerformanceChart({required this.points});

  final List<PublicDailyPointModel> points;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return const EmptyState(
        title: 'No daily history yet',
        subtitle:
            'Daily performance snapshots will appear here once the first close cycle is recorded.',
      );
    }

    final spots = <FlSpot>[
      for (var i = 0; i < points.length; i += 1)
        FlSpot(i.toDouble(), points[i].pnlPct),
    ];
    final values = points.map((point) => point.pnlPct).toList();
    final minY = values.reduce((a, b) => a < b ? a : b);
    final maxY = values.reduce((a, b) => a > b ? a : b);
    final chartColor = values.last >= 0
        ? const Color(0xFF7CE7A0)
        : const Color(0xFFFF8A80);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          height: 220,
          child: LineChart(
            LineChartData(
              minY: minY == maxY ? minY - 1 : minY - 0.5,
              maxY: minY == maxY ? maxY + 1 : maxY + 0.5,
              gridData: FlGridData(
                show: true,
                drawVerticalLine: false,
                horizontalInterval:
                    ((maxY - minY).abs() / 4).clamp(0.5, 5).toDouble(),
                getDrawingHorizontalLine: (_) => const FlLine(
                  color: Color(0xFF17303A),
                  strokeWidth: 1,
                ),
              ),
              borderData: FlBorderData(show: false),
              titlesData: FlTitlesData(
                leftTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    reservedSize: 42,
                    getTitlesWidget: (value, meta) => Text(
                      '${value.toStringAsFixed(0)}%',
                      style: const TextStyle(
                        color: Color(0xFF7F95A3),
                        fontSize: 11,
                      ),
                    ),
                  ),
                ),
                rightTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                topTitles: const AxisTitles(
                  sideTitles: SideTitles(showTitles: false),
                ),
                bottomTitles: AxisTitles(
                  sideTitles: SideTitles(
                    showTitles: true,
                    interval: points.length > 6
                        ? (points.length / 4).floorToDouble()
                        : 1,
                    getTitlesWidget: (value, meta) {
                      final index = value.toInt();
                      if (index < 0 || index >= points.length) {
                        return const SizedBox.shrink();
                      }
                      final date = points[index].date;
                      final label = date.length >= 5 ? date.substring(5) : date;
                      return Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text(
                          label,
                          style: const TextStyle(
                            color: Color(0xFF7F95A3),
                            fontSize: 11,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
              lineBarsData: <LineChartBarData>[
                LineChartBarData(
                  spots: spots,
                  isCurved: true,
                  color: chartColor,
                  barWidth: 3,
                  dotData: FlDotData(show: spots.length <= 10),
                  belowBarData: BarAreaData(
                    show: true,
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: <Color>[
                        chartColor.withAlpha(56),
                        chartColor.withAlpha(6),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 14),
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                '30-day readout',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: const Color(0xFF9CB3C8),
                    ),
              ),
            ),
            Text(
              'Latest ${_formatPct(points.last.pnlPct)}',
              style: TextStyle(
                color: chartColor,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _PublicTradeTile extends StatelessWidget {
  const _PublicTradeTile({required this.trade});

  final PublicTradeModel trade;

  @override
  Widget build(BuildContext context) {
    final accent = trade.isPositive
        ? const Color(0xFF7CE7A0)
        : const Color(0xFFFF8A80);
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF11262E),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF173642)),
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 4,
            height: 46,
            decoration: BoxDecoration(
              color: accent,
              borderRadius: BorderRadius.circular(99),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: Text(
                        trade.symbol,
                        style: const TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    _HeaderChip(label: trade.side),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'Entry ${trade.entry.toStringAsFixed(2)} | Exit ${trade.exit.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: const Color(0xFF9CB3C8),
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
                _formatPct(trade.pnlPct),
                style: TextStyle(
                  color: accent,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                trade.status,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: accent,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeaderChip extends StatelessWidget {
  const _HeaderChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF153540),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: const Color(0xFFB7D3E0),
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _TargetChip extends StatelessWidget {
  const _TargetChip({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(999),
        child: Ink(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF11262E),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: const Color(0xFF173642)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon, size: 16, color: const Color(0xFFB7D3E0)),
              const SizedBox(width: 8),
              Text(label),
            ],
          ),
        ),
      ),
    );
  }
}

String _formatPct(double value) {
  final sign = value >= 0 ? '+' : '';
  return '$sign${value.toStringAsFixed(1)}%';
}

String _formatTimestamp(DateTime timestamp) {
  final local = timestamp.toLocal();
  final month = local.month.toString().padLeft(2, '0');
  final day = local.day.toString().padLeft(2, '0');
  final hour = local.hour.toString().padLeft(2, '0');
  final minute = local.minute.toString().padLeft(2, '0');
  return '$month/$day $hour:$minute';
}

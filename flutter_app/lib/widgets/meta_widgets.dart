import 'package:flutter/material.dart';

import '../models/meta_analytics.dart';
import '../models/meta_decision.dart';
import 'section_card.dart';

class MetaDecisionCard extends StatelessWidget {
  const MetaDecisionCard({
    super.key,
    required this.metaDecision,
    this.compact = false,
  });

  final MetaDecisionModel metaDecision;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final accent = metaDecision.isBlocked
        ? const Color(0xFFFF8E72)
        : const Color(0xFF68E3C4);
    final health = metaDecision.systemHealthSnapshot;
    final riskItems = metaDecision.riskAdjustments.entries.toList();
    final signalItems = metaDecision.signals.entries.toList();
    return SectionCard(
      title: metaDecision.isBlocked ? 'Blocked Trade' : 'Meta Decision',
      trailing: _StatusBadge(
        label: metaDecision.decision,
        color: accent,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: _MetaHeadline(
                  strategy: metaDecision.strategy,
                  reason: metaDecision.reason,
                ),
              ),
              const SizedBox(width: 16),
              SizedBox(
                width: compact ? 110 : 140,
                child: _ConfidenceBar(
                  value: metaDecision.normalizedConfidence,
                  accent: accent,
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (metaDecision.conflicts.isNotEmpty) ...<Widget>[
            BlockedTradeCard(
              reason: metaDecision.reason,
              conflicts: metaDecision.conflicts,
            ),
            const SizedBox(height: 16),
          ],
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _InfoChip(
                icon: Icons.auto_awesome_rounded,
                label: 'Strategy',
                value: metaDecision.strategy,
              ),
              _InfoChip(
                icon: Icons.health_and_safety_outlined,
                label: 'Health',
                value: (health['healthy'] ?? false) ? 'Stable' : 'Watch',
              ),
              if (health['execution_latency_ms'] != null)
                _InfoChip(
                  icon: Icons.speed_rounded,
                  label: 'Latency',
                  value:
                      '${(health['execution_latency_ms'] as num).toStringAsFixed(0)} ms',
                ),
              if (health['api_success_rate'] != null)
                _InfoChip(
                  icon: Icons.cloud_done_outlined,
                  label: 'API',
                  value:
                      '${(((health['api_success_rate'] as num).toDouble()) * 100).toStringAsFixed(0)}%',
                ),
            ],
          ),
          if (!compact) ...<Widget>[
            const SizedBox(height: 18),
            _KeyValueGrid(
              title: 'Risk Adjustments',
              items: riskItems
                  .map((entry) =>
                      MapEntry(_prettify(entry.key), _formatValue(entry.value)))
                  .toList(),
            ),
            const SizedBox(height: 14),
            _KeyValueGrid(
              title: 'Signals',
              items: signalItems
                  .map((entry) =>
                      MapEntry(_prettify(entry.key), _formatValue(entry.value)))
                  .toList(),
            ),
            const SizedBox(height: 14),
            _KeyValueGrid(
              title: 'System Health',
              items: health.entries
                  .where((entry) => entry.key != 'reasons')
                  .map((entry) =>
                      MapEntry(_prettify(entry.key), _formatValue(entry.value)))
                  .toList(),
            ),
          ],
        ],
      ),
    );
  }
}

class BlockedTradeCard extends StatelessWidget {
  const BlockedTradeCard({
    super.key,
    required this.reason,
    required this.conflicts,
  });

  final String reason;
  final List<String> conflicts;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF2A1918),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF61302A)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              const Icon(
                Icons.block_rounded,
                color: Color(0xFFFF8E72),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  reason,
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
            ],
          ),
          if (conflicts.isNotEmpty) ...<Widget>[
            const SizedBox(height: 12),
            ...conflicts.map(
              (conflict) => Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const Padding(
                      padding: EdgeInsets.only(top: 6),
                      child: Icon(
                        Icons.fiber_manual_record_rounded,
                        size: 10,
                        color: Color(0xFFFF8E72),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(child: Text(conflict)),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class MetaPulseSummaryCard extends StatelessWidget {
  const MetaPulseSummaryCard({
    super.key,
    required this.analytics,
  });

  final MetaAnalyticsModel analytics;

  @override
  Widget build(BuildContext context) {
    final topStrategy = analytics.strategyPerformance.entries.isEmpty
        ? null
        : (analytics.strategyPerformance.entries.toList()
              ..sort((a, b) => b.value.winRate.compareTo(a.value.winRate)))
            .first;
    final topConflict = analytics.blockedTrades.reasons.entries.isEmpty
        ? null
        : (analytics.blockedTrades.reasons.entries.toList()
              ..sort((a, b) => b.value.compareTo(a.value)))
            .first;
    return SectionCard(
      title: 'Meta Pulse',
      trailing: _StatusBadge(
        label: '${analytics.totalBlockedTrades} blocked',
        color: const Color(0xFFFFC36C),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _SummaryMetric(
                label: 'Executed',
                value: analytics.totalExecutedTrades.toString(),
                icon: Icons.play_arrow_rounded,
              ),
              _SummaryMetric(
                label: 'Blocked',
                value: analytics.totalBlockedTrades.toString(),
                icon: Icons.shield_outlined,
              ),
              _SummaryMetric(
                label: 'Best Strategy',
                value: topStrategy?.key ?? 'Waiting',
                icon: Icons.insights_outlined,
              ),
            ],
          ),
          if (topConflict != null) ...<Widget>[
            const SizedBox(height: 16),
            Text(
              'Top conflict',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 6),
            Text(
              '${topConflict.key} (${topConflict.value})',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ],
      ),
    );
  }
}

class ConfidenceDistributionCard extends StatelessWidget {
  const ConfidenceDistributionCard({
    super.key,
    required this.distribution,
  });

  final Map<String, int> distribution;

  @override
  Widget build(BuildContext context) {
    final total = distribution.values.fold<int>(0, (sum, value) => sum + value);
    return SectionCard(
      title: 'Confidence Distribution',
      child: Column(
        children: distribution.entries.map((entry) {
          final share = total == 0 ? 0.0 : entry.value / total;
          return Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(child: Text(entry.key.replaceAll('_', '-'))),
                    Text('${entry.value}'),
                  ],
                ),
                const SizedBox(height: 6),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: share,
                    minHeight: 8,
                    backgroundColor: const Color(0xFF17303B),
                    valueColor: const AlwaysStoppedAnimation<Color>(
                      Color(0xFF68E3C4),
                    ),
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class StrategyPerformanceCard extends StatelessWidget {
  const StrategyPerformanceCard({
    super.key,
    required this.analytics,
  });

  final MetaAnalyticsModel analytics;

  @override
  Widget build(BuildContext context) {
    final items = analytics.strategyPerformance.entries.toList()
      ..sort((a, b) => b.value.trades.compareTo(a.value.trades));
    return SectionCard(
      title: 'Strategy Performance',
      child: items.isEmpty
          ? const Text('No strategy performance data yet.')
          : Column(
              children: items.map((entry) {
                final strategy = entry.value;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(14),
                      color: const Color(0xFF0A171C),
                      border: Border.all(color: const Color(0xFF1B3741)),
                    ),
                    child: Row(
                      children: <Widget>[
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                entry.key,
                                style: Theme.of(context).textTheme.titleSmall,
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Win rate ${(strategy.winRate * 100).toStringAsFixed(0)}%',
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                        _MiniStat(
                            label: 'Trades', value: strategy.trades.toString()),
                        const SizedBox(width: 14),
                        _MiniStat(
                            label: 'Blocked',
                            value: strategy.blocked.toString()),
                        const SizedBox(width: 14),
                        _MiniStat(
                            label: 'PnL',
                            value: strategy.pnl.toStringAsFixed(2)),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
    );
  }
}

class BlockedVsExecutedCard extends StatelessWidget {
  const BlockedVsExecutedCard({
    super.key,
    required this.analytics,
  });

  final MetaAnalyticsModel analytics;

  @override
  Widget build(BuildContext context) {
    final total = analytics.totalBlockedTrades + analytics.totalExecutedTrades;
    final blockedShare =
        total == 0 ? 0.0 : analytics.totalBlockedTrades / total;
    return SectionCard(
      title: 'Blocked vs Executed',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: _SummaryMetric(
                  label: 'Executed',
                  value: analytics.totalExecutedTrades.toString(),
                  icon: Icons.check_circle_outline,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _SummaryMetric(
                  label: 'Blocked',
                  value: analytics.totalBlockedTrades.toString(),
                  icon: Icons.block_outlined,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: blockedShare,
              minHeight: 10,
              backgroundColor: const Color(0xFF153540),
              valueColor: const AlwaysStoppedAnimation<Color>(
                Color(0xFFFF9A77),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetaHeadline extends StatelessWidget {
  const _MetaHeadline({
    required this.strategy,
    required this.reason,
  });

  final String strategy;
  final String reason;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          strategy,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 6),
        Text(
          reason,
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }
}

class _ConfidenceBar extends StatelessWidget {
  const _ConfidenceBar({
    required this.value,
    required this.accent,
  });

  final double value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        Text(
          '${(value * 100).toStringAsFixed(0)}%',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: accent,
              ),
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: value,
            minHeight: 9,
            backgroundColor: const Color(0xFF17303B),
            valueColor: AlwaysStoppedAnimation<Color>(accent),
          ),
        ),
      ],
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF0A171C),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1B3741)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: 16, color: const Color(0xFF9FD8FF)),
          const SizedBox(width: 8),
          Text('$label: $value'),
        ],
      ),
    );
  }
}

class _KeyValueGrid extends StatelessWidget {
  const _KeyValueGrid({
    required this.title,
    required this.items,
  });

  final String title;
  final List<MapEntry<String, String>> items;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 10),
        if (items.isEmpty)
          Text(
            'No data available.',
            style: Theme.of(context).textTheme.bodySmall,
          )
        else
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: items
                .map(
                  (item) => Container(
                    constraints:
                        const BoxConstraints(minWidth: 140, maxWidth: 220),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0A171C),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: const Color(0xFF18323A)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          item.key,
                          style: Theme.of(context).textTheme.labelMedium,
                        ),
                        const SizedBox(height: 6),
                        Text(
                          item.value,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                )
                .toList(),
          ),
      ],
    );
  }
}

class _StatusBadge extends StatelessWidget {
  const _StatusBadge({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.45)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 120),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: const Color(0xFF0A171C),
        border: Border.all(color: const Color(0xFF1B3741)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, size: 18, color: const Color(0xFF9FD8FF)),
          const SizedBox(height: 10),
          Text(label, style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 4),
          Text(value, style: Theme.of(context).textTheme.titleMedium),
        ],
      ),
    );
  }
}

class _MiniStat extends StatelessWidget {
  const _MiniStat({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        Text(label, style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 4),
        Text(value, style: Theme.of(context).textTheme.titleSmall),
      ],
    );
  }
}

String _prettify(String input) {
  return input.replaceAll('_', ' ').replaceAllMapped(
        RegExp(r'(^\w)|(\s+\w)'),
        (match) => match.group(0)!.toUpperCase(),
      );
}

String _formatValue(dynamic value) {
  if (value is num) {
    if (value.abs() >= 100) {
      return value.toStringAsFixed(0);
    }
    return value.toStringAsFixed(2);
  }
  if (value is bool) {
    return value ? 'Yes' : 'No';
  }
  if (value is Map<String, dynamic>) {
    return value.entries
        .map((entry) => '${_prettify(entry.key)}: ${_formatValue(entry.value)}')
        .join(' | ');
  }
  return value.toString();
}

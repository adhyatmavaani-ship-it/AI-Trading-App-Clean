import 'package:flutter/material.dart';

import '../models/public_dashboard.dart';

class TrustShareCard extends StatelessWidget {
  const TrustShareCard({
    super.key,
    required this.performance,
  });

  final PublicPerformanceModel performance;

  @override
  Widget build(BuildContext context) {
    final positive = performance.totalPnlPct >= 0;
    final accent = positive
        ? const Color(0xFF7CE7A0)
        : const Color(0xFFFF8A80);
    final secondary = positive
        ? const Color(0xFF1D5B43)
        : const Color(0xFF6A2A2A);

    return AspectRatio(
      aspectRatio: 4 / 5,
      child: Container(
        padding: const EdgeInsets.all(28),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              const Color(0xFF0E1D24),
              const Color(0xFF122B35),
              secondary.withAlpha(120),
            ],
          ),
          border: Border.all(color: const Color(0xFF214250)),
          boxShadow: const <BoxShadow>[
            BoxShadow(
              color: Color(0x66050A0D),
              blurRadius: 24,
              offset: Offset(0, 16),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: const Color(0xFF153540),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Icon(
                    Icons.auto_graph_rounded,
                    color: accent,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        'AI Crypto Pulse',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Trust Dashboard',
                        style: TextStyle(
                          fontSize: 12,
                          color: Color(0xFF9CB3C8),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const Spacer(),
            Text(
              'AI Profit Today',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: const Color(0xFFD7E5EE),
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 10),
            Text(
              _formatPct(performance.totalPnlPct),
              style: TextStyle(
                fontSize: 46,
                fontWeight: FontWeight.w900,
                color: accent,
                height: 1,
              ),
            ),
            const SizedBox(height: 26),
            Row(
              children: <Widget>[
                Expanded(
                  child: _ShareMetric(
                    label: 'Win Rate',
                    value:
                        '${(performance.winRate * 100).toStringAsFixed(0)}%',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ShareMetric(
                    label: 'Closed Trades',
                    value: performance.totalTrades.toString(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _ShareMetric(
              label: 'Updated',
              value: _formatTimestamp(performance.lastUpdated),
            ),
            const Spacer(),
            Row(
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xFF17303A),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: const Text(
                    'Verified public data',
                    style: TextStyle(
                      color: Color(0xFFB9D3DF),
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  '@AICryptoPulse',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: const Color(0xFF8AA4B3),
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ShareMetric extends StatelessWidget {
  const _ShareMetric({
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
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF193944)),
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
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
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

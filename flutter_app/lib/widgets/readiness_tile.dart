import 'package:flutter/material.dart';

import '../models/activity.dart';

class ReadinessTile extends StatelessWidget {
  const ReadinessTile({
    super.key,
    required this.card,
  });

  final ReadinessCardModel card;

  Color _accentColor() {
    if (card.readiness >= 70) {
      return const Color(0xFF4DE2B1);
    }
    if (card.readiness >= 40) {
      return const Color(0xFFFFD28A);
    }
    return const Color(0xFF93A9BD);
  }

  String _statusLabel() {
    switch (card.status) {
      case 'almost_trade':
        return 'Almost Ready';
      case 'opportunity_found':
        return 'Executing';
      default:
        return card.status.replaceAll('_', ' ');
    }
  }

  @override
  Widget build(BuildContext context) {
    final accent = _accentColor();
    return Container(
      width: 240,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFF1F424D)),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF112A32), Color(0xFF0B1A21)],
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  card.symbol,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Text(
                card.readiness.toStringAsFixed(0),
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: accent,
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            _statusLabel(),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: accent,
                ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: (card.readiness / 100).clamp(0, 1),
              backgroundColor: const Color(0xFF19313A),
              color: accent,
              minHeight: 8,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            card.intent ?? card.message ?? 'Setup building',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 8),
          Text(
            card.reason ?? 'Monitoring for cleaner confluence',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: const Color(0xFF9CB3C8),
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              if (card.regime != null && card.regime!.isNotEmpty)
                Chip(
                  label: Text(card.regime!),
                  backgroundColor: const Color(0xFF153540),
                ),
              if (card.confidence != null)
                Chip(
                  label: Text(
                    'Conf ${(card.confidence! * 100).toStringAsFixed(0)}%',
                  ),
                  backgroundColor: const Color(0xFF173A2F),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

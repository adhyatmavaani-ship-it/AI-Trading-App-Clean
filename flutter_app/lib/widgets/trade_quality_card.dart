import 'package:flutter/material.dart';

import '../core/trading_palette.dart';
import 'glass_panel.dart';

class TradeQualityCard extends StatelessWidget {
  final double confidence;
  final double rr;

  const TradeQualityCard({
    super.key,
    required this.confidence,
    required this.rr,
  });

  @override
  Widget build(BuildContext context) {
    final quality = confidence >= 0.78
        ? 'HIGH'
        : confidence >= 0.62
            ? 'MEDIUM'
            : 'LOW';
    return GlassPanel(
      glowColor: TradingPalette.violet,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Text(
            'TRADE QUALITY',
            style: TextStyle(
              letterSpacing: 1.2,
              color: TradingPalette.textMuted,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            quality,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Win Probability: ${(confidence * 100).toStringAsFixed(0)}%',
          ),
          const SizedBox(height: 4),
          Text('Expected RR: 1:${rr.toStringAsFixed(2)}'),
        ],
      ),
    );
  }
}

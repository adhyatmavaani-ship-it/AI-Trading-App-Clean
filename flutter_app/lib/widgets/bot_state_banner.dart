import 'package:flutter/material.dart';

import '../core/trading_palette.dart';
import '../models/activity.dart';

class BotStateBanner extends StatelessWidget {
  const BotStateBanner({
    super.key,
    required this.activity,
  });

  final ActivityItemModel activity;

  Color _accentColor() {
    switch (activity.botState) {
      case 'EXECUTING':
        return TradingPalette.neonGreen;
      case 'ANALYZING':
        return TradingPalette.electricBlue;
      case 'SCANNING':
        return TradingPalette.amber;
      default:
        return TradingPalette.textMuted;
    }
  }

  @override
  Widget build(BuildContext context) {
    final accent = _accentColor();
    final readiness = activity.readiness?.toStringAsFixed(0) ?? '--';
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF141A35), Color(0xCC090D1F)],
        ),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: accent,
                  boxShadow: <BoxShadow>[
                    BoxShadow(
                      color: accent.withOpacity(0.35),
                      blurRadius: 14,
                      spreadRadius: 1,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  '${activity.botState}  |  ${activity.mode} MODE',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Chip(
                label: Text('Readiness $readiness'),
                backgroundColor: const Color(0xFF153540),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            activity.intent ?? activity.message,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            activity.message,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              if (activity.symbol != null && activity.symbol!.isNotEmpty)
                Chip(
                  label: Text(activity.symbol!),
                  backgroundColor: TradingPalette.panelSoft,
                ),
              if (activity.reason != null && activity.reason!.isNotEmpty)
                Chip(
                  label: Text(activity.reason!),
                  backgroundColor: TradingPalette.panelSoft,
                ),
              if (activity.nextScan != null && activity.nextScan!.isNotEmpty)
                Chip(
                  label: Text('Next ${activity.nextScan!}'),
                  backgroundColor: TradingPalette.panelSoft,
                ),
              Chip(
                label: Text(
                  activity.confidenceBuilding == true
                      ? 'Confidence Building'
                      : 'Waiting Safely',
                ),
                backgroundColor: const Color(0x3314FFB8),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

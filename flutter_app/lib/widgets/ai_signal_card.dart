import 'package:flutter/material.dart';

import '../core/trading_palette.dart';
import '../models/signal.dart';
import 'ai_reason_chips.dart';
import 'gradient_action_button.dart';
import 'status_badge.dart';

class AiSignalCard extends StatelessWidget {
  const AiSignalCard({
    super.key,
    required this.signal,
    required this.onExecute,
    this.compact = false,
  });

  final SignalModel signal;
  final VoidCallback onExecute;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final bullish = signal.action.toUpperCase() == 'BUY';
    final accent = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final gradient =
        bullish ? TradingPalette.profitGlow : TradingPalette.lossGlow;
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: LinearGradient(
          colors: <Color>[
            accent.withOpacity(0.16),
            TradingPalette.panelSoft,
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: accent.withOpacity(0.30)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: accent.withOpacity(0.18),
            blurRadius: 28,
            spreadRadius: -12,
          ),
        ],
      ),
      child: Padding(
        padding: EdgeInsets.all(compact ? 16 : 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                StatusBadge(
                  label: signal.lowConfidence
                      ? 'WATCH'
                      : bullish
                          ? 'STRONG BUY'
                          : 'STRONG SELL',
                  color: accent,
                ),
                const Spacer(),
                StatusBadge(
                  label: '${(signal.confidence * 100).toStringAsFixed(0)}%',
                  color: TradingPalette.electricBlue,
                ),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              signal.symbol,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              'AI ${signal.action.toUpperCase()} signal in ${signal.regime.toUpperCase()} regime at ${signal.price.toStringAsFixed(2)}',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                _MiniPill(label: signal.strategy),
                _MiniPill(label: 'Alpha ${signal.alphaScore.toStringAsFixed(0)}'),
                _MiniPill(label: 'Tier ${signal.requiredTier}'),
              ],
            ),
            const SizedBox(height: 16),
            AiReasonChips(
              reasons: signal.reasons.take(compact ? 2 : 3).toList(),
            ),
            const SizedBox(height: 8),
            GradientActionButton(
              label: 'Execute Trade',
              icon: bullish
                  ? Icons.north_east_rounded
                  : Icons.south_east_rounded,
              gradient: gradient,
              onPressed: onExecute,
              expanded: true,
            ),
          ],
        ),
      ),
    );
  }

}

class _MiniPill extends StatelessWidget {
  const _MiniPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: TradingPalette.glassHighlight.withOpacity(0.08),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: TradingPalette.glassHighlight.withOpacity(0.1),
        ),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: TradingPalette.textMuted,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

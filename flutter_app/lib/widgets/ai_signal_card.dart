import 'package:flutter/material.dart';

import '../core/ai_opportunity_engine.dart';
import '../core/trading_palette.dart';
import '../models/signal.dart';
import 'ai_reason_chips.dart';
import 'gradient_action_button.dart';
import 'live_energy_widgets.dart';
import 'status_badge.dart';

class AiSignalCard extends StatelessWidget {
  const AiSignalCard({
    super.key,
    required this.signal,
    required this.onExecute,
    this.compact = false,
    this.mode = AiTradingMode.balanced,
  });

  final SignalModel signal;
  final VoidCallback onExecute;
  final bool compact;
  final AiTradingMode mode;

  @override
  Widget build(BuildContext context) {
    final opportunity = SignalOpportunity.fromSignal(signal, mode: mode);
    final accent = opportunity.accent;
    final gradient = opportunity.bullish
        ? TradingPalette.profitGlow
        : TradingPalette.lossGlow;
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
                  label: opportunity.statusLabel,
                  color: accent,
                ),
                const Spacer(),
                StatusBadge(
                  label: opportunity.mode.label,
                  color: TradingPalette.electricBlue,
                ),
                const SizedBox(width: 8),
                StatusBadge(
                  label: opportunity.riskLabel,
                  color: TradingPalette.amber,
                ),
                if (signal.marketDataStale) ...<Widget>[
                  const SizedBox(width: 8),
                  const StatusBadge(
                    label: 'STALE DATA',
                    color: TradingPalette.amber,
                  ),
                ],
              ],
            ),
            const SizedBox(height: 18),
            Text(
              opportunity.heroTitle,
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              signal.price > 0
                  ? '${opportunity.userFacingState} at ${signal.price.toStringAsFixed(2)}. Expected move ${opportunity.expectedMoveLabel}.'
                  : '${opportunity.userFacingState}. AI is waiting for a fresh executable price.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
            const SizedBox(height: 16),
            _OpportunityMeters(opportunity: opportunity),
            const SizedBox(height: 14),
            OpportunityProgressRail(opportunity: opportunity),
            const SizedBox(height: 16),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                _MiniPill(label: signal.strategy),
                _MiniPill(
                  label: 'Confidence ${opportunity.confidenceLabel}',
                ),
                _MiniPill(
                  label: 'Move ${opportunity.expectedMoveLabel}',
                ),
                _MiniPill(
                  label: opportunity.canAttemptExecution
                      ? 'Execution ready'
                      : opportunity.secondaryLabel,
                ),
              ],
            ),
            const SizedBox(height: 16),
            AiReasonChips(
              reasons: opportunity.insights.take(compact ? 2 : 3).toList(),
            ),
            const SizedBox(height: 12),
            Text(
              opportunity.tradePlanLabel,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                  ),
            ),
            const SizedBox(height: 8),
            GradientActionButton(
              label: opportunity.primaryLabel,
              icon: opportunity.bullish
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

class _OpportunityMeters extends StatelessWidget {
  const _OpportunityMeters({required this.opportunity});

  final SignalOpportunity opportunity;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        _MeterRow(
          label: 'AI confidence',
          value: opportunity.score / 100,
          text: opportunity.confidenceLabel,
          color: opportunity.accent,
        ),
        const SizedBox(height: 10),
        _MeterRow(
          label: 'Breakout',
          value: opportunity.breakoutProbability / 100,
          text: '${opportunity.breakoutProbability.toStringAsFixed(0)}%',
          color: TradingPalette.electricBlue,
        ),
        const SizedBox(height: 10),
        _MeterRow(
          label: 'Whale pressure',
          value: opportunity.whalePressure / 100,
          text: '${opportunity.whalePressure.toStringAsFixed(0)}%',
          color: TradingPalette.violet,
        ),
      ],
    );
  }
}

class _MeterRow extends StatelessWidget {
  const _MeterRow({
    required this.label,
    required this.value,
    required this.text,
    required this.color,
  });

  final String label;
  final double value;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        SizedBox(
          width: 96,
          child: Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              minHeight: 7,
              value: value.clamp(0.0, 1.0),
              backgroundColor: TradingPalette.overlay,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
        ),
        const SizedBox(width: 10),
        SizedBox(
          width: 42,
          child: Text(
            text,
            textAlign: TextAlign.right,
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
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

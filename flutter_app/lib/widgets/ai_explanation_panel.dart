import 'package:flutter/material.dart';

import '../core/ai_opportunity_engine.dart';
import '../core/trading_palette.dart';
import '../models/signal.dart';
import 'ai_reason_chips.dart';
import 'glass_panel.dart';

class AiExplanationPanel extends StatelessWidget {
  const AiExplanationPanel({
    super.key,
    required this.signal,
    this.tradeQuality,
    this.winProbability,
    this.expectedRr,
  });

  final SignalModel signal;
  final String? tradeQuality;
  final double? winProbability;
  final double? expectedRr;

  @override
  Widget build(BuildContext context) {
    final opportunity = SignalOpportunity.fromSignal(signal);
    final reasons = signal.reasons;
    final riskLevel = _riskLevel(signal);

    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Why this opportunity?',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 12),
          AiReasonChips(reasons: reasons.take(3).toList()),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _Metric(
                  label: 'AI Confidence', value: opportunity.confidenceLabel),
              _Metric(
                  label: 'Expected Move', value: opportunity.expectedMoveLabel),
              _Metric(label: 'Risk Level', value: riskLevel),
              _Metric(
                label: 'Plan',
                value: opportunity.statusLabel,
              ),
              if (signal.marketDataStale)
                const _Metric(label: 'Market Data', value: 'Stale'),
              if (tradeQuality != null)
                _Metric(label: 'Trade Quality', value: tradeQuality!),
              if (winProbability != null)
                _Metric(
                  label: 'Win Probability',
                  value: '${(winProbability! * 100).toStringAsFixed(0)}%',
                ),
              if (expectedRr != null)
                _Metric(
                  label: 'Expected RR',
                  value: '1:${expectedRr!.toStringAsFixed(1)}',
                ),
            ],
          ),
        ],
      ),
    );
  }

  String _riskLevel(SignalModel signal) {
    if (!signal.executionAllowed || signal.marketDataStale) {
      return 'Guarded';
    }
    if (signal.lowConfidence) {
      return 'Watch';
    }
    if (signal.alphaScore >= 85 && signal.confidence >= 0.78) {
      return 'High';
    }
    return 'Medium';
  }
}

class _Metric extends StatelessWidget {
  const _Metric({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

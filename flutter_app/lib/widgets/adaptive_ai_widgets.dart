import 'package:flutter/material.dart';

import '../core/adaptive_ai_intelligence_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class AiSelfEvaluationPanel extends StatelessWidget {
  const AiSelfEvaluationPanel({
    super.key,
    required this.evaluation,
  });

  final AiSelfEvaluation evaluation;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'AI Reliability',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label: '${evaluation.reliabilityScore.toStringAsFixed(0)}%',
                color: TradingPalette.electricBlue,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _MetricLine(
            label: 'Signal success',
            value: evaluation.signalSuccessRate,
            color: TradingPalette.neonGreen,
          ),
          _MetricLine(
            label: 'False breakout',
            value: evaluation.falseBreakoutRate,
            color: TradingPalette.neonRed,
          ),
          _MetricLine(
            label: 'Early entry quality',
            value: evaluation.earlyEntryQuality,
            color: TradingPalette.amber,
          ),
          const SizedBox(height: 10),
          Text(
            'TP hit ${evaluation.tpHitRatio.toStringAsFixed(0)}% | SL hit ${evaluation.slHitRatio.toStringAsFixed(0)}% | Delay ${evaluation.delayedEntryRate.toStringAsFixed(0)}%',
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
        ],
      ),
    );
  }
}

class RegimeAdaptationPanel extends StatelessWidget {
  const RegimeAdaptationPanel({
    super.key,
    required this.regime,
  });

  final RegimeAdaptationRead regime;

  @override
  Widget build(BuildContext context) {
    return _AdaptiveDeskPanel(
      title: 'Regime Adaptation',
      badge: regime.currentRegime,
      color: TradingPalette.violet,
      rows: <String>[
        regime.adaptiveBehavior,
        'Frequency: ${regime.signalFrequency}',
        'Leverage multiplier: ${regime.leverageMultiplier.toStringAsFixed(2)}x',
        'Risk multiplier: ${regime.riskMultiplier.toStringAsFixed(2)}x',
        'Preferred mode: ${regime.preferredMode}',
        'Style: ${regime.tradeStyle}',
      ],
    );
  }
}

class ExecutionPrecisionPanel extends StatelessWidget {
  const ExecutionPrecisionPanel({
    super.key,
    required this.precision,
  });

  final ExecutionPrecisionRead precision;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.neonGreen,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Execution Precision',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label: '${precision.entryEfficiency.toStringAsFixed(0)}%',
                color: TradingPalette.neonGreen,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _MetricLine(
            label: 'Entry efficiency',
            value: precision.entryEfficiency,
            color: TradingPalette.neonGreen,
          ),
          _MetricLine(
            label: 'Breakout timing',
            value: precision.breakoutTimingQuality,
            color: TradingPalette.electricBlue,
          ),
          const SizedBox(height: 10),
          _Bullet(text: precision.confirmationTiming),
          _Bullet(text: precision.slippageAwareness),
          _Bullet(text: precision.fakeBreakoutFilter),
          _Bullet(text: precision.volatilityAdjustedTiming),
        ],
      ),
    );
  }
}

class AutopilotPanel extends StatelessWidget {
  const AutopilotPanel({
    super.key,
    required this.autopilot,
    required this.safety,
  });

  final AutopilotIntelligenceRead autopilot;
  final AutopilotSafetyRead safety;

  @override
  Widget build(BuildContext context) {
    final color = safety.safetyScore >= 80
        ? TradingPalette.neonGreen
        : safety.safetyScore >= 60
            ? TradingPalette.amber
            : TradingPalette.neonRed;
    return _AdaptiveDeskPanel(
      title: 'Adaptive Autopilot',
      badge: safety.verdict,
      color: color,
      rows: <String>[
        '${autopilot.action} (${autopilot.recommendedMode})',
        autopilot.reason,
        'Leverage adjustment: ${autopilot.leverageAdjustment.toStringAsFixed(2)}x',
        'Frequency: ${autopilot.signalFrequencyAdjustment}',
        'Style: ${autopilot.scalpVsSwing}',
        'Safety score: ${safety.safetyScore.toStringAsFixed(0)}%',
      ],
    );
  }
}

class SignalCalibrationPanel extends StatelessWidget {
  const SignalCalibrationPanel({
    super.key,
    required this.calibration,
  });

  final SignalCalibrationRead calibration;

  @override
  Widget build(BuildContext context) {
    return _AdaptiveDeskPanel(
      title: 'Signal Calibration',
      badge: calibration.grade,
      color: calibration.grade.startsWith('A')
          ? TradingPalette.neonGreen
          : TradingPalette.amber,
      rows: <String>[
        calibration.classification,
        calibration.setupType,
        calibration.rankReason,
      ],
    );
  }
}

class AdvancedMarketIntelPanel extends StatelessWidget {
  const AdvancedMarketIntelPanel({
    super.key,
    required this.intel,
  });

  final AdvancedMarketIntelligenceRead intel;

  @override
  Widget build(BuildContext context) {
    return _AdaptiveDeskPanel(
      title: 'Advanced Market Intelligence',
      badge:
          '${intel.volatilityExpansionProbability.toStringAsFixed(0)}% expansion',
      color: TradingPalette.electricBlue,
      rows: <String>[
        'Liquidation heat ${intel.liquidationHeat.toStringAsFixed(0)}%',
        'Correlation risk ${intel.correlationRisk.toStringAsFixed(0)}%',
        intel.dominanceRotation,
        intel.sectorRotation,
        'Macro bias: ${intel.macroBias}',
        'Smart money pressure ${intel.smartMoneyPressure.toStringAsFixed(0)}%',
      ],
    );
  }
}

class AiPerformanceReviewPanel extends StatelessWidget {
  const AiPerformanceReviewPanel({
    super.key,
    required this.review,
  });

  final AiPerformanceReview review;

  @override
  Widget build(BuildContext context) {
    return _AdaptiveDeskPanel(
      title: 'AI Performance Review',
      badge: review.bestAiMode,
      color: TradingPalette.violet,
      rows: <String>[
        review.dailyReview,
        review.weeklyReview,
        'Strongest: ${review.strongestSetupTypes.join(', ')}',
        'Weakest: ${review.weakestSetupTypes.join(', ')}',
        'Worst condition: ${review.worstMarketCondition}',
        'Adaptation ${review.adaptationPerformance.toStringAsFixed(0)}% | Timing ${review.timingQuality.toStringAsFixed(0)}%',
      ],
    );
  }
}

class HedgeFundAnalyticsPanel extends StatelessWidget {
  const HedgeFundAnalyticsPanel({
    super.key,
    required this.analytics,
  });

  final HedgeFundAnalyticsRead analytics;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.amber,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Professional Edge Analytics',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricPill(label: 'Expectancy', value: analytics.expectancy),
              _MetricPill(label: 'Stability', value: analytics.stabilityScore),
              _MetricPill(
                  label: 'Setup exp.', value: analytics.setupExpectancy),
              _MetricPill(label: 'Edge decay', value: analytics.edgeDecay),
              _MetricPill(
                label: 'Vol adj.',
                value: analytics.volatilityAdjustedPerformance,
              ),
              _MetricPill(
                label: 'Exec eff.',
                value: analytics.executionEfficiency,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ReplayFoundationPanel extends StatelessWidget {
  const ReplayFoundationPanel({
    super.key,
    required this.replay,
  });

  final ReplayFoundationRead replay;

  @override
  Widget build(BuildContext context) {
    return _AdaptiveDeskPanel(
      title: 'Replay Foundation',
      badge: replay.replayReady ? 'READY' : 'BUILDING',
      color:
          replay.replayReady ? TradingPalette.neonGreen : TradingPalette.amber,
      rows: <String>[
        'Historical windows: ${replay.historicalWindows}',
        'Setup replay: ${replay.setupReplayAvailable ? 'available' : 'waiting'}',
        'Missed opportunity replay: ${replay.missedOpportunityReplay ? 'indexed' : 'waiting'}',
        replay.trainingReviewStatus,
        replay.replayNote,
      ],
    );
  }
}

class _AdaptiveDeskPanel extends StatelessWidget {
  const _AdaptiveDeskPanel({
    required this.title,
    required this.badge,
    required this.color,
    required this.rows,
  });

  final String title;
  final String badge;
  final Color color;
  final List<String> rows;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: badge, color: color),
            ],
          ),
          const SizedBox(height: 12),
          ...rows.map((row) => _Bullet(text: row)),
        ],
      ),
    );
  }
}

class _MetricLine extends StatelessWidget {
  const _MetricLine({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: <Widget>[
          SizedBox(width: 128, child: Text(label)),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: (value / 100).clamp(0.0, 1.0),
                minHeight: 8,
                backgroundColor: TradingPalette.overlay,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 44,
            child: Text(
              value.toStringAsFixed(0),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({
    required this.label,
    required this.value,
  });

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 92),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 3),
          Text(
            value.abs() < 5
                ? value.toStringAsFixed(2)
                : value.toStringAsFixed(0),
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 7,
            height: 7,
            margin: const EdgeInsets.only(top: 6),
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: TradingPalette.electricBlue,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: TradingPalette.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

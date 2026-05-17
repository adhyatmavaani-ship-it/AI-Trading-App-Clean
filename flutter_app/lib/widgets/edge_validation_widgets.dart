import 'package:flutter/material.dart';

import '../core/edge_validation_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class SignalOutcomeReportPanel extends StatelessWidget {
  const SignalOutcomeReportPanel({
    super.key,
    required this.report,
  });

  final SignalOutcomeReport report;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _Header(
            title: 'Signal Outcome Report',
            badge: report.outcomeQuality,
            color: _qualityColor(report.exitEfficiency),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricPill(
                label: 'MFE',
                value: '${report.maxFavorableExcursion.toStringAsFixed(2)}%',
                color: TradingPalette.neonGreen,
              ),
              _MetricPill(
                label: 'MAE',
                value: '${report.maxAdverseExcursion.toStringAsFixed(2)}%',
                color: TradingPalette.neonRed,
              ),
              _MetricPill(
                label: 'TP Hits',
                value: report.tpHits.toString(),
                color: TradingPalette.electricBlue,
              ),
              _MetricPill(
                label: 'Exit Eff.',
                value: '${report.exitEfficiency.toStringAsFixed(0)}%',
                color: _qualityColor(report.exitEfficiency),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _Bullet('Setup: ${report.setupType}'),
          _Bullet(
              'Mode: ${report.aiModeUsed} | Regime: ${report.marketRegime}'),
          _Bullet(
            'Delay ${report.executionDelaySeconds}s | Hold ${report.holdingDurationMinutes}m',
          ),
          _Bullet(
            report.slHit
                ? 'SL/invalidation pressure detected: ${report.invalidationTiming}'
                : 'No stop/invalidation pressure detected yet.',
          ),
        ],
      ),
    );
  }
}

class EdgeValidationPanel extends StatelessWidget {
  const EdgeValidationPanel({
    super.key,
    required this.read,
  });

  final EdgeValidationRead read;

  @override
  Widget build(BuildContext context) {
    final best = _bestEntry(read.setupExpectancy);
    return _DeskPanel(
      title: 'Edge Validation',
      badge: best == null ? 'LEARNING' : best.key,
      color: TradingPalette.neonGreen,
      children: <Widget>[
        Text(
          read.edgeSummary,
          style: const TextStyle(color: TradingPalette.textPrimary),
        ),
        const SizedBox(height: 12),
        _MetricLine(
          label: 'Confidence calibration',
          value: read.confidenceCalibrationAccuracy,
          color: TradingPalette.electricBlue,
        ),
        _MetricLine(
          label: 'Execution impact',
          value: read.executionQualityImpact,
          color: TradingPalette.neonGreen,
        ),
        const SizedBox(height: 8),
        _MapRows(title: 'Setup expectancy', values: read.setupExpectancy),
        _MapRows(title: 'Regime expectancy', values: read.regimeExpectancy),
      ],
    );
  }
}

class ModelDriftPanel extends StatelessWidget {
  const ModelDriftPanel({
    super.key,
    required this.read,
  });

  final ModelDriftRead read;

  @override
  Widget build(BuildContext context) {
    final color =
        read.driftDetected ? TradingPalette.amber : TradingPalette.neonGreen;
    return _DeskPanel(
      title: 'AI Stability Monitor',
      badge: read.driftDetected ? 'DRIFT WATCH' : 'STABLE',
      color: color,
      children: <Widget>[
        _MetricLine(
          label: 'Stability',
          value: read.aiStabilityScore,
          color: color,
        ),
        _MetricLine(
          label: 'Win-rate trend',
          value: read.winRateTrend,
          color: TradingPalette.neonGreen,
        ),
        _MetricLine(
          label: 'False breakouts',
          value: read.falseBreakoutTrend,
          color: TradingPalette.neonRed,
        ),
        _MetricLine(
          label: 'Regime instability',
          value: read.regimeInstability,
          color: TradingPalette.amber,
        ),
        const SizedBox(height: 8),
        _Bullet(read.correctiveAction),
      ],
    );
  }
}

class SelfCorrectionPanel extends StatelessWidget {
  const SelfCorrectionPanel({
    super.key,
    required this.read,
  });

  final SelfCorrectionRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Self-Correction',
      badge: '${read.leverageMultiplier.toStringAsFixed(2)}x risk',
      color: TradingPalette.violet,
      children: <Widget>[
        _Bullet(read.learningNote),
        _Bullet('Preferred regimes: ${read.preferredRegimes.join(', ')}'),
        _Bullet('Boosted setups: ${read.boostedSetups.join(', ')}'),
        _Bullet('Suppressed: ${read.suppressedConditions.join(', ')}'),
        _Bullet(
          'Confidence floor adjustment: +${read.confidenceFloorAdjustment.toStringAsFixed(0)}',
        ),
        const SizedBox(height: 8),
        _MapRows(
          title: 'Weight adjustments',
          values: read.setupWeightAdjustments,
          multiplier: true,
        ),
      ],
    );
  }
}

class ExecutionOutcomePanel extends StatelessWidget {
  const ExecutionOutcomePanel({
    super.key,
    required this.read,
  });

  final ExecutionOutcomeRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Execution Outcome Intelligence',
      badge: '${read.executionQualityScore.toStringAsFixed(0)}%',
      color: _qualityColor(read.executionQualityScore),
      children: <Widget>[
        _MetricLine(
          label: 'Quality',
          value: read.executionQualityScore,
          color: _qualityColor(read.executionQualityScore),
        ),
        _MetricLine(
          label: 'Late penalty',
          value: read.lateEntryPenalty,
          color: TradingPalette.amber,
        ),
        _MetricLine(
          label: 'Slippage impact',
          value: read.slippageImpact,
          color: TradingPalette.neonRed,
        ),
        _MetricLine(
          label: 'Liquidity',
          value: read.liquidityQuality,
          color: TradingPalette.electricBlue,
        ),
        const SizedBox(height: 8),
        _Bullet(read.executionSummary),
      ],
    );
  }
}

class AiDecisionJournalPanel extends StatelessWidget {
  const AiDecisionJournalPanel({
    super.key,
    required this.entry,
  });

  final AiDecisionJournalEntry entry;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'AI Decision Journal',
      badge: entry.symbol,
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _LabelBlock(title: 'Why AI entered', lines: entry.enteredBecause),
        const SizedBox(height: 10),
        _Bullet('Expected: ${entry.expectedOutcome}'),
        _Bullet('Actual: ${entry.actualOutcome}'),
        _Bullet('Learned: ${entry.learned}'),
      ],
    );
  }
}

class StrategyLeaderboardPanel extends StatelessWidget {
  const StrategyLeaderboardPanel({
    super.key,
    required this.read,
  });

  final StrategyLeaderboardRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Strategy Leaderboard',
      badge: 'EDGE RANK',
      color: TradingPalette.neonGreen,
      children: <Widget>[
        _LeaderboardBlock(title: 'Setups', rows: read.bestSetupTypes),
        _LeaderboardBlock(title: 'AI modes', rows: read.bestAiModes),
        _LeaderboardBlock(title: 'Regimes', rows: read.bestRegimes),
        _LeaderboardBlock(title: 'Assets', rows: read.bestAssets),
      ],
    );
  }
}

class ReplayMetadataPanel extends StatelessWidget {
  const ReplayMetadataPanel({
    super.key,
    required this.read,
  });

  final ReplayMetadataRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Replay Metadata',
      badge: read.ready ? 'READY' : 'INDEXING',
      color: read.ready ? TradingPalette.neonGreen : TradingPalette.amber,
      children: <Widget>[
        _Bullet('Replay ID: ${read.replayId}'),
        _Bullet('Snapshots: ${read.snapshotCount}'),
        _Bullet('Decision events: ${read.decisionTimelineEvents}'),
        _Bullet(
          'Projected ${read.projectedMove.toStringAsFixed(2)} vs actual ${read.actualMove.toStringAsFixed(2)}',
        ),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Annotations', lines: read.annotations),
      ],
    );
  }
}

class QuantPerformancePanel extends StatelessWidget {
  const QuantPerformancePanel({
    super.key,
    required this.read,
  });

  final QuantPerformanceRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Quant Performance',
      badge: 'EDGE ${read.rollingExpectancy.toStringAsFixed(2)}',
      color: TradingPalette.amber,
      children: <Widget>[
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _MetricPill(
              label: 'Expectancy',
              value: read.rollingExpectancy.toStringAsFixed(2),
              color: TradingPalette.neonGreen,
            ),
            _MetricPill(
              label: 'Stability',
              value: '${read.rollingEdgeStability.toStringAsFixed(0)}%',
              color: TradingPalette.electricBlue,
            ),
            _MetricPill(
              label: 'Decay',
              value: '${read.setupDecay.toStringAsFixed(0)}%',
              color: TradingPalette.amber,
            ),
            _MetricPill(
              label: 'Exec adj.',
              value: read.executionAdjustedReturns.toStringAsFixed(2),
              color: TradingPalette.violet,
            ),
          ],
        ),
        const SizedBox(height: 12),
        _LabelBlock(
          title: 'Confidence calibration',
          lines: read.confidenceCalibrationCurve
              .map(
                (point) =>
                    '${point.confidenceBucket}: ${point.realizedAccuracy.toStringAsFixed(0)}%',
              )
              .toList(growable: false),
        ),
      ],
    );
  }
}

class _DeskPanel extends StatelessWidget {
  const _DeskPanel({
    required this.title,
    required this.badge,
    required this.color,
    required this.children,
  });

  final String title;
  final String badge;
  final Color color;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _Header(title: title, badge: badge, color: color),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.title,
    required this.badge,
    required this.color,
  });

  final String title;
  final String badge;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
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
          SizedBox(width: 138, child: Text(label)),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: (value / 100).clamp(0.0, 1.0),
                minHeight: 7,
                backgroundColor: TradingPalette.overlay,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 42,
            child: Text(
              value.toStringAsFixed(0),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w800),
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
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 92),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(color: color, fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class _MapRows extends StatelessWidget {
  const _MapRows({
    required this.title,
    required this.values,
    this.multiplier = false,
  });

  final String title;
  final Map<String, double> values;
  final bool multiplier;

  @override
  Widget build(BuildContext context) {
    final entries = values.entries.take(3).toList(growable: false);
    if (entries.isEmpty) {
      return _Bullet('$title: awaiting sample');
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          ...entries.map(
            (entry) => _Bullet(
              '${entry.key}: ${multiplier ? '${entry.value.toStringAsFixed(2)}x' : entry.value.toStringAsFixed(2)}',
            ),
          ),
        ],
      ),
    );
  }
}

class _LeaderboardBlock extends StatelessWidget {
  const _LeaderboardBlock({
    required this.title,
    required this.rows,
  });

  final String title;
  final List<LeaderboardRow> rows;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty) {
      return _Bullet('$title: building sample');
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          ...rows.take(3).map(
                (row) => _Bullet(
                  '${row.label}: ${row.score.toStringAsFixed(2)} (${row.sampleSize}) - ${row.note}',
                ),
              ),
        ],
      ),
    );
  }
}

class _LabelBlock extends StatelessWidget {
  const _LabelBlock({
    required this.title,
    required this.lines,
  });

  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(title, style: Theme.of(context).textTheme.labelMedium),
        const SizedBox(height: 6),
        ...lines.map(_Bullet.new),
      ],
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(top: 7),
            decoration: const BoxDecoration(
              color: TradingPalette.electricBlue,
              shape: BoxShape.circle,
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

MapEntry<String, double>? _bestEntry(Map<String, double> values) {
  if (values.isEmpty) {
    return null;
  }
  return values.entries.reduce((a, b) => a.value >= b.value ? a : b);
}

Color _qualityColor(double value) {
  if (value >= 74) {
    return TradingPalette.neonGreen;
  }
  if (value >= 56) {
    return TradingPalette.amber;
  }
  return TradingPalette.neonRed;
}

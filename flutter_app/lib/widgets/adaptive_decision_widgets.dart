import 'package:flutter/material.dart';

import '../core/adaptive_decision_core.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class AiConsensusEnginePanel extends StatelessWidget {
  const AiConsensusEnginePanel({super.key, required this.read});

  final AiConsensusRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'AI Consensus Engine',
      badge: read.dominantBias,
      color: _scoreColor(read.consensusConfidence),
      children: <Widget>[
        _ProbabilityTriplet(
          bullish: read.bullishProbability,
          bearish: read.bearishProbability,
          chop: read.chopProbability,
        ),
        const SizedBox(height: 12),
        _MetricLine('Consensus', read.consensusConfidence),
        _MetricLine('Adaptive quality', read.adaptiveSignalQuality),
        _MetricLine('Continuation', read.breakoutContinuationProbability),
        _MetricLine('Exhaustion', read.exhaustionProbability),
        const SizedBox(height: 8),
        _Bullet(read.summary),
      ],
    );
  }
}

class AiContributorPanel extends StatelessWidget {
  const AiContributorPanel({super.key, required this.contributors});

  final List<AiContributorRead> contributors;

  @override
  Widget build(BuildContext context) {
    final ordered = contributors.toList()
      ..sort((a, b) => b.weight.compareTo(a.weight));
    return _DecisionPanel(
      title: 'Ensemble Contributors',
      badge: '${contributors.length} feeds',
      color: TradingPalette.violet,
      children: ordered
          .take(8)
          .map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _ContributorRow(item: item),
            ),
          )
          .toList(growable: false),
    );
  }
}

class AdaptiveWeightsPanel extends StatelessWidget {
  const AdaptiveWeightsPanel({super.key, required this.read});

  final AdaptiveWeightsRead read;

  @override
  Widget build(BuildContext context) {
    final rows = read.weights.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return _DecisionPanel(
      title: 'Adaptive Weight Engine',
      badge: read.primaryWeight,
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet(read.regime),
        _Bullet(read.explanation),
        const SizedBox(height: 8),
        ...rows.map(
          (entry) => _MetricLine(
            _typeLabel(entry.key),
            entry.value * 100,
          ),
        ),
      ],
    );
  }
}

class ConfidenceCalibrationCorePanel extends StatelessWidget {
  const ConfidenceCalibrationCorePanel({super.key, required this.read});

  final ConfidenceCalibrationCoreRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'Confidence Calibration',
      badge: '${read.confidenceStabilityIndex.toStringAsFixed(0)} CSI',
      color: _scoreColor(read.confidenceStabilityIndex),
      children: <Widget>[
        _MetricLine('Stability index', read.confidenceStabilityIndex),
        _MetricLine('Overconfidence penalty', read.overconfidentFailurePenalty),
        _MetricLine('Underconfidence boost', read.underconfidentWinBoost),
        _MetricLine('Regime calibration', read.regimeCalibration),
        _MetricLine('Asset calibration', read.assetCalibration),
        const SizedBox(height: 8),
        _Bullet(read.note),
      ],
    );
  }
}

class ScenarioProbabilityMapPanel extends StatelessWidget {
  const ScenarioProbabilityMapPanel({super.key, required this.read});

  final ScenarioProbabilityMapRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'Scenario Probability Map',
      badge: read.preferredScenario,
      color: _scoreColor(read.breakoutSucceeds),
      children: <Widget>[
        _MetricLine('Breakout succeeds', read.breakoutSucceeds),
        _MetricLine('Fake breakout', read.fakeBreakout),
        _MetricLine('Trend continuation', read.trendContinuation),
        _MetricLine('Volatility rejection', read.volatilityRejection),
        _MetricLine('Sweep reversal', read.liquiditySweepReversal),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Scenario read', lines: read.scenarioNotes),
      ],
    );
  }
}

class AiConsensusTimelinePanel extends StatelessWidget {
  const AiConsensusTimelinePanel({super.key, required this.read});

  final AiConsensusTimelineRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'AI Consensus Timeline',
      badge: 'EVOLVING',
      color: TradingPalette.amber,
      children: <Widget>[
        _Bullet(read.evolutionSummary),
        const SizedBox(height: 10),
        ...read.points.map(
          (point) => Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SizedBox(
                  width: 42,
                  child: Text(
                    point.label,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Row(
                        children: <Widget>[
                          Expanded(child: Text(point.bias)),
                          Text('${point.confidence.toStringAsFixed(0)}%'),
                        ],
                      ),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(999),
                        child: LinearProgressIndicator(
                          value: (point.confidence / 100).clamp(0.0, 1.0),
                          minHeight: 6,
                          backgroundColor: TradingPalette.overlay,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            _scoreColor(point.confidence),
                          ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        point.note,
                        style: const TextStyle(color: TradingPalette.textMuted),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class MarketReasoningPanel extends StatelessWidget {
  const MarketReasoningPanel({super.key, required this.read});

  final MarketReasoningRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'Market Reasoning Layer',
      badge: 'REASONING',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        Text(
          read.headline,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 8),
        Text(
          read.reasoning,
          style: const TextStyle(color: TradingPalette.textPrimary),
        ),
        const SizedBox(height: 10),
        _LabelBlock(
          title: 'Support',
          lines: read.supportingFactors.isEmpty
              ? const <String>['No dominant support cluster yet.']
              : read.supportingFactors,
        ),
        const SizedBox(height: 8),
        _LabelBlock(
          title: 'Risks',
          lines: read.riskFactors.isEmpty
              ? const <String>['No material instability flag.']
              : read.riskFactors,
        ),
      ],
    );
  }
}

class StabilityDriftControlPanel extends StatelessWidget {
  const StabilityDriftControlPanel({super.key, required this.read});

  final StabilityDriftControlRead read;

  @override
  Widget build(BuildContext context) {
    return _DecisionPanel(
      title: 'AI Stability Control',
      badge: '${read.smoothedConfidence.toStringAsFixed(0)} smooth',
      color: _scoreColor(read.smoothedConfidence),
      children: <Widget>[
        _MetricLine('Smoothed confidence', read.smoothedConfidence),
        _MetricLine('Hysteresis band', read.hysteresisBand * 10),
        _MetricLine('Drift suppression', read.driftSuppression),
        _MetricLine('Vol normalization', read.volatilityNormalization),
        _MetricLine('Regime stability', read.regimeStabilization),
        const SizedBox(height: 8),
        _Bullet(read.action),
      ],
    );
  }
}

class AdaptiveDecisionResearchPanel extends StatelessWidget {
  const AdaptiveDecisionResearchPanel({super.key, required this.read});

  final AdaptiveDecisionResearchRead read;

  @override
  Widget build(BuildContext context) {
    final benchmarkRows = read.contributorBenchmarks.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return _DecisionPanel(
      title: 'Decision Research Foundation',
      badge: read.modelComparisonReady ? 'READY' : 'BUILDING',
      color: TradingPalette.violet,
      children: <Widget>[
        _CheckRow(label: 'ML integration shape', ok: read.mlIntegrationReady),
        _CheckRow(label: 'Offline replay', ok: read.offlineReplayReady),
        _CheckRow(
          label: 'Probabilistic replay',
          ok: read.probabilisticReplayReady,
        ),
        _CheckRow(label: 'Model comparison', ok: read.modelComparisonReady),
        const SizedBox(height: 8),
        ...benchmarkRows.take(4).map(
              (entry) => _MetricLine(entry.key, entry.value),
            ),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Research notes', lines: read.notes),
      ],
    );
  }
}

class _DecisionPanel extends StatelessWidget {
  const _DecisionPanel({
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
          ...children,
        ],
      ),
    );
  }
}

class _ProbabilityTriplet extends StatelessWidget {
  const _ProbabilityTriplet({
    required this.bullish,
    required this.bearish,
    required this.chop,
  });

  final double bullish;
  final double bearish;
  final double chop;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: _ProbabilityBox(
            label: 'Bull',
            value: bullish,
            color: TradingPalette.neonGreen,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _ProbabilityBox(
            label: 'Bear',
            value: bearish,
            color: TradingPalette.neonRed,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: _ProbabilityBox(
            label: 'Chop',
            value: chop,
            color: TradingPalette.amber,
          ),
        ),
      ],
    );
  }
}

class _ProbabilityBox extends StatelessWidget {
  const _ProbabilityBox({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.09),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.24)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 4),
          Text(
            '${value.toStringAsFixed(0)}%',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
          ),
        ],
      ),
    );
  }
}

class _ContributorRow extends StatelessWidget {
  const _ContributorRow({required this.item});

  final AiContributorRead item;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                item.name,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
            Text('${(item.weight * 100).toStringAsFixed(0)}%'),
          ],
        ),
        const SizedBox(height: 6),
        Row(
          children: <Widget>[
            Expanded(
                child:
                    _MiniBar(label: 'Bias', value: item.directionalBias.abs())),
            const SizedBox(width: 8),
            Expanded(child: _MiniBar(label: 'Edge', value: item.edgeQuality)),
            const SizedBox(width: 8),
            Expanded(child: _MiniBar(label: 'Stable', value: item.stability)),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          item.reasoning,
          style: const TextStyle(color: TradingPalette.textMuted),
        ),
      ],
    );
  }
}

class _MiniBar extends StatelessWidget {
  const _MiniBar({required this.label, required this.value});

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(label, style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: (value / 100).clamp(0.0, 1.0),
            minHeight: 5,
            backgroundColor: TradingPalette.overlay,
            valueColor: AlwaysStoppedAnimation<Color>(_scoreColor(value)),
          ),
        ),
      ],
    );
  }
}

class _MetricLine extends StatelessWidget {
  const _MetricLine(this.label, this.value);

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final color = _scoreColor(value);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: <Widget>[
          SizedBox(width: 142, child: Text(label)),
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
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.label, required this.ok});

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return _Bullet('${ok ? 'Ready' : 'Building'}: $label');
  }
}

class _LabelBlock extends StatelessWidget {
  const _LabelBlock({required this.title, required this.lines});

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
      padding: const EdgeInsets.only(bottom: 8),
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

Color _scoreColor(double value) {
  if (value >= 74) {
    return TradingPalette.neonGreen;
  }
  if (value >= 54) {
    return TradingPalette.amber;
  }
  return TradingPalette.neonRed;
}

String _typeLabel(AiContributorType type) {
  switch (type) {
    case AiContributorType.momentum:
      return 'Momentum';
    case AiContributorType.liquidity:
      return 'Liquidity';
    case AiContributorType.volatility:
      return 'Volatility';
    case AiContributorType.structure:
      return 'Structure';
    case AiContributorType.regime:
      return 'Regime';
    case AiContributorType.execution:
      return 'Execution';
    case AiContributorType.sentiment:
      return 'Sentiment';
    case AiContributorType.portfolio:
      return 'Portfolio';
  }
}

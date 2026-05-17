import 'package:flutter/material.dart';

import '../core/evolving_ai_intelligence_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class ContributorEvolutionPanel extends StatelessWidget {
  const ContributorEvolutionPanel({super.key, required this.read});

  final ContributorEvolutionRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Contributor Evolution',
      badge: read.strongestContributor,
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet(read.evolutionSummary),
        const SizedBox(height: 10),
        ...read.scores.take(5).map(
              (score) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _ContributorEvolutionRow(score: score),
              ),
            ),
      ],
    );
  }
}

class LongHorizonEdgeMemoryPanel extends StatelessWidget {
  const LongHorizonEdgeMemoryPanel({super.key, required this.read});

  final LongHorizonEdgeMemoryRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Long-Horizon Edge Memory',
      badge: read.edgeDecay > read.edgeRecovery ? 'DECAY WATCH' : 'STABLE',
      color: _scoreColor(100 - read.edgeDecay),
      children: <Widget>[
        _MetricLine('Setup quality', read.multiWeekSetupQuality),
        _MetricLine('Regime persistence', read.regimePersistence),
        _MetricLine('Edge decay', read.edgeDecay),
        _MetricLine('Edge recovery', read.edgeRecovery),
        _MetricLine('Personality shift', read.marketPersonalityShift),
        const SizedBox(height: 8),
        _Bullet(read.memorySummary),
        _LabelBlock(
            title: 'Failure memory', lines: read.recurringFailurePatterns),
      ],
    );
  }
}

class MetaIntelligencePanel extends StatelessWidget {
  const MetaIntelligencePanel({super.key, required this.read});

  final MetaIntelligenceRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Meta-Intelligence',
      badge: '${read.metaStabilityScore.toStringAsFixed(0)} stability',
      color: _scoreColor(read.metaStabilityScore),
      children: <Widget>[
        _MetricLine('Meta stability', read.metaStabilityScore),
        _MetricLine('Process quality', read.processQuality),
        const SizedBox(height: 8),
        _Bullet(read.summary),
        _LabelBlock(
            title: 'Overreacting', lines: read.overreactingContributors),
        _LabelBlock(title: 'Lagging', lines: read.laggingContributors),
        _LabelBlock(
            title: 'Unstable regimes', lines: read.destabilizingRegimes),
      ],
    );
  }
}

class StrategyEvolutionPanel extends StatelessWidget {
  const StrategyEvolutionPanel({super.key, required this.read});

  final StrategyEvolutionRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Strategy Evolution',
      badge: '${(read.leveragePreference * 100).toStringAsFixed(0)} risk pref',
      color: TradingPalette.violet,
      children: <Widget>[
        _MetricLine('Leverage preference', read.leveragePreference * 100),
        _Bullet(read.evolutionNote),
        _LabelBlock(title: 'Increase', lines: read.increasedSetups),
        _LabelBlock(title: 'Reduce', lines: read.reducedSetups),
        _LabelBlock(title: 'Suppress', lines: read.suppressedEnvironments),
        const SizedBox(height: 8),
        ...read.scenarioWeighting.entries.map(
          (entry) => _MetricLine(entry.key, entry.value),
        ),
      ],
    );
  }
}

class ReasoningMemoryPanel extends StatelessWidget {
  const ReasoningMemoryPanel({super.key, required this.read});

  final ReasoningMemoryRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Reasoning Memory',
      badge: '${read.reasoningReliabilityIndex.toStringAsFixed(0)} RRI',
      color: _scoreColor(read.reasoningReliabilityIndex),
      children: <Widget>[
        _MetricLine('Reliability index', read.reasoningReliabilityIndex),
        _MetricLine('Narrative quality', read.narrativeQuality),
        const SizedBox(height: 8),
        _Bullet(read.memoryNote),
        _LabelBlock(
            title: 'Winning reasoning', lines: read.winningReasoningPatterns),
        _LabelBlock(
            title: 'Failing reasoning', lines: read.failingReasoningPatterns),
      ],
    );
  }
}

class SelfOptimizationPanel extends StatelessWidget {
  const SelfOptimizationPanel({super.key, required this.read});

  final SelfOptimizationRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Self-Optimization Layer',
      badge: '${read.fusionCalibration.toStringAsFixed(0)} fusion',
      color: _scoreColor(read.fusionCalibration),
      children: <Widget>[
        _MetricLine('Contributor smoothing', read.contributorSmoothing),
        _MetricLine('Confidence norm', read.confidenceNormalization),
        _MetricLine('Fusion calibration', read.fusionCalibration),
        _MetricLine('Consensus stability', read.consensusStabilization),
        _MetricLine('Prob adjustment', read.probabilisticAdjustment),
        const SizedBox(height: 8),
        _Bullet(read.optimizationAction),
      ],
    );
  }
}

class RegimeEvolutionMapPanel extends StatelessWidget {
  const RegimeEvolutionMapPanel({super.key, required this.read});

  final RegimeEvolutionMapRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Regime Evolution Map',
      badge: read.regimePath.first,
      color: TradingPalette.amber,
      children: <Widget>[
        _MetricLine('Trend strengthen', read.trendStrengthening),
        _MetricLine('Compression cycle', read.volatilityCompressionCycle),
        _MetricLine('Liquidity degrade', read.liquidityDegradation),
        _MetricLine('Sentiment transition', read.sentimentTransition),
        _MetricLine('Macro instability', read.macroInstabilityPhase),
        const SizedBox(height: 8),
        _Bullet(read.evolutionSummary),
        _LabelBlock(title: 'Regime path', lines: read.regimePath),
      ],
    );
  }
}

class FutureMlFoundationPanel extends StatelessWidget {
  const FutureMlFoundationPanel({super.key, required this.read});

  final FutureMlFoundationRead read;

  @override
  Widget build(BuildContext context) {
    return _EvolutionPanel(
      title: 'Future ML Foundation',
      badge: read.probabilisticOptimizationReady ? 'READY' : 'FOUNDATION',
      color: TradingPalette.violet,
      children: <Widget>[
        _CheckRow(label: 'Online learning', ok: read.onlineLearningReady),
        _CheckRow(
            label: 'Contributor retraining',
            ok: read.contributorRetrainingReady),
        _CheckRow(label: 'Replay learning', ok: read.replayLearningReady),
        _CheckRow(
            label: 'Reinforcement layer', ok: read.reinforcementLayerReady),
        _CheckRow(
          label: 'Probabilistic optimization',
          ok: read.probabilisticOptimizationReady,
        ),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Training features', lines: read.trainingFeatures),
        _Bullet(read.foundationNote),
      ],
    );
  }
}

class _EvolutionPanel extends StatelessWidget {
  const _EvolutionPanel({
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

class _ContributorEvolutionRow extends StatelessWidget {
  const _ContributorEvolutionRow({required this.score});

  final ContributorEvolutionScore score;

  @override
  Widget build(BuildContext context) {
    final color = _scoreColor(score.qualityScore);
    final delta = score.evolvedWeight - score.currentWeight;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                score.name,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
            Text(
              '${delta >= 0 ? '+' : ''}${(delta * 100).toStringAsFixed(1)}%',
              style: TextStyle(color: color, fontWeight: FontWeight.w900),
            ),
          ],
        ),
        const SizedBox(height: 6),
        _MetricLine('Quality', score.qualityScore),
        _MetricLine('Reliability', score.reliabilityScore),
        _MetricLine('Usefulness', score.usefulnessScore),
        _Bullet(score.note),
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

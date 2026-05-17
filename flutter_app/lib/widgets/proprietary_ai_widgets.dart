import 'package:flutter/material.dart';

import '../core/proprietary_ai_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class MarketDnaPanel extends StatelessWidget {
  const MarketDnaPanel({super.key, required this.profile});

  final MarketDnaProfile profile;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Market DNA',
      badge: profile.symbol,
      color: _scoreColor(profile.compatibilityScore),
      children: <Widget>[
        Text(
          profile.summary,
          style: const TextStyle(color: TradingPalette.textPrimary),
        ),
        const SizedBox(height: 12),
        _MetricLine('Trend persistence', profile.trendPersistence),
        _MetricLine('Fakeout tendency', profile.fakeoutTendency),
        _MetricLine('Whale sensitivity', profile.whaleSensitivity),
        _MetricLine('DNA compatibility', profile.compatibilityScore),
        const SizedBox(height: 8),
        _Bullet(profile.volatilityRhythm),
        _Bullet(profile.liquidityBehavior),
        _Bullet(profile.breakoutTemperament),
      ],
    );
  }
}

class AiEdgeSignaturePanel extends StatelessWidget {
  const AiEdgeSignaturePanel({super.key, required this.signature});

  final AiEdgeSignatureRead signature;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'AI Edge Signature',
      badge: signature.family,
      color: _scoreColor(signature.score),
      children: <Widget>[
        _MetricLine('Signature score', signature.score),
        _Bullet(signature.label),
        _LabelBlock(title: 'Components', lines: signature.components),
        if (signature.evidence.isNotEmpty) ...<Widget>[
          const SizedBox(height: 8),
          _LabelBlock(title: 'Evidence', lines: signature.evidence),
        ],
      ],
    );
  }
}

class PredictivePressurePanel extends StatelessWidget {
  const PredictivePressurePanel({super.key, required this.pressure});

  final PredictivePressureRead pressure;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Predictive Pressure',
      badge: pressure.direction,
      color: _scoreColor(pressure.netPressure),
      children: <Widget>[
        _MetricLine('Net pressure', pressure.netPressure),
        _MetricLine('Breakout', pressure.breakoutPressure),
        _MetricLine('Liquidation', pressure.liquidationPressure),
        _MetricLine('Vol expansion', pressure.volatilityExpansionProbability),
        _MetricLine('Continuation', pressure.trendContinuationProbability),
        _MetricLine('Exhaustion', pressure.exhaustionProbability),
        const SizedBox(height: 8),
        _Bullet(pressure.summary),
      ],
    );
  }
}

class MarketBehaviorMemoryPanel extends StatelessWidget {
  const MarketBehaviorMemoryPanel({super.key, required this.memory});

  final MarketBehaviorMemoryRead memory;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Market Behavior Memory',
      badge: '${memory.clusterScore.toStringAsFixed(0)} cluster',
      color: TradingPalette.violet,
      children: <Widget>[
        _MetricLine('Cluster score', memory.clusterScore),
        _Bullet(memory.btcAltInfluence),
        _Bullet(memory.memeRotation),
        _Bullet(memory.liquiditySweepTiming),
        _Bullet(memory.volatilityClustering),
        _Bullet(memory.exhaustionSequence),
        const SizedBox(height: 8),
        _LabelBlock(
          title: 'Recurring structures',
          lines: memory.recurringBehaviors,
        ),
      ],
    );
  }
}

class AiMarketNarrativePanel extends StatelessWidget {
  const AiMarketNarrativePanel({super.key, required this.narrative});

  final AiMarketNarrativeRead narrative;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'AI Market Narrative',
      badge: 'DESK READ',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        Text(
          narrative.headline,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 8),
        Text(
          narrative.narrative,
          style: const TextStyle(color: TradingPalette.textPrimary),
        ),
        const SizedBox(height: 10),
        _LabelBlock(
            title: 'Supporting reads', lines: narrative.supportingReads),
      ],
    );
  }
}

class EdgeConfidencePanel extends StatelessWidget {
  const EdgeConfidencePanel({super.key, required this.confidence});

  final EdgeConfidenceRead confidence;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Edge Confidence',
      badge: '${confidence.edgeConfidenceScore.toStringAsFixed(0)}%',
      color: _scoreColor(confidence.edgeConfidenceScore),
      children: <Widget>[
        _MetricLine('Edge confidence', confidence.edgeConfidenceScore),
        _MetricLine('Setup quality', confidence.historicalSetupQuality),
        _MetricLine('Regime fit', confidence.regimeCompatibility),
        _MetricLine('Execution quality', confidence.executionQuality),
        _MetricLine('DNA fit', confidence.marketDnaCompatibility),
        const SizedBox(height: 8),
        _Bullet(confidence.verdict),
      ],
    );
  }
}

class MarketRegimeMapPanel extends StatelessWidget {
  const MarketRegimeMapPanel({super.key, required this.regime});

  final MarketRegimeMapRead regime;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Market Regime Map',
      badge: regime.riskState,
      color: TradingPalette.amber,
      children: <Widget>[
        _Bullet('Trend: ${regime.trendRegime}'),
        _Bullet('Volatility: ${regime.volatilityRegime}'),
        _Bullet('Dominance: ${regime.dominanceRotation}'),
        _Bullet('Leadership: ${regime.sectorLeadership}'),
        _Bullet('Liquidity: ${regime.liquidityConditions}'),
        const SizedBox(height: 8),
        _Bullet(regime.explanation),
      ],
    );
  }
}

class ProprietaryWatchtowerPanel extends StatelessWidget {
  const ProprietaryWatchtowerPanel({super.key, required this.watchtower});

  final ProprietaryWatchtowerRead watchtower;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'Proprietary Watchtower',
      badge: watchtower.status,
      color: _scoreColor(100 - watchtower.structuralShiftScore),
      children: <Widget>[
        _MetricLine('Structural shift', watchtower.structuralShiftScore),
        const SizedBox(height: 8),
        ...watchtower.alerts.map(_WatchAlert.new),
      ],
    );
  }
}

class AiResearchPanel extends StatelessWidget {
  const AiResearchPanel({super.key, required this.research});

  final AiResearchRead research;

  @override
  Widget build(BuildContext context) {
    return _ProPanel(
      title: 'AI Research Layer',
      badge: '${research.patternStudyCount} studies',
      color: TradingPalette.violet,
      children: <Widget>[
        _CheckRow(
            label: 'Replay annotations', ok: research.replayAnnotationReady),
        _CheckRow(
          label: 'Behavioral clustering',
          ok: research.behavioralClusteringReady,
        ),
        _LabelBlock(
          title: 'Setup families',
          lines: research.setupFamilies.isEmpty
              ? const <String>['Awaiting signature sample']
              : research.setupFamilies,
        ),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Research notes', lines: research.researchNotes),
      ],
    );
  }
}

class _ProPanel extends StatelessWidget {
  const _ProPanel({
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
          SizedBox(width: 132, child: Text(label)),
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

class _WatchAlert extends StatelessWidget {
  const _WatchAlert(this.alert);

  final ProprietaryWatchtowerAlert alert;

  @override
  Widget build(BuildContext context) {
    final color = switch (alert.severity) {
      ProprietarySeverity.critical => TradingPalette.neonRed,
      ProprietarySeverity.watch => TradingPalette.amber,
      ProprietarySeverity.normal => TradingPalette.electricBlue,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.auto_graph_rounded, size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  alert.title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 2),
                Text(
                  alert.detail,
                  style: const TextStyle(color: TradingPalette.textMuted),
                ),
              ],
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

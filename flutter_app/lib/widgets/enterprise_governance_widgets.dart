import 'package:flutter/material.dart';

import '../core/enterprise_ai_governance_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class AiGovernanceTimelinePanel extends StatelessWidget {
  const AiGovernanceTimelinePanel({super.key, required this.read});

  final AiGovernanceTimelineRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'AI Governance Timeline',
      badge: '${read.changeCount} changes',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet(read.summary),
        const SizedBox(height: 8),
        ...read.entries.map(
          (entry) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _TimelineRow(entry: entry),
          ),
        ),
      ],
    );
  }
}

class DeterministicDecisionSnapshotPanel extends StatelessWidget {
  const DeterministicDecisionSnapshotPanel({super.key, required this.snapshot});

  final DeterministicDecisionSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Decision Snapshot',
      badge: snapshot.stateHash,
      color: TradingPalette.violet,
      children: <Widget>[
        _KeyValue('Snapshot', snapshot.snapshotId),
        _KeyValue('Signal', snapshot.signalId),
        _KeyValue('Symbol', '${snapshot.symbol} ${snapshot.action}'),
        _KeyValue('Regime', snapshot.regimeState),
        _KeyValue('Lifecycle', snapshot.lifecycleState),
        _MetricLine('Edge confidence', snapshot.edgeConfidence),
        const SizedBox(height: 8),
        _LabelBlock(
          title: 'Reasoning chain',
          lines: snapshot.reasoningChain.take(5).toList(growable: false),
        ),
      ],
    );
  }
}

class DeterministicReplayPanel extends StatelessWidget {
  const DeterministicReplayPanel({super.key, required this.read});

  final DeterministicReplayRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Deterministic Replay',
      badge: read.replayReady ? 'READY' : 'PARTIAL',
      color: _scoreColor(read.replayConsistency),
      children: <Widget>[
        _KeyValue('Replay ID', read.replayId),
        _KeyValue('Replay hash', read.replayHash),
        _MetricLine('Consistency', read.replayConsistency),
        const SizedBox(height: 8),
        _Bullet(read.summary),
        _LabelBlock(title: 'Replay steps', lines: read.replaySteps),
      ],
    );
  }
}

class AiIncidentResponsePanel extends StatelessWidget {
  const AiIncidentResponsePanel({super.key, required this.read});

  final AiIncidentRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'AI Incident Response',
      badge: read.severityLabel,
      color: _incidentColor(read.severity),
      children: <Widget>[
        _MetricLine('Incident score', read.incidentScore),
        _Bullet(read.summary),
        _LabelBlock(title: 'Detected issues', lines: read.detectedIssues),
        _LabelBlock(title: 'Response actions', lines: read.responseActions),
      ],
    );
  }
}

class RolloutControlPanel extends StatelessWidget {
  const RolloutControlPanel({super.key, required this.read});

  final RolloutControlRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Rollout Control',
      badge: read.rolloutMode,
      color: _scoreColor(read.rollbackReadiness),
      children: <Widget>[
        _MetricLine('Rollback readiness', read.rollbackReadiness),
        _Bullet(read.summary),
        _CheckRow(
            label: 'Experimental isolation', ok: read.experimentalIsolation),
        _CheckRow(label: 'Shadow evaluation', ok: read.shadowEvaluation),
        const SizedBox(height: 8),
        _LabelBlock(
          title: 'Feature flags',
          lines: read.featureFlags.entries
              .map(
                  (entry) => '${entry.key}: ${entry.value ? 'enabled' : 'off'}')
              .toList(growable: false),
        ),
      ],
    );
  }
}

class ExplainabilityPersistencePanel extends StatelessWidget {
  const ExplainabilityPersistencePanel({super.key, required this.read});

  final ExplainabilityPersistenceRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Explainability Persistence',
      badge: read.operatorReviewReady ? 'REVIEW READY' : 'CAPTURED',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _KeyValue('Persistence key', read.persistenceKey),
        _CheckRow(label: 'Local retention', ok: read.localRetentionReady),
        _CheckRow(label: 'Operator review', ok: read.operatorReviewReady),
        _Bullet(read.summary),
        _LabelBlock(title: 'Persistable fields', lines: read.persistableFields),
        _LabelBlock(title: 'Review trail', lines: read.reviewTrail),
      ],
    );
  }
}

class ComplianceSafetyPosturePanel extends StatelessWidget {
  const ComplianceSafetyPosturePanel({super.key, required this.read});

  final ComplianceSafetyPostureRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Compliance + Safety Posture',
      badge: '${read.postureScore.toStringAsFixed(0)} posture',
      color: _scoreColor(read.postureScore),
      children: <Widget>[
        _MetricLine('Posture score', read.postureScore),
        _CheckRow(label: 'Advisory boundary', ok: read.advisoryOnlyBoundary),
        _CheckRow(
          label: 'Execution authority separated',
          ok: read.executionAuthoritySeparated,
        ),
        _CheckRow(
          label: 'Paper/live isolation',
          ok: read.paperLiveIsolationValidated,
        ),
        _CheckRow(
            label: 'Operator visibility', ok: read.operatorOverrideVisible),
        _CheckRow(
          label: 'Confirmation integrity',
          ok: read.executionConfirmationIntegrity,
        ),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Controls', lines: read.controls),
      ],
    );
  }
}

class OperationalHealthIndexPanel extends StatelessWidget {
  const OperationalHealthIndexPanel({super.key, required this.read});

  final OperationalHealthRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Operational Health Index',
      badge: '${read.healthIndex.toStringAsFixed(0)} OHI',
      color: _scoreColor(read.healthIndex),
      children: <Widget>[
        _MetricLine('Health index', read.healthIndex),
        _MetricLine('AI stability', read.aiStability),
        _MetricLine('Contributor drift', read.contributorDrift),
        _MetricLine('Advisory consistency', read.executionAdvisoryConsistency),
        _MetricLine('Replay consistency', read.replayConsistency),
        _MetricLine('Event sync quality', read.eventSynchronizationQuality),
        _MetricLine('Recovery success', read.recoverySuccessRate),
        const SizedBox(height: 8),
        _Bullet(read.summary),
      ],
    );
  }
}

class ResearchExperimentationPanel extends StatelessWidget {
  const ResearchExperimentationPanel({super.key, required this.read});

  final ResearchExperimentationRead read;

  @override
  Widget build(BuildContext context) {
    return _GovernancePanel(
      title: 'Research Experimentation',
      badge: read.productionIsolation ? 'ISOLATED' : 'CHECK',
      color: TradingPalette.violet,
      children: <Widget>[
        _CheckRow(label: 'Replay evaluation', ok: read.replayEvaluationReady),
        _CheckRow(label: 'Production isolation', ok: read.productionIsolation),
        _Bullet(read.summary),
        _LabelBlock(
          title: 'Experimental contributors',
          lines: read.experimentalContributors,
        ),
        _LabelBlock(title: 'Shadow comparisons', lines: read.shadowComparisons),
        const SizedBox(height: 8),
        ...read.researchBenchmarks.entries.take(4).map(
              (entry) => _MetricLine(entry.key, entry.value),
            ),
      ],
    );
  }
}

class _GovernancePanel extends StatelessWidget {
  const _GovernancePanel({
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

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.entry});

  final AiGovernanceTimelineEntry entry;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          width: 8,
          height: 8,
          margin: const EdgeInsets.only(top: 6),
          decoration: const BoxDecoration(
            color: TradingPalette.electricBlue,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                '${entry.label} • ${entry.category}',
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 4),
              Text(
                '${entry.before} -> ${entry.after}',
                style: const TextStyle(color: TradingPalette.textPrimary),
              ),
              const SizedBox(height: 4),
              Text(
                entry.reason,
                style: const TextStyle(color: TradingPalette.textMuted),
              ),
            ],
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
          SizedBox(width: 148, child: Text(label)),
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

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 118,
            child: Text(label, style: Theme.of(context).textTheme.labelMedium),
          ),
          Expanded(
            child: Text(
              value,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w800),
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
    return _Bullet('${ok ? 'Pass' : 'Review'}: $label');
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

Color _incidentColor(AiIncidentSeverity severity) {
  switch (severity) {
    case AiIncidentSeverity.normal:
      return TradingPalette.neonGreen;
    case AiIncidentSeverity.watch:
      return TradingPalette.amber;
    case AiIncidentSeverity.major:
    case AiIncidentSeverity.critical:
      return TradingPalette.neonRed;
  }
}

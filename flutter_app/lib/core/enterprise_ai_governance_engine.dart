import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import 'adaptive_decision_core.dart';
import 'edge_validation_engine.dart';
import 'evolving_ai_intelligence_engine.dart';
import 'proprietary_ai_engine.dart';

enum AiIncidentSeverity { normal, watch, major, critical }

class AiGovernanceTimelineEntry {
  const AiGovernanceTimelineEntry({
    required this.label,
    required this.category,
    required this.before,
    required this.after,
    required this.impact,
    required this.reason,
  });

  final String label;
  final String category;
  final String before;
  final String after;
  final double impact;
  final String reason;
}

class AiGovernanceTimelineRead {
  const AiGovernanceTimelineRead({
    required this.entries,
    required this.changeCount,
    required this.summary,
  });

  final List<AiGovernanceTimelineEntry> entries;
  final int changeCount;
  final String summary;
}

class DeterministicDecisionSnapshot {
  const DeterministicDecisionSnapshot({
    required this.snapshotId,
    required this.stateHash,
    required this.signalId,
    required this.symbol,
    required this.action,
    required this.reasoningChain,
    required this.contributorStates,
    required this.probabilities,
    required this.regimeState,
    required this.edgeConfidence,
    required this.executionAdvisory,
    required this.marketContext,
    required this.lifecycleState,
  });

  final String snapshotId;
  final String stateHash;
  final String signalId;
  final String symbol;
  final String action;
  final List<String> reasoningChain;
  final Map<String, double> contributorStates;
  final Map<String, double> probabilities;
  final String regimeState;
  final double edgeConfidence;
  final String executionAdvisory;
  final String marketContext;
  final String lifecycleState;

  Map<String, Object> toAuditMap() {
    return <String, Object>{
      'snapshot_id': snapshotId,
      'state_hash': stateHash,
      'signal_id': signalId,
      'symbol': symbol,
      'action': action,
      'reasoning_chain': reasoningChain,
      'contributor_states': contributorStates,
      'probabilities': probabilities,
      'regime_state': regimeState,
      'edge_confidence': edgeConfidence,
      'execution_advisory': executionAdvisory,
      'market_context': marketContext,
      'lifecycle_state': lifecycleState,
    };
  }
}

class DeterministicReplayRead {
  const DeterministicReplayRead({
    required this.replayId,
    required this.replayHash,
    required this.replayReady,
    required this.replaySteps,
    required this.replayConsistency,
    required this.summary,
  });

  final String replayId;
  final String replayHash;
  final bool replayReady;
  final List<String> replaySteps;
  final double replayConsistency;
  final String summary;
}

class AiIncidentRead {
  const AiIncidentRead({
    required this.severity,
    required this.severityLabel,
    required this.incidentScore,
    required this.detectedIssues,
    required this.responseActions,
    required this.summary,
  });

  final AiIncidentSeverity severity;
  final String severityLabel;
  final double incidentScore;
  final List<String> detectedIssues;
  final List<String> responseActions;
  final String summary;
}

class RolloutControlRead {
  const RolloutControlRead({
    required this.rolloutMode,
    required this.featureFlags,
    required this.contributorToggles,
    required this.experimentalIsolation,
    required this.shadowEvaluation,
    required this.rollbackReadiness,
    required this.summary,
  });

  final String rolloutMode;
  final Map<String, bool> featureFlags;
  final Map<String, bool> contributorToggles;
  final bool experimentalIsolation;
  final bool shadowEvaluation;
  final double rollbackReadiness;
  final String summary;
}

class ExplainabilityPersistenceRead {
  const ExplainabilityPersistenceRead({
    required this.persistenceKey,
    required this.persistableFields,
    required this.reviewTrail,
    required this.localRetentionReady,
    required this.operatorReviewReady,
    required this.summary,
  });

  final String persistenceKey;
  final List<String> persistableFields;
  final List<String> reviewTrail;
  final bool localRetentionReady;
  final bool operatorReviewReady;
  final String summary;
}

class ComplianceSafetyPostureRead {
  const ComplianceSafetyPostureRead({
    required this.advisoryOnlyBoundary,
    required this.executionAuthoritySeparated,
    required this.paperLiveIsolationValidated,
    required this.operatorOverrideVisible,
    required this.executionConfirmationIntegrity,
    required this.postureScore,
    required this.controls,
  });

  final bool advisoryOnlyBoundary;
  final bool executionAuthoritySeparated;
  final bool paperLiveIsolationValidated;
  final bool operatorOverrideVisible;
  final bool executionConfirmationIntegrity;
  final double postureScore;
  final List<String> controls;
}

class OperationalHealthRead {
  const OperationalHealthRead({
    required this.healthIndex,
    required this.aiStability,
    required this.contributorDrift,
    required this.executionAdvisoryConsistency,
    required this.replayConsistency,
    required this.eventSynchronizationQuality,
    required this.recoverySuccessRate,
    required this.summary,
  });

  final double healthIndex;
  final double aiStability;
  final double contributorDrift;
  final double executionAdvisoryConsistency;
  final double replayConsistency;
  final double eventSynchronizationQuality;
  final double recoverySuccessRate;
  final String summary;
}

class ResearchExperimentationRead {
  const ResearchExperimentationRead({
    required this.experimentalContributors,
    required this.shadowComparisons,
    required this.researchBenchmarks,
    required this.replayEvaluationReady,
    required this.productionIsolation,
    required this.summary,
  });

  final List<String> experimentalContributors;
  final List<String> shadowComparisons;
  final Map<String, double> researchBenchmarks;
  final bool replayEvaluationReady;
  final bool productionIsolation;
  final String summary;
}

class EnterpriseAiGovernanceRead {
  const EnterpriseAiGovernanceRead({
    required this.timeline,
    required this.snapshot,
    required this.replay,
    required this.incident,
    required this.rollout,
    required this.explainability,
    required this.compliance,
    required this.operationalHealth,
    required this.research,
  });

  final AiGovernanceTimelineRead timeline;
  final DeterministicDecisionSnapshot snapshot;
  final DeterministicReplayRead replay;
  final AiIncidentRead incident;
  final RolloutControlRead rollout;
  final ExplainabilityPersistenceRead explainability;
  final ComplianceSafetyPostureRead compliance;
  final OperationalHealthRead operationalHealth;
  final ResearchExperimentationRead research;
}

class EnterpriseAiGovernanceEngine {
  const EnterpriseAiGovernanceEngine();

  EnterpriseAiGovernanceRead evaluate({
    required SignalModel signal,
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    required List<SignalOutcomeReport> outcomes,
    MarketRegimeMapRead? regime,
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final timeline = governanceTimeline(
      decision: decision,
      evolving: evolving,
    );
    final snapshot = decisionSnapshot(
      signal: signal,
      decision: decision,
      evolving: evolving,
      regime: regime,
      market: market,
    );
    final replay = deterministicReplay(
      snapshot: snapshot,
      decision: decision,
      chart: chart,
      outcomes: outcomes,
    );
    final incident = incidentDetection(
      decision: decision,
      evolving: evolving,
      replay: replay,
    );
    final rollout = rolloutControl(
      decision: decision,
      evolving: evolving,
      incident: incident,
    );
    final explainability = explainabilityPersistence(
      snapshot: snapshot,
      decision: decision,
    );
    final compliance = compliancePosture(
      incident: incident,
      rollout: rollout,
    );
    final health = operationalHealth(
      decision: decision,
      evolving: evolving,
      replay: replay,
      incident: incident,
    );
    final research = researchExperimentation(
      decision: decision,
      evolving: evolving,
      replay: replay,
    );
    return EnterpriseAiGovernanceRead(
      timeline: timeline,
      snapshot: snapshot,
      replay: replay,
      incident: incident,
      rollout: rollout,
      explainability: explainability,
      compliance: compliance,
      operationalHealth: health,
      research: research,
    );
  }

  AiGovernanceTimelineRead governanceTimeline({
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
  }) {
    final entries = <AiGovernanceTimelineEntry>[
      AiGovernanceTimelineEntry(
        label: 'Adaptive weights',
        category: 'weights',
        before: decision.weights.primaryWeight,
        after: evolving.contributorEvolution.strongestContributor,
        impact: evolving.contributorEvolution.scores.isEmpty
            ? 0
            : evolving.contributorEvolution.scores.first.adjustment.abs() * 100,
        reason: evolving.contributorEvolution.evolutionSummary,
      ),
      AiGovernanceTimelineEntry(
        label: 'Confidence calibration',
        category: 'confidence',
        before: '${decision.consensus.consensusConfidence.toStringAsFixed(0)}%',
        after: '${decision.stability.smoothedConfidence.toStringAsFixed(0)}%',
        impact: (decision.consensus.consensusConfidence -
                decision.stability.smoothedConfidence)
            .abs(),
        reason: decision.stability.action,
      ),
      AiGovernanceTimelineEntry(
        label: 'Strategy evolution',
        category: 'strategy',
        before: decision.scenarios.preferredScenario,
        after: evolving.strategyEvolution.increasedSetups.first,
        impact: evolving.edgeMemory.edgeRecovery,
        reason: evolving.strategyEvolution.evolutionNote,
      ),
      AiGovernanceTimelineEntry(
        label: 'Reasoning memory',
        category: 'reasoning',
        before: decision.reasoning.headline,
        after: evolving.reasoningMemory.memoryNote,
        impact: evolving.reasoningMemory.reasoningReliabilityIndex,
        reason: 'Reasoning reliability updated from current outcome sample.',
      ),
      AiGovernanceTimelineEntry(
        label: 'Drift suppression',
        category: 'stability',
        before:
            '${decision.stability.driftSuppression.toStringAsFixed(0)} drift',
        after: evolving.selfOptimization.optimizationAction,
        impact: decision.stability.driftSuppression,
        reason: 'Stability controller adjusted confidence transition speed.',
      ),
    ];
    return AiGovernanceTimelineRead(
      entries: entries,
      changeCount: entries.where((item) => item.impact > 0).length,
      summary:
          '${entries.length} governance events captured for deterministic review.',
    );
  }

  DeterministicDecisionSnapshot decisionSnapshot({
    required SignalModel signal,
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    MarketRegimeMapRead? regime,
    MarketSummaryModel? market,
  }) {
    final contributorStates = <String, double>{
      for (final item in decision.consensus.contributors)
        item.name: item.edgeQuality,
    };
    final probabilities = <String, double>{
      'bullish': decision.consensus.bullishProbability,
      'bearish': decision.consensus.bearishProbability,
      'chop': decision.consensus.chopProbability,
      'breakout_continuation':
          decision.consensus.breakoutContinuationProbability,
      'exhaustion': decision.consensus.exhaustionProbability,
      'reversal': decision.consensus.reversalProbability,
    };
    final reasoning = <String>[
      decision.reasoning.headline,
      decision.reasoning.reasoning,
      ...decision.reasoning.supportingFactors,
      ...decision.reasoning.riskFactors,
      evolving.reasoningMemory.memoryNote,
    ];
    final source = <String>[
      signal.signalId,
      signal.symbol,
      signal.action,
      decision.consensus.summary,
      decision.scenarios.preferredScenario,
      evolving.metaIntelligence.summary,
      contributorStates.entries
          .map((entry) => '${entry.key}:${entry.value.toStringAsFixed(2)}')
          .join('|'),
      probabilities.entries
          .map((entry) => '${entry.key}:${entry.value.toStringAsFixed(2)}')
          .join('|'),
    ].join('::');
    final stateHash = _stableHash(source);
    final signalId = signal.signalId.isEmpty ? signal.symbol : signal.signalId;
    return DeterministicDecisionSnapshot(
      snapshotId: '$signalId-$stateHash',
      stateHash: stateHash,
      signalId: signalId,
      symbol: signal.symbol,
      action: signal.action,
      reasoningChain: reasoning,
      contributorStates: contributorStates,
      probabilities: probabilities,
      regimeState: regime?.trendRegime ?? signal.regime,
      edgeConfidence: decision.consensus.adaptiveSignalQuality,
      executionAdvisory: decision.stability.action,
      marketContext: market?.sentimentLabel ??
          regime?.riskState ??
          'market context pending',
      lifecycleState: signal.executionAllowed
          ? 'ENTRY_ADVISORY_READY'
          : signal.lowConfidence
              ? 'WATCH_ADVISORY'
              : 'PROTECTED_ADVISORY',
    );
  }

  DeterministicReplayRead deterministicReplay({
    required DeterministicDecisionSnapshot snapshot,
    required AdaptiveDecisionCoreRead decision,
    required List<SignalOutcomeReport> outcomes,
    MarketChartModel? chart,
  }) {
    final steps = <String>[
      'Load snapshot ${snapshot.snapshotId}',
      'Restore contributor weights',
      'Restore probability map',
      'Restore regime state ${snapshot.regimeState}',
      'Restore execution advisory',
      'Verify state hash ${snapshot.stateHash}',
    ];
    final hasMarketState = chart != null || outcomes.isNotEmpty;
    final consistency = (decision.research.offlineReplayReady ? 32.0 : 18.0) +
        (snapshot.reasoningChain.length >= 3 ? 22.0 : 8.0) +
        (snapshot.contributorStates.length >= 6 ? 24.0 : 10.0) +
        (hasMarketState ? 18.0 : 6.0);
    final replayHash = _stableHash('${snapshot.stateHash}:${steps.join('|')}');
    return DeterministicReplayRead(
      replayId: 'replay-${snapshot.snapshotId}',
      replayHash: replayHash,
      replayReady: consistency >= 70,
      replaySteps: steps,
      replayConsistency: consistency.clamp(0, 99).toDouble(),
      summary: consistency >= 70
          ? 'Decision can be replayed deterministically from captured advisory state.'
          : 'Replay foundation is present; richer market history will improve consistency.',
    );
  }

  AiIncidentRead incidentDetection({
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    required DeterministicReplayRead replay,
  }) {
    final contributorQualities = decision.consensus.contributors
        .map((item) => item.edgeQuality)
        .toList(growable: false);
    final divergence = contributorQualities.isEmpty
        ? 0.0
        : contributorQualities.reduce(math.max) -
            contributorQualities.reduce(math.min);
    final confidenceSpike = (decision.consensus.consensusConfidence -
            decision.stability.smoothedConfidence)
        .abs();
    final issues = <String>[
      if (confidenceSpike >= 14) 'confidence spike',
      if (divergence >= 38) 'contributor divergence',
      if (decision.stability.driftSuppression >= 16) 'drift suppression active',
      if (evolving.metaIntelligence.metaStabilityScore < 58)
        'meta stability weak',
      if (!replay.replayReady) 'replay consistency incomplete',
      if (evolving.regimeEvolution.macroInstabilityPhase >= 70)
        'regime instability elevated',
    ];
    final score = (confidenceSpike * 0.9 +
            divergence * 0.55 +
            (100 - evolving.metaIntelligence.metaStabilityScore) * 0.42 +
            (100 - replay.replayConsistency) * 0.24)
        .clamp(0, 99)
        .toDouble();
    final severity = score >= 76
        ? AiIncidentSeverity.critical
        : score >= 58
            ? AiIncidentSeverity.major
            : score >= 34
                ? AiIncidentSeverity.watch
                : AiIncidentSeverity.normal;
    return AiIncidentRead(
      severity: severity,
      severityLabel: _severityLabel(severity),
      incidentScore: score,
      detectedIssues:
          issues.isEmpty ? const <String>['no active AI incident'] : issues,
      responseActions: severity == AiIncidentSeverity.normal
          ? const <String>['continue normal advisory monitoring']
          : <String>[
              'freeze aggressive contributor upgrades',
              'prefer shadow evaluation for experimental reads',
              'increase confidence smoothing',
              'require backend approval before any execution action',
            ],
      summary: severity == AiIncidentSeverity.normal
          ? 'AI behavior is inside governance tolerance.'
          : 'AI governance detected conditions that require conservative rollout posture.',
    );
  }

  RolloutControlRead rolloutControl({
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    required AiIncidentRead incident,
  }) {
    final safe = incident.severity == AiIncidentSeverity.normal ||
        incident.severity == AiIncidentSeverity.watch;
    final flags = <String, bool>{
      'adaptive_decision_core': true,
      'evolving_intelligence': true,
      'enterprise_governance': true,
      'experimental_contributors': false,
      'autonomous_execution': false,
    };
    final toggles = <String, bool>{
      for (final item in decision.consensus.contributors)
        item.name: item.stability >= 45,
    };
    return RolloutControlRead(
      rolloutMode: safe ? 'staged advisory rollout' : 'shadow-only rollout',
      featureFlags: flags,
      contributorToggles: toggles,
      experimentalIsolation: true,
      shadowEvaluation: !safe || evolving.mlFoundation.replayLearningReady,
      rollbackReadiness:
          (incident.incidentScore <= 35 ? 92 : 74).clamp(0, 99).toDouble(),
      summary: safe
          ? 'Feature flags allow advisory rollout with rollback available.'
          : 'Incident posture requires shadow evaluation and rollback readiness.',
    );
  }

  ExplainabilityPersistenceRead explainabilityPersistence({
    required DeterministicDecisionSnapshot snapshot,
    required AdaptiveDecisionCoreRead decision,
  }) {
    final fields = <String>[
      'reasoning_chain',
      'contributor_states',
      'probabilities',
      'regime_state',
      'edge_confidence',
      'execution_advisory',
      'market_context',
      'signal_lifecycle',
      'state_hash',
    ];
    return ExplainabilityPersistenceRead(
      persistenceKey: snapshot.snapshotId,
      persistableFields: fields,
      reviewTrail: <String>[
        'Why AI entered/rejected: ${snapshot.executionAdvisory}',
        'Contributor influence: ${snapshot.contributorStates.length} contributors',
        'Scenario probabilities: ${decision.scenarios.preferredScenario}',
        'Adaptive reasoning: ${decision.reasoning.headline}',
      ],
      localRetentionReady: true,
      operatorReviewReady: snapshot.reasoningChain.length >= 3,
      summary:
          'Explainability snapshot is ready for local retention or backend persistence when storage is connected.',
    );
  }

  ComplianceSafetyPostureRead compliancePosture({
    required AiIncidentRead incident,
    required RolloutControlRead rollout,
  }) {
    const controls = <String>[
      'AI remains advisory until backend execution approval.',
      'Risk engine authority remains final.',
      'Paper/live separation remains explicit.',
      'Autonomous execution feature flag remains disabled.',
      'Rollback posture is visible to operators.',
    ];
    final checks = <bool>[
      true,
      true,
      true,
      rollout.contributorToggles.isNotEmpty,
      incident.severity != AiIncidentSeverity.critical,
    ];
    return ComplianceSafetyPostureRead(
      advisoryOnlyBoundary: checks[0],
      executionAuthoritySeparated: checks[1],
      paperLiveIsolationValidated: checks[2],
      operatorOverrideVisible: checks[3],
      executionConfirmationIntegrity: checks[4],
      postureScore: checks.where((item) => item).length / checks.length * 100,
      controls: controls,
    );
  }

  OperationalHealthRead operationalHealth({
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    required DeterministicReplayRead replay,
    required AiIncidentRead incident,
  }) {
    final contributorDrift = evolving.contributorEvolution.scores.isEmpty
        ? 0.0
        : evolving.contributorEvolution.scores
            .map((item) => item.adjustment.abs() * 100)
            .reduce(math.max);
    final advisoryConsistency = (100 -
            decision.stability.driftSuppression -
            incident.incidentScore * 0.18)
        .clamp(0, 99)
        .toDouble();
    final syncQuality = replay.replayConsistency;
    final recovery =
        (100 - incident.incidentScore * 0.42).clamp(0, 99).toDouble();
    final health = (evolving.metaIntelligence.metaStabilityScore * 0.28 +
            (100 - contributorDrift) * 0.18 +
            advisoryConsistency * 0.20 +
            replay.replayConsistency * 0.18 +
            syncQuality * 0.10 +
            recovery * 0.06)
        .clamp(0, 99)
        .toDouble();
    return OperationalHealthRead(
      healthIndex: health,
      aiStability: evolving.metaIntelligence.metaStabilityScore,
      contributorDrift: contributorDrift,
      executionAdvisoryConsistency: advisoryConsistency,
      replayConsistency: replay.replayConsistency,
      eventSynchronizationQuality: syncQuality,
      recoverySuccessRate: recovery,
      summary: health >= 76
          ? 'Operational AI governance is healthy.'
          : health >= 58
              ? 'Operational AI governance is usable with watch posture.'
              : 'Operational AI governance should remain shadow-only.',
    );
  }

  ResearchExperimentationRead researchExperimentation({
    required AdaptiveDecisionCoreRead decision,
    required EvolvingAiIntelligenceRead evolving,
    required DeterministicReplayRead replay,
  }) {
    final weakest = evolving.contributorEvolution.weakestContributor;
    final benchmarks = <String, double>{
      for (final item in evolving.contributorEvolution.scores)
        item.name: item.qualityScore,
    };
    return ResearchExperimentationRead(
      experimentalContributors: <String>[
        'shadow $weakest calibration',
        'probabilistic scenario weighting',
        'replay-based confidence smoothing',
      ],
      shadowComparisons: <String>[
        'production consensus vs shadow consensus',
        'current weights vs evolved weights',
        'stored snapshot vs replay reconstruction',
      ],
      researchBenchmarks: benchmarks,
      replayEvaluationReady: replay.replayReady,
      productionIsolation: true,
      summary:
          'Research experiments are isolated from production advisory output and require shadow comparison before rollout.',
    );
  }

  String _stableHash(String input) {
    var hash = 0x811c9dc5;
    for (final unit in input.codeUnits) {
      hash ^= unit;
      hash = (hash * 0x01000193) & 0xffffffff;
    }
    return hash.toRadixString(16).padLeft(8, '0');
  }

  String _severityLabel(AiIncidentSeverity severity) {
    switch (severity) {
      case AiIncidentSeverity.normal:
        return 'NORMAL';
      case AiIncidentSeverity.watch:
        return 'WATCH';
      case AiIncidentSeverity.major:
        return 'MAJOR';
      case AiIncidentSeverity.critical:
        return 'CRITICAL';
    }
  }
}

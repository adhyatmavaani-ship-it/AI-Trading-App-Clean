import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import 'adaptive_decision_core.dart';
import 'edge_validation_engine.dart';
import 'proprietary_ai_engine.dart';

class ContributorEvolutionScore {
  const ContributorEvolutionScore({
    required this.name,
    required this.currentWeight,
    required this.evolvedWeight,
    required this.qualityScore,
    required this.reliabilityScore,
    required this.usefulnessScore,
    required this.adjustment,
    required this.note,
  });

  final String name;
  final double currentWeight;
  final double evolvedWeight;
  final double qualityScore;
  final double reliabilityScore;
  final double usefulnessScore;
  final double adjustment;
  final String note;
}

class ContributorEvolutionRead {
  const ContributorEvolutionRead({
    required this.scores,
    required this.strongestContributor,
    required this.weakestContributor,
    required this.evolutionSummary,
  });

  final List<ContributorEvolutionScore> scores;
  final String strongestContributor;
  final String weakestContributor;
  final String evolutionSummary;
}

class LongHorizonEdgeMemoryRead {
  const LongHorizonEdgeMemoryRead({
    required this.multiWeekSetupQuality,
    required this.regimePersistence,
    required this.recurringFailurePatterns,
    required this.edgeDecay,
    required this.edgeRecovery,
    required this.marketPersonalityShift,
    required this.memorySummary,
  });

  final double multiWeekSetupQuality;
  final double regimePersistence;
  final List<String> recurringFailurePatterns;
  final double edgeDecay;
  final double edgeRecovery;
  final double marketPersonalityShift;
  final String memorySummary;
}

class MetaIntelligenceRead {
  const MetaIntelligenceRead({
    required this.metaStabilityScore,
    required this.overreactingContributors,
    required this.laggingContributors,
    required this.destabilizingRegimes,
    required this.unreliableAssets,
    required this.processQuality,
    required this.summary,
  });

  final double metaStabilityScore;
  final List<String> overreactingContributors;
  final List<String> laggingContributors;
  final List<String> destabilizingRegimes;
  final List<String> unreliableAssets;
  final double processQuality;
  final String summary;
}

class StrategyEvolutionRead {
  const StrategyEvolutionRead({
    required this.reducedSetups,
    required this.increasedSetups,
    required this.suppressedEnvironments,
    required this.leveragePreference,
    required this.scenarioWeighting,
    required this.evolutionNote,
  });

  final List<String> reducedSetups;
  final List<String> increasedSetups;
  final List<String> suppressedEnvironments;
  final double leveragePreference;
  final Map<String, double> scenarioWeighting;
  final String evolutionNote;
}

class ReasoningMemoryRead {
  const ReasoningMemoryRead({
    required this.reasoningReliabilityIndex,
    required this.winningReasoningPatterns,
    required this.failingReasoningPatterns,
    required this.narrativeQuality,
    required this.memoryNote,
  });

  final double reasoningReliabilityIndex;
  final List<String> winningReasoningPatterns;
  final List<String> failingReasoningPatterns;
  final double narrativeQuality;
  final String memoryNote;
}

class SelfOptimizationRead {
  const SelfOptimizationRead({
    required this.contributorSmoothing,
    required this.confidenceNormalization,
    required this.fusionCalibration,
    required this.consensusStabilization,
    required this.probabilisticAdjustment,
    required this.optimizationAction,
  });

  final double contributorSmoothing;
  final double confidenceNormalization;
  final double fusionCalibration;
  final double consensusStabilization;
  final double probabilisticAdjustment;
  final String optimizationAction;
}

class RegimeEvolutionMapRead {
  const RegimeEvolutionMapRead({
    required this.trendStrengthening,
    required this.volatilityCompressionCycle,
    required this.liquidityDegradation,
    required this.sentimentTransition,
    required this.macroInstabilityPhase,
    required this.regimePath,
    required this.evolutionSummary,
  });

  final double trendStrengthening;
  final double volatilityCompressionCycle;
  final double liquidityDegradation;
  final double sentimentTransition;
  final double macroInstabilityPhase;
  final List<String> regimePath;
  final String evolutionSummary;
}

class FutureMlFoundationRead {
  const FutureMlFoundationRead({
    required this.onlineLearningReady,
    required this.contributorRetrainingReady,
    required this.replayLearningReady,
    required this.reinforcementLayerReady,
    required this.probabilisticOptimizationReady,
    required this.trainingFeatures,
    required this.foundationNote,
  });

  final bool onlineLearningReady;
  final bool contributorRetrainingReady;
  final bool replayLearningReady;
  final bool reinforcementLayerReady;
  final bool probabilisticOptimizationReady;
  final List<String> trainingFeatures;
  final String foundationNote;
}

class EvolvingAiIntelligenceRead {
  const EvolvingAiIntelligenceRead({
    required this.contributorEvolution,
    required this.edgeMemory,
    required this.metaIntelligence,
    required this.strategyEvolution,
    required this.reasoningMemory,
    required this.selfOptimization,
    required this.regimeEvolution,
    required this.mlFoundation,
  });

  final ContributorEvolutionRead contributorEvolution;
  final LongHorizonEdgeMemoryRead edgeMemory;
  final MetaIntelligenceRead metaIntelligence;
  final StrategyEvolutionRead strategyEvolution;
  final ReasoningMemoryRead reasoningMemory;
  final SelfOptimizationRead selfOptimization;
  final RegimeEvolutionMapRead regimeEvolution;
  final FutureMlFoundationRead mlFoundation;
}

class EvolvingAiIntelligenceEngine {
  const EvolvingAiIntelligenceEngine();

  EvolvingAiIntelligenceRead evaluate({
    required AdaptiveDecisionCoreRead decision,
    required List<SignalModel> signals,
    required List<SignalOutcomeReport> outcomes,
    MarketRegimeMapRead? regime,
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final contributorEvolution = evolveContributors(
      decision: decision,
      outcomes: outcomes,
    );
    final edgeMemory = longHorizonEdgeMemory(
      signals: signals,
      outcomes: outcomes,
      decision: decision,
      market: market,
    );
    final meta = metaIntelligence(
      contributorEvolution: contributorEvolution,
      edgeMemory: edgeMemory,
      outcomes: outcomes,
      decision: decision,
    );
    final strategy = strategyEvolution(
      decision: decision,
      edgeMemory: edgeMemory,
      meta: meta,
    );
    final reasoning = reasoningMemory(
      decision: decision,
      outcomes: outcomes,
      signals: signals,
    );
    final selfOptimization = selfOptimizationLayer(
      decision: decision,
      meta: meta,
      strategy: strategy,
    );
    final regimeEvolution = regimeEvolutionMap(
      decision: decision,
      regime: regime,
      market: market,
      chart: chart,
      edgeMemory: edgeMemory,
    );
    final mlFoundation = futureMlFoundation(
      decision: decision,
      outcomes: outcomes,
      reasoning: reasoning,
      contributorEvolution: contributorEvolution,
    );
    return EvolvingAiIntelligenceRead(
      contributorEvolution: contributorEvolution,
      edgeMemory: edgeMemory,
      metaIntelligence: meta,
      strategyEvolution: strategy,
      reasoningMemory: reasoning,
      selfOptimization: selfOptimization,
      regimeEvolution: regimeEvolution,
      mlFoundation: mlFoundation,
    );
  }

  ContributorEvolutionRead evolveContributors({
    required AdaptiveDecisionCoreRead decision,
    required List<SignalOutcomeReport> outcomes,
  }) {
    final expectancy = _expectancy(outcomes);
    final scores = decision.consensus.contributors.map((item) {
      final usefulness =
          (item.edgeQuality * 0.42 + item.confidence * 0.28 + expectancy * 12)
              .clamp(0, 99)
              .toDouble();
      final reliability = (item.stability * 0.64 +
              decision.calibration.confidenceStabilityIndex * 0.24)
          .clamp(0, 99)
          .toDouble();
      final quality =
          (usefulness * 0.48 + reliability * 0.36 + item.weight * 100 * 0.16)
              .clamp(0, 99)
              .toDouble();
      final adjustment = quality >= 72
          ? 0.08
          : quality < 52
              ? -0.10
              : 0.0;
      return ContributorEvolutionScore(
        name: item.name,
        currentWeight: item.weight,
        evolvedWeight:
            (item.weight * (1 + adjustment)).clamp(0.01, 0.35).toDouble(),
        qualityScore: quality,
        reliabilityScore: reliability,
        usefulnessScore: usefulness,
        adjustment: adjustment,
        note: adjustment > 0
            ? 'Increase influence gradually.'
            : adjustment < 0
                ? 'Reduce influence until reliability improves.'
                : 'Keep influence stable.',
      );
    }).toList()
      ..sort((a, b) => b.qualityScore.compareTo(a.qualityScore));
    return ContributorEvolutionRead(
      scores: scores,
      strongestContributor: scores.isEmpty ? 'none' : scores.first.name,
      weakestContributor: scores.isEmpty ? 'none' : scores.last.name,
      evolutionSummary: scores.isEmpty
          ? 'Contributor evolution is waiting for ensemble data.'
          : '${scores.first.name} is earning higher trust; ${scores.last.name} needs monitoring.',
    );
  }

  LongHorizonEdgeMemoryRead longHorizonEdgeMemory({
    required List<SignalModel> signals,
    required List<SignalOutcomeReport> outcomes,
    required AdaptiveDecisionCoreRead decision,
    MarketSummaryModel? market,
  }) {
    final expectancy = _expectancy(outcomes);
    final failurePatterns = <String>[
      if (decision.consensus.exhaustionProbability >= 62)
        'Exhaustion probability is repeatedly elevated.',
      if (decision.calibration.overconfidentFailurePenalty >= 25)
        'Overconfident failures are recurring.',
      if (outcomes.where((item) => item.slHit).length >= 2)
        'Stop-loss pressure appeared in recent outcomes.',
      if (signals.where((item) => item.lowConfidence).length >= 3)
        'Low-confidence signal density remains high.',
    ];
    final regimePersistence = outcomes.isEmpty
        ? decision.stability.regimeStabilization
        : _dominantShare(outcomes.map((item) => item.marketRegime));
    final edgeDecay = (decision.consensus.exhaustionProbability * 0.36 +
            decision.calibration.overconfidentFailurePenalty * 0.32 -
            expectancy * 8)
        .clamp(0, 99)
        .toDouble();
    final edgeRecovery = (decision.consensus.adaptiveSignalQuality * 0.36 +
            decision.calibration.underconfidentWinBoost * 0.28 +
            math.max(expectancy, 0) * 10)
        .clamp(0, 99)
        .toDouble();
    final personalityShift = ((market?.avgVolatilityPct ?? 4) * 10 +
            decision.stability.driftSuppression +
            decision.consensus.chopProbability * 0.22)
        .clamp(0, 99)
        .toDouble();
    return LongHorizonEdgeMemoryRead(
      multiWeekSetupQuality:
          (decision.consensus.adaptiveSignalQuality + expectancy * 8)
              .clamp(0, 99)
              .toDouble(),
      regimePersistence: regimePersistence,
      recurringFailurePatterns: failurePatterns.isEmpty
          ? const <String>['No persistent failure cluster detected.']
          : failurePatterns,
      edgeDecay: edgeDecay,
      edgeRecovery: edgeRecovery,
      marketPersonalityShift: personalityShift,
      memorySummary: edgeDecay > edgeRecovery
          ? 'Long-horizon memory is detecting edge decay pressure.'
          : 'Long-horizon memory sees recoverable or stable edge behavior.',
    );
  }

  MetaIntelligenceRead metaIntelligence({
    required ContributorEvolutionRead contributorEvolution,
    required LongHorizonEdgeMemoryRead edgeMemory,
    required List<SignalOutcomeReport> outcomes,
    required AdaptiveDecisionCoreRead decision,
  }) {
    final overreacting = decision.consensus.contributors
        .where((item) => item.confidence >= 76 && item.stability < 58)
        .map((item) => item.name)
        .toList(growable: false);
    final lagging = decision.consensus.contributors
        .where((item) => item.confidence < 54 && item.edgeQuality >= 66)
        .map((item) => item.name)
        .toList(growable: false);
    final destabilizing = _weakGroups(
      outcomes,
      (item) => item.marketRegime,
    );
    final unreliableAssets = _weakGroups(
      outcomes,
      (item) => item.symbol,
    );
    final processQuality =
        (decision.calibration.confidenceStabilityIndex * 0.34 +
                decision.stability.smoothedConfidence * 0.26 +
                (100 - edgeMemory.edgeDecay) * 0.22 +
                edgeMemory.regimePersistence * 0.18)
            .clamp(0, 99)
            .toDouble();
    final metaScore = (processQuality -
            overreacting.length * 4 -
            lagging.length * 2 -
            math.max(0, edgeMemory.edgeDecay - edgeMemory.edgeRecovery) * 0.12)
        .clamp(0, 99)
        .toDouble();
    return MetaIntelligenceRead(
      metaStabilityScore: metaScore,
      overreactingContributors:
          overreacting.isEmpty ? const <String>['none'] : overreacting,
      laggingContributors: lagging.isEmpty ? const <String>['none'] : lagging,
      destabilizingRegimes:
          destabilizing.isEmpty ? const <String>['none'] : destabilizing,
      unreliableAssets:
          unreliableAssets.isEmpty ? const <String>['none'] : unreliableAssets,
      processQuality: processQuality,
      summary: metaScore >= 72
          ? 'Reasoning process is stable enough for normal adaptive weighting.'
          : 'Reasoning process needs slower evolution and tighter contributor smoothing.',
    );
  }

  StrategyEvolutionRead strategyEvolution({
    required AdaptiveDecisionCoreRead decision,
    required LongHorizonEdgeMemoryRead edgeMemory,
    required MetaIntelligenceRead meta,
  }) {
    final reduced = <String>[
      if (edgeMemory.edgeDecay >= 58) 'late breakout continuation',
      if (decision.consensus.chopProbability >= 58) 'trend entries inside chop',
      if (meta.overreactingContributors.length > 1) 'fast contributor upgrades',
    ];
    final increased = <String>[
      if (edgeMemory.edgeRecovery >= 58) 'confirmed continuation',
      if (decision.scenarios.liquiditySweepReversal >= 64)
        'liquidity sweep reversal',
      if (decision.consensus.breakoutContinuationProbability >= 70)
        'breakout continuation',
    ];
    final suppressed = <String>[
      if (decision.stability.driftSuppression >= 12) 'model drift clusters',
      if (edgeMemory.marketPersonalityShift >= 68) 'personality shift regimes',
      if (decision.scenarios.volatilityRejection >= 65)
        'volatility rejection windows',
    ];
    final scenarioWeights = <String, double>{
      'breakout': decision.scenarios.breakoutSucceeds,
      'fakeout': 100 - decision.scenarios.fakeBreakout,
      'continuation': decision.scenarios.trendContinuation,
      'reversal': decision.scenarios.liquiditySweepReversal,
    };
    final leverage = (decision.consensus.adaptiveSignalQuality * 0.006 +
            meta.metaStabilityScore * 0.004 -
            edgeMemory.edgeDecay * 0.003)
        .clamp(0.25, 0.95)
        .toDouble();
    return StrategyEvolutionRead(
      reducedSetups:
          reduced.isEmpty ? const <String>['none currently'] : reduced,
      increasedSetups: increased.isEmpty
          ? const <String>['high-stability confirmation']
          : increased,
      suppressedEnvironments:
          suppressed.isEmpty ? const <String>['none currently'] : suppressed,
      leveragePreference: leverage,
      scenarioWeighting: scenarioWeights,
      evolutionNote: meta.metaStabilityScore >= 72
          ? 'Strategy evolution can adjust gradually without destabilizing consensus.'
          : 'Strategy evolution should stay conservative until meta stability improves.',
    );
  }

  ReasoningMemoryRead reasoningMemory({
    required AdaptiveDecisionCoreRead decision,
    required List<SignalOutcomeReport> outcomes,
    required List<SignalModel> signals,
  }) {
    final winners = outcomes
        .where((item) => item.maxFavorableExcursion > item.maxAdverseExcursion)
        .map((item) => item.setupType)
        .toSet()
        .toList(growable: false);
    final failures = outcomes
        .where((item) => item.maxAdverseExcursion >= item.maxFavorableExcursion)
        .map((item) => item.setupType)
        .toSet()
        .toList(growable: false);
    final reasoningTokens = signals
        .expand((signal) => signal.reasons)
        .where((item) => item.trim().isNotEmpty)
        .take(5)
        .toList(growable: false);
    final reliability = (decision.reasoning.supportingFactors.length * 14 +
            decision.calibration.confidenceStabilityIndex * 0.38 +
            winners.length * 5 -
            failures.length * 4)
        .clamp(0, 99)
        .toDouble();
    return ReasoningMemoryRead(
      reasoningReliabilityIndex: reliability,
      winningReasoningPatterns:
          winners.isEmpty ? const <String>['awaiting winners'] : winners,
      failingReasoningPatterns:
          failures.isEmpty ? const <String>['no failure cluster'] : failures,
      narrativeQuality: (reasoningTokens.length * 12 +
              decision.reasoning.supportingFactors.length * 8)
          .clamp(0, 99)
          .toDouble(),
      memoryNote: reliability >= 68
          ? 'Reasoning memory is reinforcing current narrative patterns.'
          : 'Reasoning memory needs more confirmed outcomes before increasing trust.',
    );
  }

  SelfOptimizationRead selfOptimizationLayer({
    required AdaptiveDecisionCoreRead decision,
    required MetaIntelligenceRead meta,
    required StrategyEvolutionRead strategy,
  }) {
    final smoothing =
        (100 - meta.metaStabilityScore + decision.stability.hysteresisBand * 3)
            .clamp(8, 48)
            .toDouble();
    final normalization =
        (decision.calibration.confidenceStabilityIndex * 0.52 +
                decision.stability.volatilityNormalization * 0.24)
            .clamp(0, 99)
            .toDouble();
    final fusion = (meta.processQuality * 0.42 +
            decision.consensus.adaptiveSignalQuality * 0.30 +
            normalization * 0.18)
        .clamp(0, 99)
        .toDouble();
    final stabilization = (decision.stability.smoothedConfidence * 0.48 +
            meta.metaStabilityScore * 0.34)
        .clamp(0, 99)
        .toDouble();
    final probabilistic = strategy.scenarioWeighting.values.isEmpty
        ? 50.0
        : strategy.scenarioWeighting.values.reduce((a, b) => a + b) /
            strategy.scenarioWeighting.length;
    return SelfOptimizationRead(
      contributorSmoothing: smoothing,
      confidenceNormalization: normalization,
      fusionCalibration: fusion,
      consensusStabilization: stabilization,
      probabilisticAdjustment: probabilistic.clamp(0, 99).toDouble(),
      optimizationAction: meta.metaStabilityScore >= 72
          ? 'Allow gradual contributor evolution with normal confidence smoothing.'
          : 'Freeze aggressive contributor upgrades and normalize confidence harder.',
    );
  }

  RegimeEvolutionMapRead regimeEvolutionMap({
    required AdaptiveDecisionCoreRead decision,
    required LongHorizonEdgeMemoryRead edgeMemory,
    MarketRegimeMapRead? regime,
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final trend = chart?.opportunity.trendStrength ??
        market?.confidenceScore ??
        decision.consensus.breakoutContinuationProbability;
    final volatility = chart?.opportunity.volatilityScore ??
        ((market?.avgVolatilityPct ?? 4) * 12);
    final liquidity = chart?.liquidityHeatmap.pressureScore ??
        decision.scenarios.liquiditySweepReversal;
    final sentiment = market?.sentimentScore ?? 50;
    final path = <String>[
      regime?.trendRegime ?? 'selective trend',
      volatility >= 65 ? 'volatility expansion' : 'volatility controlled',
      liquidity < 42 ? 'liquidity degradation' : 'liquidity stable',
      sentiment >= 58 ? 'risk-on transition' : 'neutral/risk-off transition',
    ];
    return RegimeEvolutionMapRead(
      trendStrengthening: trend.clamp(0, 99).toDouble(),
      volatilityCompressionCycle: (100 - volatility).clamp(0, 99).toDouble(),
      liquidityDegradation: (100 - liquidity).clamp(0, 99).toDouble(),
      sentimentTransition: (sentiment - 50).abs().clamp(0, 99).toDouble(),
      macroInstabilityPhase: edgeMemory.marketPersonalityShift,
      regimePath: path,
      evolutionSummary:
          'Regime path is moving through ${path.take(3).join(' -> ')}.',
    );
  }

  FutureMlFoundationRead futureMlFoundation({
    required AdaptiveDecisionCoreRead decision,
    required List<SignalOutcomeReport> outcomes,
    required ReasoningMemoryRead reasoning,
    required ContributorEvolutionRead contributorEvolution,
  }) {
    final features = <String>[
      'contributor_weight',
      'contributor_quality',
      'consensus_probability',
      'scenario_probability',
      'confidence_stability',
      'reasoning_reliability',
      'edge_decay_recovery',
      'regime_evolution',
    ];
    return FutureMlFoundationRead(
      onlineLearningReady: contributorEvolution.scores.length >= 6,
      contributorRetrainingReady: outcomes.length >= 3,
      replayLearningReady: decision.research.offlineReplayReady,
      reinforcementLayerReady: outcomes.length >= 5,
      probabilisticOptimizationReady:
          reasoning.reasoningReliabilityIndex >= 50 && outcomes.length >= 2,
      trainingFeatures: features,
      foundationNote:
          'Features are normalized for future online learning, replay learning, and contributor benchmarking. No training is executed in-app.',
    );
  }

  double _expectancy(List<SignalOutcomeReport> outcomes) {
    if (outcomes.isEmpty) {
      return 0;
    }
    return outcomes.fold<double>(
          0,
          (sum, item) =>
              sum +
              item.maxFavorableExcursion -
              item.maxAdverseExcursion * 0.78,
        ) /
        outcomes.length;
  }

  double _dominantShare(Iterable<String> values) {
    final items = values.where((item) => item.trim().isNotEmpty).toList();
    if (items.isEmpty) {
      return 50;
    }
    final counts = <String, int>{};
    for (final item in items) {
      counts[item] = (counts[item] ?? 0) + 1;
    }
    final maxCount = counts.values.reduce(math.max);
    return (maxCount / items.length * 100).clamp(0, 99).toDouble();
  }

  List<String> _weakGroups(
    List<SignalOutcomeReport> outcomes,
    String Function(SignalOutcomeReport item) keyOf,
  ) {
    final grouped = <String, List<SignalOutcomeReport>>{};
    for (final outcome in outcomes) {
      grouped
          .putIfAbsent(keyOf(outcome), () => <SignalOutcomeReport>[])
          .add(outcome);
    }
    return grouped.entries
        .where((entry) => _expectancy(entry.value) < 0)
        .map((entry) => entry.key)
        .take(3)
        .toList(growable: false);
  }
}

import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import 'ai_opportunity_engine.dart';
import 'edge_validation_engine.dart';
import 'proprietary_ai_engine.dart';

enum AiContributorType {
  momentum,
  liquidity,
  volatility,
  structure,
  regime,
  execution,
  sentiment,
  portfolio,
}

class AiContributorRead {
  const AiContributorRead({
    required this.name,
    required this.type,
    required this.directionalBias,
    required this.confidence,
    required this.edgeQuality,
    required this.stability,
    required this.weight,
    required this.reasoning,
  });

  final String name;
  final AiContributorType type;
  final double directionalBias;
  final double confidence;
  final double edgeQuality;
  final double stability;
  final double weight;
  final String reasoning;
}

class AdaptiveWeightsRead {
  const AdaptiveWeightsRead({
    required this.regime,
    required this.weights,
    required this.primaryWeight,
    required this.explanation,
  });

  final String regime;
  final Map<AiContributorType, double> weights;
  final String primaryWeight;
  final String explanation;
}

class AiConsensusRead {
  const AiConsensusRead({
    required this.contributors,
    required this.bullishProbability,
    required this.bearishProbability,
    required this.chopProbability,
    required this.breakoutContinuationProbability,
    required this.exhaustionProbability,
    required this.reversalProbability,
    required this.consensusConfidence,
    required this.adaptiveSignalQuality,
    required this.dominantBias,
    required this.summary,
  });

  final List<AiContributorRead> contributors;
  final double bullishProbability;
  final double bearishProbability;
  final double chopProbability;
  final double breakoutContinuationProbability;
  final double exhaustionProbability;
  final double reversalProbability;
  final double consensusConfidence;
  final double adaptiveSignalQuality;
  final String dominantBias;
  final String summary;
}

class ConfidenceCalibrationCoreRead {
  const ConfidenceCalibrationCoreRead({
    required this.confidenceStabilityIndex,
    required this.overconfidentFailurePenalty,
    required this.underconfidentWinBoost,
    required this.regimeCalibration,
    required this.assetCalibration,
    required this.smoothingFactor,
    required this.note,
  });

  final double confidenceStabilityIndex;
  final double overconfidentFailurePenalty;
  final double underconfidentWinBoost;
  final double regimeCalibration;
  final double assetCalibration;
  final double smoothingFactor;
  final String note;
}

class ScenarioProbabilityMapRead {
  const ScenarioProbabilityMapRead({
    required this.breakoutSucceeds,
    required this.fakeBreakout,
    required this.trendContinuation,
    required this.volatilityRejection,
    required this.liquiditySweepReversal,
    required this.preferredScenario,
    required this.scenarioNotes,
  });

  final double breakoutSucceeds;
  final double fakeBreakout;
  final double trendContinuation;
  final double volatilityRejection;
  final double liquiditySweepReversal;
  final String preferredScenario;
  final List<String> scenarioNotes;
}

class ConsensusTimelinePoint {
  const ConsensusTimelinePoint({
    required this.label,
    required this.confidence,
    required this.bias,
    required this.note,
  });

  final String label;
  final double confidence;
  final String bias;
  final String note;
}

class AiConsensusTimelineRead {
  const AiConsensusTimelineRead({
    required this.points,
    required this.evolutionSummary,
  });

  final List<ConsensusTimelinePoint> points;
  final String evolutionSummary;
}

class MarketReasoningRead {
  const MarketReasoningRead({
    required this.headline,
    required this.reasoning,
    required this.supportingFactors,
    required this.riskFactors,
  });

  final String headline;
  final String reasoning;
  final List<String> supportingFactors;
  final List<String> riskFactors;
}

class StabilityDriftControlRead {
  const StabilityDriftControlRead({
    required this.smoothedConfidence,
    required this.hysteresisBand,
    required this.driftSuppression,
    required this.volatilityNormalization,
    required this.regimeStabilization,
    required this.action,
  });

  final double smoothedConfidence;
  final double hysteresisBand;
  final double driftSuppression;
  final double volatilityNormalization;
  final double regimeStabilization;
  final String action;
}

class AdaptiveDecisionResearchRead {
  const AdaptiveDecisionResearchRead({
    required this.mlIntegrationReady,
    required this.offlineReplayReady,
    required this.probabilisticReplayReady,
    required this.modelComparisonReady,
    required this.contributorBenchmarks,
    required this.notes,
  });

  final bool mlIntegrationReady;
  final bool offlineReplayReady;
  final bool probabilisticReplayReady;
  final bool modelComparisonReady;
  final Map<String, double> contributorBenchmarks;
  final List<String> notes;
}

class AdaptiveDecisionCoreRead {
  const AdaptiveDecisionCoreRead({
    required this.weights,
    required this.consensus,
    required this.calibration,
    required this.scenarios,
    required this.timeline,
    required this.reasoning,
    required this.stability,
    required this.research,
  });

  final AdaptiveWeightsRead weights;
  final AiConsensusRead consensus;
  final ConfidenceCalibrationCoreRead calibration;
  final ScenarioProbabilityMapRead scenarios;
  final AiConsensusTimelineRead timeline;
  final MarketReasoningRead reasoning;
  final StabilityDriftControlRead stability;
  final AdaptiveDecisionResearchRead research;
}

class AdaptiveDecisionCore {
  const AdaptiveDecisionCore();

  AdaptiveDecisionCoreRead evaluate({
    required SignalModel signal,
    required List<SignalModel> signals,
    required List<SignalOutcomeReport> outcomes,
    MarketSummaryModel? market,
    MarketChartModel? chart,
    MarketDnaProfile? dna,
    PredictivePressureRead? pressure,
    EdgeConfidenceRead? edgeConfidence,
    MarketRegimeMapRead? regime,
    ModelDriftRead? drift,
  }) {
    const proprietary = ProprietaryAiEngine();
    final resolvedDna = dna ??
        proprietary.marketDna(signal: signal, market: market, chart: chart);
    final resolvedPressure = pressure ??
        proprietary.predictivePressure(
          signal: signal,
          market: market,
          chart: chart,
        );
    final signature = proprietary.edgeSignature(signal);
    final resolvedDrift = drift ??
        const EdgeValidationEngine().modelDrift(outcomes, chart: chart);
    final resolvedEdge = edgeConfidence ??
        proprietary.edgeConfidence(
          dna: resolvedDna,
          signature: signature,
          outcomes: outcomes,
          drift: resolvedDrift,
        );
    final resolvedRegime =
        regime ?? proprietary.regimeMap(market: market, chart: chart);
    final weights = adaptiveWeights(
      regime: resolvedRegime,
      pressure: resolvedPressure,
      chart: chart,
    );
    final contributors = contributorsFor(
      signal: signal,
      signals: signals,
      market: market,
      chart: chart,
      dna: resolvedDna,
      pressure: resolvedPressure,
      edgeConfidence: resolvedEdge,
      regime: resolvedRegime,
      drift: resolvedDrift,
      weights: weights,
    );
    final consensus = consensusFrom(
      contributors: contributors,
      pressure: resolvedPressure,
      dna: resolvedDna,
      edgeConfidence: resolvedEdge,
      drift: resolvedDrift,
    );
    final calibration = confidenceCalibration(
      signal: signal,
      outcomes: outcomes,
      drift: resolvedDrift,
      consensus: consensus,
    );
    final scenarios = scenarioMap(
      consensus: consensus,
      pressure: resolvedPressure,
      dna: resolvedDna,
      calibration: calibration,
    );
    final timeline = consensusTimeline(
      consensus: consensus,
      contributors: contributors,
      pressure: resolvedPressure,
      drift: resolvedDrift,
    );
    final reasoning = marketReasoning(
      signal: signal,
      consensus: consensus,
      scenarios: scenarios,
      contributors: contributors,
      regime: resolvedRegime,
    );
    final stability = stabilityControl(
      consensus: consensus,
      calibration: calibration,
      pressure: resolvedPressure,
      drift: resolvedDrift,
      regime: resolvedRegime,
    );
    final research = researchFoundation(
      contributors: contributors,
      outcomes: outcomes,
      chart: chart,
    );
    return AdaptiveDecisionCoreRead(
      weights: weights,
      consensus: consensus,
      calibration: calibration,
      scenarios: scenarios,
      timeline: timeline,
      reasoning: reasoning,
      stability: stability,
      research: research,
    );
  }

  AdaptiveWeightsRead adaptiveWeights({
    required MarketRegimeMapRead regime,
    required PredictivePressureRead pressure,
    MarketChartModel? chart,
  }) {
    final volatility = pressure.volatilityExpansionProbability;
    final text =
        '${regime.trendRegime} ${regime.volatilityRegime} ${regime.riskState}'
            .toLowerCase();
    final trending = text.contains('trend');
    final ranging = text.contains('range') || text.contains('chop');
    final highVol = text.contains('high volatility') || volatility >= 72;
    final weights = <AiContributorType, double>{
      AiContributorType.momentum: trending ? 0.20 : 0.12,
      AiContributorType.liquidity: ranging ? 0.20 : 0.14,
      AiContributorType.volatility: highVol ? 0.17 : 0.10,
      AiContributorType.structure: trending ? 0.16 : 0.14,
      AiContributorType.regime: highVol ? 0.12 : 0.15,
      AiContributorType.execution: highVol ? 0.16 : 0.12,
      AiContributorType.sentiment: 0.07,
      AiContributorType.portfolio: 0.06,
    };
    final total = weights.values.fold<double>(0, (sum, item) => sum + item);
    final normalized =
        weights.map((key, value) => MapEntry(key, value / total));
    final primary = normalized.entries.reduce(
      (a, b) => a.value >= b.value ? a : b,
    );
    return AdaptiveWeightsRead(
      regime: highVol
          ? 'High volatility decision regime'
          : trending
              ? 'Trending decision regime'
              : ranging
                  ? 'Range/reversal decision regime'
                  : 'Balanced decision regime',
      weights: normalized,
      primaryWeight: _typeLabel(primary.key),
      explanation: highVol
          ? 'Execution and volatility contributors are weighted higher to suppress unstable entries.'
          : trending
              ? 'Momentum and structure contributors are weighted higher because trend persistence matters most.'
              : ranging
                  ? 'Liquidity and reversal contributors are weighted higher because range conditions punish late continuation.'
                  : 'Weights are balanced because no single regime dominates.',
    );
  }

  List<AiContributorRead> contributorsFor({
    required SignalModel signal,
    required List<SignalModel> signals,
    required MarketDnaProfile dna,
    required PredictivePressureRead pressure,
    required EdgeConfidenceRead edgeConfidence,
    required MarketRegimeMapRead regime,
    required ModelDriftRead drift,
    required AdaptiveWeightsRead weights,
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final opportunity = SignalOpportunity.fromSignal(signal);
    final side = signal.action.toUpperCase() == 'SELL' ? -1.0 : 1.0;
    final marketSentiment = market?.sentimentScore ?? 50;
    final portfolioLoad = signals
        .where(
            (item) => item.action.toUpperCase() == signal.action.toUpperCase())
        .length;
    return <AiContributorRead>[
      _contributor(
        name: 'Momentum intelligence',
        type: AiContributorType.momentum,
        bias: side * opportunity.breakoutProbability,
        confidence: opportunity.breakoutProbability,
        edge: edgeConfidence.edgeConfidenceScore,
        stability: drift.aiStabilityScore,
        weight: weights.weights[AiContributorType.momentum]!,
        reasoning:
            'Breakout and continuation pressure are driving momentum read.',
      ),
      _contributor(
        name: 'Liquidity intelligence',
        type: AiContributorType.liquidity,
        bias: side *
            (100 - dna.fakeoutTendency + pressure.liquidationPressure) /
            2,
        confidence: pressure.liquidationPressure,
        edge: dna.whaleSensitivity,
        stability: 100 - dna.fakeoutTendency,
        weight: weights.weights[AiContributorType.liquidity]!,
        reasoning:
            'Liquidity pressure is compared with fakeout tendency and whale sensitivity.',
      ),
      _contributor(
        name: 'Volatility intelligence',
        type: AiContributorType.volatility,
        bias: side * (100 - pressure.exhaustionProbability),
        confidence: pressure.volatilityExpansionProbability,
        edge: 100 - pressure.exhaustionProbability,
        stability: 100 - drift.regimeInstability,
        weight: weights.weights[AiContributorType.volatility]!,
        reasoning:
            'Volatility expansion is normalized against exhaustion and regime instability.',
      ),
      _contributor(
        name: 'Market structure intelligence',
        type: AiContributorType.structure,
        bias: side * dna.trendPersistence,
        confidence: dna.trendPersistence,
        edge: dna.compatibilityScore,
        stability: 100 - dna.fakeoutTendency,
        weight: weights.weights[AiContributorType.structure]!,
        reasoning:
            'Market DNA trend persistence and breakout temperament support structure read.',
      ),
      _contributor(
        name: 'Regime intelligence',
        type: AiContributorType.regime,
        bias: regime.riskState == 'risk-off' ? -28 : side * 58,
        confidence: edgeConfidence.regimeCompatibility,
        edge: edgeConfidence.regimeCompatibility,
        stability: drift.aiStabilityScore,
        weight: weights.weights[AiContributorType.regime]!,
        reasoning: regime.explanation,
      ),
      _contributor(
        name: 'Execution intelligence',
        type: AiContributorType.execution,
        bias: side * edgeConfidence.executionQuality,
        confidence: edgeConfidence.executionQuality,
        edge: edgeConfidence.executionQuality,
        stability: 100 - pressure.exhaustionProbability,
        weight: weights.weights[AiContributorType.execution]!,
        reasoning:
            'Execution quality is penalized when exhaustion or volatility rejection rises.',
      ),
      _contributor(
        name: 'Sentiment intelligence',
        type: AiContributorType.sentiment,
        bias: side * (marketSentiment - 50) * 1.6,
        confidence: marketSentiment,
        edge: market?.confidenceScore ?? marketSentiment,
        stability: 100 - (market?.avgVolatilityPct ?? 4) * 10,
        weight: weights.weights[AiContributorType.sentiment]!,
        reasoning: 'Market breadth and sentiment adjust the directional read.',
      ),
      _contributor(
        name: 'Portfolio intelligence',
        type: AiContributorType.portfolio,
        bias: side * (portfolioLoad >= 4 ? 35 : 58),
        confidence: portfolioLoad >= 4 ? 48 : 64,
        edge: portfolioLoad >= 4 ? 46 : 62,
        stability: portfolioLoad >= 4 ? 52 : 70,
        weight: weights.weights[AiContributorType.portfolio]!,
        reasoning: portfolioLoad >= 4
            ? 'Correlated signal load is elevated; portfolio contributor is suppressing risk.'
            : 'Signal load is balanced enough for normal portfolio risk.',
      ),
    ];
  }

  AiConsensusRead consensusFrom({
    required List<AiContributorRead> contributors,
    required PredictivePressureRead pressure,
    required MarketDnaProfile dna,
    required EdgeConfidenceRead edgeConfidence,
    required ModelDriftRead drift,
  }) {
    final weightedBias = contributors.fold<double>(
      0,
      (sum, item) => sum + item.directionalBias * item.weight,
    );
    final weightedConfidence = contributors.fold<double>(
      0,
      (sum, item) => sum + item.confidence * item.weight,
    );
    final weightedEdge = contributors.fold<double>(
      0,
      (sum, item) => sum + item.edgeQuality * item.weight,
    );
    final weightedStability = contributors.fold<double>(
      0,
      (sum, item) => sum + item.stability * item.weight,
    );
    final bullish = (50 + weightedBias * 0.42 + weightedEdge * 0.08)
        .clamp(1, 98)
        .toDouble();
    final bearish =
        (50 - weightedBias * 0.42 + pressure.exhaustionProbability * 0.08)
            .clamp(1, 98)
            .toDouble();
    final chop = (100 -
            (bullish - bearish).abs() -
            weightedStability * 0.24 +
            drift.regimeInstability * 0.22)
        .clamp(2, 92)
        .toDouble();
    final continuation = (pressure.trendContinuationProbability * 0.42 +
            edgeConfidence.edgeConfidenceScore * 0.32 +
            dna.trendPersistence * 0.20)
        .clamp(0, 99)
        .toDouble();
    final exhaustion = (pressure.exhaustionProbability * 0.58 +
            dna.fakeoutTendency * 0.22 +
            drift.falseBreakoutTrend * 0.20)
        .clamp(0, 99)
        .toDouble();
    final reversal = (exhaustion * 0.45 + pressure.liquidationPressure * 0.28)
        .clamp(0, 99)
        .toDouble();
    final confidence = (weightedConfidence * 0.36 +
            weightedEdge * 0.30 +
            weightedStability * 0.24 -
            chop * 0.10)
        .clamp(0, 99)
        .toDouble();
    final quality = (confidence * 0.50 +
            continuation * 0.22 +
            edgeConfidence.edgeConfidenceScore * 0.20 -
            exhaustion * 0.12)
        .clamp(0, 99)
        .toDouble();
    final dominant = bullish >= bearish + 8
        ? 'Bullish'
        : bearish >= bullish + 8
            ? 'Bearish'
            : 'Neutral / Chop';
    return AiConsensusRead(
      contributors: contributors,
      bullishProbability: bullish,
      bearishProbability: bearish,
      chopProbability: chop,
      breakoutContinuationProbability: continuation,
      exhaustionProbability: exhaustion,
      reversalProbability: reversal,
      consensusConfidence: confidence,
      adaptiveSignalQuality: quality,
      dominantBias: dominant,
      summary:
          '$dominant consensus with ${confidence.toStringAsFixed(0)}% calibrated confidence and ${quality.toStringAsFixed(0)} adaptive quality.',
    );
  }

  ConfidenceCalibrationCoreRead confidenceCalibration({
    required SignalModel signal,
    required List<SignalOutcomeReport> outcomes,
    required ModelDriftRead drift,
    required AiConsensusRead consensus,
  }) {
    final overconfident = outcomes
        .where(
          (item) =>
              item.confidenceAtEntry >= 75 &&
              item.maxAdverseExcursion > item.maxFavorableExcursion,
        )
        .length;
    final underconfident = outcomes
        .where(
          (item) =>
              item.confidenceAtEntry < 62 &&
              item.maxFavorableExcursion > item.maxAdverseExcursion,
        )
        .length;
    final sample = math.max(outcomes.length, 1);
    final overPenalty = overconfident / sample * 100;
    final underBoost = underconfident / sample * 100;
    final assetOutcomes =
        outcomes.where((item) => item.symbol == signal.symbol).toList();
    final assetCalibration = assetOutcomes.isEmpty
        ? consensus.consensusConfidence
        : assetOutcomes.fold<double>(
                0, (sum, item) => sum + item.exitEfficiency) /
            assetOutcomes.length;
    final regimeOutcomes =
        outcomes.where((item) => item.marketRegime == signal.regime).toList();
    final regimeCalibration = regimeOutcomes.isEmpty
        ? drift.aiStabilityScore
        : regimeOutcomes.fold<double>(
                0, (sum, item) => sum + item.exitEfficiency) /
            regimeOutcomes.length;
    final stability = (consensus.consensusConfidence * 0.34 +
            drift.aiStabilityScore * 0.28 +
            assetCalibration * 0.18 +
            regimeCalibration * 0.14 -
            overPenalty * 0.20 +
            underBoost * 0.08)
        .clamp(0, 99)
        .toDouble();
    return ConfidenceCalibrationCoreRead(
      confidenceStabilityIndex: stability,
      overconfidentFailurePenalty: overPenalty.clamp(0, 99).toDouble(),
      underconfidentWinBoost: underBoost.clamp(0, 99).toDouble(),
      regimeCalibration: regimeCalibration.clamp(0, 99).toDouble(),
      assetCalibration: assetCalibration.clamp(0, 99).toDouble(),
      smoothingFactor: stability >= 72
          ? 0.18
          : stability >= 54
              ? 0.28
              : 0.42,
      note: stability >= 72
          ? 'Confidence calibration is stable; normal smoothing is sufficient.'
          : 'Confidence calibration needs tighter smoothing and slower signal transitions.',
    );
  }

  ScenarioProbabilityMapRead scenarioMap({
    required AiConsensusRead consensus,
    required PredictivePressureRead pressure,
    required MarketDnaProfile dna,
    required ConfidenceCalibrationCoreRead calibration,
  }) {
    final breakout = (consensus.breakoutContinuationProbability * 0.50 +
            pressure.breakoutPressure * 0.30 +
            calibration.confidenceStabilityIndex * 0.20)
        .clamp(0, 99)
        .toDouble();
    final fakeout =
        (dna.fakeoutTendency * 0.44 + consensus.exhaustionProbability * 0.34)
            .clamp(0, 99)
            .toDouble();
    final continuation = (consensus.breakoutContinuationProbability * 0.54 +
            consensus.consensusConfidence * 0.26)
        .clamp(0, 99)
        .toDouble();
    final volReject = (pressure.volatilityExpansionProbability * 0.36 +
            consensus.exhaustionProbability * 0.30 +
            calibration.overconfidentFailurePenalty * 0.18)
        .clamp(0, 99)
        .toDouble();
    final sweepReversal = (pressure.liquidationPressure * 0.42 +
            dna.whaleSensitivity * 0.24 +
            fakeout * 0.20)
        .clamp(0, 99)
        .toDouble();
    final scenarios = <String, double>{
      'Breakout succeeds': breakout,
      'Fake breakout': fakeout,
      'Trend continuation': continuation,
      'Volatility rejection': volReject,
      'Liquidity sweep reversal': sweepReversal,
    };
    final preferred = scenarios.entries.reduce(
      (a, b) => a.value >= b.value ? a : b,
    );
    return ScenarioProbabilityMapRead(
      breakoutSucceeds: breakout,
      fakeBreakout: fakeout,
      trendContinuation: continuation,
      volatilityRejection: volReject,
      liquiditySweepReversal: sweepReversal,
      preferredScenario: preferred.key,
      scenarioNotes: scenarios.entries
          .map((entry) => '${entry.key}: ${entry.value.toStringAsFixed(0)}%')
          .toList(growable: false),
    );
  }

  AiConsensusTimelineRead consensusTimeline({
    required AiConsensusRead consensus,
    required List<AiContributorRead> contributors,
    required PredictivePressureRead pressure,
    required ModelDriftRead drift,
  }) {
    final momentum = contributors
        .firstWhere((item) => item.type == AiContributorType.momentum);
    final liquidity = contributors
        .firstWhere((item) => item.type == AiContributorType.liquidity);
    final regime = contributors
        .firstWhere((item) => item.type == AiContributorType.regime);
    final points = <ConsensusTimelinePoint>[
      ConsensusTimelinePoint(
        label: 'T-3',
        confidence: (consensus.consensusConfidence - 8).clamp(0, 99).toDouble(),
        bias: consensus.dominantBias,
        note: 'Baseline read formed from market structure and prior outcomes.',
      ),
      ConsensusTimelinePoint(
        label: 'T-2',
        confidence: (momentum.confidence * 0.52 + liquidity.confidence * 0.28)
            .clamp(0, 99)
            .toDouble(),
        bias: momentum.directionalBias >= 0
            ? 'Momentum improving'
            : 'Momentum fading',
        note: momentum.reasoning,
      ),
      ConsensusTimelinePoint(
        label: 'T-1',
        confidence: (pressure.netPressure * 0.56 + regime.confidence * 0.24)
            .clamp(0, 99)
            .toDouble(),
        bias: pressure.direction,
        note: 'Pressure and regime contributors were reweighted.',
      ),
      ConsensusTimelinePoint(
        label: 'Now',
        confidence: consensus.consensusConfidence,
        bias: consensus.dominantBias,
        note: drift.driftDetected
            ? 'Drift suppression is active; confidence changes are slowed.'
            : 'Consensus is stable enough for normal advisory output.',
      ),
    ];
    return AiConsensusTimelineRead(
      points: points,
      evolutionSummary:
          'AI opinion evolved toward ${consensus.dominantBias.toLowerCase()} with ${consensus.consensusConfidence.toStringAsFixed(0)}% confidence.',
    );
  }

  MarketReasoningRead marketReasoning({
    required SignalModel signal,
    required AiConsensusRead consensus,
    required ScenarioProbabilityMapRead scenarios,
    required List<AiContributorRead> contributors,
    required MarketRegimeMapRead regime,
  }) {
    final strongest = contributors.reduce(
      (a, b) => a.edgeQuality >= b.edgeQuality ? a : b,
    );
    final weakest = contributors.reduce(
      (a, b) => a.stability <= b.stability ? a : b,
    );
    final headline = consensus.adaptiveSignalQuality >= 74
        ? 'Adaptive decision core supports a controlled ${signal.action.toUpperCase()} thesis.'
        : consensus.chopProbability >= 58
            ? 'Decision core sees opportunity, but chop risk is limiting conviction.'
            : 'Decision core is building confirmation before higher risk.';
    return MarketReasoningRead(
      headline: headline,
      reasoning:
          '${strongest.name} is the strongest contributor, while ${weakest.name} limits stability. ${scenarios.preferredScenario} is currently the dominant scenario under ${regime.trendRegime}.',
      supportingFactors: contributors
          .where((item) => item.edgeQuality >= 60)
          .map((item) => '${item.name}: ${item.reasoning}')
          .take(3)
          .toList(growable: false),
      riskFactors: contributors
          .where((item) => item.stability < 58 || item.edgeQuality < 54)
          .map((item) => '${item.name}: ${item.reasoning}')
          .take(3)
          .toList(growable: false),
    );
  }

  StabilityDriftControlRead stabilityControl({
    required AiConsensusRead consensus,
    required ConfidenceCalibrationCoreRead calibration,
    required PredictivePressureRead pressure,
    required ModelDriftRead drift,
    required MarketRegimeMapRead regime,
  }) {
    final volatilityNorm =
        (100 - pressure.volatilityExpansionProbability * 0.55)
            .clamp(0, 99)
            .toDouble();
    final regimeStability = regime.volatilityRegime == 'high volatility'
        ? 48.0
        : regime.trendRegime == 'range/chop'
            ? 56.0
            : 72.0;
    final driftSuppression =
        drift.driftDetected ? 24.0 : drift.falseBreakoutTrend * 0.12;
    final smoothed = (consensus.consensusConfidence *
                (1 - calibration.smoothingFactor) +
            calibration.confidenceStabilityIndex * calibration.smoothingFactor -
            driftSuppression * 0.22)
        .clamp(0, 99)
        .toDouble();
    return StabilityDriftControlRead(
      smoothedConfidence: smoothed,
      hysteresisBand: calibration.confidenceStabilityIndex >= 72 ? 4 : 9,
      driftSuppression: driftSuppression.clamp(0, 40).toDouble(),
      volatilityNormalization: volatilityNorm,
      regimeStabilization: regimeStability,
      action: drift.driftDetected || smoothed < 55
          ? 'Suppress sudden signal upgrades; keep advisory or reduced-size mode.'
          : 'Signal transitions are stable enough for normal advisory ranking.',
    );
  }

  AdaptiveDecisionResearchRead researchFoundation({
    required List<AiContributorRead> contributors,
    required List<SignalOutcomeReport> outcomes,
    MarketChartModel? chart,
  }) {
    final benchmarks = <String, double>{
      for (final contributor in contributors)
        contributor.name: (contributor.edgeQuality * 0.56 +
                contributor.stability * 0.28 +
                contributor.confidence * 0.16)
            .clamp(0, 99)
            .toDouble(),
    };
    return AdaptiveDecisionResearchRead(
      mlIntegrationReady: contributors.length >= 8,
      offlineReplayReady:
          outcomes.isNotEmpty || (chart?.candles.isNotEmpty ?? false),
      probabilisticReplayReady: outcomes.length >= 2,
      modelComparisonReady: benchmarks.length >= 6,
      contributorBenchmarks: benchmarks,
      notes: <String>[
        'Contributor outputs are normalized for future model benchmarking.',
        if (outcomes.isNotEmpty)
          'Outcome reports can be used for offline confidence calibration replay.',
        'No ML training is performed in-app; this layer prepares deterministic research inputs.',
      ],
    );
  }

  AiContributorRead _contributor({
    required String name,
    required AiContributorType type,
    required double bias,
    required double confidence,
    required double edge,
    required double stability,
    required double weight,
    required String reasoning,
  }) {
    return AiContributorRead(
      name: name,
      type: type,
      directionalBias: bias.clamp(-99, 99).toDouble(),
      confidence: confidence.clamp(0, 99).toDouble(),
      edgeQuality: edge.clamp(0, 99).toDouble(),
      stability: stability.clamp(0, 99).toDouble(),
      weight: weight,
      reasoning: reasoning,
    );
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
}

import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import 'ai_opportunity_engine.dart';
import 'edge_validation_engine.dart';

class MarketDnaProfile {
  const MarketDnaProfile({
    required this.symbol,
    required this.assetPersonality,
    required this.volatilityRhythm,
    required this.liquidityBehavior,
    required this.breakoutTemperament,
    required this.trendPersistence,
    required this.fakeoutTendency,
    required this.whaleSensitivity,
    required this.compatibilityScore,
    required this.summary,
  });

  final String symbol;
  final String assetPersonality;
  final String volatilityRhythm;
  final String liquidityBehavior;
  final String breakoutTemperament;
  final double trendPersistence;
  final double fakeoutTendency;
  final double whaleSensitivity;
  final double compatibilityScore;
  final String summary;
}

class AiEdgeSignatureRead {
  const AiEdgeSignatureRead({
    required this.family,
    required this.label,
    required this.score,
    required this.components,
    required this.evidence,
  });

  final String family;
  final String label;
  final double score;
  final List<String> components;
  final List<String> evidence;
}

class PredictivePressureRead {
  const PredictivePressureRead({
    required this.breakoutPressure,
    required this.liquidationPressure,
    required this.volatilityExpansionProbability,
    required this.directionalBiasPressure,
    required this.trendContinuationProbability,
    required this.exhaustionProbability,
    required this.netPressure,
    required this.direction,
    required this.summary,
  });

  final double breakoutPressure;
  final double liquidationPressure;
  final double volatilityExpansionProbability;
  final double directionalBiasPressure;
  final double trendContinuationProbability;
  final double exhaustionProbability;
  final double netPressure;
  final String direction;
  final String summary;
}

class MarketBehaviorMemoryRead {
  const MarketBehaviorMemoryRead({
    required this.recurringBehaviors,
    required this.clusterScore,
    required this.btcAltInfluence,
    required this.memeRotation,
    required this.liquiditySweepTiming,
    required this.volatilityClustering,
    required this.exhaustionSequence,
  });

  final List<String> recurringBehaviors;
  final double clusterScore;
  final String btcAltInfluence;
  final String memeRotation;
  final String liquiditySweepTiming;
  final String volatilityClustering;
  final String exhaustionSequence;
}

class AiMarketNarrativeRead {
  const AiMarketNarrativeRead({
    required this.headline,
    required this.narrative,
    required this.supportingReads,
  });

  final String headline;
  final String narrative;
  final List<String> supportingReads;
}

class EdgeConfidenceRead {
  const EdgeConfidenceRead({
    required this.edgeConfidenceScore,
    required this.historicalSetupQuality,
    required this.regimeCompatibility,
    required this.executionQuality,
    required this.marketDnaCompatibility,
    required this.assetEdgeHistory,
    required this.verdict,
  });

  final double edgeConfidenceScore;
  final double historicalSetupQuality;
  final double regimeCompatibility;
  final double executionQuality;
  final double marketDnaCompatibility;
  final double assetEdgeHistory;
  final String verdict;
}

class MarketRegimeMapRead {
  const MarketRegimeMapRead({
    required this.trendRegime,
    required this.volatilityRegime,
    required this.riskState,
    required this.dominanceRotation,
    required this.sectorLeadership,
    required this.liquidityConditions,
    required this.explanation,
  });

  final String trendRegime;
  final String volatilityRegime;
  final String riskState;
  final String dominanceRotation;
  final String sectorLeadership;
  final String liquidityConditions;
  final String explanation;
}

class ProprietaryWatchtowerAlert {
  const ProprietaryWatchtowerAlert({
    required this.title,
    required this.detail,
    required this.severity,
  });

  final String title;
  final String detail;
  final ProprietarySeverity severity;
}

enum ProprietarySeverity { normal, watch, critical }

class ProprietaryWatchtowerRead {
  const ProprietaryWatchtowerRead({
    required this.status,
    required this.alerts,
    required this.structuralShiftScore,
  });

  final String status;
  final List<ProprietaryWatchtowerAlert> alerts;
  final double structuralShiftScore;
}

class AiResearchRead {
  const AiResearchRead({
    required this.patternStudyCount,
    required this.setupFamilies,
    required this.replayAnnotationReady,
    required this.behavioralClusteringReady,
    required this.researchNotes,
  });

  final int patternStudyCount;
  final List<String> setupFamilies;
  final bool replayAnnotationReady;
  final bool behavioralClusteringReady;
  final List<String> researchNotes;
}

class ProprietaryAiEngine {
  const ProprietaryAiEngine();

  MarketDnaProfile marketDna({
    required SignalModel signal,
    MarketChartModel? chart,
    MarketSummaryModel? market,
  }) {
    final opportunity = SignalOpportunity.fromSignal(signal);
    final volatility = chart?.opportunity.volatilityScore ??
        market?.avgVolatilityPct.clamp(0, 100).toDouble() ??
        (signal.lowConfidence ? 64.0 : 42.0);
    final trend = chart?.opportunity.trendStrength ??
        math.max(signal.alphaScore, signal.qualityScore);
    final whale = chart?.opportunity.whalePressure ?? opportunity.whalePressure;
    final fakeout =
        (100 - signal.qualityScore + volatility * 0.22).clamp(0, 99).toDouble();
    final compatibility = (trend * 0.36 +
            whale * 0.24 +
            signal.qualityScore * 0.26 -
            fakeout * 0.14)
        .clamp(0, 99)
        .toDouble();
    return MarketDnaProfile(
      symbol: signal.symbol,
      assetPersonality: _assetPersonality(signal.symbol, volatility, trend),
      volatilityRhythm: volatility >= 70
          ? 'fast expansion rhythm'
          : volatility >= 45
              ? 'balanced rotation rhythm'
              : 'compressed rhythm',
      liquidityBehavior: whale >= 70
          ? 'whale-sensitive liquidity'
          : whale >= 45
              ? 'responsive liquidity'
              : 'thin confirmation liquidity',
      breakoutTemperament: opportunity.breakoutProbability >= 75
          ? 'impulsive breakout temperament'
          : opportunity.breakoutProbability >= 55
              ? 'selective breakout temperament'
              : 'range-bound breakout temperament',
      trendPersistence: trend.clamp(0, 99).toDouble(),
      fakeoutTendency: fakeout,
      whaleSensitivity: whale.clamp(0, 99).toDouble(),
      compatibilityScore: compatibility,
      summary:
          '${signal.symbol}: ${_assetPersonality(signal.symbol, volatility, trend)}, ${volatility >= 60 ? 'elevated volatility' : 'controlled volatility'}, ${whale >= 60 ? 'high whale sensitivity' : 'moderate whale sensitivity'}.',
    );
  }

  AiEdgeSignatureRead edgeSignature(SignalModel signal) {
    final opportunity = SignalOpportunity.fromSignal(signal);
    final reasons = signal.reasons.map((item) => item.toLowerCase()).join(' ');
    final family = opportunity.liquiditySweepProbability >= 72 &&
            opportunity.breakoutProbability >= 68
        ? 'Liquidity Compression Breakout'
        : opportunity.whalePressure >= 74 && signal.lowConfidence
            ? 'Whale Trap Reversal'
            : opportunity.breakoutProbability >= 78
                ? 'Momentum Ignition'
                : opportunity.expectedMovePct >= 5.2
                    ? 'Volatility Expansion Pulse'
                    : reasons.contains('reclaim')
                        ? 'Smart Money Reclaim'
                        : signal.rejectionReason != null
                            ? 'Exhaustion Failure Setup'
                            : 'Dominance Rotation Shift';
    final score = (opportunity.score * 0.62 +
            opportunity.breakoutProbability * 0.18 +
            opportunity.whalePressure * 0.12 +
            signal.qualityScore * 0.08)
        .clamp(0, 99)
        .toDouble();
    return AiEdgeSignatureRead(
      family: family,
      label: '$family - ${signal.action.toUpperCase()}',
      score: score,
      components: <String>[
        'confidence ${opportunity.confidenceLabel}',
        'breakout ${opportunity.breakoutProbability.toStringAsFixed(0)}%',
        'liquidity ${opportunity.liquiditySweepProbability.toStringAsFixed(0)}%',
        'whale ${opportunity.whalePressure.toStringAsFixed(0)}%',
      ],
      evidence: signal.reasons.take(4).toList(growable: false),
    );
  }

  PredictivePressureRead predictivePressure({
    SignalModel? signal,
    MarketChartModel? chart,
    MarketSummaryModel? market,
  }) {
    final opportunity =
        signal == null ? null : SignalOpportunity.fromSignal(signal);
    final breakout = chart?.opportunity.momentumScore ??
        opportunity?.breakoutProbability ??
        market?.confidenceScore ??
        50;
    final liquidation = chart?.liquidityHeatmap.pressureScore ??
        chart?.orderbookDepth.pressureScore ??
        44;
    final volatility = chart?.opportunity.volatilityScore ??
        ((market?.avgVolatilityPct ?? 4) * 12).clamp(0, 99).toDouble();
    final directional = ((signal?.action.toUpperCase() == 'SELL' ? -1 : 1) *
            (breakout * 0.52 + (market?.sentimentScore ?? 50) * 0.22))
        .clamp(-99, 99)
        .toDouble();
    final continuation =
        (breakout * 0.48 + (chart?.opportunity.trendStrength ?? 50) * 0.34)
            .clamp(0, 99)
            .toDouble();
    final exhaustion =
        (volatility * 0.38 + liquidation * 0.32 - continuation * 0.18)
            .clamp(0, 99)
            .toDouble();
    final net = (breakout * 0.35 +
            liquidation * 0.2 +
            continuation * 0.28 -
            exhaustion * 0.18)
        .clamp(0, 99)
        .toDouble();
    final direction = directional >= 8
        ? 'bullish pressure'
        : directional <= -8
            ? 'bearish pressure'
            : 'balanced pressure';
    return PredictivePressureRead(
      breakoutPressure: breakout.toDouble().clamp(0, 99),
      liquidationPressure: liquidation.toDouble().clamp(0, 99),
      volatilityExpansionProbability: volatility.toDouble().clamp(0, 99),
      directionalBiasPressure: directional,
      trendContinuationProbability: continuation,
      exhaustionProbability: exhaustion,
      netPressure: net,
      direction: direction,
      summary:
          '${direction[0].toUpperCase()}${direction.substring(1)} with ${net.toStringAsFixed(0)} net pressure and ${volatility.toStringAsFixed(0)} volatility expansion probability.',
    );
  }

  MarketBehaviorMemoryRead behaviorMemory({
    required List<SignalModel> signals,
    MarketSummaryModel? market,
  }) {
    final btcWeak = (market?.ticker.any(
              (item) =>
                  item.symbol.toUpperCase().contains('BTC') &&
                  item.changePct < 0,
            ) ??
            false) ||
        signals.any((signal) =>
            signal.symbol.contains('BTC') && signal.action == 'SELL');
    final memeCount = signals
        .where((signal) =>
            RegExp('PEPE|SHIB|BONK|WIF|DOGE').hasMatch(signal.symbol))
        .length;
    final sweepCount = signals
        .where((signal) =>
            signal.reasons.join(' ').toLowerCase().contains('liquidity'))
        .length;
    final volatilityCluster = (market?.avgVolatilityPct ?? 0) >= 4.5 ||
        signals.where((signal) => signal.lowConfidence).length >= 3;
    final behaviors = <String>[
      if (btcWeak) 'BTC weakness is pressuring alt continuation.',
      if (memeCount >= 2) 'Meme volatility rotation is active.',
      if (sweepCount >= 2) 'Liquidity sweep timing is repeating.',
      if (volatilityCluster) 'Volatility clustering is present.',
      if (signals.any((signal) => signal.rejectionReason != null))
        'Trend exhaustion sequence appeared in rejected setups.',
    ];
    return MarketBehaviorMemoryRead(
      recurringBehaviors: behaviors.isEmpty
          ? const <String>['No dominant recurring behavior cluster yet.']
          : behaviors,
      clusterScore:
          (behaviors.length * 18 + signals.length * 2).clamp(0, 99).toDouble(),
      btcAltInfluence: btcWeak
          ? 'BTC weakness reduces alt continuation probability.'
          : 'BTC influence is not blocking alt continuation.',
      memeRotation: memeCount >= 2
          ? 'Meme sector rotation detected.'
          : 'Meme sector rotation is muted.',
      liquiditySweepTiming: sweepCount >= 2
          ? 'Repeated liquidity sweep timing detected.'
          : 'Liquidity sweep timing is isolated.',
      volatilityClustering: volatilityCluster
          ? 'Volatility clustering is active.'
          : 'Volatility clustering is controlled.',
      exhaustionSequence:
          signals.any((signal) => signal.rejectionReason != null)
              ? 'Exhaustion/rejection sequence needs monitoring.'
              : 'No clear exhaustion sequence detected.',
    );
  }

  AiMarketNarrativeRead marketNarrative({
    required MarketDnaProfile dna,
    required AiEdgeSignatureRead signature,
    required PredictivePressureRead pressure,
    required MarketRegimeMapRead regime,
  }) {
    final headline = pressure.netPressure >= 72
        ? 'Pressure expansion favors ${signature.family.toLowerCase()}.'
        : pressure.exhaustionProbability >= 64
            ? 'Exhaustion risk is limiting clean continuation.'
            : 'Market structure is building a selective edge window.';
    return AiMarketNarrativeRead(
      headline: headline,
      narrative:
          '${dna.symbol} shows ${dna.assetPersonality} with ${dna.volatilityRhythm}. ${pressure.summary} ${regime.explanation}',
      supportingReads: <String>[
        'Market DNA compatibility ${dna.compatibilityScore.toStringAsFixed(0)}%',
        'Signature ${signature.family} scored ${signature.score.toStringAsFixed(0)}%',
        'Liquidity condition: ${regime.liquidityConditions}',
        'Risk state: ${regime.riskState}',
      ],
    );
  }

  EdgeConfidenceRead edgeConfidence({
    required MarketDnaProfile dna,
    required AiEdgeSignatureRead signature,
    required List<SignalOutcomeReport> outcomes,
    ModelDriftRead? drift,
  }) {
    final matching = outcomes
        .where((outcome) =>
            outcome.symbol == dna.symbol ||
            outcome.setupType == signature.family)
        .toList(growable: false);
    final history = matching.isEmpty
        ? 52.0
        : matching.fold<double>(
                  0,
                  (sum, item) =>
                      sum +
                      item.maxFavorableExcursion -
                      item.maxAdverseExcursion,
                ) /
                matching.length *
                18 +
            50;
    final execution = matching.isEmpty
        ? 62.0
        : matching.fold<double>(0, (sum, item) => sum + item.exitEfficiency) /
            matching.length;
    final regime = (drift?.aiStabilityScore ?? 68).clamp(0, 99).toDouble();
    final score = (history * 0.26 +
            regime * 0.22 +
            execution * 0.18 +
            dna.compatibilityScore * 0.22 +
            signature.score * 0.12)
        .clamp(0, 99)
        .toDouble();
    return EdgeConfidenceRead(
      edgeConfidenceScore: score,
      historicalSetupQuality: history.clamp(0, 99).toDouble(),
      regimeCompatibility: regime,
      executionQuality: execution.clamp(0, 99).toDouble(),
      marketDnaCompatibility: dna.compatibilityScore,
      assetEdgeHistory: history.clamp(0, 99).toDouble(),
      verdict: score >= 78
          ? 'Validated proprietary edge window.'
          : score >= 58
              ? 'Developing edge; use controlled sizing.'
              : 'Weak edge; keep advisory/watch mode.',
    );
  }

  MarketRegimeMapRead regimeMap({
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final trend =
        chart?.opportunity.trendStrength ?? market?.confidenceScore ?? 50;
    final volatility = chart?.opportunity.volatilityScore ??
        ((market?.avgVolatilityPct ?? 4) * 12).clamp(0, 99).toDouble();
    final liquidity = chart?.liquidityHeatmap.pressureScore ?? 50;
    final sentiment = market?.sentimentScore ?? 50;
    return MarketRegimeMapRead(
      trendRegime: trend >= 68
          ? 'trend expansion'
          : trend >= 45
              ? 'selective trend'
              : 'range/chop',
      volatilityRegime: volatility >= 70
          ? 'high volatility'
          : volatility >= 42
              ? 'normal volatility'
              : 'compression',
      riskState: sentiment >= 58
          ? 'risk-on'
          : sentiment <= 42
              ? 'risk-off'
              : 'neutral risk',
      dominanceRotation:
          sentiment >= 55 ? 'dominance supportive' : 'dominance defensive',
      sectorLeadership: market?.heatmap.isNotEmpty == true
          ? '${market!.heatmap.first.symbol} leading'
          : 'leadership still forming',
      liquidityConditions: liquidity >= 65
          ? 'liquidity pressure elevated'
          : liquidity >= 42
              ? 'liquidity balanced'
              : 'liquidity thin',
      explanation:
          'Current market is ${trend >= 68 ? 'trend-led' : 'selective'} with ${volatility >= 70 ? 'expanding volatility' : 'controlled volatility'}.',
    );
  }

  ProprietaryWatchtowerRead proprietaryWatchtower({
    required PredictivePressureRead pressure,
    required MarketDnaProfile dna,
    ModelDriftRead? drift,
  }) {
    final structuralShift = (pressure.exhaustionProbability * 0.36 +
            pressure.volatilityExpansionProbability * 0.28 +
            dna.fakeoutTendency * 0.22 +
            (drift?.falseBreakoutTrend ?? 0) * 0.14)
        .clamp(0, 99)
        .toDouble();
    final alerts = <ProprietaryWatchtowerAlert>[
      if (structuralShift >= 72)
        const ProprietaryWatchtowerAlert(
          title: 'Regime transition warning',
          detail: 'Structure is shifting faster than confirmation quality.',
          severity: ProprietarySeverity.critical,
        ),
      if (pressure.volatilityExpansionProbability >= 72)
        const ProprietaryWatchtowerAlert(
          title: 'Abnormal volatility pressure',
          detail: 'Volatility expansion can distort entry timing.',
          severity: ProprietarySeverity.watch,
        ),
      if (dna.whaleSensitivity >= 72)
        const ProprietaryWatchtowerAlert(
          title: 'Smart money displacement',
          detail: 'Whale sensitivity is high; avoid late chasing.',
          severity: ProprietarySeverity.watch,
        ),
      if (drift?.driftDetected == true)
        const ProprietaryWatchtowerAlert(
          title: 'Edge deterioration',
          detail: 'Recent outcomes are reducing confidence in this edge.',
          severity: ProprietarySeverity.critical,
        ),
    ];
    return ProprietaryWatchtowerRead(
      status:
          alerts.any((item) => item.severity == ProprietarySeverity.critical)
              ? 'STRUCTURAL WATCH'
              : alerts.isEmpty
                  ? 'NORMAL'
                  : 'WATCH',
      alerts: alerts.isEmpty
          ? const <ProprietaryWatchtowerAlert>[
              ProprietaryWatchtowerAlert(
                title: 'No proprietary warning',
                detail: 'Market DNA and pressure state are aligned.',
                severity: ProprietarySeverity.normal,
              ),
            ]
          : alerts,
      structuralShiftScore: structuralShift,
    );
  }

  AiResearchRead researchLayer({
    required List<SignalModel> signals,
    required List<SignalOutcomeReport> outcomes,
  }) {
    final families = signals
        .map((signal) => edgeSignature(signal).family)
        .toSet()
        .toList(growable: false);
    return AiResearchRead(
      patternStudyCount: signals.length + outcomes.length,
      setupFamilies: families,
      replayAnnotationReady: outcomes.isNotEmpty,
      behavioralClusteringReady: signals.length >= 3,
      researchNotes: <String>[
        'Setup family analysis is indexed for ${families.length} signatures.',
        if (outcomes.isNotEmpty)
          'Replay annotations can compare projected vs realized path.',
        'Behavioral clustering remains heuristic until historical backend storage is connected.',
      ],
    );
  }

  String _assetPersonality(String symbol, double volatility, double trend) {
    final normalized = symbol.toUpperCase();
    if (normalized.contains('BTC')) {
      return trend >= 65 ? 'macro trend anchor' : 'dominance anchor';
    }
    if (normalized.contains('ETH')) {
      return volatility >= 60 ? 'beta expansion asset' : 'institutional beta';
    }
    if (RegExp('SOL|AVAX|INJ|TIA|SUI').hasMatch(normalized)) {
      return 'high momentum persistence asset';
    }
    if (RegExp('DOGE|PEPE|SHIB|BONK|WIF|FLOKI').hasMatch(normalized)) {
      return 'reflexive volatility asset';
    }
    return volatility >= 65 ? 'rotation-sensitive alt' : 'selective alt beta';
  }
}

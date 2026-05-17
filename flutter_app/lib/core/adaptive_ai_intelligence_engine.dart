import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/signal.dart';
import '../models/trade_execution.dart';
import 'ai_opportunity_engine.dart';
import 'institutional_intelligence_engine.dart';

class AiSelfEvaluation {
  const AiSelfEvaluation({
    required this.reliabilityScore,
    required this.signalSuccessRate,
    required this.falseBreakoutRate,
    required this.delayedEntryRate,
    required this.earlyEntryQuality,
    required this.tpHitRatio,
    required this.slHitRatio,
    required this.regimeAccuracy,
    required this.assetAccuracy,
    required this.volatilityAccuracy,
  });

  final double reliabilityScore;
  final double signalSuccessRate;
  final double falseBreakoutRate;
  final double delayedEntryRate;
  final double earlyEntryQuality;
  final double tpHitRatio;
  final double slHitRatio;
  final Map<String, double> regimeAccuracy;
  final Map<String, double> assetAccuracy;
  final Map<String, double> volatilityAccuracy;
}

class RegimeAdaptationRead {
  const RegimeAdaptationRead({
    required this.currentRegime,
    required this.adaptiveBehavior,
    required this.signalFrequency,
    required this.leverageMultiplier,
    required this.riskMultiplier,
    required this.preferredMode,
    required this.tradeStyle,
  });

  final String currentRegime;
  final String adaptiveBehavior;
  final String signalFrequency;
  final double leverageMultiplier;
  final double riskMultiplier;
  final String preferredMode;
  final String tradeStyle;
}

class ExecutionPrecisionRead {
  const ExecutionPrecisionRead({
    required this.entryEfficiency,
    required this.slippageAwareness,
    required this.confirmationTiming,
    required this.breakoutTimingQuality,
    required this.fakeBreakoutFilter,
    required this.spreadAwareness,
    required this.volatilityAdjustedTiming,
  });

  final double entryEfficiency;
  final String slippageAwareness;
  final String confirmationTiming;
  final double breakoutTimingQuality;
  final String fakeBreakoutFilter;
  final String spreadAwareness;
  final String volatilityAdjustedTiming;
}

class AutopilotIntelligenceRead {
  const AutopilotIntelligenceRead({
    required this.recommendedMode,
    required this.action,
    required this.reason,
    required this.leverageAdjustment,
    required this.signalFrequencyAdjustment,
    required this.scalpVsSwing,
  });

  final String recommendedMode;
  final String action;
  final String reason;
  final double leverageAdjustment;
  final String signalFrequencyAdjustment;
  final String scalpVsSwing;
}

class SignalCalibrationRead {
  const SignalCalibrationRead({
    required this.grade,
    required this.setupType,
    required this.classification,
    required this.rankReason,
  });

  final String grade;
  final String setupType;
  final String classification;
  final String rankReason;
}

class AdvancedMarketIntelligenceRead {
  const AdvancedMarketIntelligenceRead({
    required this.liquidationHeat,
    required this.correlationRisk,
    required this.dominanceRotation,
    required this.sectorRotation,
    required this.macroBias,
    required this.smartMoneyPressure,
    required this.volatilityExpansionProbability,
  });

  final double liquidationHeat;
  final double correlationRisk;
  final String dominanceRotation;
  final String sectorRotation;
  final String macroBias;
  final double smartMoneyPressure;
  final double volatilityExpansionProbability;
}

class AiPerformanceReview {
  const AiPerformanceReview({
    required this.dailyReview,
    required this.weeklyReview,
    required this.strongestSetupTypes,
    required this.weakestSetupTypes,
    required this.bestAiMode,
    required this.worstMarketCondition,
    required this.timingQuality,
    required this.adaptationPerformance,
  });

  final String dailyReview;
  final String weeklyReview;
  final List<String> strongestSetupTypes;
  final List<String> weakestSetupTypes;
  final String bestAiMode;
  final String worstMarketCondition;
  final double timingQuality;
  final double adaptationPerformance;
}

class AutopilotSafetyRead {
  const AutopilotSafetyRead({
    required this.safetyScore,
    required this.volatilityAcceptable,
    required this.liquidityAcceptable,
    required this.spreadAcceptable,
    required this.leverageAcceptable,
    required this.regimeAcceptable,
    required this.confidenceStable,
    required this.verdict,
  });

  final double safetyScore;
  final bool volatilityAcceptable;
  final bool liquidityAcceptable;
  final bool spreadAcceptable;
  final bool leverageAcceptable;
  final bool regimeAcceptable;
  final bool confidenceStable;
  final String verdict;
}

class HedgeFundAnalyticsRead {
  const HedgeFundAnalyticsRead({
    required this.expectancy,
    required this.stabilityScore,
    required this.setupExpectancy,
    required this.regimeExpectancy,
    required this.edgeDecay,
    required this.volatilityAdjustedPerformance,
    required this.executionEfficiency,
  });

  final double expectancy;
  final double stabilityScore;
  final double setupExpectancy;
  final double regimeExpectancy;
  final double edgeDecay;
  final double volatilityAdjustedPerformance;
  final double executionEfficiency;
}

class ReplayFoundationRead {
  const ReplayFoundationRead({
    required this.replayReady,
    required this.historicalWindows,
    required this.setupReplayAvailable,
    required this.missedOpportunityReplay,
    required this.trainingReviewStatus,
    required this.replayNote,
  });

  final bool replayReady;
  final int historicalWindows;
  final bool setupReplayAvailable;
  final bool missedOpportunityReplay;
  final String trainingReviewStatus;
  final String replayNote;
}

class AdaptiveAiIntelligenceEngine {
  const AdaptiveAiIntelligenceEngine();

  AiSelfEvaluation selfEvaluation(
    List<SignalModel> signals, {
    MarketChartModel? chart,
  }) {
    final count = math.max(signals.length, 1);
    final avgQuality = signals.fold<double>(
          0,
          (sum, signal) =>
              sum + math.max(signal.qualityScore, signal.alphaScore),
        ) /
        count;
    final executable =
        signals.where((signal) => signal.executionAllowed).length;
    final stale = signals.where((signal) => signal.marketDataStale).length;
    final falseBreakout =
        (100 - avgQuality + stale * 5).clamp(4, 48).toDouble();
    final delayedEntry =
        (signals.where((signal) => signal.lowConfidence).length / count * 100)
            .clamp(0, 44)
            .toDouble();
    final reliability = (avgQuality * 0.72 + executable * 4 - stale * 3)
        .clamp(0, 99)
        .toDouble();
    return AiSelfEvaluation(
      reliabilityScore: reliability,
      signalSuccessRate: (52 + avgQuality * 0.34).clamp(45, 88).toDouble(),
      falseBreakoutRate: falseBreakout,
      delayedEntryRate: delayedEntry,
      earlyEntryQuality:
          (avgQuality - delayedEntry * 0.25).clamp(35, 92).toDouble(),
      tpHitRatio: (48 + avgQuality * 0.28).clamp(40, 82).toDouble(),
      slHitRatio: (34 - avgQuality * 0.12 + stale * 2).clamp(8, 34).toDouble(),
      regimeAccuracy: _regimeAccuracy(signals),
      assetAccuracy: _assetAccuracy(signals),
      volatilityAccuracy: <String, double>{
        chart?.opportunity.volatilityScore != null &&
                chart!.opportunity.volatilityScore >= 65
            ? 'High volatility'
            : 'Normal volatility': reliability,
      },
    );
  }

  RegimeAdaptationRead regimeAdaptation(MarketChartModel? chart) {
    final regime = chart?.marketRegime.state.toUpperCase() ?? 'UNKNOWN';
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final whale = chart?.opportunity.whalePressure ?? 50;
    final trend = chart?.opportunity.trendStrength ?? 50;
    final liquidation = chart?.orderbookDepth.exhaustionWarning == true;
    if (volatility >= 78 || liquidation) {
      return const RegimeAdaptationRead(
        currentRegime: 'HIGH VOLATILITY',
        adaptiveBehavior: 'Reduce leverage and demand confirmation.',
        signalFrequency: 'Low',
        leverageMultiplier: 0.45,
        riskMultiplier: 0.40,
        preferredMode: 'Safe AI',
        tradeStyle: 'Scalp only',
      );
    }
    if (whale >= 72) {
      return const RegimeAdaptationRead(
        currentRegime: 'WHALE-DRIVEN',
        adaptiveBehavior:
            'Follow smart-money pressure with reduced chase risk.',
        signalFrequency: 'Medium',
        leverageMultiplier: 0.75,
        riskMultiplier: 0.65,
        preferredMode: 'Whale Follow AI',
        tradeStyle: 'Scalp into confirmation',
      );
    }
    if (trend >= 72 || regime.contains('TREND')) {
      return const RegimeAdaptationRead(
        currentRegime: 'TRENDING',
        adaptiveBehavior: 'Allow swing extension after momentum confirmation.',
        signalFrequency: 'Normal',
        leverageMultiplier: 0.90,
        riskMultiplier: 0.80,
        preferredMode: 'Swing AI',
        tradeStyle: 'Momentum continuation',
      );
    }
    return const RegimeAdaptationRead(
      currentRegime: 'RANGING / CHOP',
      adaptiveBehavior: 'Reduce frequency and prioritize mean reversion.',
      signalFrequency: 'Reduced',
      leverageMultiplier: 0.55,
      riskMultiplier: 0.50,
      preferredMode: 'Safe AI',
      tradeStyle: 'Mean reversion',
    );
  }

  ExecutionPrecisionRead executionPrecision({
    required SignalModel? signal,
    TradeEvaluationModel? evaluation,
    MarketChartModel? chart,
  }) {
    final confidence = _confidencePct(signal, evaluation, chart);
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final spreadProxy = evaluation?.alphaDecision.executionCostTotal ?? 0.0008;
    final breakoutQuality =
        ((signal?.alphaScore ?? chart?.opportunity.momentumScore ?? 50) -
                volatility * 0.12)
            .clamp(0, 99)
            .toDouble();
    return ExecutionPrecisionRead(
      entryEfficiency:
          (confidence * 0.65 + breakoutQuality * 0.35).clamp(0, 99).toDouble(),
      slippageAwareness: spreadProxy > 0.004
          ? 'High cost: wait for better fill'
          : 'Cost acceptable',
      confirmationTiming: confidence >= 76
          ? 'Confirmation window active'
          : 'Wait for stronger timing confirmation',
      breakoutTimingQuality: breakoutQuality,
      fakeBreakoutFilter: volatility >= 72
          ? 'Elevated fakeout filter active'
          : 'Normal fakeout filter',
      spreadAwareness: spreadProxy > 0.002
          ? 'Spread/cost proxy elevated'
          : 'Spread/cost proxy normal',
      volatilityAdjustedTiming: volatility >= 70
          ? 'Delay entries until volatility compresses'
          : 'Timing quality acceptable',
    );
  }

  AutopilotIntelligenceRead autopilot({
    required MarketChartModel? chart,
    required SignalModel? signal,
    TradeEvaluationModel? evaluation,
  }) {
    final regime = regimeAdaptation(chart);
    final confidence = _confidencePct(signal, evaluation, chart);
    final whaleConflict = (chart?.opportunity.whalePressure ?? 0) >= 70 &&
        signal != null &&
        signal.lowConfidence;
    if (whaleConflict) {
      return const AutopilotIntelligenceRead(
        recommendedMode: 'Scalp AI',
        action: 'Switch to scalp mode',
        reason:
            'Whale pressure exists, but confidence stability is not strong enough for swing risk.',
        leverageAdjustment: 0.45,
        signalFrequencyAdjustment: 'Selective',
        scalpVsSwing: 'Scalp',
      );
    }
    if (confidence >= 82 && regime.currentRegime == 'TRENDING') {
      return const AutopilotIntelligenceRead(
        recommendedMode: 'Swing AI',
        action: 'Allow swing extension',
        reason: 'Trend and confidence alignment support longer hold duration.',
        leverageAdjustment: 0.85,
        signalFrequencyAdjustment: 'Normal',
        scalpVsSwing: 'Swing',
      );
    }
    return AutopilotIntelligenceRead(
      recommendedMode: regime.preferredMode,
      action: regime.adaptiveBehavior,
      reason:
          'Autopilot adapted to ${regime.currentRegime.toLowerCase()} conditions.',
      leverageAdjustment: regime.leverageMultiplier,
      signalFrequencyAdjustment: regime.signalFrequency,
      scalpVsSwing: regime.tradeStyle,
    );
  }

  SignalCalibrationRead calibrateSignal(
    SignalModel signal, {
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final opportunity = SignalOpportunity.fromSignal(signal, mode: mode);
    final grade = opportunity.score >= 88
        ? 'A+'
        : opportunity.score >= 76
            ? 'A'
            : opportunity.score >= 58
                ? 'B'
                : 'Experimental';
    final setupType = opportunity.breakoutProbability >= 78
        ? 'Breakout continuation'
        : opportunity.whalePressure >= 72
            ? 'Smart-money pressure'
            : opportunity.liquiditySweepProbability >= 68
                ? 'Mean reversion after sweep'
                : 'Momentum continuation';
    return SignalCalibrationRead(
      grade: grade,
      setupType: setupType,
      classification: grade == 'A+' ? 'Sniper setup' : setupType,
      rankReason:
          '${opportunity.statusLabel}: ${opportunity.confidenceLabel} confidence, ${opportunity.expectedMoveLabel} expected move.',
    );
  }

  AdvancedMarketIntelligenceRead advancedMarketIntel(MarketChartModel? chart) {
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final whale = chart?.opportunity.whalePressure ?? 50;
    final trend = chart?.opportunity.trendStrength ?? 50;
    final liquidationHeat =
        (volatility * 0.45 + whale * 0.35).clamp(0, 99).toDouble();
    return AdvancedMarketIntelligenceRead(
      liquidationHeat: liquidationHeat,
      correlationRisk: volatility >= 70 ? 78 : 42,
      dominanceRotation:
          trend >= 65 ? 'BTC dominance supportive' : 'Dominance rotation mixed',
      sectorRotation:
          trend >= 70 ? 'Risk-on sector rotation' : 'Selective alts',
      macroBias: chart?.changePct != null && chart!.changePct >= 0
          ? 'Constructive'
          : 'Defensive',
      smartMoneyPressure: whale,
      volatilityExpansionProbability:
          (volatility * 0.72 + trend * 0.20).clamp(0, 99).toDouble(),
    );
  }

  AiPerformanceReview performanceReview(
    List<SignalModel> signals, {
    MarketChartModel? chart,
  }) {
    final eval = selfEvaluation(signals, chart: chart);
    final bestAsset = eval.assetAccuracy.entries.isEmpty
        ? 'BTCUSDT'
        : eval.assetAccuracy.entries
            .reduce((a, b) => a.value >= b.value ? a : b)
            .key;
    return AiPerformanceReview(
      dailyReview:
          'AI reliability is ${eval.reliabilityScore.toStringAsFixed(0)}%. Best current read is $bestAsset.',
      weeklyReview:
          'Breakout reliability is stable while false breakout risk is ${eval.falseBreakoutRate.toStringAsFixed(0)}%.',
      strongestSetupTypes: const <String>[
        'Momentum continuation',
        'Breakout continuation',
        'Whale pressure follow',
      ],
      weakestSetupTypes: const <String>[
        'Late chop entries',
        'Low-volume reversals',
      ],
      bestAiMode: eval.reliabilityScore >= 74 ? 'Smart AI' : 'Safe AI',
      worstMarketCondition: eval.falseBreakoutRate >= 28
          ? 'High volatility chop'
          : 'Low participation range',
      timingQuality: eval.earlyEntryQuality,
      adaptationPerformance:
          (eval.reliabilityScore - eval.falseBreakoutRate * 0.30)
              .clamp(0, 99)
              .toDouble(),
    );
  }

  AutopilotSafetyRead autopilotSafety({
    required SignalModel? signal,
    required TradeEvaluationModel? evaluation,
    required MarketChartModel? chart,
  }) {
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final liquidity = chart?.liquidityHeatmap.pressureScore ?? 50;
    final spread = evaluation?.alphaDecision.executionCostTotal ?? 0.0008;
    final leverage = const InstitutionalIntelligenceEngine()
        .executionBriefing(
          symbol: signal?.symbol ?? chart?.symbol ?? '',
          side: signal?.action ?? chart?.executionGuide.side ?? 'BUY',
          notional: 100,
          evaluation: evaluation,
          signal: signal,
          chart: chart,
        )
        .suggestedLeverage;
    final confidence = _confidencePct(signal, evaluation, chart);
    final checks = <bool>[
      volatility < 78,
      liquidity >= 32,
      spread < 0.004,
      leverage <= 3.5,
      chart?.marketRegime.state.toUpperCase() != 'UNKNOWN',
      confidence >= 58,
    ];
    final score = checks.where((item) => item).length / checks.length * 100;
    return AutopilotSafetyRead(
      safetyScore: score,
      volatilityAcceptable: checks[0],
      liquidityAcceptable: checks[1],
      spreadAcceptable: checks[2],
      leverageAcceptable: checks[3],
      regimeAcceptable: checks[4],
      confidenceStable: checks[5],
      verdict: score >= 84
          ? 'Autopilot ready'
          : score >= 66
              ? 'Semi-auto only'
              : 'Watch / simulate only',
    );
  }

  HedgeFundAnalyticsRead hedgeFundAnalytics(
    List<SignalModel> signals, {
    MarketChartModel? chart,
  }) {
    final eval = selfEvaluation(signals, chart: chart);
    final precision = executionPrecision(
      signal: signals.isEmpty ? null : signals.first,
      chart: chart,
    );
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    return HedgeFundAnalyticsRead(
      expectancy: (eval.tpHitRatio / 100 * 1.8 - eval.slHitRatio / 100)
          .clamp(-1, 2.5)
          .toDouble(),
      stabilityScore:
          (100 - eval.falseBreakoutRate - eval.delayedEntryRate * 0.35)
              .clamp(0, 99)
              .toDouble(),
      setupExpectancy: (eval.signalSuccessRate / 100 * 2.0 - 0.72)
          .clamp(-0.5, 2.2)
          .toDouble(),
      regimeExpectancy: (eval.regimeAccuracy.values.isEmpty
              ? eval.reliabilityScore
              : eval.regimeAccuracy.values.first) /
          100,
      edgeDecay: (eval.falseBreakoutRate * 0.42 + volatility * 0.18)
          .clamp(0, 55)
          .toDouble(),
      volatilityAdjustedPerformance:
          (eval.reliabilityScore - volatility * 0.18).clamp(0, 99).toDouble(),
      executionEfficiency: precision.entryEfficiency,
    );
  }

  ReplayFoundationRead replayFoundation(MarketChartModel? chart) {
    final windows = chart == null ? 0 : (chart.candles.length / 24).floor();
    return ReplayFoundationRead(
      replayReady: chart != null && chart.candles.length >= 24,
      historicalWindows: windows,
      setupReplayAvailable: chart != null && chart.markers.isNotEmpty,
      missedOpportunityReplay:
          chart != null && chart.confidenceHistory.length >= 2,
      trainingReviewStatus:
          chart == null ? 'Awaiting chart history' : 'Replay index prepared',
      replayNote: chart == null
          ? 'Historical setup replay will activate when chart state loads.'
          : 'Replay foundation can reconstruct ${chart.candles.length} candles and ${chart.markers.length} AI markers.',
    );
  }

  Map<String, double> _regimeAccuracy(List<SignalModel> signals) {
    final grouped = <String, List<SignalModel>>{};
    for (final signal in signals) {
      grouped.putIfAbsent(signal.regime, () => <SignalModel>[]).add(signal);
    }
    return grouped.map((key, value) {
      final avg = value.fold<double>(
            0,
            (sum, signal) =>
                sum + math.max(signal.qualityScore, signal.alphaScore),
          ) /
          math.max(value.length, 1);
      return MapEntry(
          key.isEmpty ? 'UNKNOWN' : key, avg.clamp(0, 99).toDouble());
    });
  }

  Map<String, double> _assetAccuracy(List<SignalModel> signals) {
    final grouped = <String, List<SignalModel>>{};
    for (final signal in signals) {
      grouped.putIfAbsent(signal.symbol, () => <SignalModel>[]).add(signal);
    }
    return grouped.map((key, value) {
      final avg = value.fold<double>(
            0,
            (sum, signal) =>
                sum + math.max(signal.qualityScore, signal.alphaScore),
          ) /
          math.max(value.length, 1);
      return MapEntry(key, avg.clamp(0, 99).toDouble());
    });
  }

  double _confidencePct(
    SignalModel? signal,
    TradeEvaluationModel? evaluation,
    MarketChartModel? chart,
  ) {
    final raw = evaluation?.confidenceScore ??
        signal?.confidence ??
        chart?.opportunity.confidence ??
        0;
    return raw <= 1 ? raw * 100 : raw;
  }
}

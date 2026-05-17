import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/signal.dart';
import 'adaptive_ai_intelligence_engine.dart';
import 'ai_opportunity_engine.dart';

class SignalOutcomeReport {
  const SignalOutcomeReport({
    required this.signalId,
    required this.symbol,
    required this.entryTimestamp,
    required this.marketRegime,
    required this.aiModeUsed,
    required this.setupType,
    required this.confidenceAtEntry,
    required this.executionDelaySeconds,
    required this.maxFavorableExcursion,
    required this.maxAdverseExcursion,
    required this.tpHits,
    required this.slHit,
    required this.invalidationTiming,
    required this.holdingDurationMinutes,
    required this.exitEfficiency,
    required this.outcomeQuality,
  });

  final String signalId;
  final String symbol;
  final DateTime entryTimestamp;
  final String marketRegime;
  final String aiModeUsed;
  final String setupType;
  final double confidenceAtEntry;
  final int executionDelaySeconds;
  final double maxFavorableExcursion;
  final double maxAdverseExcursion;
  final int tpHits;
  final bool slHit;
  final String invalidationTiming;
  final int holdingDurationMinutes;
  final double exitEfficiency;
  final String outcomeQuality;
}

class EdgeValidationRead {
  const EdgeValidationRead({
    required this.setupExpectancy,
    required this.regimeExpectancy,
    required this.assetExpectancy,
    required this.aiModeExpectancy,
    required this.confidenceCalibrationAccuracy,
    required this.signalGradePerformance,
    required this.executionQualityImpact,
    required this.edgeSummary,
  });

  final Map<String, double> setupExpectancy;
  final Map<String, double> regimeExpectancy;
  final Map<String, double> assetExpectancy;
  final Map<String, double> aiModeExpectancy;
  final double confidenceCalibrationAccuracy;
  final Map<String, double> signalGradePerformance;
  final double executionQualityImpact;
  final String edgeSummary;
}

class ModelDriftRead {
  const ModelDriftRead({
    required this.aiStabilityScore,
    required this.winRateTrend,
    required this.falseBreakoutTrend,
    required this.expectancyTrend,
    required this.executionEfficiencyTrend,
    required this.regimeInstability,
    required this.driftDetected,
    required this.correctiveAction,
  });

  final double aiStabilityScore;
  final double winRateTrend;
  final double falseBreakoutTrend;
  final double expectancyTrend;
  final double executionEfficiencyTrend;
  final double regimeInstability;
  final bool driftDetected;
  final String correctiveAction;
}

class SelfCorrectionRead {
  const SelfCorrectionRead({
    required this.setupWeightAdjustments,
    required this.preferredRegimes,
    required this.suppressedConditions,
    required this.boostedSetups,
    required this.confidenceFloorAdjustment,
    required this.leverageMultiplier,
    required this.learningNote,
  });

  final Map<String, double> setupWeightAdjustments;
  final List<String> preferredRegimes;
  final List<String> suppressedConditions;
  final List<String> boostedSetups;
  final double confidenceFloorAdjustment;
  final double leverageMultiplier;
  final String learningNote;
}

class ExecutionOutcomeRead {
  const ExecutionOutcomeRead({
    required this.executionQualityScore,
    required this.lateEntryPenalty,
    required this.slippageImpact,
    required this.volatilityTimingImpact,
    required this.confirmationLag,
    required this.overextensionRisk,
    required this.liquidityQuality,
    required this.executionSummary,
  });

  final double executionQualityScore;
  final double lateEntryPenalty;
  final double slippageImpact;
  final double volatilityTimingImpact;
  final int confirmationLag;
  final double overextensionRisk;
  final double liquidityQuality;
  final String executionSummary;
}

class AiDecisionJournalEntry {
  const AiDecisionJournalEntry({
    required this.signalId,
    required this.symbol,
    required this.enteredBecause,
    required this.expectedOutcome,
    required this.actualOutcome,
    required this.learned,
  });

  final String signalId;
  final String symbol;
  final List<String> enteredBecause;
  final String expectedOutcome;
  final String actualOutcome;
  final String learned;
}

class StrategyLeaderboardRead {
  const StrategyLeaderboardRead({
    required this.bestSetupTypes,
    required this.bestAiModes,
    required this.bestRegimes,
    required this.bestAssets,
    required this.bestVolatilityConditions,
  });

  final List<LeaderboardRow> bestSetupTypes;
  final List<LeaderboardRow> bestAiModes;
  final List<LeaderboardRow> bestRegimes;
  final List<LeaderboardRow> bestAssets;
  final List<LeaderboardRow> bestVolatilityConditions;
}

class LeaderboardRow {
  const LeaderboardRow({
    required this.label,
    required this.score,
    required this.sampleSize,
    required this.note,
  });

  final String label;
  final double score;
  final int sampleSize;
  final String note;
}

class ReplayMetadataRead {
  const ReplayMetadataRead({
    required this.replayId,
    required this.snapshotCount,
    required this.decisionTimelineEvents,
    required this.projectedMove,
    required this.actualMove,
    required this.annotations,
    required this.ready,
  });

  final String replayId;
  final int snapshotCount;
  final int decisionTimelineEvents;
  final double projectedMove;
  final double actualMove;
  final List<String> annotations;
  final bool ready;
}

class QuantPerformanceRead {
  const QuantPerformanceRead({
    required this.rollingExpectancy,
    required this.rollingEdgeStability,
    required this.confidenceCalibrationCurve,
    required this.regimeAdjustedPerformance,
    required this.aiAdaptationQuality,
    required this.setupDecay,
    required this.executionAdjustedReturns,
  });

  final double rollingExpectancy;
  final double rollingEdgeStability;
  final List<CalibrationPoint> confidenceCalibrationCurve;
  final double regimeAdjustedPerformance;
  final double aiAdaptationQuality;
  final double setupDecay;
  final double executionAdjustedReturns;
}

class CalibrationPoint {
  const CalibrationPoint({
    required this.confidenceBucket,
    required this.realizedAccuracy,
  });

  final String confidenceBucket;
  final double realizedAccuracy;
}

class EdgeValidationEngine {
  const EdgeValidationEngine();

  List<SignalOutcomeReport> signalOutcomes(
    List<SignalModel> signals, {
    MarketChartModel? chart,
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final candles = chart?.candles ?? const <MarketCandleModel>[];
    return signals.take(8).map((signal) {
      final calibration = const AdaptiveAiIntelligenceEngine()
          .calibrateSignal(signal, mode: mode);
      final move = _moveForSignal(signal, candles);
      final confidence = _confidencePct(signal.confidence);
      final direction = signal.action.toUpperCase() == 'SELL' ? -1 : 1;
      final favorable = math.max<double>(0, move * direction);
      final adverse = math.max<double>(0, -move * direction);
      final tpHits = favorable >= 3
          ? 3
          : favorable >= 1.8
              ? 2
              : favorable >= 0.8
                  ? 1
                  : 0;
      final slHit = adverse >= 1.2 || signal.rejectionReason != null;
      final exitEfficiency = (favorable * 18 + confidence * 0.55 - adverse * 16)
          .clamp(0, 99)
          .toDouble();
      return SignalOutcomeReport(
        signalId: signal.signalId.isEmpty ? signal.symbol : signal.signalId,
        symbol: signal.symbol,
        entryTimestamp: signal.publishedAt,
        marketRegime: signal.regime.isEmpty ? 'UNKNOWN' : signal.regime,
        aiModeUsed: _modeLabel(mode),
        setupType: calibration.setupType,
        confidenceAtEntry: confidence,
        executionDelaySeconds: _executionDelay(signal),
        maxFavorableExcursion: favorable,
        maxAdverseExcursion: adverse,
        tpHits: tpHits,
        slHit: slHit,
        invalidationTiming: slHit
            ? adverse >= 2
                ? 'Fast invalidation'
                : 'Controlled invalidation'
            : 'Not invalidated',
        holdingDurationMinutes: _holdingMinutes(signal, candles),
        exitEfficiency: exitEfficiency,
        outcomeQuality: exitEfficiency >= 76
            ? 'High quality'
            : exitEfficiency >= 58
                ? 'Acceptable'
                : 'Needs review',
      );
    }).toList(growable: false);
  }

  EdgeValidationRead edgeValidation(List<SignalOutcomeReport> outcomes) {
    final expectancy = _expectancy(outcomes);
    final setup = _groupExpectancy(outcomes, (item) => item.setupType);
    final regime = _groupExpectancy(outcomes, (item) => item.marketRegime);
    final asset = _groupExpectancy(outcomes, (item) => item.symbol);
    final mode = _groupExpectancy(outcomes, (item) => item.aiModeUsed);
    final grade = _gradePerformance(outcomes);
    final calibration = _confidenceCalibration(outcomes);
    final executionImpact = outcomes.isEmpty
        ? 0
        : outcomes.fold<double>(
              0,
              (sum, item) => sum + item.exitEfficiency,
            ) /
            outcomes.length;
    return EdgeValidationRead(
      setupExpectancy: setup,
      regimeExpectancy: regime,
      assetExpectancy: asset,
      aiModeExpectancy: mode,
      confidenceCalibrationAccuracy: calibration,
      signalGradePerformance: grade,
      executionQualityImpact: executionImpact.clamp(0, 99).toDouble(),
      edgeSummary: expectancy >= 1
          ? 'Measured edge is positive across the current signal sample.'
          : expectancy >= 0
              ? 'Edge is present but not yet strong enough for higher risk.'
              : 'Current sample shows weak edge; autopilot should stay conservative.',
    );
  }

  ModelDriftRead modelDrift(
    List<SignalOutcomeReport> outcomes, {
    MarketChartModel? chart,
  }) {
    final edge = edgeValidation(outcomes);
    final falseBreakouts = outcomes
        .where((item) => item.maxAdverseExcursion > item.maxFavorableExcursion)
        .length;
    final falseBreakoutTrend =
        outcomes.isEmpty ? 0.0 : falseBreakouts / outcomes.length * 100;
    final executionEfficiency = edge.executionQualityImpact;
    final regimeInstability =
        ((chart?.opportunity.volatilityScore ?? 50) * 0.55 +
                falseBreakoutTrend * 0.45)
            .clamp(0, 99)
            .toDouble();
    final expectancyTrend = _expectancy(outcomes);
    final winRate = outcomes.isEmpty
        ? 0.0
        : outcomes.where((item) => item.maxFavorableExcursion > 0.6).length /
            outcomes.length *
            100;
    final stability = (winRate * 0.34 +
            executionEfficiency * 0.32 +
            (100 - regimeInstability) * 0.34)
        .clamp(0, 99)
        .toDouble();
    final drift = stability < 58 || expectancyTrend < -0.2;
    return ModelDriftRead(
      aiStabilityScore: stability,
      winRateTrend: winRate,
      falseBreakoutTrend: falseBreakoutTrend,
      expectancyTrend: expectancyTrend,
      executionEfficiencyTrend: executionEfficiency,
      regimeInstability: regimeInstability,
      driftDetected: drift,
      correctiveAction: drift
          ? 'Reduce aggressiveness, lower leverage, and require stronger confirmation.'
          : 'Current edge is stable enough for normal advisory behavior.',
    );
  }

  SelfCorrectionRead selfCorrection(
    List<SignalOutcomeReport> outcomes, {
    MarketChartModel? chart,
  }) {
    final drift = modelDrift(outcomes, chart: chart);
    final setupExpectancy = edgeValidation(outcomes).setupExpectancy;
    final adjustments = setupExpectancy.map(
      (key, value) => MapEntry(
          key,
          value >= 0.8
              ? 1.12
              : value < 0
                  ? 0.82
                  : 1.0),
    );
    final preferred = edgeValidation(outcomes)
        .regimeExpectancy
        .entries
        .where((entry) => entry.value >= 0.5)
        .map((entry) => entry.key)
        .take(3)
        .toList(growable: false);
    final suppressed = <String>[
      if (drift.falseBreakoutTrend >= 35) 'false breakout clusters',
      if (drift.regimeInstability >= 70) 'unstable volatility',
      if (drift.executionEfficiencyTrend < 58) 'late execution windows',
    ];
    final boosted = setupExpectancy.entries
        .where((entry) => entry.value >= 0.8)
        .map((entry) => entry.key)
        .take(3)
        .toList(growable: false);
    return SelfCorrectionRead(
      setupWeightAdjustments: adjustments,
      preferredRegimes:
          preferred.isEmpty ? const <String>['Stable trend'] : preferred,
      suppressedConditions:
          suppressed.isEmpty ? const <String>['none currently'] : suppressed,
      boostedSetups: boosted.isEmpty
          ? const <String>['high-confidence continuation']
          : boosted,
      confidenceFloorAdjustment: drift.driftDetected ? 6 : 0,
      leverageMultiplier: drift.driftDetected ? 0.62 : 0.90,
      learningNote: drift.driftDetected
          ? 'Heuristic correction is tightening signal admission until edge stabilizes.'
          : 'Heuristic correction is preserving current weights and monitoring decay.',
    );
  }

  ExecutionOutcomeRead executionOutcome(
    SignalOutcomeReport? outcome, {
    MarketChartModel? chart,
  }) {
    final resolved = outcome;
    final delayPenalty = resolved == null
        ? 8.0
        : (resolved.executionDelaySeconds / 8).clamp(0, 30).toDouble();
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final slippage =
        (volatility * 0.08 + delayPenalty * 0.28).clamp(0, 35).toDouble();
    final overextension =
        ((resolved?.maxFavorableExcursion ?? 0) > 3.5 ? 16 : volatility * 0.10)
            .clamp(0, 30)
            .toDouble();
    final liquidity = chart?.liquidityHeatmap.pressureScore ?? 58;
    final score =
        (100 - delayPenalty - slippage - overextension + liquidity * 0.12)
            .clamp(0, 99)
            .toDouble();
    return ExecutionOutcomeRead(
      executionQualityScore: score,
      lateEntryPenalty: delayPenalty,
      slippageImpact: slippage,
      volatilityTimingImpact: (volatility * 0.24).clamp(0, 30).toDouble(),
      confirmationLag: resolved?.executionDelaySeconds ?? 0,
      overextensionRisk: overextension,
      liquidityQuality: liquidity,
      executionSummary: score >= 76
          ? 'Entry timing is efficient for the current market state.'
          : score >= 58
              ? 'Execution is acceptable but should avoid chasing extensions.'
              : 'Execution quality is weak; prefer watch, simulate, or smaller size.',
    );
  }

  AiDecisionJournalEntry decisionJournal(
    SignalModel signal,
    SignalOutcomeReport? outcome, {
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final calibration = const AdaptiveAiIntelligenceEngine()
        .calibrateSignal(signal, mode: mode);
    final reasons = signal.reasons.take(4).toList(growable: false);
    final resolvedOutcome = outcome;
    return AiDecisionJournalEntry(
      signalId: signal.signalId.isEmpty ? signal.symbol : signal.signalId,
      symbol: signal.symbol,
      enteredBecause: reasons.isEmpty
          ? <String>[calibration.rankReason]
          : <String>[...reasons, calibration.classification],
      expectedOutcome:
          '${calibration.setupType} with ${_confidencePct(signal.confidence).toStringAsFixed(0)}% entry confidence.',
      actualOutcome: resolvedOutcome == null
          ? 'Outcome is still being tracked.'
          : '${resolvedOutcome.outcomeQuality}: MFE ${resolvedOutcome.maxFavorableExcursion.toStringAsFixed(2)}%, MAE ${resolvedOutcome.maxAdverseExcursion.toStringAsFixed(2)}%, TP hits ${resolvedOutcome.tpHits}.',
      learned: resolvedOutcome == null
          ? 'Wait for enough post-signal price path before changing weights.'
          : resolvedOutcome.exitEfficiency >= 70
              ? 'Increase trust slightly for this setup/regime combination.'
              : 'Reduce weight for similar timing until confirmation improves.',
    );
  }

  StrategyLeaderboardRead strategyLeaderboard(
      List<SignalOutcomeReport> outcomes) {
    return StrategyLeaderboardRead(
      bestSetupTypes: _leaderboard(outcomes, (item) => item.setupType),
      bestAiModes: _leaderboard(outcomes, (item) => item.aiModeUsed),
      bestRegimes: _leaderboard(outcomes, (item) => item.marketRegime),
      bestAssets: _leaderboard(outcomes, (item) => item.symbol),
      bestVolatilityConditions: _leaderboard(
        outcomes,
        (item) => item.maxAdverseExcursion > 1.4
            ? 'High volatility'
            : 'Controlled volatility',
      ),
    );
  }

  ReplayMetadataRead replayMetadata(
    List<SignalOutcomeReport> outcomes, {
    MarketChartModel? chart,
  }) {
    final projected = chart?.opportunity.expectedRr ?? 0;
    final actual = outcomes.isEmpty
        ? 0.0
        : outcomes.fold<double>(
              0,
              (sum, item) =>
                  sum + item.maxFavorableExcursion - item.maxAdverseExcursion,
            ) /
            outcomes.length;
    return ReplayMetadataRead(
      replayId:
          '${chart?.symbol ?? outcomes.firstOrNull?.symbol ?? 'signal'}-${chart?.snapshotVersion ?? outcomes.length}',
      snapshotCount: (chart?.candles.length ?? 0) + outcomes.length,
      decisionTimelineEvents: outcomes.length * 4,
      projectedMove: projected,
      actualMove: actual,
      annotations: <String>[
        'Signal snapshot captured',
        'Decision timeline indexed',
        'Projected vs actual path prepared',
        if (chart?.stateHash.isNotEmpty == true) 'State hash linked',
      ],
      ready: outcomes.isNotEmpty || (chart?.candles.isNotEmpty ?? false),
    );
  }

  QuantPerformanceRead quantPerformance(List<SignalOutcomeReport> outcomes) {
    final edge = edgeValidation(outcomes);
    final drift = modelDrift(outcomes);
    final expectancy = _expectancy(outcomes);
    final decay = outcomes.isEmpty
        ? 0.0
        : outcomes
                .where((item) => item.outcomeQuality == 'Needs review')
                .length /
            outcomes.length *
            100;
    return QuantPerformanceRead(
      rollingExpectancy: expectancy,
      rollingEdgeStability: drift.aiStabilityScore,
      confidenceCalibrationCurve: _calibrationCurve(outcomes),
      regimeAdjustedPerformance: edge.regimeExpectancy.values.isEmpty
          ? 0
          : edge.regimeExpectancy.values.reduce((a, b) => a + b) /
              edge.regimeExpectancy.length,
      aiAdaptationQuality:
          (drift.aiStabilityScore - decay * 0.25).clamp(0, 99).toDouble(),
      setupDecay: decay,
      executionAdjustedReturns:
          expectancy * (edge.executionQualityImpact / 100).clamp(0.2, 1.2),
    );
  }

  double _moveForSignal(
    SignalModel signal,
    List<MarketCandleModel> candles,
  ) {
    if (candles.length >= 2 && signal.price > 0) {
      final window = candles.takeLast(16).toList(growable: false);
      final high = window.map((item) => item.high).reduce(math.max);
      final low = window.map((item) => item.low).reduce(math.min);
      final reference = signal.price == 0 ? window.first.close : signal.price;
      final upMove = (high - reference) / reference * 100;
      final downMove = (reference - low) / reference * 100;
      return signal.action.toUpperCase() == 'SELL'
          ? downMove - upMove
          : upMove - downMove;
    }
    final confidence = _confidencePct(signal.confidence);
    final directionQuality = signal.executionAllowed ? 1 : -0.2;
    return (confidence / 100 * 2.8 + signal.qualityScore / 100 * 1.2) *
        directionQuality;
  }

  int _executionDelay(SignalModel signal) {
    if (signal.executionAllowed) {
      return signal.lowConfidence ? 34 : 12;
    }
    return signal.lowConfidence ? 75 : 48;
  }

  int _holdingMinutes(
    SignalModel signal,
    List<MarketCandleModel> candles,
  ) {
    if (candles.length >= 2) {
      final first = candles.first.timestampMs;
      final last = candles.last.timestampMs;
      return ((last - first).abs() / 60000).clamp(1, 1440).round();
    }
    return signal.lowConfidence ? 18 : 45;
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

  Map<String, double> _groupExpectancy(
    List<SignalOutcomeReport> outcomes,
    String Function(SignalOutcomeReport item) keyOf,
  ) {
    final grouped = <String, List<SignalOutcomeReport>>{};
    for (final item in outcomes) {
      grouped.putIfAbsent(keyOf(item), () => <SignalOutcomeReport>[]).add(item);
    }
    final entries = grouped.entries.map(
      (entry) => MapEntry(entry.key, _expectancy(entry.value)),
    );
    return Map<String, double>.fromEntries(entries);
  }

  Map<String, double> _gradePerformance(List<SignalOutcomeReport> outcomes) {
    final grouped = <String, List<SignalOutcomeReport>>{};
    for (final item in outcomes) {
      final grade = item.confidenceAtEntry >= 88
          ? 'A+'
          : item.confidenceAtEntry >= 76
              ? 'A'
              : item.confidenceAtEntry >= 58
                  ? 'B'
                  : 'Experimental';
      grouped.putIfAbsent(grade, () => <SignalOutcomeReport>[]).add(item);
    }
    return grouped.map((key, value) => MapEntry(key, _expectancy(value)));
  }

  double _confidenceCalibration(List<SignalOutcomeReport> outcomes) {
    if (outcomes.isEmpty) {
      return 0;
    }
    final error = outcomes.fold<double>(0, (sum, item) {
          final realized = item.maxFavorableExcursion > item.maxAdverseExcursion
              ? 100.0
              : 0.0;
          return sum + (item.confidenceAtEntry - realized).abs();
        }) /
        outcomes.length;
    return (100 - error).clamp(0, 99).toDouble();
  }

  List<LeaderboardRow> _leaderboard(
    List<SignalOutcomeReport> outcomes,
    String Function(SignalOutcomeReport item) keyOf,
  ) {
    final grouped = <String, List<SignalOutcomeReport>>{};
    for (final item in outcomes) {
      grouped.putIfAbsent(keyOf(item), () => <SignalOutcomeReport>[]).add(item);
    }
    final rows = grouped.entries.map((entry) {
      final expectancy = _expectancy(entry.value);
      return LeaderboardRow(
        label: entry.key,
        score: expectancy,
        sampleSize: entry.value.length,
        note: expectancy >= 0.8 ? 'validated edge' : 'monitor sample',
      );
    }).toList()
      ..sort((a, b) => b.score.compareTo(a.score));
    return rows.take(4).toList(growable: false);
  }

  List<CalibrationPoint> _calibrationCurve(List<SignalOutcomeReport> outcomes) {
    final buckets = <String, List<SignalOutcomeReport>>{
      '40-55': <SignalOutcomeReport>[],
      '55-70': <SignalOutcomeReport>[],
      '70-85': <SignalOutcomeReport>[],
      '85+': <SignalOutcomeReport>[],
    };
    for (final item in outcomes) {
      final key = item.confidenceAtEntry >= 85
          ? '85+'
          : item.confidenceAtEntry >= 70
              ? '70-85'
              : item.confidenceAtEntry >= 55
                  ? '55-70'
                  : '40-55';
      buckets[key]!.add(item);
    }
    return buckets.entries.map((entry) {
      final items = entry.value;
      final accuracy = items.isEmpty
          ? 0.0
          : items
                  .where(
                    (item) =>
                        item.maxFavorableExcursion > item.maxAdverseExcursion,
                  )
                  .length /
              items.length *
              100;
      return CalibrationPoint(
        confidenceBucket: entry.key,
        realizedAccuracy: accuracy,
      );
    }).toList(growable: false);
  }

  String _modeLabel(AiTradingMode mode) {
    switch (mode) {
      case AiTradingMode.safe:
        return 'Safe AI';
      case AiTradingMode.aggressive:
        return 'Aggressive AI';
      case AiTradingMode.balanced:
        return 'Smart AI';
    }
  }

  double _confidencePct(double raw) => raw <= 1 ? raw * 100 : raw;
}

extension _TakeLast<T> on Iterable<T> {
  Iterable<T> takeLast(int count) {
    final list = toList(growable: false);
    if (list.length <= count) {
      return list;
    }
    return list.skip(list.length - count);
  }
}

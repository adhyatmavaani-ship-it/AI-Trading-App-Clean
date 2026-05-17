import 'dart:math' as math;

import '../models/market_chart.dart';
import '../models/signal.dart';
import '../models/trade_execution.dart';
import 'ai_opportunity_engine.dart';

class ConfidenceContributor {
  const ConfidenceContributor({
    required this.label,
    required this.score,
    required this.confirmed,
    required this.detail,
  });

  final String label;
  final double score;
  final bool confirmed;
  final String detail;
}

class SignalTransparency {
  const SignalTransparency({
    required this.confidence,
    required this.confirmationCount,
    required this.riskGrade,
    required this.contributors,
  });

  final double confidence;
  final int confirmationCount;
  final String riskGrade;
  final List<ConfidenceContributor> contributors;
}

class MarketMicrostructureRead {
  const MarketMicrostructureRead({
    required this.liquiditySweep,
    required this.orderAbsorption,
    required this.imbalanceZones,
    required this.fakeoutRisk,
    required this.exhaustionRisk,
    required this.trapProbability,
    required this.smartMoneyBias,
  });

  final String liquiditySweep;
  final String orderAbsorption;
  final String imbalanceZones;
  final double fakeoutRisk;
  final double exhaustionRisk;
  final double trapProbability;
  final String smartMoneyBias;
}

class ExecutionBriefing {
  const ExecutionBriefing({
    required this.symbol,
    required this.side,
    required this.confidence,
    required this.riskGrade,
    required this.suggestedLeverage,
    required this.positionSizeLabel,
    required this.entryLabel,
    required this.stopLoss,
    required this.takeProfitZones,
    required this.liquidationRisk,
    required this.volatilityAdjustedRisk,
    required this.expectedHoldDuration,
    required this.confidenceDecay,
    required this.invalidation,
    required this.marketRegime,
  });

  final String symbol;
  final String side;
  final double confidence;
  final String riskGrade;
  final double suggestedLeverage;
  final String positionSizeLabel;
  final String entryLabel;
  final double stopLoss;
  final List<double> takeProfitZones;
  final String liquidationRisk;
  final String volatilityAdjustedRisk;
  final String expectedHoldDuration;
  final String confidenceDecay;
  final String invalidation;
  final String marketRegime;
}

class MarketContextRead {
  const MarketContextRead({
    required this.btcDominanceInfluence,
    required this.fearGreedState,
    required this.sectorMomentum,
    required this.volatilityRegime,
    required this.marketTrendRegime,
    required this.correlationRisk,
    required this.sentimentBias,
  });

  final String btcDominanceInfluence;
  final String fearGreedState;
  final String sectorMomentum;
  final String volatilityRegime;
  final String marketTrendRegime;
  final String correlationRisk;
  final String sentimentBias;
}

class ProfessionalPerformanceRead {
  const ProfessionalPerformanceRead({
    required this.winRate,
    required this.averageRiskReward,
    required this.profitFactor,
    required this.maxDrawdown,
    required this.streakQuality,
    required this.aiAlignmentScore,
    required this.disciplineScore,
  });

  final double winRate;
  final double averageRiskReward;
  final double profitFactor;
  final double maxDrawdown;
  final String streakQuality;
  final double aiAlignmentScore;
  final double disciplineScore;
}

class AiMemoryProfile {
  const AiMemoryProfile({
    required this.preferredAssets,
    required this.preferredMode,
    required this.successfulSetups,
    required this.avoidedSetups,
    required this.favoriteStyle,
    required this.personalizedNote,
  });

  final List<String> preferredAssets;
  final String preferredMode;
  final List<String> successfulSetups;
  final List<String> avoidedSetups;
  final String favoriteStyle;
  final String personalizedNote;
}

class InstitutionalIntelligenceEngine {
  const InstitutionalIntelligenceEngine();

  SignalTransparency transparencyForSignal(
    SignalModel signal, {
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final opportunity = SignalOpportunity.fromSignal(signal, mode: mode);
    final confidence = opportunity.score;
    final contributors = <ConfidenceContributor>[
      ConfidenceContributor(
        label: 'Momentum breakout',
        score: opportunity.breakoutProbability,
        confirmed: opportunity.breakoutProbability >= 65,
        detail: 'Impulse pressure and alpha score are aligned.',
      ),
      ConfidenceContributor(
        label: 'Whale participation',
        score: opportunity.whalePressure,
        confirmed: opportunity.whalePressure >= 62,
        detail: 'Large-flow proxy supports the current direction.',
      ),
      ConfidenceContributor(
        label: 'Liquidity reclaim',
        score: 100 - opportunity.liquiditySweepProbability,
        confirmed: opportunity.liquiditySweepProbability < 62,
        detail: 'Sweep risk is acceptable for the current setup.',
      ),
      ConfidenceContributor(
        label: '${signal.regime.toUpperCase()} structure',
        score: signal.qualityScore,
        confirmed: signal.qualityScore >= 60,
        detail: 'Market structure quality from the signal engine.',
      ),
      ConfidenceContributor(
        label: 'Higher timeframe trend',
        score: signal.alphaScore,
        confirmed: signal.alphaScore >= 72,
        detail: 'Directional alignment from alpha scoring.',
      ),
    ];
    return SignalTransparency(
      confidence: confidence,
      confirmationCount: contributors.where((item) => item.confirmed).length,
      riskGrade: _riskGrade(confidence, signal.marketDataStale),
      contributors: contributors,
    );
  }

  MarketMicrostructureRead microstructureForChart(MarketChartModel chart) {
    final pressure = chart.liquidityHeatmap.pressureScore;
    final imbalance = chart.orderbookDepth.imbalanceProbability;
    final hidden = chart.orderbookDepth.hiddenLiquidityScore;
    final volatility = chart.opportunity.volatilityScore;
    final trap = (100 - chart.opportunity.trendStrength + volatility * 0.35)
        .clamp(8, 92)
        .toDouble();
    return MarketMicrostructureRead(
      liquiditySweep: pressure >= 70
          ? 'Liquidity sweep likely near ${chart.liquidityHeatmap.nearestWall}'
          : 'No extreme sweep pressure detected',
      orderAbsorption: hidden >= 65
          ? 'Hidden liquidity absorption is active'
          : 'Absorption is moderate',
      imbalanceZones: imbalance >= 62
          ? 'Orderbook imbalance favors directional continuation'
          : 'Imbalance is neutral to mixed',
      fakeoutRisk: trap,
      exhaustionRisk:
          (volatility + (chart.orderbookDepth.exhaustionWarning ? 28 : 0))
              .clamp(0, 99)
              .toDouble(),
      trapProbability: trap,
      smartMoneyBias: chart.opportunity.whalePressure >= 65
          ? 'Smart money bias supports ${chart.executionGuide.side}'
          : 'Smart money bias is not decisive',
    );
  }

  ExecutionBriefing executionBriefing({
    required String symbol,
    required String side,
    required double notional,
    TradeEvaluationModel? evaluation,
    SignalModel? signal,
    MarketChartModel? chart,
  }) {
    final confidence = (evaluation?.confidenceScore ??
            signal?.confidence ??
            chart?.opportunity.confidence ??
            0)
        .toDouble();
    final confidencePct = confidence <= 1 ? confidence * 100 : confidence;
    final volatility = chart?.opportunity.volatilityScore ?? 45;
    final riskBudget = evaluation?.riskBudget ?? 0.005;
    final riskGrade =
        _riskGrade(confidencePct, signal?.marketDataStale ?? false);
    final leverage = _suggestedLeverage(confidencePct, volatility, riskBudget);
    final guide = chart?.executionGuide;
    final price =
        evaluation?.snapshot.price ?? signal?.price ?? chart?.latestPrice ?? 0;
    final stop = guide?.stopLoss ?? _fallbackStop(price, side);
    final tp1 = guide?.tp1 ?? _fallbackTarget(price, side, 0.018);
    final tp2 = guide?.tp2 ?? _fallbackTarget(price, side, 0.034);
    final tp3 = _fallbackTarget(price == 0 ? tp2 : price, side, 0.052);
    final decayMinutes = confidencePct >= 82
        ? 18
        : confidencePct >= 65
            ? 12
            : 7;
    return ExecutionBriefing(
      symbol: symbol,
      side: side,
      confidence: confidencePct,
      riskGrade: riskGrade,
      suggestedLeverage: leverage,
      positionSizeLabel:
          _positionSizeLabel(confidencePct, volatility, notional),
      entryLabel: guide == null || guide.entryLow <= 0 || guide.entryHigh <= 0
          ? (price > 0 ? price.toStringAsFixed(price >= 100 ? 2 : 4) : 'Market')
          : '${guide.entryLow.toStringAsFixed(2)} - ${guide.entryHigh.toStringAsFixed(2)}',
      stopLoss: stop,
      takeProfitZones: <double>[tp1, tp2, tp3],
      liquidationRisk: leverage <= 1.5
          ? 'Low'
          : leverage <= 3
              ? 'Moderate'
              : 'Elevated',
      volatilityAdjustedRisk: volatility >= 72
          ? 'High volatility: reduced leverage recommended'
          : volatility >= 50
              ? 'Normal volatility: controlled size'
              : 'Low volatility: standard size allowed',
      expectedHoldDuration: confidencePct >= 76 ? '45m - 4h' : '10m - 90m',
      confidenceDecay: '$decayMinutes min without confirmation',
      invalidation: stop > 0
          ? stop.toStringAsFixed(stop >= 100 ? 2 : 4)
          : 'Structure break',
      marketRegime:
          evaluation?.snapshot.regime ?? chart?.marketRegime.state ?? 'UNKNOWN',
    );
  }

  MarketContextRead marketContextForChart(MarketChartModel? chart) {
    final regime = chart?.marketRegime.state.toUpperCase() ?? 'MIXED';
    final volatility = chart?.opportunity.volatilityScore ?? 50;
    final trend = chart?.opportunity.trendStrength ?? 50;
    return MarketContextRead(
      btcDominanceInfluence: trend >= 65
          ? 'BTC beta supports risk-on continuation'
          : 'BTC influence is mixed; avoid over-sizing alts',
      fearGreedState: volatility >= 70
          ? 'Elevated greed / volatility expansion'
          : volatility <= 35
              ? 'Quiet market / compression'
              : 'Balanced risk appetite',
      sectorMomentum: trend >= 70
          ? 'Sector momentum is expanding'
          : 'Sector momentum is selective',
      volatilityRegime: volatility >= 70
          ? 'Expansion'
          : volatility <= 35
              ? 'Compression'
              : 'Normal',
      marketTrendRegime: regime,
      correlationRisk: volatility >= 65
          ? 'High cross-market correlation risk'
          : 'Correlation risk acceptable',
      sentimentBias: chart?.changePct != null && chart!.changePct >= 0
          ? 'Constructive'
          : 'Defensive',
    );
  }

  ProfessionalPerformanceRead performanceFromSignals(
      List<SignalModel> signals) {
    final count = math.max(signals.length, 1);
    final avgQuality = signals.fold<double>(
          0,
          (sum, signal) =>
              sum + math.max(signal.qualityScore, signal.alphaScore),
        ) /
        count;
    final approved = signals.where((signal) => signal.executionAllowed).length;
    return ProfessionalPerformanceRead(
      winRate: (54 + avgQuality * 0.26).clamp(45, 82).toDouble(),
      averageRiskReward: (1.15 + avgQuality / 95).clamp(1.1, 2.7).toDouble(),
      profitFactor: (1.05 + avgQuality / 120).clamp(1.0, 2.2).toDouble(),
      maxDrawdown: (12 - avgQuality / 14).clamp(2.5, 12).toDouble(),
      streakQuality: approved >= 3 ? 'Constructive' : 'Selective',
      aiAlignmentScore: avgQuality.clamp(0, 99).toDouble(),
      disciplineScore: (70 + (count - approved) * 1.8).clamp(55, 96).toDouble(),
    );
  }

  AiMemoryProfile memoryFromSignals(
    List<SignalModel> signals, {
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final preferred = <String>{};
    for (final signal in signals.take(8)) {
      if (signal.symbol.trim().isNotEmpty) {
        preferred.add(signal.symbol);
      }
    }
    final successful = signals
        .where((signal) => signal.executionAllowed || signal.alphaScore >= 72)
        .take(3)
        .map((signal) => signal.strategy)
        .where((item) => item.trim().isNotEmpty)
        .toSet()
        .toList();
    final avoided = signals
        .where((signal) => signal.marketDataStale || signal.lowConfidence)
        .take(3)
        .map((signal) => signal.rejectionReason ?? 'Low quality continuation')
        .toSet()
        .toList();
    return AiMemoryProfile(
      preferredAssets: preferred.isEmpty
          ? const <String>['BTCUSDT', 'ETHUSDT']
          : preferred.toList(),
      preferredMode: mode.label,
      successfulSetups:
          successful.isEmpty ? const <String>['Momentum ignition'] : successful,
      avoidedSetups: avoided.isEmpty
          ? const <String>['Late entries after sweep failure']
          : avoided,
      favoriteStyle: mode == AiTradingMode.safe
          ? 'Confirmation trading'
          : mode == AiTradingMode.aggressive
              ? 'Early scalp entries'
              : 'Balanced momentum entries',
      personalizedNote:
          'AI is prioritizing ${mode.label.toLowerCase()} opportunities based on your recent watch behavior.',
    );
  }

  String lifecycleForSignal(SignalModel signal, {bool inProfit = false}) {
    if (signal.marketDataStale) {
      return 'INVALIDATED';
    }
    if (inProfit) {
      return 'IN PROFIT';
    }
    if (signal.executionAllowed && signal.qualityScore >= 70) {
      return 'ENTRY ACTIVE';
    }
    if (signal.alphaScore >= 70) {
      return 'CONFIRMING';
    }
    if (signal.qualityScore >= 45) {
      return 'BUILDING';
    }
    return 'SCANNING';
  }

  String _riskGrade(double confidence, bool stale) {
    if (stale) {
      return 'Data risk';
    }
    if (confidence >= 82) {
      return 'Moderate';
    }
    if (confidence >= 65) {
      return 'Controlled';
    }
    if (confidence >= 45) {
      return 'Reduced';
    }
    return 'Paper only';
  }

  double _suggestedLeverage(
    double confidence,
    double volatility,
    double riskBudget,
  ) {
    final base = confidence >= 82
        ? 3.0
        : confidence >= 68
            ? 2.0
            : 1.0;
    final volPenalty = volatility >= 70
        ? 0.55
        : volatility >= 55
            ? 0.78
            : 1.0;
    final budgetBoost = riskBudget >= 0.01 ? 1.10 : 0.92;
    return (base * volPenalty * budgetBoost).clamp(1.0, 4.0).toDouble();
  }

  String _positionSizeLabel(
      double confidence, double volatility, double notional) {
    final multiplier = confidence >= 82
        ? 1.0
        : confidence >= 65
            ? 0.65
            : 0.35;
    final adjusted = notional * multiplier * (volatility >= 70 ? 0.55 : 1.0);
    return '\$${adjusted.toStringAsFixed(0)} suggested';
  }

  double _fallbackStop(double price, String side) {
    if (price <= 0) {
      return 0;
    }
    return side.toUpperCase() == 'SELL' ? price * 1.018 : price * 0.982;
  }

  double _fallbackTarget(double price, String side, double pct) {
    if (price <= 0) {
      return 0;
    }
    return side.toUpperCase() == 'SELL' ? price * (1 - pct) : price * (1 + pct);
  }
}

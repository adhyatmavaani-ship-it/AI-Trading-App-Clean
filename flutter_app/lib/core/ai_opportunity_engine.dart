import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../models/signal.dart';
import 'trading_palette.dart';

enum AiTradingMode {
  safe,
  balanced,
  aggressive,
}

enum OpportunityTier {
  noTrade,
  scalpWatch,
  balancedEntry,
  strongSignal,
  highConviction,
}

AiTradingMode aiTradingModeFromRiskLevel(String riskLevel) {
  final normalized = riskLevel.trim().toLowerCase();
  if (normalized == 'low' ||
      normalized == 'safe' ||
      normalized == 'conservative') {
    return AiTradingMode.safe;
  }
  if (normalized == 'high' || normalized == 'aggressive') {
    return AiTradingMode.aggressive;
  }
  return AiTradingMode.balanced;
}

extension AiTradingModeLabels on AiTradingMode {
  String get label {
    switch (this) {
      case AiTradingMode.safe:
        return 'Safe AI';
      case AiTradingMode.balanced:
        return 'Smart AI';
      case AiTradingMode.aggressive:
        return 'Aggressive AI';
    }
  }

  String get riskProfile {
    switch (this) {
      case AiTradingMode.safe:
        return 'Strict confirmation';
      case AiTradingMode.balanced:
        return 'Controlled entries';
      case AiTradingMode.aggressive:
        return 'Early scalp hunting';
    }
  }

  double get activityBoost {
    switch (this) {
      case AiTradingMode.safe:
        return -6;
      case AiTradingMode.balanced:
        return 0;
      case AiTradingMode.aggressive:
        return 10;
    }
  }

  double get suggestedRiskMultiplier {
    switch (this) {
      case AiTradingMode.safe:
        return 0.45;
      case AiTradingMode.balanced:
        return 0.70;
      case AiTradingMode.aggressive:
        return 1.00;
    }
  }
}

class SignalOpportunity {
  const SignalOpportunity({
    required this.signal,
    required this.mode,
    required this.score,
    required this.tier,
    required this.accent,
    required this.expectedMovePct,
    required this.breakoutProbability,
    required this.liquiditySweepProbability,
    required this.whalePressure,
    required this.primaryLabel,
    required this.secondaryLabel,
    required this.heroTitle,
    required this.riskLabel,
    required this.tradePlanLabel,
    required this.insights,
    required this.canAttemptExecution,
    required this.progressionStage,
    required this.stageProgress,
  });

  final SignalModel signal;
  final AiTradingMode mode;
  final double score;
  final OpportunityTier tier;
  final Color accent;
  final double expectedMovePct;
  final double breakoutProbability;
  final double liquiditySweepProbability;
  final double whalePressure;
  final String primaryLabel;
  final String secondaryLabel;
  final String heroTitle;
  final String riskLabel;
  final String tradePlanLabel;
  final List<String> insights;
  final bool canAttemptExecution;
  final String progressionStage;
  final double stageProgress;

  static const List<String> progressionStages = <String>[
    'Scanning',
    'Building structure',
    'Momentum detected',
    'Liquidity sweep',
    'Entry near',
    'Breakout ready',
  ];

  bool get bullish => signal.action.toUpperCase() != 'SELL';

  String get sideLabel => bullish ? 'BUY' : 'SELL';

  String get confidenceLabel => '${score.toStringAsFixed(0)}%';

  String get expectedMoveLabel =>
      '${bullish ? '+' : '-'}${expectedMovePct.toStringAsFixed(1)}%';

  String get statusLabel {
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'AI TRACKING';
      case OpportunityTier.scalpWatch:
        return 'SCALP WATCH';
      case OpportunityTier.balancedEntry:
        return 'BALANCED ENTRY';
      case OpportunityTier.strongSignal:
        return 'STRONG SIGNAL';
      case OpportunityTier.highConviction:
        return 'HIGH CONVICTION';
    }
  }

  String get userFacingState {
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'AI scanning for cleaner entry';
      case OpportunityTier.scalpWatch:
        return 'Micro setup forming';
      case OpportunityTier.balancedEntry:
        return 'Entry window active';
      case OpportunityTier.strongSignal:
        return 'Momentum confirmation active';
      case OpportunityTier.highConviction:
        return 'High conviction trade plan';
    }
  }

  static SignalOpportunity fromSignal(
    SignalModel signal, {
    AiTradingMode mode = AiTradingMode.balanced,
  }) {
    final confidencePct =
        signal.confidence <= 1 ? signal.confidence * 100 : signal.confidence;
    final baseScore = math.max(
      confidencePct,
      math.max(signal.qualityScore, signal.alphaScore),
    );
    final stalePenalty = signal.marketDataStale ? 12.0 : 0.0;
    final degradedPenalty = signal.isDegraded ? 8.0 : 0.0;
    final lowConfidencePenalty = signal.lowConfidence ? 4.0 : 0.0;
    final score = (baseScore +
            mode.activityBoost -
            stalePenalty -
            degradedPenalty -
            lowConfidencePenalty)
        .clamp(0.0, 99.0);
    final tier = _tierForScore(score);
    final bullish = signal.action.toUpperCase() != 'SELL';
    final accent = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final expectedMove = _expectedMove(score, signal.alphaScore, mode);
    final breakout = (score + signal.alphaScore * 0.25).clamp(0.0, 99.0);
    final liquiditySweep =
        (100 - score + signal.qualityScore * 0.35).clamp(12.0, 88.0);
    final whalePressure =
        (signal.alphaScore * 0.55 + confidencePct * 0.30).clamp(5.0, 96.0);
    final canAttemptExecution = signal.executionAllowed &&
        !signal.marketDataStale &&
        (tier == OpportunityTier.balancedEntry ||
            tier == OpportunityTier.strongSignal ||
            tier == OpportunityTier.highConviction);

    return SignalOpportunity(
      signal: signal,
      mode: mode,
      score: score,
      tier: tier,
      accent: accent,
      expectedMovePct: expectedMove,
      breakoutProbability: breakout,
      liquiditySweepProbability: liquiditySweep,
      whalePressure: whalePressure,
      primaryLabel: canAttemptExecution ? 'Trade Now' : _primaryForTier(tier),
      secondaryLabel:
          canAttemptExecution ? 'Auto Trade' : _secondaryForTier(tier),
      heroTitle: _heroTitle(signal, tier),
      riskLabel: _riskLabel(tier, signal, mode),
      tradePlanLabel: _tradePlanLabel(tier, mode),
      insights: _buildInsights(signal, tier, breakout, liquiditySweep),
      canAttemptExecution: canAttemptExecution,
      progressionStage: _stageForScore(score),
      stageProgress: (score / 100).clamp(0.05, 1.0),
    );
  }

  static OpportunityTier _tierForScore(double score) {
    if (score >= 85) {
      return OpportunityTier.highConviction;
    }
    if (score >= 70) {
      return OpportunityTier.strongSignal;
    }
    if (score >= 55) {
      return OpportunityTier.balancedEntry;
    }
    if (score >= 40) {
      return OpportunityTier.scalpWatch;
    }
    return OpportunityTier.noTrade;
  }

  static double _expectedMove(
    double score,
    double alphaScore,
    AiTradingMode mode,
  ) {
    final activity = mode == AiTradingMode.aggressive
        ? 0.8
        : mode == AiTradingMode.safe
            ? -0.35
            : 0.25;
    return (1.0 + score / 24 + alphaScore / 90 + activity).clamp(0.8, 8.8);
  }

  static String _primaryForTier(OpportunityTier tier) {
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'Track Setup';
      case OpportunityTier.scalpWatch:
        return 'Open Scalp Plan';
      case OpportunityTier.balancedEntry:
        return 'Open Trade Plan';
      case OpportunityTier.strongSignal:
      case OpportunityTier.highConviction:
        return 'Trade Now';
    }
  }

  static String _secondaryForTier(OpportunityTier tier) {
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'Paper Watch';
      case OpportunityTier.scalpWatch:
        return 'Shadow Trade';
      case OpportunityTier.balancedEntry:
        return 'Semi Auto';
      case OpportunityTier.strongSignal:
      case OpportunityTier.highConviction:
        return 'Auto Trade';
    }
  }

  static String _heroTitle(SignalModel signal, OpportunityTier tier) {
    final side = signal.action.toUpperCase() == 'SELL' ? 'SELL' : 'BUY';
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'AI PREPARING ENTRY - ${signal.symbol}';
      case OpportunityTier.scalpWatch:
        return 'AI SCALP WATCH - ${signal.symbol}';
      case OpportunityTier.balancedEntry:
        return 'AI $side SETUP - ${signal.symbol}';
      case OpportunityTier.strongSignal:
        return 'AI $side ALERT - ${signal.symbol}';
      case OpportunityTier.highConviction:
        return 'HIGH CONVICTION $side - ${signal.symbol}';
    }
  }

  static String _riskLabel(
    OpportunityTier tier,
    SignalModel signal,
    AiTradingMode mode,
  ) {
    if (signal.marketDataStale) {
      return 'Fresh data required';
    }
    if (tier == OpportunityTier.highConviction) {
      return mode == AiTradingMode.safe ? 'Medium' : 'Controlled high';
    }
    if (tier == OpportunityTier.strongSignal) {
      return 'Medium';
    }
    if (tier == OpportunityTier.balancedEntry) {
      return 'Reduced size';
    }
    return 'Paper / micro only';
  }

  static String _tradePlanLabel(OpportunityTier tier, AiTradingMode mode) {
    switch (tier) {
      case OpportunityTier.noTrade:
        return 'No capital at risk. AI is tracking the next trigger.';
      case OpportunityTier.scalpWatch:
        return mode == AiTradingMode.aggressive
            ? 'Early scalp plan. Use micro size until confirmation improves.'
            : 'Shadow trade first. Wait for stronger confirmation before capital.';
      case OpportunityTier.balancedEntry:
        return 'Controlled risk entry. Backend still performs final risk validation.';
      case OpportunityTier.strongSignal:
        return 'Trade-ready plan with backend safety confirmation.';
      case OpportunityTier.highConviction:
        return 'Best current opportunity. Use risk-managed sizing only.';
    }
  }

  static String _stageForScore(double score) {
    if (score >= 85) {
      return 'Breakout ready';
    }
    if (score >= 70) {
      return 'Entry near';
    }
    if (score >= 55) {
      return 'Liquidity sweep';
    }
    if (score >= 40) {
      return 'Momentum detected';
    }
    if (score >= 24) {
      return 'Building structure';
    }
    return 'Scanning';
  }

  static List<String> _buildInsights(
    SignalModel signal,
    OpportunityTier tier,
    double breakout,
    double liquiditySweep,
  ) {
    final insights = <String>[
      'Breakout probability ${breakout.toStringAsFixed(0)}%',
      'Liquidity sweep risk ${liquiditySweep.toStringAsFixed(0)}%',
    ];
    if (signal.regime.trim().isNotEmpty) {
      insights.add('${signal.regime.toUpperCase()} regime active');
    }
    if (signal.qualityReasons.isNotEmpty) {
      insights.add(signal.qualityReasons.first);
    } else if (signal.reasons.isNotEmpty) {
      insights.add(signal.reasons.first);
    }
    if (tier == OpportunityTier.scalpWatch) {
      insights.add('AI is building a scalp watchlist entry');
    }
    if (signal.marketDataStale) {
      insights.add('Waiting for fresh market feed before execution');
    }
    return insights.take(4).toList(growable: false);
  }
}

import 'package:ai_trading_app/core/ai_opportunity_engine.dart';
import 'package:ai_trading_app/core/edge_validation_engine.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('edge validation produces outcome, drift, correction, and replay reads',
      () {
    const engine = EdgeValidationEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.84,
        alphaScore: 84,
        qualityScore: 82,
        executionAllowed: true,
      ),
      _signal(
        symbol: 'ETHUSDT',
        confidence: 0.62,
        alphaScore: 62,
        qualityScore: 58,
        lowConfidence: true,
      ),
    ];

    final outcomes = engine.signalOutcomes(
      signals,
      mode: AiTradingMode.balanced,
    );
    final edge = engine.edgeValidation(outcomes);
    final drift = engine.modelDrift(outcomes);
    final correction = engine.selfCorrection(outcomes);
    final leaderboard = engine.strategyLeaderboard(outcomes);
    final replay = engine.replayMetadata(outcomes);
    final quant = engine.quantPerformance(outcomes);

    expect(outcomes, hasLength(2));
    expect(edge.setupExpectancy, isNotEmpty);
    expect(edge.executionQualityImpact, greaterThanOrEqualTo(0));
    expect(drift.aiStabilityScore, inInclusiveRange(0, 99));
    expect(correction.leverageMultiplier, greaterThan(0));
    expect(leaderboard.bestAssets, isNotEmpty);
    expect(replay.ready, isTrue);
    expect(quant.confidenceCalibrationCurve, hasLength(4));
  });
}

SignalModel _signal({
  required String symbol,
  required double confidence,
  required double alphaScore,
  required double qualityScore,
  bool executionAllowed = false,
  bool lowConfidence = false,
}) {
  return SignalModel(
    signalId: 'sig-$symbol',
    symbol: symbol,
    action: 'BUY',
    strategy: 'AI_MOMENTUM',
    confidence: confidence,
    alphaScore: alphaScore,
    regime: 'TRENDING',
    price: 100,
    signalVersion: 1,
    publishedAt: DateTime.utc(2026, 5, 14),
    decisionReason: 'Momentum confirmed; Liquidity reclaimed',
    degradedMode: false,
    requiredTier: 'pro',
    minBalance: 0,
    rejectionReason: null,
    lowConfidence: lowConfidence,
    quality: executionAllowed ? 'approved' : 'watchlist',
    qualityScore: qualityScore,
    qualityReasons: const <String>['breakout structure'],
    executionAllowed: executionAllowed,
    marketDataStale: false,
    marketDataSources: const <String, String>{'price': 'test'},
  );
}

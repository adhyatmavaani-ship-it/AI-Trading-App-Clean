import 'package:ai_trading_app/core/adaptive_decision_core.dart';
import 'package:ai_trading_app/core/ai_opportunity_engine.dart';
import 'package:ai_trading_app/core/edge_validation_engine.dart';
import 'package:ai_trading_app/core/proprietary_ai_engine.dart';
import 'package:ai_trading_app/models/market_summary.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('adaptive decision core builds probabilistic ensemble decision reads',
      () {
    const decisionCore = AdaptiveDecisionCore();
    const edgeEngine = EdgeValidationEngine();
    const proprietaryEngine = ProprietaryAiEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'INJUSDT',
        confidence: 0.82,
        alphaScore: 84,
        qualityScore: 80,
        reasons: const <String>[
          'Momentum strength improving',
          'Liquidity reclaim confirmed',
          'Bullish structure holding',
        ],
      ),
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.56,
        alphaScore: 55,
        qualityScore: 52,
        action: 'SELL',
        lowConfidence: true,
        reasons: const <String>['BTC weakness affecting alts'],
      ),
      _signal(
        symbol: 'SOLUSDT',
        confidence: 0.70,
        alphaScore: 72,
        qualityScore: 69,
        reasons: const <String>['Volatility expansion building'],
      ),
    ];
    const market = MarketSummaryModel(
      sentimentScore: 64,
      sentimentLabel: 'Selective risk-on',
      marketBreadth: 61,
      avgChangePct: 1.6,
      avgVolatilityPct: 4.8,
      participationScore: 67,
      confidenceScore: 70,
      ticker: <MarketTickerItemModel>[
        MarketTickerItemModel(
          symbol: 'BTCUSDT',
          price: 100,
          changePct: -0.4,
        ),
      ],
      heatmap: <MarketHeatmapItemModel>[
        MarketHeatmapItemModel(
          symbol: 'INJUSDT',
          changePct: 4.4,
          intensity: 81,
        ),
      ],
      scanner: MarketScannerModel(
        activeSymbols: <String>['BTCUSDT', 'INJUSDT', 'SOLUSDT'],
        fixedSymbols: <String>['BTCUSDT'],
        rotatingSymbols: <String>['INJUSDT', 'SOLUSDT'],
        candidates: <ScannerCandidateModel>[],
        rotationStartedAt: null,
        nextRotationAt: null,
        secondsUntilRotation: 30,
      ),
      confidenceHistory: [],
    );
    final outcomes = edgeEngine.signalOutcomes(
      signals,
      mode: AiTradingMode.balanced,
    );
    final drift = edgeEngine.modelDrift(outcomes);
    final dna = proprietaryEngine.marketDna(
      signal: signals.first,
      market: market,
    );
    final pressure = proprietaryEngine.predictivePressure(
      signal: signals.first,
      market: market,
    );
    final signature = proprietaryEngine.edgeSignature(signals.first);
    final edgeConfidence = proprietaryEngine.edgeConfidence(
      dna: dna,
      signature: signature,
      outcomes: outcomes,
      drift: drift,
    );
    final regime = proprietaryEngine.regimeMap(market: market);

    final read = decisionCore.evaluate(
      signal: signals.first,
      signals: signals,
      outcomes: outcomes,
      market: market,
      dna: dna,
      pressure: pressure,
      edgeConfidence: edgeConfidence,
      regime: regime,
      drift: drift,
    );

    expect(read.consensus.contributors, hasLength(8));
    expect(read.consensus.bullishProbability, inInclusiveRange(1, 98));
    expect(read.consensus.bearishProbability, inInclusiveRange(1, 98));
    expect(read.consensus.chopProbability, inInclusiveRange(2, 92));
    expect(read.consensus.adaptiveSignalQuality, inInclusiveRange(0, 99));
    expect(read.weights.weights.values.fold<double>(0, (a, b) => a + b),
        closeTo(1, 0.0001));
    expect(read.calibration.confidenceStabilityIndex, inInclusiveRange(0, 99));
    expect(read.scenarios.preferredScenario, isNotEmpty);
    expect(read.timeline.points, hasLength(4));
    expect(read.reasoning.reasoning, contains('contributor'));
    expect(read.stability.smoothedConfidence, inInclusiveRange(0, 99));
    expect(read.research.contributorBenchmarks, hasLength(8));
  });
}

SignalModel _signal({
  required String symbol,
  required double confidence,
  required double alphaScore,
  required double qualityScore,
  String action = 'BUY',
  bool lowConfidence = false,
  List<String> reasons = const <String>['Momentum confirmed'],
}) {
  return SignalModel(
    signalId: 'sig-$symbol',
    symbol: symbol,
    action: action,
    strategy: 'AI_ADAPTIVE_DECISION',
    confidence: confidence,
    alphaScore: alphaScore,
    regime: 'TRENDING',
    price: 100,
    signalVersion: 1,
    publishedAt: DateTime.utc(2026, 5, 14),
    decisionReason: reasons.join('; '),
    degradedMode: false,
    requiredTier: 'pro',
    minBalance: 0,
    rejectionReason: lowConfidence ? 'watch mode only' : null,
    lowConfidence: lowConfidence,
    quality: lowConfidence ? 'watchlist' : 'approved',
    qualityScore: qualityScore,
    qualityReasons: reasons,
    executionAllowed: !lowConfidence,
    marketDataStale: false,
    marketDataSources: const <String, String>{'price': 'test'},
  );
}

import 'package:ai_trading_app/core/adaptive_decision_core.dart';
import 'package:ai_trading_app/core/ai_opportunity_engine.dart';
import 'package:ai_trading_app/core/edge_validation_engine.dart';
import 'package:ai_trading_app/core/evolving_ai_intelligence_engine.dart';
import 'package:ai_trading_app/core/proprietary_ai_engine.dart';
import 'package:ai_trading_app/models/market_summary.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('evolving AI intelligence produces strategic evolution reads', () {
    const edgeEngine = EdgeValidationEngine();
    const proprietaryEngine = ProprietaryAiEngine();
    const decisionCore = AdaptiveDecisionCore();
    const evolvingEngine = EvolvingAiIntelligenceEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'INJUSDT',
        confidence: 0.84,
        alphaScore: 86,
        qualityScore: 82,
        reasons: const <String>[
          'Momentum strength improving',
          'Liquidity reclaim confirmed',
          'Bullish structure holding',
        ],
      ),
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.55,
        alphaScore: 54,
        qualityScore: 50,
        action: 'SELL',
        lowConfidence: true,
        reasons: const <String>['BTC weakness affecting alts'],
      ),
      _signal(
        symbol: 'SOLUSDT',
        confidence: 0.73,
        alphaScore: 74,
        qualityScore: 70,
        reasons: const <String>['Breakout continuation'],
      ),
    ];
    const market = MarketSummaryModel(
      sentimentScore: 63,
      sentimentLabel: 'Selective risk-on',
      marketBreadth: 59,
      avgChangePct: 1.4,
      avgVolatilityPct: 4.9,
      participationScore: 65,
      confidenceScore: 71,
      ticker: <MarketTickerItemModel>[
        MarketTickerItemModel(
          symbol: 'BTCUSDT',
          price: 100,
          changePct: -0.5,
        ),
      ],
      heatmap: <MarketHeatmapItemModel>[
        MarketHeatmapItemModel(
          symbol: 'INJUSDT',
          changePct: 4.8,
          intensity: 82,
        ),
      ],
      scanner: MarketScannerModel(
        activeSymbols: <String>['BTCUSDT', 'INJUSDT', 'SOLUSDT'],
        fixedSymbols: <String>['BTCUSDT'],
        rotatingSymbols: <String>['INJUSDT', 'SOLUSDT'],
        candidates: <ScannerCandidateModel>[],
        rotationStartedAt: null,
        nextRotationAt: null,
        secondsUntilRotation: 45,
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
    final decision = decisionCore.evaluate(
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

    final read = evolvingEngine.evaluate(
      decision: decision,
      signals: signals,
      outcomes: outcomes,
      market: market,
      regime: regime,
    );

    expect(read.contributorEvolution.scores, hasLength(8));
    expect(read.contributorEvolution.strongestContributor, isNotEmpty);
    expect(read.edgeMemory.multiWeekSetupQuality, inInclusiveRange(0, 99));
    expect(read.edgeMemory.recurringFailurePatterns, isNotEmpty);
    expect(read.metaIntelligence.metaStabilityScore, inInclusiveRange(0, 99));
    expect(read.strategyEvolution.scenarioWeighting, contains('breakout'));
    expect(read.reasoningMemory.reasoningReliabilityIndex,
        inInclusiveRange(0, 99));
    expect(read.selfOptimization.fusionCalibration, inInclusiveRange(0, 99));
    expect(read.regimeEvolution.regimePath, isNotEmpty);
    expect(read.mlFoundation.trainingFeatures, contains('contributor_weight'));
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
    strategy: 'AI_EVOLUTION',
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

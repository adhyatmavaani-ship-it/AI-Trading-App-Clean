import 'package:ai_trading_app/core/adaptive_decision_core.dart';
import 'package:ai_trading_app/core/ai_opportunity_engine.dart';
import 'package:ai_trading_app/core/edge_validation_engine.dart';
import 'package:ai_trading_app/core/enterprise_ai_governance_engine.dart';
import 'package:ai_trading_app/core/evolving_ai_intelligence_engine.dart';
import 'package:ai_trading_app/core/proprietary_ai_engine.dart';
import 'package:ai_trading_app/models/market_summary.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('enterprise AI governance produces auditable deterministic reads', () {
    const edgeEngine = EdgeValidationEngine();
    const proprietaryEngine = ProprietaryAiEngine();
    const decisionCore = AdaptiveDecisionCore();
    const evolvingEngine = EvolvingAiIntelligenceEngine();
    const governanceEngine = EnterpriseAiGovernanceEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'INJUSDT',
        confidence: 0.83,
        alphaScore: 85,
        qualityScore: 81,
        reasons: const <String>[
          'Liquidity reclaim confirmed',
          'Momentum strength improving',
          'Bullish structure holding',
        ],
      ),
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.57,
        alphaScore: 56,
        qualityScore: 52,
        action: 'SELL',
        lowConfidence: true,
        reasons: const <String>['BTC weakness affecting alts'],
      ),
      _signal(
        symbol: 'SOLUSDT',
        confidence: 0.71,
        alphaScore: 73,
        qualityScore: 68,
        reasons: const <String>['Volatility expansion building'],
      ),
    ];
    const market = MarketSummaryModel(
      sentimentScore: 62,
      sentimentLabel: 'Selective risk-on',
      marketBreadth: 58,
      avgChangePct: 1.3,
      avgVolatilityPct: 4.7,
      participationScore: 64,
      confidenceScore: 70,
      ticker: <MarketTickerItemModel>[
        MarketTickerItemModel(
          symbol: 'BTCUSDT',
          price: 100,
          changePct: -0.3,
        ),
      ],
      heatmap: <MarketHeatmapItemModel>[
        MarketHeatmapItemModel(
          symbol: 'INJUSDT',
          changePct: 4.1,
          intensity: 79,
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
    final evolving = evolvingEngine.evaluate(
      decision: decision,
      signals: signals,
      outcomes: outcomes,
      market: market,
      regime: regime,
    );

    final read = governanceEngine.evaluate(
      signal: signals.first,
      decision: decision,
      evolving: evolving,
      outcomes: outcomes,
      market: market,
      regime: regime,
    );
    final repeated = governanceEngine.evaluate(
      signal: signals.first,
      decision: decision,
      evolving: evolving,
      outcomes: outcomes,
      market: market,
      regime: regime,
    );

    expect(read.timeline.entries, isNotEmpty);
    expect(read.snapshot.stateHash, repeated.snapshot.stateHash);
    expect(read.snapshot.toAuditMap(), contains('reasoning_chain'));
    expect(read.snapshot.contributorStates, hasLength(8));
    expect(read.replay.replayHash, repeated.replay.replayHash);
    expect(read.replay.replayConsistency, inInclusiveRange(0, 99));
    expect(read.incident.incidentScore, inInclusiveRange(0, 99));
    expect(read.rollout.featureFlags['autonomous_execution'], isFalse);
    expect(read.explainability.persistableFields, contains('state_hash'));
    expect(read.compliance.advisoryOnlyBoundary, isTrue);
    expect(read.compliance.executionAuthoritySeparated, isTrue);
    expect(read.operationalHealth.healthIndex, inInclusiveRange(0, 99));
    expect(read.research.productionIsolation, isTrue);
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
    strategy: 'AI_GOVERNANCE',
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

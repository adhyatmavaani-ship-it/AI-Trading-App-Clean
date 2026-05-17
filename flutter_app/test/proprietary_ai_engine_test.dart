import 'package:ai_trading_app/core/ai_opportunity_engine.dart';
import 'package:ai_trading_app/core/edge_validation_engine.dart';
import 'package:ai_trading_app/core/proprietary_ai_engine.dart';
import 'package:ai_trading_app/models/market_summary.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('proprietary AI engine builds market DNA and edge intelligence', () {
    const engine = ProprietaryAiEngine();
    const edgeEngine = EdgeValidationEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'SOLUSDT',
        confidence: 0.84,
        alphaScore: 86,
        qualityScore: 82,
        reasons: const <String>[
          'Liquidity reclaim confirmed',
          'Whale accumulation rising',
          'Breakout compression',
        ],
      ),
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.58,
        alphaScore: 58,
        qualityScore: 54,
        action: 'SELL',
        lowConfidence: true,
        reasons: const <String>['BTC weakness affecting alts'],
      ),
      _signal(
        symbol: 'DOGEUSDT',
        confidence: 0.67,
        alphaScore: 70,
        qualityScore: 63,
        reasons: const <String>['Meme volatility rotation'],
      ),
    ];
    final outcomes = edgeEngine.signalOutcomes(
      signals,
      mode: AiTradingMode.balanced,
    );
    final drift = edgeEngine.modelDrift(outcomes);
    const market = MarketSummaryModel(
      sentimentScore: 61,
      sentimentLabel: 'Risk-on selective',
      marketBreadth: 58,
      avgChangePct: 1.8,
      avgVolatilityPct: 5.4,
      participationScore: 64,
      confidenceScore: 72,
      scanner: MarketScannerModel(
        activeSymbols: <String>['BTCUSDT', 'SOLUSDT'],
        fixedSymbols: <String>['BTCUSDT'],
        rotatingSymbols: <String>['SOLUSDT'],
        candidates: <ScannerCandidateModel>[
          ScannerCandidateModel(
            symbol: 'SOLUSDT',
            price: 100,
            changePct: 4.2,
            quoteVolume: 1000000,
            volumeRatio: 2.4,
            volumeSpikePct: 26,
            volatilityPct: 5.4,
            potentialScore: 78,
            exchange: 'binance',
          ),
        ],
        rotationStartedAt: null,
        nextRotationAt: null,
        secondsUntilRotation: 40,
      ),
      ticker: <MarketTickerItemModel>[
        MarketTickerItemModel(
          symbol: 'BTCUSDT',
          price: 100,
          changePct: -0.6,
        ),
      ],
      heatmap: <MarketHeatmapItemModel>[
        MarketHeatmapItemModel(
          symbol: 'SOLUSDT',
          changePct: 4.2,
          intensity: 78,
        ),
      ],
      confidenceHistory: [],
    );

    final dna = engine.marketDna(signal: signals.first, market: market);
    final signature = engine.edgeSignature(signals.first);
    final pressure = engine.predictivePressure(
      signal: signals.first,
      market: market,
    );
    final memory = engine.behaviorMemory(signals: signals, market: market);
    final regime = engine.regimeMap(market: market);
    final narrative = engine.marketNarrative(
      dna: dna,
      signature: signature,
      pressure: pressure,
      regime: regime,
    );
    final edgeConfidence = engine.edgeConfidence(
      dna: dna,
      signature: signature,
      outcomes: outcomes,
      drift: drift,
    );
    final watchtower = engine.proprietaryWatchtower(
      pressure: pressure,
      dna: dna,
      drift: drift,
    );
    final research = engine.researchLayer(
      signals: signals,
      outcomes: outcomes,
    );

    expect(dna.symbol, 'SOLUSDT');
    expect(dna.compatibilityScore, inInclusiveRange(0, 99));
    expect(signature.family, isNotEmpty);
    expect(signature.components, isNotEmpty);
    expect(pressure.netPressure, inInclusiveRange(0, 99));
    expect(memory.recurringBehaviors, isNotEmpty);
    expect(regime.trendRegime, isNotEmpty);
    expect(narrative.narrative, contains('SOLUSDT'));
    expect(edgeConfidence.edgeConfidenceScore, inInclusiveRange(0, 99));
    expect(watchtower.alerts, isNotEmpty);
    expect(research.setupFamilies, isNotEmpty);
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
    strategy: 'AI_PROPRIETARY_EDGE',
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

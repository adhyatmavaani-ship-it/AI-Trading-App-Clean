import 'package:ai_trading_app/core/platformization_engine.dart';
import 'package:ai_trading_app/core/retention_engine.dart';
import 'package:ai_trading_app/models/signal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('platformization engine produces deployable platform reads', () {
    const engine = PlatformizationEngine();
    final signals = <SignalModel>[
      _signal(
        symbol: 'BTCUSDT',
        confidence: 0.82,
        alphaScore: 84,
        qualityScore: 80,
      ),
      _signal(
        symbol: 'SOLUSDT',
        confidence: 0.54,
        alphaScore: 58,
        qualityScore: 52,
        quality: 'watchlist',
        executionAllowed: false,
      ),
    ];

    final read = engine.evaluate(
      tier: PlanTier.free,
      mode: PlatformExperienceMode.simple,
      channel: ReleaseChannel.beta,
      signals: signals,
    );

    expect(
      read.exchangeConnectivity.adapters.map((item) => item.exchange),
      containsAll(<String>['Binance', 'Bybit', 'Hyperliquid', 'OKX']),
    );
    expect(read.exchangeConnectivity.healthiestExchange, isNotEmpty);
    expect(read.exchangeConnectivity.executionConstraints.first,
        contains('backend approval'));
    expect(read.cloudDeployment.deploymentScore, inInclusiveRange(0, 99));
    expect(read.entitlements.tier, PlanTier.free);
    expect(read.entitlements.lockedFeatures, isNotEmpty);
    expect(read.entitlements.aiModes, contains('Safe AI'));
    expect(read.experienceMode.mode, PlatformExperienceMode.simple);
    expect(read.experienceMode.hiddenSections, contains('Replay hashes'));
    expect(
        read.productionOps.featureFlags['autonomous_live_execution'], isFalse);
    expect(read.mobilePerformance.performanceScore, inInclusiveRange(0, 99));
    expect(read.offlineDegraded.cachedSignalsAvailable, isTrue);
    expect(read.offlineDegraded.degradedAiAdvisory, isTrue);
    expect(read.platformAnalytics.privacySafe, isTrue);
    expect(read.releaseChannel.channel, ReleaseChannel.beta);
    expect(read.releaseChannel.stagedRelease, isTrue);
    expect(
      read.releaseChannel.configurationSnapshot['risk_engine'],
      'required',
    );
  });
}

SignalModel _signal({
  required String symbol,
  required double confidence,
  required double alphaScore,
  required double qualityScore,
  String quality = 'approved',
  bool executionAllowed = true,
}) {
  return SignalModel(
    signalId: 'platform-$symbol',
    symbol: symbol,
    action: 'BUY',
    strategy: 'PLATFORMIZATION_TEST',
    confidence: confidence,
    alphaScore: alphaScore,
    regime: 'TRENDING',
    price: 100,
    signalVersion: 1,
    publishedAt: DateTime.utc(2026, 5, 14),
    decisionReason: 'Backend approval remains authoritative',
    degradedMode: false,
    requiredTier: 'free',
    minBalance: 0,
    rejectionReason: executionAllowed ? null : 'watch mode only',
    lowConfidence: !executionAllowed,
    quality: quality,
    qualityScore: qualityScore,
    qualityReasons: const <String>['Platform analytics event'],
    executionAllowed: executionAllowed,
    marketDataStale: false,
    marketDataSources: const <String, String>{'price': 'test'},
  );
}

import 'package:ai_trading_app/core/production_infrastructure_engine.dart';
import 'package:ai_trading_app/core/websocket_service.dart';
import 'package:ai_trading_app/models/activity.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('production infrastructure builds resilience and failsafe reads', () {
    const engine = ProductionInfrastructureEngine();
    final now = DateTime.now().toUtc().millisecondsSinceEpoch;
    final chart = MarketChartModel(
      symbol: 'BTCUSDT',
      interval: '1m',
      latestPrice: 100,
      changePct: 1.2,
      candles: <MarketCandleModel>[
        MarketCandleModel(
          timestampMs: now - 120000,
          open: 98,
          high: 101,
          low: 97,
          close: 100,
          volume: 1000,
        ),
        MarketCandleModel(
          timestampMs: now - 60000,
          open: 100,
          high: 102,
          low: 99,
          close: 101,
          volume: 1100,
        ),
        MarketCandleModel(
          timestampMs: now,
          open: 101,
          high: 103,
          low: 100,
          close: 102,
          volume: 1200,
        ),
      ],
      markers: const <TradeMarkerModel>[],
      confidenceIntervals: const <ConfidenceIntervalModel>[],
      confidenceHistory: const <ConfidenceHistoryPointModel>[],
    );

    final realtime = engine.realtimeResilience(
      websocketState: WsState.connected,
      lastEventAt: DateTime.now(),
    );
    final data = engine.marketDataIntegrity(chart: chart);
    final reconciliation = engine.executionReconciliation(
      requestedSide: 'BUY',
      requestedAmount: 100,
      submitting: false,
    );
    final failsafe = engine.failsafe(
      realtime: realtime,
      data: data,
      execution: reconciliation,
    );
    final recovery = engine.stateRecovery(
      aiMemoryAvailable: true,
      executionStateAvailable: true,
    );
    final telemetry = engine.telemetry(localSignalQueue: 4);
    final failure = engine.failureHandling(
      realtime: realtime,
      failsafe: failsafe,
    );

    expect(realtime.streamHealthScore, greaterThan(60));
    expect(data.reliabilityScore, greaterThan(60));
    expect(reconciliation.consistencyScore, inInclusiveRange(0, 99));
    expect(failsafe.failsafeScore, inInclusiveRange(0, 100));
    expect(recovery.recoveryPlan, isNotEmpty);
    expect(telemetry.healthScore, inInclusiveRange(0, 99));
    expect(failure.userMessage, isNotEmpty);
  });
}

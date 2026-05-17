import 'package:ai_trading_app/core/trading_palette.dart';
import 'package:ai_trading_app/models/activity.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:ai_trading_app/widgets/pro_trading_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('pro trading chart renders overlays and AI feed', (tester) async {
    final chart = MarketChartModel(
      symbol: 'BTCUSDT',
      interval: '5m',
      latestPrice: 100250,
      changePct: 1.8,
      candles: List<MarketCandleModel>.generate(
        36,
        (index) => MarketCandleModel(
          timestampMs: 1714212300000 + (index * 60000),
          open: 100000 + (index * 10),
          high: 100020 + (index * 10),
          low: 99990 + (index * 10),
          close: 100005 + (index * 10),
          volume: 1500 + (index * 40),
        ),
      ),
      markers: <TradeMarkerModel>[
        TradeMarkerModel(
          type: 'signal',
          markerType: 'BUY',
          markerStyle: 'outline',
          side: 'BUY',
          price: 100120,
          timestamp: DateTime.utc(2026, 1, 1, 0, 0),
          confidenceScore: 0.82,
          reason: 'Momentum ignition',
        ),
      ],
      confidenceIntervals: const <ConfidenceIntervalModel>[],
      confidenceHistory: const <ConfidenceHistoryPointModel>[],
      overlays: const <MarketOverlayModel>[
        MarketOverlayModel(
          zoneType: 'breakout_zone',
          label: 'Breakout Compression',
          startTs: 1714212300000,
          endTs: 1714215900000,
          low: 100010,
          high: 100180,
          confidence: 82,
          side: 'BUY',
          style: 'neutral',
        ),
      ],
      opportunity: const OpportunityScoreModel(
        confidence: 82,
        expectedRr: 2.1,
        momentumScore: 76,
        volatilityScore: 64,
        whalePressure: 71,
        trendStrength: 79,
        scalpScore: 81,
      ),
      marketRegime: const MarketRegimeSnapshotModel(
        state: 'TRENDING',
        confidence: 84,
        summary: 'Trend alignment is strong.',
      ),
      assistantModes: const <String>[
        'MANUAL',
        'ASSISTED',
        'SEMI_AUTO',
        'FULL_AUTO',
      ],
      activeAssistantMode: 'ASSISTED',
      executionGuide: const ChartExecutionGuideModel(
        side: 'BUY',
        entryLow: 100100,
        entryHigh: 100180,
        stopLoss: 99840,
        tp1: 100520,
        tp2: 100940,
        trailingStopPath: <ChartGuidePointModel>[
          ChartGuidePointModel(label: 'initial', price: 99840),
          ChartGuidePointModel(label: 'projected', price: 100020),
        ],
        riskReward: 2.1,
        riskPct: 0.41,
        rewardPct: 0.86,
      ),
      strategyState: const StrategyStateModel(),
      aiFeed: <AiFeedItemModel>[
        AiFeedItemModel(
          title: 'Momentum ignition detected on BTCUSDT',
          detail: 'Short-term impulse improved.',
          severity: 'high',
          timestamp: DateTime.utc(2026, 1, 1, 0, 0),
        ),
      ],
      trailingStop: const TrailingStopModel(
        mode: 'ATR_TRAIL',
        currentStop: 99980,
        projectedStop: 100040,
        path: <ChartGuidePointModel>[
          ChartGuidePointModel(label: 'initial', price: 99840),
          ChartGuidePointModel(label: 'atr', price: 99980),
        ],
      ),
      chartEngine: 'custom_canvas_pro',
      renderHints: const <String, dynamic>{'preferred_fps': 60},
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark().copyWith(
          scaffoldBackgroundColor: TradingPalette.midnight,
        ),
        home: Scaffold(
          body: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: SizedBox(
                height: 1200,
                child: ProTradingChart(
                  chart: chart,
                  onAssistantModeChanged: (_) {},
                ),
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('Execution Guide'), findsOneWidget);
    expect(find.text('Breakout Compression'), findsOneWidget);
    expect(
      find.text('Momentum ignition detected on BTCUSDT'),
      findsOneWidget,
    );
    expect(find.text('ASSISTED'), findsWidgets);
  });
}

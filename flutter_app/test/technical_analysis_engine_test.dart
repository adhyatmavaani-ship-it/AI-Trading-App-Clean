import 'package:ai_trading_app/core/technical_analysis_engine.dart';
import 'package:ai_trading_app/models/activity.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('technical analysis builds a risk-bounded report from candles', () {
    final candles = <MarketCandleModel>[];
    var price = 100.0;
    for (var i = 0; i < 80; i++) {
      final open = price;
      price += 0.35 + (i % 5) * 0.04;
      final close = price;
      candles.add(
        MarketCandleModel(
          timestampMs: i * 60000,
          open: open,
          high: close + 0.8,
          low: open - 0.6,
          close: close,
          volume: 1000 + i * 10,
        ),
      );
    }

    final report = const TechnicalAnalysisEngine().analyze(
      MarketChartModel(
        symbol: 'BTCUSDT',
        interval: '5m',
        latestPrice: candles.last.close,
        changePct: 2.4,
        candles: candles,
        markers: const <TradeMarkerModel>[],
        confidenceIntervals: const <ConfidenceIntervalModel>[],
        confidenceHistory: const <ConfidenceHistoryPointModel>[],
      ),
    );

    expect(report.symbol, 'BTCUSDT');
    expect(report.side, isNot('WAIT'));
    expect(report.confidence, greaterThan(0));
    expect(report.rsi14, greaterThan(0));
    expect(report.sma20, greaterThan(0));
    expect(report.sma50, greaterThan(0));
    expect(report.ema9, greaterThan(0));
    expect(report.ema21, greaterThan(0));
    expect(report.pivot, greaterThan(0));
    expect(report.atr14, greaterThan(0));
    expect(report.adx14, greaterThan(0));
    expect(report.volumeRatio, greaterThan(0));
    expect(report.scalpScore, greaterThan(0));
    expect(report.swingScore, greaterThan(0));
    expect(report.regime, isNotEmpty);
    expect(report.whyTitle, isNotEmpty);
    expect(report.stopLoss, greaterThan(0));
    expect(report.riskReward, greaterThan(0));
    expect(report.marketSentiment, isNotEmpty);
    expect(report.riskLabel, isNotEmpty);
    expect(report.beginnerAction, contains('Beginner'));
    expect(report.bullets, isNotEmpty);
  });

  test('technical analysis waits when candle history is insufficient', () {
    final report = const TechnicalAnalysisEngine().analyze(
      const MarketChartModel(
        symbol: 'ETHUSDT',
        interval: '5m',
        latestPrice: 2000,
        changePct: 0,
        candles: <MarketCandleModel>[],
        markers: <TradeMarkerModel>[],
        confidenceIntervals: <ConfidenceIntervalModel>[],
        confidenceHistory: <ConfidenceHistoryPointModel>[],
      ),
    );

    expect(report.side, 'WAIT');
    expect(report.stopLoss, 0);
    expect(report.regime, 'UNKNOWN');
    expect(report.marketSentiment, 'Data loading');
    expect(report.beginnerAction, contains('WAIT'));
    expect(report.summary, contains('waiting'));
  });
}

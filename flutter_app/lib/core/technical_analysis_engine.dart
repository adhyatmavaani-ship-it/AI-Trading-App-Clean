import 'dart:math' as math;

import '../models/market_chart.dart';

class TechnicalAnalysisReport {
  const TechnicalAnalysisReport({
    required this.symbol,
    required this.side,
    required this.confidence,
    required this.entryLow,
    required this.entryHigh,
    required this.stopLoss,
    required this.takeProfit1,
    required this.takeProfit2,
    required this.riskReward,
    required this.rsi14,
    required this.macd,
    required this.macdSignal,
    required this.macdHistogram,
    required this.sma20,
    required this.sma50,
    required this.ema9,
    required this.ema21,
    required this.pivot,
    required this.support1,
    required this.support2,
    required this.resistance1,
    required this.resistance2,
    required this.atr14,
    required this.adx14,
    required this.volumeRatio,
    required this.scalpScore,
    required this.swingScore,
    required this.regime,
    required this.warning,
    required this.whyTitle,
    required this.trendLabel,
    required this.marketSentiment,
    required this.riskLabel,
    required this.beginnerAction,
    required this.summary,
    required this.bullets,
  });

  final String symbol;
  final String side;
  final double confidence;
  final double entryLow;
  final double entryHigh;
  final double stopLoss;
  final double takeProfit1;
  final double takeProfit2;
  final double riskReward;
  final double rsi14;
  final double macd;
  final double macdSignal;
  final double macdHistogram;
  final double sma20;
  final double sma50;
  final double ema9;
  final double ema21;
  final double pivot;
  final double support1;
  final double support2;
  final double resistance1;
  final double resistance2;
  final double atr14;
  final double adx14;
  final double volumeRatio;
  final double scalpScore;
  final double swingScore;
  final String regime;
  final String warning;
  final String whyTitle;
  final String trendLabel;
  final String marketSentiment;
  final String riskLabel;
  final String beginnerAction;
  final String summary;
  final List<String> bullets;

  bool get actionable => side == 'BUY' || side == 'SELL';
}

class TechnicalAnalysisEngine {
  const TechnicalAnalysisEngine();

  TechnicalAnalysisReport analyze(MarketChartModel chart) {
    final candles = chart.candles
        .where((candle) =>
            candle.open > 0 &&
            candle.high > 0 &&
            candle.low > 0 &&
            candle.close > 0)
        .toList(growable: false);
    if (candles.length < 30) {
      final price = _lastPrice(chart, candles);
      return TechnicalAnalysisReport(
        symbol: chart.symbol,
        side: 'WAIT',
        confidence: 0,
        entryLow: price,
        entryHigh: price,
        stopLoss: 0,
        takeProfit1: 0,
        takeProfit2: 0,
        riskReward: 0,
        rsi14: 0,
        macd: 0,
        macdSignal: 0,
        macdHistogram: 0,
        sma20: 0,
        sma50: 0,
        ema9: 0,
        ema21: 0,
        pivot: 0,
        support1: 0,
        support2: 0,
        resistance1: 0,
        resistance2: 0,
        atr14: 0,
        adx14: 0,
        volumeRatio: 0,
        scalpScore: 0,
        swingScore: 0,
        regime: 'UNKNOWN',
        warning: '',
        whyTitle: 'AI needs more verified candles',
        trendLabel: 'Need more candles',
        marketSentiment: 'Data loading',
        riskLabel: 'High until candles load',
        beginnerAction:
            'WAIT. Do not enter until enough live candles are verified.',
        summary:
            'AI is waiting for at least 30 verified candles before giving a buy/sell plan.',
        bullets: const <String>[
          'No trade suggestion is generated from incomplete candle history.',
          'Risk guard remains active while market context loads.',
        ],
      );
    }

    final closes = candles.map((candle) => candle.close).toList();
    final volumes = candles.map((candle) => candle.volume).toList();
    final current = _lastPrice(chart, candles);
    final sma20 = _sma(closes, 20);
    final sma50 = _sma(closes, math.min(50, closes.length));
    final ema20 = _ema(closes, 20);
    final ema50 = _ema(closes, math.min(50, closes.length));
    final ema9 = _ema(closes, 9);
    final ema12Series = _emaSeries(closes, 12);
    final ema26Series = _emaSeries(closes, 26);
    final macdSeries = <double>[];
    final start = math.max(0, ema12Series.length - ema26Series.length);
    for (var i = 0; i < ema26Series.length; i++) {
      macdSeries.add(ema12Series[start + i] - ema26Series[i]);
    }
    final macd = macdSeries.isEmpty ? 0.0 : macdSeries.last;
    final macdSignal = _ema(macdSeries, math.min(9, macdSeries.length));
    final macdHistogram = macd - macdSignal;
    final ema21 = _ema(closes, 21);
    final rsi14 = _rsi(closes, 14);
    final atr14 = _atr(candles, 14);
    final previousAtr14 = _atr(
      candles.take(math.max(2, candles.length - 14)).toList(growable: false),
      14,
    );
    final adx14 = _adx(candles, 14);
    final recentVolume = volumes.isEmpty ? 0.0 : volumes.last;
    final avgVolume20 = _sma(volumes, 20);
    final volumeRatio = avgVolume20 <= 0 ? 0.0 : recentVolume / avgVolume20;
    final pivotSet = _pivot(candles);
    final recentHigh = candles
        .skip(math.max(0, candles.length - 20))
        .map((c) => c.high)
        .reduce(math.max);
    final recentLow = candles
        .skip(math.max(0, candles.length - 20))
        .map((c) => c.low)
        .reduce(math.min);

    final isTrending = adx14 > 25;
    final isSideways = adx14 < 20;
    final regime = isTrending
        ? 'TRENDING'
        : isSideways
            ? 'SIDEWAYS_CHOP'
            : 'TRANSITION';
    final weightSet = _weightsForInterval(chart.interval);
    final indicatorScores = _indicatorScores(
      current: current,
      previousClose: candles[candles.length - 2].close,
      rsi: rsi14,
      macd: macd,
      macdSignal: macdSignal,
      macdPrevious:
          macdSeries.length >= 2 ? macdSeries[macdSeries.length - 2] : macd,
      ema20: ema20,
      ema50: ema50,
      atr: atr14,
      previousAtr: previousAtr14,
      volumeRatio: volumeRatio,
      pivot: pivotSet.pivot,
      support: pivotSet.s1,
      resistance: pivotSet.r1,
      sideways: isSideways,
    );
    final scalpScore = _weightedScore(indicatorScores, _WeightSet.scalp);
    final swingScore = _weightedScore(indicatorScores, _WeightSet.swing);
    final selectedScore = _weightedScore(indicatorScores, weightSet);
    final warning = _warning(
      rsiScore: indicatorScores.rsi,
      volumeScore: indicatorScores.volume,
      resistanceScore: indicatorScores.resistancePenalty,
      selectedScore: selectedScore,
      sideways: isSideways,
    );

    var buyScore = selectedScore;
    var sellScore = 0.0;
    final bullets = <String>[];

    if (ema9 < ema21 || current < ema20) {
      sellScore = math.max(
        sellScore,
        100 - selectedScore + (ema9 < ema21 ? 12 : 0),
      );
    }
    if (isSideways) {
      bullets.add(
        'ADX ${adx14.toStringAsFixed(1)} shows sideways/chop, so RSI and MACD crossover signals are bypassed.',
      );
      if (current >= pivotSet.pivot) {
        bullets.add(
            'Price is above pivot; AI focuses on resistance breakout confirmation.');
      } else {
        bullets.add(
            'Price is below pivot; AI focuses on support reaction instead of oscillator signals.');
      }
    } else {
      if (indicatorScores.volume >= 80) {
        bullets.add(
          'Volume is ${((volumeRatio - 1) * 100).clamp(0, 999).toStringAsFixed(0)}% higher than average, confirming buyers.',
        );
      } else if (volumeRatio < 1) {
        bullets.add(
            'Volume is dry versus the 20-period average, so confidence is capped.');
      }
      if (indicatorScores.ema >= 75) {
        bullets.add(
            'Price is above 20 EMA and 20/50 EMA structure supports trend continuation.');
      }
      if (indicatorScores.macd >= 70) {
        bullets.add(
            'MACD has crossed above signal below/near the zero line, showing early momentum shift.');
      }
      if (indicatorScores.atr >= 70) {
        bullets.add(
            'ATR compression is visible, which can precede breakout expansion.');
      }
      if (indicatorScores.rsi >= 70) {
        bullets.add(
            'RSI is recovering from lower levels and heading toward bullish momentum.');
      }
    }
    if (warning.isNotEmpty) {
      bullets.insert(0, warning);
    }

    final side = (buyScore - sellScore).abs() < 10
        ? 'WAIT'
        : buyScore > sellScore
            ? 'BUY'
            : 'SELL';
    final confidence = side == 'WAIT'
        ? math.max(buyScore, sellScore).clamp(0, 58).toDouble()
        : math.max(buyScore, sellScore).clamp(0, 96).toDouble();
    final buffer = math.max(atr14 * 0.35, current * 0.0015);
    final entryLow = side == 'SELL' ? current - buffer : current - buffer * 0.5;
    final entryHigh =
        side == 'SELL' ? current + buffer * 0.5 : current + buffer;
    final stopLoss = side == 'BUY'
        ? math.min(recentLow, current - atr14 * 1.25)
        : side == 'SELL'
            ? math.max(recentHigh, current + atr14 * 1.25)
            : 0.0;
    final risk = side == 'BUY'
        ? (current - stopLoss).abs()
        : side == 'SELL'
            ? (stopLoss - current).abs()
            : 0.0;
    final takeProfit1 = side == 'BUY'
        ? current + risk * 1.5
        : side == 'SELL'
            ? current - risk * 1.5
            : 0.0;
    final takeProfit2 = side == 'BUY'
        ? current + risk * 2.2
        : side == 'SELL'
            ? current - risk * 2.2
            : 0.0;

    final trendLabel = side == 'BUY'
        ? '$regime bullish setup'
        : side == 'SELL'
            ? '$regime bearish setup'
            : '$regime no-trade setup';
    final atrPct = current <= 0 ? 0.0 : (atr14 / current) * 100;
    final riskLabel = atrPct >= 1.6
        ? 'High volatility'
        : atrPct >= 0.8
            ? 'Medium volatility'
            : 'Controlled volatility';
    final marketSentiment = side == 'BUY' && confidence >= 70
        ? 'Bullish'
        : side == 'SELL' && confidence >= 70
            ? 'Bearish'
            : side == 'BUY'
                ? 'Mild bullish'
                : side == 'SELL'
                    ? 'Mild bearish'
                    : 'Sideways / choppy';
    final beginnerAction = side == 'WAIT'
        ? 'WAIT. Market is not clean enough for a beginner entry.'
        : side == 'BUY'
            ? 'Beginner plan: consider BUY only near entry zone after a green confirmation candle.'
            : 'Beginner plan: consider SELL only near entry zone after a red confirmation candle.';
    final summary = side == 'WAIT'
        ? warning.isNotEmpty
            ? warning
            : 'No clean buy/sell edge right now. AI is reading candles and waiting for better confluence.'
        : '$side zone has ${confidence.toStringAsFixed(0)}% confidence from weighted $regime analysis, with SL at ${_price(stopLoss)}.';
    final whyTitle = confidence >= 85
        ? 'Trend, volume, and momentum are aligned'
        : warning.isNotEmpty
            ? 'Contradicting data detected'
            : side == 'WAIT'
                ? 'AI is waiting for cleaner confirmation'
                : 'Weighted indicators support a controlled setup';

    return TechnicalAnalysisReport(
      symbol: chart.symbol,
      side: side,
      confidence: confidence,
      entryLow: entryLow,
      entryHigh: entryHigh,
      stopLoss: stopLoss,
      takeProfit1: takeProfit1,
      takeProfit2: takeProfit2,
      riskReward: risk <= 0 ? 0 : ((takeProfit1 - current).abs() / risk),
      rsi14: rsi14,
      macd: macd,
      macdSignal: macdSignal,
      macdHistogram: macdHistogram,
      sma20: sma20,
      sma50: sma50,
      ema9: ema9,
      ema21: ema21,
      pivot: pivotSet.pivot,
      support1: pivotSet.s1,
      support2: pivotSet.s2,
      resistance1: pivotSet.r1,
      resistance2: pivotSet.r2,
      atr14: atr14,
      adx14: adx14,
      volumeRatio: volumeRatio,
      scalpScore: scalpScore,
      swingScore: swingScore,
      regime: regime,
      warning: warning,
      whyTitle: whyTitle,
      trendLabel: trendLabel,
      marketSentiment: marketSentiment,
      riskLabel: riskLabel,
      beginnerAction: beginnerAction,
      summary: summary,
      bullets: bullets.take(6).toList(growable: false),
    );
  }

  double _lastPrice(MarketChartModel chart, List<MarketCandleModel> candles) {
    if (chart.latestPrice > 0) {
      return chart.latestPrice;
    }
    return candles.isEmpty ? 0 : candles.last.close;
  }

  double _sma(List<double> values, int period) {
    if (values.isEmpty) {
      return 0;
    }
    final length = math.min(period, values.length);
    final slice = values.skip(values.length - length);
    return slice.reduce((a, b) => a + b) / length;
  }

  double _ema(List<double> values, int period) {
    final series = _emaSeries(values, period);
    return series.isEmpty ? 0 : series.last;
  }

  List<double> _emaSeries(List<double> values, int period) {
    if (values.isEmpty) {
      return const <double>[];
    }
    final multiplier = 2 / (period + 1);
    final series = <double>[];
    var ema = values.first;
    for (final value in values) {
      ema = (value - ema) * multiplier + ema;
      series.add(ema);
    }
    return series;
  }

  double _rsi(List<double> values, int period) {
    if (values.length <= period) {
      return 50;
    }
    var gain = 0.0;
    var loss = 0.0;
    final start = values.length - period;
    for (var i = start; i < values.length; i++) {
      final delta = values[i] - values[i - 1];
      if (delta >= 0) {
        gain += delta;
      } else {
        loss += delta.abs();
      }
    }
    if (loss == 0) {
      return 100;
    }
    final rs = (gain / period) / (loss / period);
    return 100 - (100 / (1 + rs));
  }

  double _atr(List<MarketCandleModel> candles, int period) {
    if (candles.length < 2) {
      return 0;
    }
    final ranges = <double>[];
    final start = math.max(1, candles.length - period);
    for (var i = start; i < candles.length; i++) {
      final candle = candles[i];
      final previousClose = candles[i - 1].close;
      ranges.add(
        math.max(
          candle.high - candle.low,
          math.max(
            (candle.high - previousClose).abs(),
            (candle.low - previousClose).abs(),
          ),
        ),
      );
    }
    return ranges.reduce((a, b) => a + b) / ranges.length;
  }

  double _adx(List<MarketCandleModel> candles, int period) {
    if (candles.length <= period + 1) {
      return 0;
    }
    final plusDm = <double>[];
    final minusDm = <double>[];
    final trueRanges = <double>[];
    final start = math.max(1, candles.length - period);
    for (var i = start; i < candles.length; i++) {
      final current = candles[i];
      final previous = candles[i - 1];
      final upMove = current.high - previous.high;
      final downMove = previous.low - current.low;
      plusDm.add(upMove > downMove && upMove > 0 ? upMove : 0);
      minusDm.add(downMove > upMove && downMove > 0 ? downMove : 0);
      trueRanges.add(
        math.max(
          current.high - current.low,
          math.max(
            (current.high - previous.close).abs(),
            (current.low - previous.close).abs(),
          ),
        ),
      );
    }
    final tr = trueRanges.fold<double>(0, (sum, value) => sum + value);
    if (tr <= 0) {
      return 0;
    }
    final plusDi =
        100 * plusDm.fold<double>(0, (sum, value) => sum + value) / tr;
    final minusDi =
        100 * minusDm.fold<double>(0, (sum, value) => sum + value) / tr;
    final total = plusDi + minusDi;
    if (total <= 0) {
      return 0;
    }
    return 100 * (plusDi - minusDi).abs() / total;
  }

  _WeightSet _weightsForInterval(String interval) {
    final normalized = interval.trim().toLowerCase();
    if (normalized == '1m' ||
        normalized == '3m' ||
        normalized == '5m' ||
        normalized == '15m') {
      return _WeightSet.scalp;
    }
    return _WeightSet.swing;
  }

  _IndicatorScores _indicatorScores({
    required double current,
    required double previousClose,
    required double rsi,
    required double macd,
    required double macdSignal,
    required double macdPrevious,
    required double ema20,
    required double ema50,
    required double atr,
    required double previousAtr,
    required double volumeRatio,
    required double pivot,
    required double support,
    required double resistance,
    required bool sideways,
  }) {
    final rsiRecovering = rsi >= 40 && rsi <= 62 && current >= previousClose;
    final macdCrossing = macd > macdSignal && macdPrevious <= macdSignal;
    final emaBullish = current > ema20 && (ema20 >= ema50 || current > ema50);
    final atrCompression =
        previousAtr > 0 && atr > 0 && atr <= previousAtr * 0.92;
    final volumeSpike = volumeRatio >= 2.0;
    final pivotReaction = current >= pivot ||
        (support > 0 && (current - support).abs() / current <= 0.006);
    final nearResistance =
        resistance > 0 && (resistance - current).abs() / current <= 0.004;

    return _IndicatorScores(
      rsi: sideways
          ? 0
          : (rsiRecovering
              ? 100
              : rsi >= 50 && rsi < 70
                  ? 68
                  : 25),
      macd: sideways
          ? 0
          : (macdCrossing
              ? 100
              : macd > macdSignal
                  ? 72
                  : 20),
      ema: emaBullish
          ? 100
          : current > ema20
              ? 72
              : 20,
      atr: atrCompression
          ? 100
          : atr > 0 && previousAtr > 0
              ? 55
              : 20,
      volume: volumeSpike ? 100 : (volumeRatio >= 1.2 ? 72 : 25),
      pivot: pivotReaction ? 85 : 35,
      resistancePenalty: nearResistance ? 100 : 0,
      oscillatorBypassed: sideways,
    );
  }

  double _weightedScore(_IndicatorScores scores, _WeightSet weights) {
    final rsiScore = scores.oscillatorBypassed ? 0.0 : scores.rsi;
    final macdScore = scores.oscillatorBypassed ? 0.0 : scores.macd;
    final oscillatorWeight =
        scores.oscillatorBypassed ? 0.0 : weights.rsi + weights.macd;
    final pivotWeight =
        scores.oscillatorBypassed ? oscillatorWeight + 0.12 : 0.0;
    final totalWeight = weights.ema +
        weights.atr +
        weights.volume +
        oscillatorWeight +
        pivotWeight;
    if (totalWeight <= 0) {
      return 0;
    }
    final weighted = (rsiScore * weights.rsi) +
        (macdScore * weights.macd) +
        (scores.ema * weights.ema) +
        (scores.atr * weights.atr) +
        (scores.volume * weights.volume) +
        (scores.pivot * pivotWeight);
    return (weighted / totalWeight).clamp(0.0, 100.0).toDouble();
  }

  String _warning({
    required double rsiScore,
    required double volumeScore,
    required double resistanceScore,
    required double selectedScore,
    required bool sideways,
  }) {
    if (sideways) {
      return 'Sideways market: oscillator crossovers are ignored; focus is pivot and support-resistance only.';
    }
    if (rsiScore >= 70 && volumeScore < 50 && resistanceScore >= 80) {
      return 'Contradicting Data: High Risk Setup';
    }
    if (selectedScore < 50) {
      return 'Contradicting Data: High Risk Setup';
    }
    return '';
  }

  _PivotSet _pivot(List<MarketCandleModel> candles) {
    final lookback = candles.skip(math.max(0, candles.length - 24)).toList();
    final high = lookback.map((c) => c.high).reduce(math.max);
    final low = lookback.map((c) => c.low).reduce(math.min);
    final close = lookback.last.close;
    final pivot = (high + low + close) / 3;
    final r1 = (2 * pivot) - low;
    final s1 = (2 * pivot) - high;
    final r2 = pivot + (high - low);
    final s2 = pivot - (high - low);
    return _PivotSet(pivot: pivot, r1: r1, r2: r2, s1: s1, s2: s2);
  }
}

class _PivotSet {
  const _PivotSet({
    required this.pivot,
    required this.r1,
    required this.r2,
    required this.s1,
    required this.s2,
  });

  final double pivot;
  final double r1;
  final double r2;
  final double s1;
  final double s2;
}

class _WeightSet {
  const _WeightSet({
    required this.rsi,
    required this.macd,
    required this.ema,
    required this.atr,
    required this.volume,
  });

  static const scalp = _WeightSet(
    rsi: 0.20,
    macd: 0.15,
    ema: 0.10,
    atr: 0.25,
    volume: 0.30,
  );

  static const swing = _WeightSet(
    rsi: 0.10,
    macd: 0.25,
    ema: 0.30,
    atr: 0.10,
    volume: 0.25,
  );

  final double rsi;
  final double macd;
  final double ema;
  final double atr;
  final double volume;
}

class _IndicatorScores {
  const _IndicatorScores({
    required this.rsi,
    required this.macd,
    required this.ema,
    required this.atr,
    required this.volume,
    required this.pivot,
    required this.resistancePenalty,
    required this.oscillatorBypassed,
  });

  final double rsi;
  final double macd;
  final double ema;
  final double atr;
  final double volume;
  final double pivot;
  final double resistancePenalty;
  final bool oscillatorBypassed;
}

String _price(double value) {
  if (value <= 0) {
    return 'pending';
  }
  return value >= 100 ? value.toStringAsFixed(2) : value.toStringAsFixed(4);
}

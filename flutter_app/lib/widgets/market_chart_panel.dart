import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../models/activity.dart';
import '../models/market_chart.dart';
import 'section_card.dart';
import 'state_widgets.dart';

class MarketChartPanel extends ConsumerWidget {
  const MarketChartPanel({
    super.key,
    this.latestActivity,
  });

  final ActivityItemModel? latestActivity;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final chartAsync = ref.watch(marketChartProvider);
    final universeAsync = ref.watch(marketUniverseProvider);
    final selectedSymbol = ref.watch(selectedMarketSymbolProvider);
    final selectedInterval = ref.watch(selectedMarketIntervalProvider);

    return SectionCard(
      title: 'Live Market Board',
      trailing: _TickerPill(
        message: latestActivity?.intent ??
            latestActivity?.message ??
            'AI scanning liquid markets for structure + momentum',
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          universeAsync.when(
            data: (universe) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _CategoryRow(
                  title: 'AI Picks',
                  entries: universe.aiPicks,
                  selectedSymbol: selectedSymbol,
                  onSelect: (symbol) => ref
                      .read(selectedMarketSymbolProvider.notifier)
                      .state = symbol,
                ),
                const SizedBox(height: 12),
                _CategoryRow(
                  title: 'Top Gainers',
                  entries: universe.topGainers,
                  selectedSymbol: selectedSymbol,
                  onSelect: (symbol) => ref
                      .read(selectedMarketSymbolProvider.notifier)
                      .state = symbol,
                ),
                const SizedBox(height: 12),
                _CategoryRow(
                  title: 'High Volatility',
                  entries: universe.highVolatility,
                  selectedSymbol: selectedSymbol,
                  onSelect: (symbol) => ref
                      .read(selectedMarketSymbolProvider.notifier)
                      .state = symbol,
                ),
              ],
            ),
            loading: () => const LoadingState(label: 'Loading market universe'),
            error: (error, _) => ErrorState(message: error.toString()),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              for (final interval in const <String>['1m', '5m', '15m', '1h'])
                ChoiceChip(
                  label: Text(interval),
                  selected: selectedInterval == interval,
                  onSelected: (_) => ref
                      .read(selectedMarketIntervalProvider.notifier)
                      .state = interval,
                ),
            ],
          ),
          const SizedBox(height: 18),
          chartAsync.when(
            data: (chart) => _ChartBody(chart: chart),
            loading: () => const SizedBox(
              height: 360,
              child: LoadingState(label: 'Loading chart'),
            ),
            error: (error, _) => ErrorState(message: error.toString()),
          ),
        ],
      ),
    );
  }
}

class _ChartBody extends StatelessWidget {
  const _ChartBody({required this.chart});

  final MarketChartModel chart;

  @override
  Widget build(BuildContext context) {
    final candles = chart.candles;
    if (candles.isEmpty) {
      return const SizedBox(
        height: 320,
        child: EmptyState(
          title: 'No candle data yet',
          subtitle: 'Market candles will appear here when the backend cache warms up.',
        ),
      );
    }
    final latest = candles.last;
    final previous = candles.length > 1 ? candles[candles.length - 2] : latest;
    final changeColor =
        chart.changePct >= 0 ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final minPrice = candles
        .map((item) => item.low)
        .reduce((left, right) => left < right ? left : right);
    final maxPrice = candles
        .map((item) => item.high)
        .reduce((left, right) => left > right ? left : right);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                chart.symbol,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ),
            TweenAnimationBuilder<double>(
              tween: Tween<double>(begin: previous.close, end: latest.close),
              duration: const Duration(milliseconds: 600),
              builder: (context, value, child) {
                return Text(
                  value.toStringAsFixed(value >= 100 ? 2 : 4),
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        color: changeColor,
                        shadows: <Shadow>[
                          Shadow(
                            color: changeColor.withOpacity(0.42),
                            blurRadius: 16,
                          ),
                        ],
                      ),
                );
              },
            ),
            const SizedBox(width: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: changeColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: changeColor.withOpacity(0.35)),
              ),
              child: Text(
                '${chart.changePct >= 0 ? '+' : ''}${chart.changePct.toStringAsFixed(2)}%',
                style: TextStyle(
                  color: changeColor,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'TradingView-style market pulse with AI markers',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 16),
        SizedBox(
          height: 280,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final chartSize = Size(
                constraints.maxWidth,
                constraints.maxHeight - 24,
              );
              final geometry = _ChartGeometry(
                candles: candles,
                minPrice: minPrice,
                maxPrice: maxPrice,
                size: chartSize,
              );
              return Column(
                children: <Widget>[
                  Expanded(
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onTapDown: (details) {
                        final ghostMarker = _nearestGhostMarker(
                          geometry: geometry,
                          tap: details.localPosition,
                          markers: chart.markers,
                        );
                        if (ghostMarker == null) {
                          return;
                        }
                        _showGhostMarkerSheet(context, ghostMarker);
                      },
                      child: CustomPaint(
                        painter: _CandlestickPainter(
                          candles: candles,
                          minPrice: minPrice,
                          maxPrice: maxPrice,
                          markers: chart.markers,
                        ),
                        child: const SizedBox.expand(),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: _buildTimeLabels(context, candles),
                  ),
                ],
              );
            },
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _StatPill(
              label: 'Open',
              value: latest.open.toStringAsFixed(latest.open >= 100 ? 2 : 4),
            ),
            _StatPill(
              label: 'High',
              value: latest.high.toStringAsFixed(latest.high >= 100 ? 2 : 4),
            ),
            _StatPill(
              label: 'Low',
              value: latest.low.toStringAsFixed(latest.low >= 100 ? 2 : 4),
            ),
            _StatPill(
              label: 'Volume',
              value: latest.volume.toStringAsFixed(0),
            ),
          ],
        ),
        if (chart.markers.isNotEmpty) ...<Widget>[
          const SizedBox(height: 16),
          Text(
            'AI Entry / Exit Markers',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: chart.markers.take(8).map(_markerChip).toList(),
          ),
        ],
      ],
    );
  }

  Widget _markerChip(TradeMarkerModel marker) {
    final isGhost = marker.markerStyle == 'ghost';
    final isEntry = marker.markerType == 'ENTRY';
    final accent = isGhost
        ? TradingPalette.textMuted
        : isEntry
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed;
    final icon = isGhost
        ? Icons.add_rounded
        : isEntry
            ? Icons.arrow_upward_rounded
            : Icons.arrow_downward_rounded;
    return Chip(
      avatar: Icon(icon, size: 16, color: accent),
      label: Text(
        isGhost
            ? 'GHOST ${marker.readinessScore?.toStringAsFixed(0) ?? '--'}% ${marker.reason ?? marker.message ?? ''}'
            : '${marker.markerType} ${marker.side} @ ${marker.price.toStringAsFixed(marker.price >= 100 ? 2 : 4)}',
      ),
      backgroundColor: isGhost
          ? TradingPalette.panelSoft
          : accent.withOpacity(0.12),
      side: BorderSide(color: accent.withOpacity(0.35)),
    );
  }

  List<Widget> _buildTimeLabels(
    BuildContext context,
    List<MarketCandleModel> candles,
  ) {
    if (candles.length < 4) {
      return const <Widget>[];
    }
    final indices = <int>{
      0,
      candles.length ~/ 3,
      (candles.length * 2) ~/ 3,
      candles.length - 1,
    }.toList()
      ..sort();
    return indices.map((index) {
      final time = DateTime.fromMillisecondsSinceEpoch(candles[index].timestampMs);
      final label =
          '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
      return Text(
        label,
        style: Theme.of(context).textTheme.labelSmall,
      );
    }).toList();
  }
}

class _ChartGeometry {
  const _ChartGeometry({
    required this.candles,
    required this.minPrice,
    required this.maxPrice,
    required this.size,
  });

  final List<MarketCandleModel> candles;
  final double minPrice;
  final double maxPrice;
  final Size size;

  double get usableHeight => size.height - 18;

  double get gap => size.width / math.max(candles.length, 1);

  Offset markerOffset(TradeMarkerModel marker) {
    final timestamp = marker.timestamp.millisecondsSinceEpoch;
    var markerIndex = 0;
    var minDiff = 1 << 30;
    for (var index = 0; index < candles.length; index += 1) {
      final diff = (candles[index].timestampMs - timestamp).abs();
      if (diff < minDiff) {
        minDiff = diff;
        markerIndex = index;
      }
    }
    final x = (markerIndex * gap) + (gap / 2);
    final y = mapY(marker.price);
    return Offset(x, y);
  }

  double mapY(double price) {
    final denominator = (maxPrice - minPrice).abs() < 1e-8
        ? 1
        : (maxPrice - minPrice);
    final ratio = (price - minPrice) / denominator;
    return usableHeight - (ratio * usableHeight) + 9;
  }
}

TradeMarkerModel? _nearestGhostMarker({
  required _ChartGeometry geometry,
  required Offset tap,
  required List<TradeMarkerModel> markers,
}) {
  TradeMarkerModel? best;
  double bestDistance = 30;
  for (final marker in markers) {
    if (marker.markerStyle != 'ghost') {
      continue;
    }
    final offset = geometry.markerOffset(marker);
    final distance = (offset - tap).distance;
    if (distance < bestDistance) {
      best = marker;
      bestDistance = distance;
    }
  }
  return best;
}

void _showGhostMarkerSheet(BuildContext context, TradeMarkerModel marker) {
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: TradingPalette.deepNavy,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (context) {
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: TradingPalette.textMuted,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  'Ghost Setup',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: TradingPalette.textPrimary,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              marker.reason ?? marker.message ?? 'AI rejected this setup.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
            const SizedBox(height: 14),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                _GhostMetaPill(
                  label: 'Confidence',
                  value: '${(marker.confidenceScore * 100).toStringAsFixed(0)}%',
                ),
                _GhostMetaPill(
                  label: 'Readiness',
                  value: '${(marker.readinessScore ?? 0).toStringAsFixed(0)}%',
                ),
                if ((marker.intent ?? '').isNotEmpty)
                  _GhostMetaPill(
                    label: 'Intent',
                    value: marker.intent!,
                  ),
              ],
            ),
          ],
        ),
      );
    },
  );
}

class _CategoryRow extends StatelessWidget {
  const _CategoryRow({
    required this.title,
    required this.entries,
    required this.selectedSymbol,
    required this.onSelect,
  });

  final String title;
  final List<MarketUniverseEntryModel> entries;
  final String selectedSymbol;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: entries.map((entry) {
              final isSelected = entry.symbol == selectedSymbol;
              final accent = entry.changePct >= 0
                  ? TradingPalette.neonGreen
                  : TradingPalette.neonRed;
              return Padding(
                padding: const EdgeInsets.only(right: 10),
                child: GestureDetector(
                  onTap: () => onSelect(entry.symbol),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? const Color(0x3310FFC3)
                          : TradingPalette.panelSoft,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: isSelected
                            ? TradingPalette.neonGreen
                            : TradingPalette.panelBorder,
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          entry.symbol,
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontSize: 14),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '${entry.changePct >= 0 ? '+' : ''}${entry.changePct.toStringAsFixed(2)}%',
                          style: TextStyle(
                            color: accent,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'Vol ${entry.volatilityPct.toStringAsFixed(2)}%',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }
}

class _CandlestickPainter extends CustomPainter {
  const _CandlestickPainter({
    required this.candles,
    required this.minPrice,
    required this.maxPrice,
    required this.markers,
  });

  final List<MarketCandleModel> candles;
  final double minPrice;
  final double maxPrice;
  final List<TradeMarkerModel> markers;

  @override
  void paint(Canvas canvas, Size size) {
    final geometry = _ChartGeometry(
      candles: candles,
      minPrice: minPrice,
      maxPrice: maxPrice,
      size: size,
    );
    final background = Paint()
      ..style = PaintingStyle.fill
      ..shader = const LinearGradient(
        colors: <Color>[Color(0x2200FFA3), Color(0x11000000)],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Offset.zero & size);
    final grid = Paint()
      ..color = const Color(0xFF1E294E)
      ..strokeWidth = 1;
    final border = Paint()
      ..color = TradingPalette.panelBorder
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(18)),
      background,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(18)),
      border,
    );

    for (var i = 1; i < 4; i += 1) {
      final y = (size.height / 4) * i;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }

    final candleWidth = size.width / (candles.length * 1.25);

    for (var index = 0; index < candles.length; index += 1) {
      final candle = candles[index];
      final x = (index * geometry.gap) + (geometry.gap / 2);
      final wickPaint = Paint()
        ..color = candle.close >= candle.open
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed
        ..strokeWidth = 1.3;
      final bodyPaint = Paint()
        ..color = candle.close >= candle.open
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed
        ..style = PaintingStyle.fill;
      final highY = geometry.mapY(candle.high);
      final lowY = geometry.mapY(candle.low);
      final openY = geometry.mapY(candle.open);
      final closeY = geometry.mapY(candle.close);
      canvas.drawLine(Offset(x, highY), Offset(x, lowY), wickPaint);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTRB(
            x - candleWidth / 2,
            openY < closeY ? openY : closeY,
            x + candleWidth / 2,
            (openY > closeY ? openY : closeY) + 1.5,
          ),
          const Radius.circular(4),
        ),
        bodyPaint,
      );
    }

    _paintTradeBridges(canvas, geometry);
    for (final marker in markers.take(18)) {
      _paintMarker(canvas, geometry, marker);
    }
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.markers != markers ||
        oldDelegate.minPrice != minPrice ||
        oldDelegate.maxPrice != maxPrice;
  }

  void _paintTradeBridges(Canvas canvas, _ChartGeometry geometry) {
    final trades = <String, Map<String, TradeMarkerModel>>{};
    for (final marker in markers) {
      final tradeId = marker.tradeId;
      if (tradeId == null || tradeId.isEmpty) {
        continue;
      }
      final slot = trades.putIfAbsent(tradeId, () => <String, TradeMarkerModel>{});
      slot[marker.markerType] = marker;
    }
    for (final entry in trades.values) {
      final startMarker = entry['ENTRY'];
      final endMarker = entry['EXIT'];
      if (startMarker == null || endMarker == null) {
        continue;
      }
      final start = geometry.markerOffset(startMarker);
      final end = geometry.markerOffset(endMarker);
      final path = Path()
        ..moveTo(start.dx, start.dy)
        ..quadraticBezierTo(
          (start.dx + end.dx) / 2,
          math.min(start.dy, end.dy) - 22,
          end.dx,
          end.dy,
        );
      final bridgePaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.4
        ..color = TradingPalette.electricBlue.withOpacity(0.7);
      _drawDashedPath(canvas, path, bridgePaint);
    }
  }

  void _paintMarker(
    Canvas canvas,
    _ChartGeometry geometry,
    TradeMarkerModel marker,
  ) {
    final offset = geometry.markerOffset(marker);
    if (marker.confidenceScore > 0.7) {
      final haloColor = marker.markerStyle == 'ghost'
          ? TradingPalette.textMuted
          : TradingPalette.neonGreen;
      canvas.drawCircle(
        offset,
        24 + (marker.confidenceScore * 10),
        Paint()
          ..color = haloColor.withOpacity(
            marker.markerStyle == 'ghost' ? 0.06 : 0.11,
          )
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 14),
      );
    }
    if (marker.markerStyle == 'ghost') {
      _drawGhostPlus(canvas, offset, TradingPalette.textMuted);
      return;
    }
    final isEntry = marker.markerType == 'ENTRY';
    final accent = isEntry ? TradingPalette.neonGreen : TradingPalette.neonRed;
    _drawArrowMarker(
      canvas,
      offset,
      accent,
      upward: isEntry,
    );
  }

  void _drawArrowMarker(
    Canvas canvas,
    Offset center,
    Color color, {
    required bool upward,
  }) {
    canvas.drawCircle(
      center,
      9,
      Paint()
        ..color = color.withOpacity(0.18)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10),
    );
    final path = Path();
    if (upward) {
      path
        ..moveTo(center.dx, center.dy - 9)
        ..lineTo(center.dx - 7, center.dy + 4)
        ..lineTo(center.dx - 2, center.dy + 4)
        ..lineTo(center.dx - 2, center.dy + 10)
        ..lineTo(center.dx + 2, center.dy + 10)
        ..lineTo(center.dx + 2, center.dy + 4)
        ..lineTo(center.dx + 7, center.dy + 4)
        ..close();
    } else {
      path
        ..moveTo(center.dx, center.dy + 9)
        ..lineTo(center.dx - 7, center.dy - 4)
        ..lineTo(center.dx - 2, center.dy - 4)
        ..lineTo(center.dx - 2, center.dy - 10)
        ..lineTo(center.dx + 2, center.dy - 10)
        ..lineTo(center.dx + 2, center.dy - 4)
        ..lineTo(center.dx + 7, center.dy - 4)
        ..close();
    }
    canvas.drawPath(
      path,
      Paint()..color = color,
    );
  }

  void _drawGhostPlus(Canvas canvas, Offset center, Color color) {
    final paint = Paint()
      ..color = color.withOpacity(0.75)
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(
      center,
      10,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = color.withOpacity(0.32),
    );
    canvas.drawLine(
      Offset(center.dx - 5, center.dy),
      Offset(center.dx + 5, center.dy),
      paint,
    );
    canvas.drawLine(
      Offset(center.dx, center.dy - 5),
      Offset(center.dx, center.dy + 5),
      paint,
    );
  }

  void _drawDashedPath(Canvas canvas, Path source, Paint paint) {
    for (final metric in source.computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = math.min(distance + 6, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance += 10;
      }
    }
  }
}

class _TickerPill extends StatelessWidget {
  const _TickerPill({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 260),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0x2214FFB8),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0x4414FFB8)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: TradingPalette.neonGreen,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Text(
              message,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: TradingPalette.textPrimary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatPill extends StatelessWidget {
  const _StatPill({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context)
                .textTheme
                .titleMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _GhostMetaPill extends StatelessWidget {
  const _GhostMetaPill({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

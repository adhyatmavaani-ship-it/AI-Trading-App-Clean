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
          child: Column(
            children: <Widget>[
              Expanded(
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
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: _buildTimeLabels(context, candles),
              ),
            ],
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
    final isEntry = marker.type == 'entry';
    final accent = isEntry ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final icon = isEntry ? Icons.login_rounded : Icons.logout_rounded;
    return Chip(
      avatar: Icon(icon, size: 16, color: accent),
      label: Text(
        '${marker.type.toUpperCase()} ${marker.side} @ ${marker.price.toStringAsFixed(marker.price >= 100 ? 2 : 4)}',
      ),
      backgroundColor: accent.withOpacity(0.12),
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

    final usableHeight = size.height - 18;
    final candleWidth = size.width / (candles.length * 1.25);
    final gap = size.width / candles.length;

    double mapY(double price) {
      final ratio = (price - minPrice) / ((maxPrice - minPrice).abs() < 1e-8 ? 1 : (maxPrice - minPrice));
      return usableHeight - (ratio * usableHeight) + 9;
    }

    for (var index = 0; index < candles.length; index += 1) {
      final candle = candles[index];
      final x = (index * gap) + (gap / 2);
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
      final highY = mapY(candle.high);
      final lowY = mapY(candle.low);
      final openY = mapY(candle.open);
      final closeY = mapY(candle.close);
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

    final markerPaint = Paint()..style = PaintingStyle.fill;
    for (final marker in markers.take(8)) {
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
      markerPaint.color =
          marker.type == 'entry' ? TradingPalette.electricBlue : TradingPalette.amber;
      canvas.drawCircle(Offset(x, y), 4.5, markerPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _CandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.markers != markers ||
        oldDelegate.minPrice != minPrice ||
        oldDelegate.maxPrice != maxPrice;
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

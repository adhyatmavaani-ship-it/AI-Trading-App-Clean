import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/chart_spatial_index.dart';
import '../core/chart_render_scheduler.dart';
import '../core/trading_palette.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import 'live_energy_widgets.dart';
import 'status_badge.dart';

class ProTradingChart extends StatefulWidget {
  const ProTradingChart({
    super.key,
    required this.chart,
    required this.onAssistantModeChanged,
    this.fullscreenActionBar,
    this.height = 400,
    this.activeTrades = const <ActiveTradeModel>[],
  });

  final MarketChartModel chart;
  final ValueChanged<String> onAssistantModeChanged;
  final Widget? fullscreenActionBar;
  final double height;
  final List<ActiveTradeModel> activeTrades;

  @override
  State<ProTradingChart> createState() => _ProTradingChartState();
}

class _ProTradingChartState extends State<ProTradingChart>
    with SingleTickerProviderStateMixin {
  double _zoomX = 1.0;
  double _windowPosition = 1.0;
  Offset? _crosshair;
  double _baseZoom = 1.0;
  bool _replayMode = false;
  bool _interacting = false;
  final ChartRenderScheduler _crosshairScheduler = ChartRenderScheduler();
  late final AnimationController _chartEnergyController;

  @override
  void initState() {
    super.initState();
    _chartEnergyController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2400),
    )..repeat();
  }

  @override
  void dispose() {
    _chartEnergyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final chart = widget.chart;
    final feed = chart.aiFeed;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        _HeaderRow(
          chart: chart,
          onFullscreen: () => _openFullscreen(context),
          onResetView: _resetView,
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: chart.assistantModes
              .map(
                (mode) => ChoiceChip(
                  label: Text(_formatMode(mode)),
                  selected: chart.activeAssistantMode == mode,
                  onSelected: (_) => widget.onAssistantModeChanged(mode),
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 12),
        _ChartModeBar(
          replayMode: _replayMode,
          onReplayChanged: (value) {
            HapticFeedback.selectionClick();
            setState(() => _replayMode = value);
          },
        ),
        const SizedBox(height: 12),
        SizedBox(
          height: widget.height,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final geometry = _ProChartGeometry(
                chart: chart,
                activeTrades: widget.activeTrades,
                size: constraints.biggest,
                zoomX: _zoomX,
                windowPosition: _windowPosition,
              );
              return Stack(
                children: <Widget>[
                  RepaintBoundary(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(24),
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onScaleStart: (details) {
                          _pauseChartMotion();
                          _baseZoom = _zoomX;
                          _updateCrosshair(geometry, details.localFocalPoint);
                        },
                        onScaleUpdate: (details) {
                          if (details.pointerCount >= 2) {
                            setState(() {
                              _zoomX =
                                  (_baseZoom * details.scale).clamp(1.0, 5.5);
                              _windowPosition = (_windowPosition -
                                      (details.focalPointDelta.dx /
                                              math.max(
                                                  constraints.maxWidth, 1)) /
                                          math.max(_zoomX, 1.0))
                                  .clamp(0.0, 1.0);
                            });
                          }
                          _updateCrosshair(geometry, details.localFocalPoint);
                        },
                        onScaleEnd: (_) => _resumeChartMotion(),
                        onHorizontalDragStart: (_) => _pauseChartMotion(),
                        onHorizontalDragUpdate: (details) {
                          setState(() {
                            _windowPosition = (_windowPosition -
                                    (details.delta.dx /
                                            math.max(constraints.maxWidth, 1)) /
                                        math.max(_zoomX, 1.0))
                                .clamp(0.0, 1.0);
                          });
                        },
                        onHorizontalDragEnd: (_) => _resumeChartMotion(),
                        onHorizontalDragCancel: _resumeChartMotion,
                        onDoubleTap: _resetView,
                        onLongPressStart: (details) =>
                            _updateCrosshair(geometry, details.localPosition),
                        onLongPressMoveUpdate: (details) =>
                            _updateCrosshair(geometry, details.localPosition),
                        onLongPressEnd: (_) =>
                            setState(() => _crosshair = null),
                        child: Stack(
                          fit: StackFit.expand,
                          children: <Widget>[
                            RepaintBoundary(
                              child: AnimatedBuilder(
                                animation: _chartEnergyController,
                                builder: (context, _) {
                                  return CustomPaint(
                                    painter: _ProTradingChartPainter(
                                      chart: chart,
                                      activeTrades: widget.activeTrades,
                                      geometry: geometry,
                                      pulse: _chartEnergyController.value,
                                      replayMode: _replayMode,
                                    ),
                                    child: const SizedBox.expand(),
                                  );
                                },
                              ),
                            ),
                            Positioned(
                              left: 14,
                              right: 14,
                              top: 14,
                              child: IgnorePointer(
                                child: _ChartLiveOverlay(
                                  chart: chart,
                                  replayMode: _replayMode,
                                ),
                              ),
                            ),
                            if (_crosshair != null)
                              RepaintBoundary(
                                child: CustomPaint(
                                  painter: _CrosshairPainter(
                                    geometry: geometry,
                                    crosshair: _crosshair!,
                                  ),
                                  child: const SizedBox.expand(),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  if (_crosshair != null)
                    _CrosshairHud(
                      chart: chart,
                      geometry: geometry,
                      crosshair: _crosshair!,
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
            _ScoreChip(
              label: 'Confidence',
              value: '${chart.opportunity.confidence.toStringAsFixed(0)}%',
              accent: TradingPalette.neonGreen,
            ),
            _ScoreChip(
              label: 'Scalp Score',
              value: chart.opportunity.scalpScore.toStringAsFixed(0),
              accent: TradingPalette.electricBlue,
            ),
            _ScoreChip(
              label: 'Expected RR',
              value: chart.opportunity.expectedRr.toStringAsFixed(2),
              accent: TradingPalette.amber,
            ),
            _ScoreChip(
              label: 'Whale Pressure',
              value: chart.opportunity.whalePressure.toStringAsFixed(0),
              accent: TradingPalette.violet,
            ),
            _ScoreChip(
              label: 'Trend Strength',
              value: chart.opportunity.trendStrength.toStringAsFixed(0),
              accent: TradingPalette.neonGreen,
            ),
            _ScoreChip(
              label: 'Volatility',
              value: chart.opportunity.volatilityScore.toStringAsFixed(0),
              accent: TradingPalette.neonRed,
            ),
          ],
        ),
        const SizedBox(height: 14),
        _ExecutionGuideCard(chart: chart),
        const SizedBox(height: 14),
        _LegendRow(overlays: chart.overlays),
        if (feed.isNotEmpty) ...<Widget>[
          const SizedBox(height: 14),
          _AiFeedCard(feed: feed),
        ],
      ],
    );
  }

  void _updateCrosshair(_ProChartGeometry geometry, Offset position) {
    if (!_crosshairScheduler.shouldRender()) {
      return;
    }
    final next = geometry.clampPoint(position);
    if (_crosshair != null && (_crosshair! - next).distance < 1.2) {
      return;
    }
    setState(() {
      _crosshair = next;
    });
  }

  void _resetView() {
    HapticFeedback.selectionClick();
    setState(() {
      _zoomX = 1.0;
      _windowPosition = 1.0;
      _crosshair = null;
    });
  }

  void _pauseChartMotion() {
    if (_interacting) {
      return;
    }
    _interacting = true;
    _chartEnergyController.stop();
  }

  void _resumeChartMotion() {
    if (!_interacting) {
      return;
    }
    _interacting = false;
    if (mounted) {
      _chartEnergyController.repeat();
    }
  }

  Future<void> _openFullscreen(BuildContext context) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) {
          return Scaffold(
            backgroundColor: TradingPalette.midnight,
            body: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        IconButton(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.close_fullscreen_rounded),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${widget.chart.symbol} Pro Chart',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Expanded(
                      child: Stack(
                        children: <Widget>[
                          Positioned.fill(
                            child: ProTradingChart(
                              chart: widget.chart,
                              activeTrades: widget.activeTrades,
                              onAssistantModeChanged:
                                  widget.onAssistantModeChanged,
                              fullscreenActionBar: widget.fullscreenActionBar,
                              height: math.max(
                                420,
                                MediaQuery.sizeOf(context).height - 260,
                              ),
                            ),
                          ),
                          if (widget.fullscreenActionBar != null)
                            Positioned(
                              left: 0,
                              right: 0,
                              bottom: 0,
                              child: widget.fullscreenActionBar!,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _HeaderRow extends StatelessWidget {
  const _HeaderRow({
    required this.chart,
    required this.onFullscreen,
    required this.onResetView,
  });

  final MarketChartModel chart;
  final VoidCallback onFullscreen;
  final VoidCallback onResetView;

  @override
  Widget build(BuildContext context) {
    final changeColor = chart.changePct >= 0
        ? TradingPalette.neonGreen
        : TradingPalette.neonRed;
    return Row(
      children: <Widget>[
        Expanded(
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              StatusBadge(
                label: chart.symbol,
                color: TradingPalette.electricBlue,
              ),
              StatusBadge(
                label: chart.marketRegime.state,
                color: _regimeColor(chart.marketRegime.state),
              ),
              StatusBadge(
                label: chart.chartEngine.toUpperCase(),
                color: TradingPalette.violet,
              ),
              StatusBadge(
                label:
                    '${chart.changePct >= 0 ? '+' : ''}${chart.changePct.toStringAsFixed(2)}%',
                color: changeColor,
              ),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Reset view',
          onPressed: onResetView,
          icon: const Icon(Icons.center_focus_strong_rounded),
        ),
        IconButton(
          tooltip: 'Fullscreen',
          onPressed: onFullscreen,
          icon: const Icon(Icons.open_in_full_rounded),
        ),
      ],
    );
  }
}

class _ChartModeBar extends StatelessWidget {
  const _ChartModeBar({
    required this.replayMode,
    required this.onReplayChanged,
  });

  final bool replayMode;
  final ValueChanged<bool> onReplayChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: LiveEnergyBars(
            color:
                replayMode ? TradingPalette.amber : TradingPalette.electricBlue,
            height: 28,
            barCount: 22,
          ),
        ),
        const SizedBox(width: 12),
        FilterChip(
          selected: replayMode,
          onSelected: onReplayChanged,
          avatar: Icon(
            replayMode ? Icons.history_rounded : Icons.play_arrow_rounded,
            size: 18,
          ),
          label: Text(replayMode ? 'Replay' : 'Live'),
        ),
      ],
    );
  }
}

class _ChartLiveOverlay extends StatelessWidget {
  const _ChartLiveOverlay({
    required this.chart,
    required this.replayMode,
  });

  final MarketChartModel chart;
  final bool replayMode;

  @override
  Widget build(BuildContext context) {
    final changeColor = chart.changePct >= 0
        ? TradingPalette.neonGreen
        : TradingPalette.neonRed;
    final title = replayMode
        ? 'AI replaying structure and liquidity'
        : chart.opportunity.whalePressure >= 70
            ? 'Whale accumulation increasing'
            : chart.opportunity.momentumScore >= 70
                ? 'Momentum ignition building'
                : 'AI detecting market expansion';
    return DecoratedBox(
      decoration: BoxDecoration(
        color: const Color(0x99101523),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: changeColor.withOpacity(0.24)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: <Widget>[
            Icon(
              replayMode
                  ? Icons.replay_circle_filled_rounded
                  : Icons.radar_rounded,
              color: changeColor,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                title,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${chart.opportunity.confidence.toStringAsFixed(0)}%',
              style: TextStyle(color: changeColor, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class _ExecutionGuideCard extends StatelessWidget {
  const _ExecutionGuideCard({required this.chart});

  final MarketChartModel chart;

  @override
  Widget build(BuildContext context) {
    final guide = chart.executionGuide;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: TradingPalette.panelBorder.withOpacity(0.72)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text(
                'Execution Guide',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const Spacer(),
              StatusBadge(
                label: guide.side,
                color: guide.side == 'BUY'
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _GuidePill(
                label: 'Entry',
                value:
                    '${guide.entryLow.toStringAsFixed(2)} - ${guide.entryHigh.toStringAsFixed(2)}',
              ),
              _GuidePill(
                label: 'SL',
                value: guide.stopLoss.toStringAsFixed(2),
              ),
              _GuidePill(
                label: 'TP1',
                value: guide.tp1.toStringAsFixed(2),
              ),
              _GuidePill(
                label: 'TP2',
                value: guide.tp2.toStringAsFixed(2),
              ),
              _GuidePill(
                label: 'RR',
                value: guide.riskReward.toStringAsFixed(2),
              ),
              _GuidePill(
                label: 'Trail',
                value: chart.trailingStop.mode.replaceAll('_', ' '),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Risk ${guide.riskPct.toStringAsFixed(2)}% vs reward ${guide.rewardPct.toStringAsFixed(2)}%. Trailing stop projects from ${chart.trailingStop.currentStop.toStringAsFixed(2)} to ${chart.trailingStop.projectedStop.toStringAsFixed(2)}.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
        ],
      ),
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow({required this.overlays});

  final List<MarketOverlayModel> overlays;

  @override
  Widget build(BuildContext context) {
    final labels = <String>{
      for (final overlay in overlays)
        overlay.label.isEmpty ? overlay.zoneType : overlay.label,
    }.take(6);
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: labels
          .map(
            (label) => Chip(
              label: Text(label),
              backgroundColor: TradingPalette.panelSoft,
              side: BorderSide(
                color: TradingPalette.panelBorder.withOpacity(0.65),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _AiFeedCard extends StatelessWidget {
  const _AiFeedCard({required this.feed});

  final List<AiFeedItemModel> feed;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: TradingPalette.panelBorder.withOpacity(0.72)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Realtime AI Feed',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 10),
          ...feed.take(4).map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Container(
                        width: 10,
                        height: 10,
                        margin: const EdgeInsets.only(top: 6),
                        decoration: BoxDecoration(
                          color: _severityColor(item.severity),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              item.title,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodyMedium
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              item.detail,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }
}

class _GuidePill extends StatelessWidget {
  const _GuidePill({
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
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 3),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({
    required this.label,
    required this.value,
    required this.accent,
  });

  final String label;
  final String value;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: accent.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: accent,
                ),
          ),
        ],
      ),
    );
  }
}

class _CrosshairHud extends StatelessWidget {
  const _CrosshairHud({
    required this.chart,
    required this.geometry,
    required this.crosshair,
  });

  final MarketChartModel chart;
  final _ProChartGeometry geometry;
  final Offset crosshair;

  @override
  Widget build(BuildContext context) {
    final point = geometry.dataPointFor(crosshair);
    final candle = point.candle;
    final price = geometry.priceFor(crosshair.dy);
    return Positioned(
      left: 12,
      top: 12,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: const Color(0xE6111B33),
          borderRadius: BorderRadius.circular(16),
          border:
              Border.all(color: TradingPalette.panelBorder.withOpacity(0.8)),
        ),
        child: DefaultTextStyle(
          style: Theme.of(context).textTheme.bodySmall ?? const TextStyle(),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('${candle.timestampMs}'),
              Text(
                'O ${candle.open.toStringAsFixed(2)} H ${candle.high.toStringAsFixed(2)}',
              ),
              Text(
                'L ${candle.low.toStringAsFixed(2)} C ${candle.close.toStringAsFixed(2)}',
              ),
              Text('Crosshair ${price.toStringAsFixed(2)}'),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProTradingChartPainter extends CustomPainter {
  const _ProTradingChartPainter({
    required this.chart,
    required this.activeTrades,
    required this.geometry,
    required this.pulse,
    required this.replayMode,
  });

  final MarketChartModel chart;
  final List<ActiveTradeModel> activeTrades;
  final _ProChartGeometry geometry;
  final double pulse;
  final bool replayMode;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Rect.fromLTWH(0, 0, size.width, size.height);
    canvas.drawRect(
      background,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            Color(0xFF0E1630),
            Color(0xFF0B1122),
            Color(0xFF060A15),
          ],
        ).createShader(background),
    );
    _paintGrid(canvas, size);
    _paintLiquidityHeatmap(canvas);
    _paintSmartMoneyZones(canvas);
    _paintOrderbookLadder(canvas);
    _paintOverlays(canvas);
    _paintPredictionProjection(canvas);
    _paintVolatilityCone(canvas);
    _paintVolume(canvas);
    _paintCandles(canvas);
    _paintConfidenceBands(canvas);
    _paintMarkers(canvas);
    _paintExecutionGuide(canvas);
    _paintActiveTrades(canvas);
    _paintAxisLabels(canvas, size);
  }

  void _paintGrid(Canvas canvas, Size size) {
    final gridPaint = Paint()
      ..color = TradingPalette.panelBorder.withOpacity(0.18)
      ..strokeWidth = 1;
    for (var step = 1; step <= 5; step += 1) {
      final y =
          geometry.priceTop + ((geometry.priceHeight / 6) * step.toDouble());
      canvas.drawLine(
        Offset(0, y),
        Offset(size.width, y),
        gridPaint,
      );
    }
    for (var step = 1; step <= 4; step += 1) {
      final x = (size.width / 5) * step.toDouble();
      canvas.drawLine(
        Offset(x, 0),
        Offset(x, geometry.priceBottom),
        gridPaint,
      );
    }
  }

  void _paintVolume(Canvas canvas) {
    final candleWidth = geometry.candleBodyWidth;
    final maxVolume = geometry.maxVolume <= 0 ? 1.0 : geometry.maxVolume;
    for (final point in geometry.visiblePoints) {
      final candle = point.candle;
      final bullish = candle.close >= candle.open;
      final color = bullish
          ? TradingPalette.neonGreen.withOpacity(0.38)
          : TradingPalette.neonRed.withOpacity(0.38);
      final height = (candle.volume / maxVolume) * geometry.volumeHeight;
      final rect = Rect.fromLTWH(
        point.center.dx - (candleWidth / 2),
        geometry.volumeBottom - height,
        candleWidth,
        height,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(3)),
        Paint()..color = color,
      );
    }
  }

  void _paintCandles(Canvas canvas) {
    final wickPaint = Paint()..strokeWidth = 1.2;
    for (final point in geometry.visiblePoints) {
      final candle = point.candle;
      final bullish = candle.close >= candle.open;
      final color = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
      wickPaint.color = color.withOpacity(0.95);
      final highY = geometry.yFor(candle.high);
      final lowY = geometry.yFor(candle.low);
      final openY = geometry.yFor(candle.open);
      final closeY = geometry.yFor(candle.close);
      canvas.drawLine(
        Offset(point.center.dx, highY),
        Offset(point.center.dx, lowY),
        wickPaint,
      );
      final rect = Rect.fromLTRB(
        point.center.dx - (geometry.candleBodyWidth / 2),
        math.min(openY, closeY),
        point.center.dx + (geometry.candleBodyWidth / 2),
        math.max(openY, closeY) + 1.5,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(4)),
        Paint()
          ..color = color.withOpacity(replayMode ? 0.74 : 0.96)
          ..maskFilter = bullish && chart.opportunity.momentumScore >= 70
              ? MaskFilter.blur(BlurStyle.normal, 1.2 + (pulse * 1.4))
              : null,
      );
    }
  }

  void _paintOverlays(Canvas canvas) {
    for (final overlay
        in geometry.visibleOverlays.take(chart.renderProfile.maxOverlays)) {
      final startX = geometry.xForTimestamp(overlay.startTs);
      final endX = geometry.xForTimestamp(overlay.endTs);
      final rect = Rect.fromLTRB(
        math.min(startX, endX),
        geometry.yFor(overlay.high),
        math.max(startX, endX),
        geometry.yFor(overlay.low),
      );
      final color = _overlayColor(overlay.style, overlay.side);
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(14)),
        Paint()..color = color.withOpacity(0.08 + (pulse * 0.05)),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(14)),
        Paint()
          ..color = color.withOpacity(0.26)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0,
      );
    }
  }

  void _paintLiquidityHeatmap(Canvas canvas) {
    for (final zone in geometry.visibleHeatmapZones) {
      final startX = geometry.xForTimestamp(zone.startTs);
      final endX = geometry.xForTimestamp(zone.endTs);
      final rect = Rect.fromLTRB(
        math.min(startX, endX),
        geometry.yFor(zone.high),
        math.max(startX, endX),
        geometry.yFor(zone.low),
      );
      if (rect.width <= 0 || rect.height <= 0) {
        continue;
      }
      final bullish = zone.side.toUpperCase() == 'BUY';
      final base = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
      final opacity = zone.opacity.clamp(0.06, 0.38).toDouble();
      final shader = LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: <Color>[
          base.withOpacity(0.02),
          base.withOpacity((opacity + pulse * 0.08).clamp(0.06, 0.48)),
          base.withOpacity(0.04),
        ],
      ).createShader(rect);
      canvas.drawRect(
        rect,
        Paint()
          ..shader = shader
          ..blendMode = BlendMode.plus,
      );
    }
  }

  void _paintOrderbookLadder(Canvas canvas) {
    final levels = chart.orderbookDepth.liquidityLadder
        .take(chart.renderProfile.maxDomLevels);
    if (levels.isEmpty || geometry.chartWidth <= 80) {
      return;
    }
    final right = geometry.chartWidth - 8;
    const maxWidth = 42.0;
    for (final level in levels) {
      final bidY = geometry.yFor(level.bidPrice);
      final askY = geometry.yFor(level.askPrice);
      final bidWidth = maxWidth * (level.intensity / 100).clamp(0.05, 1.0);
      final askWidth = maxWidth * (level.intensity / 100).clamp(0.05, 1.0);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(right - bidWidth, bidY - 2, bidWidth, 4),
          const Radius.circular(3),
        ),
        Paint()
          ..color = TradingPalette.neonGreen.withOpacity(
            (0.12 + (level.intensity / 100) * 0.22)
                .clamp(0.12, 0.34)
                .toDouble(),
          ),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(right - askWidth, askY - 2, askWidth, 4),
          const Radius.circular(3),
        ),
        Paint()
          ..color = TradingPalette.neonRed.withOpacity(
            (0.12 + (level.intensity / 100) * 0.22)
                .clamp(0.12, 0.34)
                .toDouble(),
          ),
      );
    }
  }

  void _paintSmartMoneyZones(Canvas canvas) {
    if (geometry.visibleCandles.isEmpty) {
      return;
    }
    final biasColor = chart.opportunity.whalePressure >= 62
        ? (chart.executionGuide.side == 'SELL'
            ? TradingPalette.neonRed
            : TradingPalette.neonGreen)
        : TradingPalette.electricBlue;
    final height = geometry.priceHeight * 0.16;
    final centerY = geometry.yFor(chart.latestPrice);
    final rect = Rect.fromLTRB(
      0,
      (centerY - height / 2).clamp(geometry.priceTop, geometry.priceBottom),
      geometry.chartWidth,
      (centerY + height / 2).clamp(geometry.priceTop, geometry.priceBottom),
    );
    canvas.drawRect(
      rect,
      Paint()
        ..shader = LinearGradient(
          colors: <Color>[
            biasColor.withOpacity(0.00),
            biasColor.withOpacity(0.06 + pulse * 0.04),
            biasColor.withOpacity(0.00),
          ],
        ).createShader(rect),
    );
    _drawText(
      canvas,
      chart.opportunity.whalePressure >= 62
          ? 'Smart money zone'
          : 'Institutional reaction zone',
      Offset(12, rect.top + 8),
      biasColor,
      weight: FontWeight.w800,
      size: 11,
    );
  }

  void _paintMarkers(Canvas canvas) {
    for (final marker in geometry.visibleMarkers.take(32)) {
      final point = geometry.pointForMarker(marker);
      final accent = marker.markerStyle == 'ghost'
          ? TradingPalette.textMuted
          : marker.markerType.contains('SELL') ||
                  marker.side.toUpperCase() == 'SELL'
              ? TradingPalette.neonRed
              : TradingPalette.neonGreen;
      canvas.drawCircle(
        point,
        8.0 + (pulse * 5.0),
        Paint()..color = accent.withOpacity(0.12 + (pulse * 0.10)),
      );
      canvas.drawCircle(
        point,
        5.5,
        Paint()..color = accent.withOpacity(0.30),
      );
      final path = Path();
      if (marker.side.toUpperCase() == 'SELL' ||
          marker.markerType.contains('RESISTANCE')) {
        path
          ..moveTo(point.dx, point.dy + 6)
          ..lineTo(point.dx - 5, point.dy - 4)
          ..lineTo(point.dx + 5, point.dy - 4)
          ..close();
      } else {
        path
          ..moveTo(point.dx, point.dy - 6)
          ..lineTo(point.dx - 5, point.dy + 4)
          ..lineTo(point.dx + 5, point.dy + 4)
          ..close();
      }
      canvas.drawPath(path, Paint()..color = accent);
    }
  }

  void _paintConfidenceBands(Canvas canvas) {
    for (final interval in chart.confidenceIntervals.take(24)) {
      final startX = geometry.xForTimestamp(interval.startTs);
      final endX = geometry.xForTimestamp(interval.endTs);
      if ((endX - startX).abs() < 2) {
        continue;
      }
      final color = interval.score >= 75
          ? TradingPalette.neonGreen
          : interval.score >= 55
              ? TradingPalette.amber
              : TradingPalette.neonRed;
      final rect = Rect.fromLTRB(
        math.min(startX, endX),
        geometry.priceTop,
        math.max(startX, endX),
        geometry.priceBottom,
      );
      canvas.drawRect(
        rect,
        Paint()..color = color.withOpacity(0.025 + interval.score / 5000),
      );
    }
  }

  void _paintPredictionProjection(Canvas canvas) {
    if (geometry.visiblePoints.length < 4) {
      return;
    }
    final last = geometry.visiblePoints.last;
    final guide = chart.executionGuide;
    final target = guide.tp2 > 0
        ? guide.tp2
        : chart.latestPrice * (1 + (chart.changePct >= 0 ? 0.015 : -0.015));
    final targetY = geometry.yFor(target);
    final start = Offset(last.center.dx, geometry.yFor(last.candle.close));
    final end = Offset(geometry.chartWidth - 16, targetY);
    final control = Offset(
      (start.dx + end.dx) / 2,
      math.min(start.dy, end.dy) - 34 - (pulse * 14),
    );
    final path = Path()
      ..moveTo(start.dx, start.dy)
      ..quadraticBezierTo(control.dx, control.dy, end.dx, end.dy);
    final accent = chart.changePct >= 0
        ? TradingPalette.neonGreen
        : TradingPalette.neonRed;
    canvas.drawPath(
      path,
      Paint()
        ..color = accent.withOpacity(0.28)
        ..strokeWidth = 8
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = accent.withOpacity(0.72)
        ..strokeWidth = 1.8
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
    _drawText(
      canvas,
      replayMode ? 'Replay path' : 'AI projection',
      Offset(math.max(end.dx - 92, 8), end.dy - 20),
      accent,
      weight: FontWeight.w800,
      size: 11,
    );
  }

  void _paintVolatilityCone(Canvas canvas) {
    if (geometry.visiblePoints.length < 5) {
      return;
    }
    final last = geometry.visiblePoints.last;
    final volatility =
        (chart.opportunity.volatilityScore / 100).clamp(0.12, 1.0);
    final startX = last.center.dx;
    final endX = geometry.chartWidth;
    final startY = geometry.yFor(last.candle.close);
    final spread = geometry.priceHeight * (0.05 + volatility * 0.12);
    final cone = Path()
      ..moveTo(startX, startY)
      ..lineTo(endX, startY - spread)
      ..lineTo(endX, startY + spread)
      ..close();
    canvas.drawPath(
      cone,
      Paint()
        ..shader = LinearGradient(
          colors: <Color>[
            TradingPalette.electricBlue.withOpacity(0.12),
            TradingPalette.electricBlue.withOpacity(0.00),
          ],
        ).createShader(
            Rect.fromLTRB(startX, startY - spread, endX, startY + spread)),
    );
  }

  void _paintExecutionGuide(Canvas canvas) {
    final guide = chart.executionGuide;
    final entryLowY = geometry.yFor(guide.entryLow);
    final entryHighY = geometry.yFor(guide.entryHigh);
    final stopY = geometry.yFor(guide.stopLoss);
    final tp1Y = geometry.yFor(guide.tp1);
    final tp2Y = geometry.yFor(guide.tp2);
    canvas.drawRect(
      Rect.fromLTRB(0, math.min(entryLowY, entryHighY), geometry.chartWidth,
          math.max(entryLowY, entryHighY)),
      Paint()..color = TradingPalette.electricBlue.withOpacity(0.08),
    );
    for (final line in <({double y, Color color, double width})>[
      (y: stopY, color: TradingPalette.neonRed, width: 1.1),
      (y: tp1Y, color: TradingPalette.amber, width: 1.1),
      (y: tp2Y, color: TradingPalette.neonGreen, width: 1.2),
    ]) {
      canvas.drawLine(
        Offset(0, line.y),
        Offset(geometry.chartWidth, line.y),
        Paint()
          ..color = line.color.withOpacity(0.75)
          ..strokeWidth = line.width,
      );
    }
    _drawPriceTag(canvas, 'ENTRY', (entryLowY + entryHighY) / 2,
        TradingPalette.electricBlue);
    _drawPriceTag(canvas, 'SL', stopY, TradingPalette.neonRed);
    _drawPriceTag(canvas, 'TP1', tp1Y, TradingPalette.amber);
    _drawPriceTag(canvas, 'TP2', tp2Y, TradingPalette.neonGreen);
    final path = chart.trailingStop.path;
    if (path.length >= 2) {
      final trailPath = Path();
      for (var index = 0; index < path.length; index += 1) {
        final x = geometry.chartWidth *
            (index / math.max(path.length - 1, 1)).toDouble();
        final y = geometry.yFor(path[index].price);
        if (index == 0) {
          trailPath.moveTo(x, y);
        } else {
          trailPath.lineTo(x, y);
        }
      }
      canvas.drawPath(
        trailPath,
        Paint()
          ..color = TradingPalette.violet.withOpacity(0.92)
          ..strokeWidth = 1.4
          ..style = PaintingStyle.stroke,
      );
      _drawPriceTag(
        canvas,
        'TRAIL',
        geometry.yFor(path.last.price),
        TradingPalette.violet,
      );
    }
  }

  void _paintActiveTrades(Canvas canvas) {
    for (final trade in activeTrades
        .where(
            (item) => item.symbol.toUpperCase() == chart.symbol.toUpperCase())
        .take(3)) {
      final bullish = trade.side.toUpperCase() != 'SELL';
      final color = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
      final entryY = geometry.yFor(trade.entry);
      canvas.drawLine(
        Offset(0, entryY),
        Offset(geometry.chartWidth, entryY),
        Paint()
          ..color = color.withOpacity(0.58)
          ..strokeWidth = 1.3,
      );
      _drawPriceTag(canvas, 'ACTIVE', entryY, color);
    }
  }

  void _drawPriceTag(Canvas canvas, String label, double y, Color color) {
    if (y.isNaN || y.isInfinite) {
      return;
    }
    final clampedY = y.clamp(geometry.priceTop + 8, geometry.priceBottom - 8);
    final width = math.max(42.0, label.length * 8.0 + 14.0);
    final rect = Rect.fromLTWH(
      math.max(geometry.chartWidth - width - 8, 0),
      clampedY - 10,
      width,
      20,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(7)),
      Paint()..color = color.withOpacity(0.18),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(7)),
      Paint()
        ..color = color.withOpacity(0.55)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );
    _drawText(
      canvas,
      label,
      Offset(rect.left + 7, rect.top + 4),
      color,
      weight: FontWeight.w900,
      size: 10,
    );
  }

  void _paintAxisLabels(Canvas canvas, Size size) {
    final latest = chart.candles.isNotEmpty ? chart.candles.last : null;
    if (latest == null) {
      return;
    }
    _drawText(
      canvas,
      latest.close.toStringAsFixed(latest.close >= 100 ? 2 : 4),
      Offset(size.width - 92, geometry.yFor(latest.close) - 10),
      TradingPalette.textPrimary,
      weight: FontWeight.w700,
    );
    final visible = geometry.visibleCandles;
    if (visible.isEmpty) {
      return;
    }
    final timeSteps = <int>{
      0,
      visible.length ~/ 3,
      (visible.length * 2) ~/ 3,
      visible.length - 1,
    };
    for (final index in timeSteps) {
      final candle = visible[index];
      final x = geometry.xForTimestamp(candle.timestampMs);
      final time = DateTime.fromMillisecondsSinceEpoch(candle.timestampMs);
      final label =
          '${time.hour.toString().padLeft(2, '0')}:${time.minute.toString().padLeft(2, '0')}';
      _drawText(
        canvas,
        label,
        Offset(x - 18, geometry.volumeBottom + 6),
        TradingPalette.textMuted,
      );
    }
  }

  void _drawText(
    Canvas canvas,
    String text,
    Offset offset,
    Color color, {
    FontWeight weight = FontWeight.w500,
    double size = 11,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: size,
          fontWeight: weight,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, offset);
  }

  @override
  bool shouldRepaint(covariant _ProTradingChartPainter oldDelegate) {
    return oldDelegate.chart != chart ||
        oldDelegate.activeTrades != activeTrades ||
        oldDelegate.geometry != geometry ||
        oldDelegate.pulse != pulse ||
        oldDelegate.replayMode != replayMode;
  }
}

class _CrosshairPainter extends CustomPainter {
  const _CrosshairPainter({
    required this.geometry,
    required this.crosshair,
  });

  final _ProChartGeometry geometry;
  final Offset crosshair;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withOpacity(0.42)
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(crosshair.dx, geometry.priceTop),
      Offset(crosshair.dx, geometry.volumeBottom),
      paint,
    );
    canvas.drawLine(
      Offset(0, crosshair.dy),
      Offset(geometry.chartWidth, crosshair.dy),
      paint,
    );
  }

  @override
  bool shouldRepaint(covariant _CrosshairPainter oldDelegate) {
    return oldDelegate.crosshair != crosshair ||
        oldDelegate.geometry != geometry;
  }
}

class _ProChartGeometry {
  _ProChartGeometry({
    required MarketChartModel chart,
    required List<ActiveTradeModel> activeTrades,
    required Size size,
    required double zoomX,
    required double windowPosition,
  })  : chartWidth = size.width,
        chartHeight = size.height,
        priceTop = 0,
        priceHeight = size.height * 0.76,
        priceBottom = size.height * 0.76,
        volumeTop = size.height * 0.80,
        volumeHeight = size.height * 0.20 - 14,
        volumeBottom = size.height - 4,
        visibleCandles = _visibleCandles(
          chart.candles,
          zoomX,
          windowPosition,
          _maxVisibleCandles(chart.renderHints),
        ),
        visiblePoints = <_VisiblePoint>[] {
    final visibleStartTs =
        visibleCandles.isEmpty ? 0 : visibleCandles.first.timestampMs;
    final visibleEndTs =
        visibleCandles.isEmpty ? 0 : visibleCandles.last.timestampMs;
    final viewportIndex = ChartViewportIndex(
      visibleStartTs: visibleStartTs,
      visibleEndTs: visibleEndTs,
    );
    visibleOverlays = viewportIndex.overlays(chart.overlays);
    visibleMarkers = viewportIndex.markers(chart.markers);
    visibleHeatmapZones = _visibleHeatmapZones(
      chart.liquidityHeatmap.heatmapZones,
      visibleStartTs,
      visibleEndTs,
    );
    final levels = <double>[
      ...visibleCandles.expand((c) => <double>[c.low, c.high]),
      for (final zone in visibleHeatmapZones) ...<double>[zone.low, zone.high],
      for (final overlay in visibleOverlays) ...<double>[
        overlay.low,
        overlay.high
      ],
      chart.executionGuide.stopLoss,
      chart.executionGuide.tp1,
      chart.executionGuide.tp2,
      chart.executionGuide.entryLow,
      chart.executionGuide.entryHigh,
      for (final trade in activeTrades.where((item) =>
          item.symbol.toUpperCase() == chart.symbol.toUpperCase())) ...<double>[
        trade.entry,
        trade.stopLoss,
        trade.takeProfit
      ],
    ].where((value) => value > 0).toList();
    minPrice = levels.isEmpty ? 0 : levels.reduce(math.min);
    maxPrice = levels.isEmpty ? 1 : levels.reduce(math.max);
    if ((maxPrice - minPrice).abs() < 0.000001) {
      maxPrice = minPrice + 1;
    }
    final padding = (maxPrice - minPrice) * 0.08;
    minPrice -= padding;
    maxPrice += padding;
    maxVolume = visibleCandles.isEmpty
        ? 1
        : visibleCandles.map((item) => item.volume).reduce(math.max);
    final gap = visibleCandles.isEmpty
        ? 0.0
        : chartWidth / math.max(visibleCandles.length, 1);
    candleBodyWidth = math.max(3.5, gap * 0.56);
    for (var index = 0; index < visibleCandles.length; index += 1) {
      visiblePoints.add(
        _VisiblePoint(
          candle: visibleCandles[index],
          center: Offset((gap * index) + (gap / 2), 0),
        ),
      );
    }
  }

  final double chartWidth;
  final double chartHeight;
  final double priceTop;
  final double priceHeight;
  final double priceBottom;
  final double volumeTop;
  final double volumeHeight;
  final double volumeBottom;
  final List<MarketCandleModel> visibleCandles;
  late final List<MarketOverlayModel> visibleOverlays;
  late final List<TradeMarkerModel> visibleMarkers;
  late final List<LiquidityHeatmapZoneModel> visibleHeatmapZones;
  final List<_VisiblePoint> visiblePoints;
  late double minPrice;
  late double maxPrice;
  late final double maxVolume;
  late final double candleBodyWidth;

  Offset clampPoint(Offset point) {
    return Offset(
      point.dx.clamp(0.0, chartWidth),
      point.dy.clamp(priceTop, volumeBottom),
    );
  }

  double yFor(double price) {
    final ratio = (price - minPrice) / math.max(maxPrice - minPrice, 0.000001);
    return priceBottom - (ratio * priceHeight);
  }

  double priceFor(double y) {
    final ratio =
        ((priceBottom - y) / math.max(priceHeight, 1)).clamp(0.0, 1.0);
    return minPrice + ((maxPrice - minPrice) * ratio);
  }

  double xForTimestamp(int timestampMs) {
    if (visibleCandles.isEmpty) {
      return 0;
    }
    var index = 0;
    var bestDelta = double.infinity;
    for (var i = 0; i < visibleCandles.length; i += 1) {
      final delta =
          (visibleCandles[i].timestampMs - timestampMs).abs().toDouble();
      if (delta < bestDelta) {
        bestDelta = delta;
        index = i;
      }
    }
    return visiblePoints[index].center.dx;
  }

  Offset pointForMarker(TradeMarkerModel marker) {
    return Offset(
      xForTimestamp(marker.timestamp.millisecondsSinceEpoch),
      yFor(marker.price),
    );
  }

  _ChartDataPoint dataPointFor(Offset position) {
    if (visiblePoints.isEmpty) {
      return const _ChartDataPoint(
        candle: MarketCandleModel(
          timestampMs: 0,
          open: 0,
          high: 0,
          low: 0,
          close: 0,
          volume: 0,
        ),
        index: 0,
      );
    }
    var bestIndex = 0;
    var bestDelta = double.infinity;
    for (var index = 0; index < visiblePoints.length; index += 1) {
      final delta = (visiblePoints[index].center.dx - position.dx).abs();
      if (delta < bestDelta) {
        bestDelta = delta;
        bestIndex = index;
      }
    }
    return _ChartDataPoint(
      candle: visibleCandles[bestIndex],
      index: bestIndex,
    );
  }

  static List<MarketCandleModel> _visibleCandles(
    List<MarketCandleModel> candles,
    double zoomX,
    double windowPosition,
    int maxVisibleCandles,
  ) {
    if (candles.isEmpty) {
      return const <MarketCandleModel>[];
    }
    final visibleCount = math.max(
      24,
      math.min(
        math.min(candles.length, maxVisibleCandles),
        (candles.length / zoomX).round(),
      ),
    );
    final maxStart = math.max(0, candles.length - visibleCount);
    final start = (windowPosition * maxStart).round().clamp(0, maxStart);
    final end = math.min(candles.length, start + visibleCount);
    return candles.sublist(start, end);
  }

  static int _maxVisibleCandles(Map<String, dynamic> renderHints) {
    final raw = renderHints['max_visible_candles'];
    final value =
        raw is num ? raw.toInt() : int.tryParse(raw?.toString() ?? '');
    return (value ?? 140).clamp(48, 240).toInt();
  }

  static List<LiquidityHeatmapZoneModel> _visibleHeatmapZones(
    List<LiquidityHeatmapZoneModel> zones,
    int visibleStartTs,
    int visibleEndTs,
  ) {
    if (zones.isEmpty) {
      return const <LiquidityHeatmapZoneModel>[];
    }
    final filtered = zones
        .where((zone) =>
            visibleStartTs <= 0 ||
            visibleEndTs <= 0 ||
            (zone.endTs >= visibleStartTs && zone.startTs <= visibleEndTs))
        .toList();
    filtered.sort((left, right) => right.intensity.compareTo(left.intensity));
    return filtered.take(24).toList(growable: false);
  }

  @override
  bool operator ==(Object other) {
    return other is _ProChartGeometry &&
        other.chartWidth == chartWidth &&
        other.chartHeight == chartHeight &&
        other.minPrice == minPrice &&
        other.maxPrice == maxPrice &&
        other.visibleCandles.length == visibleCandles.length &&
        other.visibleOverlays.length == visibleOverlays.length &&
        other.visibleHeatmapZones.length == visibleHeatmapZones.length &&
        other.visibleMarkers.length == visibleMarkers.length;
  }

  @override
  int get hashCode => Object.hash(
        chartWidth,
        chartHeight,
        minPrice,
        maxPrice,
        visibleCandles.length,
        visibleOverlays.length,
        visibleHeatmapZones.length,
        visibleMarkers.length,
      );
}

class _VisiblePoint {
  const _VisiblePoint({
    required this.candle,
    required this.center,
  });

  final MarketCandleModel candle;
  final Offset center;
}

class _ChartDataPoint {
  const _ChartDataPoint({
    required this.candle,
    required this.index,
  });

  final MarketCandleModel candle;
  final int index;
}

String _formatMode(String mode) {
  return mode.replaceAll('_', ' ');
}

Color _regimeColor(String regime) {
  switch (regime) {
    case 'TRENDING':
      return TradingPalette.neonGreen;
    case 'HIGH_VOLATILITY':
      return TradingPalette.amber;
    case 'LOW_LIQUIDITY':
      return TradingPalette.neonRed;
    case 'CHOPPY':
      return TradingPalette.violet;
    default:
      return TradingPalette.electricBlue;
  }
}

Color _severityColor(String severity) {
  switch (severity) {
    case 'high':
      return TradingPalette.neonGreen;
    case 'medium':
      return TradingPalette.amber;
    default:
      return TradingPalette.textMuted;
  }
}

Color _overlayColor(String style, String side) {
  switch (style) {
    case 'reward':
      return TradingPalette.neonGreen;
    case 'risk':
      return TradingPalette.neonRed;
    case 'trail':
      return TradingPalette.violet;
    case 'warning':
      return TradingPalette.amber;
    case 'accent':
      return TradingPalette.electricBlue;
    case 'bullish':
      return TradingPalette.neonGreen;
    case 'bearish':
      return TradingPalette.neonRed;
    default:
      return side.toUpperCase() == 'SELL'
          ? TradingPalette.neonRed
          : TradingPalette.electricBlue;
  }
}

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/trading_palette.dart';
import '../controllers/execution_controller.dart';
import '../models/risk_coach_models.dart';
import '../providers/risk_coach_providers.dart';


class RiskCoachTerminal extends StatefulWidget {
  const RiskCoachTerminal({
    super.key,
    required this.state,
    required this.executionState,
    required this.onCreateTrade,
    required this.onCloseTrade,
    required this.onPanicClose,
    required this.onTradeLevelChanged,
  });

  final RiskCoachTerminalState state;
  final ExecutionDraft executionState;
  final Future<void> Function() onCreateTrade;
  final Future<void> Function() onCloseTrade;
  final Future<void> Function() onPanicClose;
  final Future<void> Function({
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) onTradeLevelChanged;

  @override
  State<RiskCoachTerminal> createState() => _RiskCoachTerminalState();
}


class _RiskCoachTerminalState extends State<RiskCoachTerminal> {
  double _panicSlider = 0;

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final trade = widget.executionState.trade ?? state.trade;
    if (state.isLoading) {
      return Column(
        children: List<Widget>.generate(
          4,
          (index) => Container(
            height: index == 1 ? 300 : 56,
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: TradingPalette.panelSoft,
              borderRadius: BorderRadius.circular(22),
            ),
          ),
        ),
      );
    }
    if (state.candles.isEmpty) {
      return const _NoticeCard(message: 'Offline fallback active. Market feed unavailable right now.');
    }
    final latest = state.candles.last.close;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: <Widget>[
            _MetricChip(label: 'Feed', value: state.connectionState.toUpperCase()),
            _MetricChip(label: 'Source', value: state.source),
            _MetricChip(label: 'Last', value: latest.toStringAsFixed(2)),
            _MetricChip(
              label: 'Heatmap',
              value: '${((state.heatmap?.intensity ?? 0) * 100).toStringAsFixed(0)}%',
              accent: _heatmapColor(state.heatmap?.state ?? 'neutral'),
            ),
          ],
        ),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: TradingPalette.panelSoft,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: TradingPalette.panelBorder),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Educational Risk Terminal',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 6),
              Text(
                state.disclaimer,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: TradingPalette.textMuted),
              ),
              const SizedBox(height: 18),
              SizedBox(
                height: 360,
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return _DragChart(
                      candles: state.candles,
                      trade: trade,
                      heatmap: state.heatmap,
                      connectionState: state.connectionState,
                      onTradeLevelChanged: widget.onTradeLevelChanged,
                    );
                  },
                ),
              ),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: <Widget>[
                  FilledButton.tonalIcon(
                    onPressed: trade == null ? widget.onCreateTrade : null,
                    icon: const Icon(Icons.school_rounded),
                    label: const Text('Start Practice Trade'),
                  ),
                  FilledButton.tonalIcon(
                    onPressed: trade == null ? null : widget.onCloseTrade,
                    icon: const Icon(Icons.analytics_outlined),
                    label: const Text('Run Post-Mortem'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: <Widget>[
            _MetricChip(label: 'Position', value: (state.riskPlan?.positionSize ?? 0).toStringAsFixed(4)),
            _MetricChip(label: 'RR', value: (state.riskPlan?.effectiveRr ?? 0).toStringAsFixed(2)),
            _MetricChip(label: 'EV', value: (state.riskPlan?.expectedValue ?? 0).toStringAsFixed(2)),
            _MetricChip(label: 'Exec', value: widget.executionState.status),
            if (trade != null) _MetricChip(label: 'Trade', value: trade.tradeId.substring(0, 6)),
          ],
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: TradingPalette.panelSoft,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: TradingPalette.panelBorder),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('Panic Switch', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              const Text('Slide to liquidate practice positions. This is a coaching control, not a live broker action.'),
              Slider(
                value: _panicSlider,
                onChanged: (value) async {
                  setState(() => _panicSlider = value);
                  if (value >= 0.98) {
                    HapticFeedback.heavyImpact();
                    await widget.onPanicClose();
                    if (mounted) {
                      setState(() => _panicSlider = 0);
                    }
                  }
                },
              ),
            ],
          ),
        ),
        if (state.postMortem != null) ...<Widget>[
          const SizedBox(height: 16),
          _PostMortemCard(report: state.postMortem!),
        ],
      ],
    );
  }

  Color _heatmapColor(String state) {
    switch (state) {
      case 'glow':
        return TradingPalette.neonGreen;
      case 'warning':
        return TradingPalette.amber;
      default:
        return TradingPalette.electricBlue;
    }
  }
}


class _DragChart extends StatefulWidget {
  const _DragChart({
    required this.candles,
    required this.trade,
    required this.heatmap,
    required this.connectionState,
    required this.onTradeLevelChanged,
  });

  final List<RiskCoachCandle> candles;
  final RiskCoachTrade? trade;
  final HeatmapZoneModel? heatmap;
  final String connectionState;
  final Future<void> Function({
    double? entry,
    double? stopLoss,
    double? takeProfit,
  }) onTradeLevelChanged;

  @override
  State<_DragChart> createState() => _DragChartState();
}


class _DragChartState extends State<_DragChart> {
  String? _dragTarget;
  RiskCoachTrade? _previewTrade;

  @override
  Widget build(BuildContext context) {
    final trade = _previewTrade ?? widget.trade;
    return GestureDetector(
      onVerticalDragStart: trade == null
          ? null
          : (details) {
              final slY = _priceToY(trade.stopLoss);
              final tpY = _priceToY(trade.takeProfit);
              _dragTarget = (details.localPosition.dy - slY).abs() < (details.localPosition.dy - tpY).abs() ? 'sl' : 'tp';
            },
      onVerticalDragUpdate: trade == null
          ? null
          : (details) {
              if (_dragTarget == null) {
                return;
              }
              final nextPrice = _yToPrice(details.localPosition.dy);
              HapticFeedback.selectionClick();
              setState(() {
                _previewTrade = _dragTarget == 'sl'
                    ? trade.copyWith(stopLoss: nextPrice, state: 'pending')
                    : trade.copyWith(takeProfit: nextPrice, state: 'pending');
              });
            },
      onVerticalDragEnd: trade == null
          ? null
          : (_) async {
              final preview = _previewTrade;
              if (_dragTarget != null && preview != null) {
                await widget.onTradeLevelChanged(
                  stopLoss: _dragTarget == 'sl' ? preview.stopLoss : null,
                  takeProfit: _dragTarget == 'tp' ? preview.takeProfit : null,
                );
              }
              if (mounted) {
                setState(() {
                  _dragTarget = null;
                  _previewTrade = null;
                });
              }
            },
      child: CustomPaint(
        painter: _RiskCoachPainter(
          candles: widget.candles,
          trade: trade,
          heatmap: widget.heatmap,
          connectionState: widget.connectionState,
        ),
        child: const SizedBox.expand(),
      ),
    );
  }

  double _priceToY(double price) {
    final minPrice = widget.candles.map((e) => e.low).reduce(math.min);
    final maxPrice = widget.candles.map((e) => e.high).reduce(math.max);
    final span = math.max(maxPrice - minPrice, 1e-8);
    return ((maxPrice - price) / span) * 360;
  }

  double _yToPrice(double y) {
    final minPrice = widget.candles.map((e) => e.low).reduce(math.min);
    final maxPrice = widget.candles.map((e) => e.high).reduce(math.max);
    final ratio = (y / 360).clamp(0.0, 1.0);
    return maxPrice - ((maxPrice - minPrice) * ratio);
  }
}


class _RiskCoachPainter extends CustomPainter {
  _RiskCoachPainter({
    required this.candles,
    required this.trade,
    required this.heatmap,
    required this.connectionState,
  });

  final List<RiskCoachCandle> candles;
  final RiskCoachTrade? trade;
  final HeatmapZoneModel? heatmap;
  final String connectionState;

  final Paint _gridPaint = Paint()
    ..color = const Color(0xFF263454)
    ..strokeWidth = 1;
  final Paint _borderPaint = Paint()
    ..style = PaintingStyle.stroke
    ..strokeWidth = 1
    ..color = TradingPalette.panelBorder;
  final Paint _bullPaint = Paint()..color = TradingPalette.neonGreen;
  final Paint _bearPaint = Paint()..color = TradingPalette.neonRed;

  @override
  void paint(Canvas canvas, Size size) {
    final minPrice = candles.map((e) => e.low).reduce(math.min);
    final maxPrice = candles.map((e) => e.high).reduce(math.max);
    final span = math.max(maxPrice - minPrice, 1e-8);
    final gap = size.width / candles.length;
    final bodyWidth = gap * 0.62;

    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(22)),
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF121B33), Color(0xFF0A1021)],
        ).createShader(Offset.zero & size),
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(22)),
      _borderPaint,
    );

    for (var index = 1; index < 4; index += 1) {
      final y = size.height * (index / 4);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), _gridPaint);
    }

    if (heatmap != null) {
      final top = _mapY(heatmap!.endPrice, minPrice, span, size.height);
      final bottom = _mapY(heatmap!.startPrice, minPrice, span, size.height);
      final rect = Rect.fromLTRB(0, math.min(top, bottom), size.width, math.max(top, bottom));
      canvas.drawRect(
        rect,
        Paint()..color = _heatmapFill(heatmap!.state).withOpacity(heatmap!.intensity.clamp(0.08, 0.26)),
      );
    }

    for (var index = 0; index < candles.length; index += 1) {
      final candle = candles[index];
      final isBull = candle.close >= candle.open;
      final paint = isBull ? _bullPaint : _bearPaint;
      final x = (index * gap) + (gap / 2);
      final highY = _mapY(candle.high, minPrice, span, size.height);
      final lowY = _mapY(candle.low, minPrice, span, size.height);
      final openY = _mapY(candle.open, minPrice, span, size.height);
      final closeY = _mapY(candle.close, minPrice, span, size.height);
      canvas.drawLine(Offset(x, highY), Offset(x, lowY), paint..strokeWidth = 1.2);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTRB(
            x - (bodyWidth / 2),
            math.min(openY, closeY),
            x + (bodyWidth / 2),
            math.max(openY, closeY) + 1.5,
          ),
          const Radius.circular(4),
        ),
        paint,
      );
    }

    if (trade != null) {
      _drawExecutionLine(canvas, size, minPrice, span, trade!.entry, 'Entry', TradingPalette.electricBlue);
      _drawExecutionLine(canvas, size, minPrice, span, trade!.stopLoss, 'SL', TradingPalette.neonRed);
      _drawExecutionLine(canvas, size, minPrice, span, trade!.takeProfit, 'TP', TradingPalette.neonGreen);
    }

    if (connectionState != 'connected') {
      final painter = TextPainter(
        text: const TextSpan(
          text: 'Offline fallback',
          style: TextStyle(color: TradingPalette.amber, fontWeight: FontWeight.w700),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      painter.paint(canvas, Offset(size.width - painter.width - 16, 16));
    }
  }

  void _drawExecutionLine(Canvas canvas, Size size, double minPrice, double span, double price, String label, Color color) {
    final y = _mapY(price, minPrice, span, size.height);
    canvas.drawLine(
      Offset(0, y),
      Offset(size.width, y),
      Paint()
        ..color = color
        ..strokeWidth = 1.2,
    );
    final painter = TextPainter(
      text: TextSpan(
        text: '$label ${price.toStringAsFixed(2)}',
        style: TextStyle(color: color, fontWeight: FontWeight.w700, fontSize: 11),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    final rect = RRect.fromRectAndRadius(
      Rect.fromLTWH(size.width - painter.width - 22, y - 11, painter.width + 12, 22),
      const Radius.circular(999),
    );
    canvas.drawRRect(rect, Paint()..color = const Color(0xE6111830));
    painter.paint(canvas, Offset(size.width - painter.width - 16, y - (painter.height / 2)));
  }

  double _mapY(double price, double minPrice, double span, double height) {
    return ((minPrice + span - price) / span) * height;
  }

  Color _heatmapFill(String state) {
    switch (state) {
      case 'glow':
        return TradingPalette.neonGreen;
      case 'warning':
        return TradingPalette.amber;
      default:
        return TradingPalette.electricBlue;
    }
  }

  @override
  bool shouldRepaint(covariant _RiskCoachPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.trade != trade ||
        oldDelegate.heatmap != heatmap ||
        oldDelegate.connectionState != connectionState;
  }
}


class _PostMortemCard extends StatelessWidget {
  const _PostMortemCard({required this.report});

  final PostMortemReportModel report;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('Post-Mortem', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricChip(label: 'MFE R', value: report.mfeR.toStringAsFixed(2)),
              _MetricChip(label: 'MAE R', value: report.maeR.toStringAsFixed(2)),
              _MetricChip(label: 'Realized R', value: report.realizedRr.toStringAsFixed(2)),
            ],
          ),
          const SizedBox(height: 12),
          ...report.insights.map(
            (insight) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const Icon(Icons.fiber_manual_record_rounded, size: 14, color: TradingPalette.electricBlue),
                  const SizedBox(width: 8),
                  Expanded(child: Text(insight.message)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}


class _MetricChip extends StatelessWidget {
  const _MetricChip({
    required this.label,
    required this.value,
    this.accent,
  });

  final String label;
  final String value;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final color = accent ?? TradingPalette.electricBlue;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.32)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w800)),
        ],
      ),
    );
  }
}


class _NoticeCard extends StatelessWidget {
  const _NoticeCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Text(message),
    );
  }
}

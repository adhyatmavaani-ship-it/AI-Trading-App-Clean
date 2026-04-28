import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/activity/providers/activity_providers.dart';
import '../features/market/providers/market_providers.dart';
import '../models/activity.dart';
import '../models/market_summary.dart';
import 'section_card.dart';
import 'state_widgets.dart';

class MarketSentimentGauge extends ConsumerWidget {
  const MarketSentimentGauge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summaryAsync = ref.watch(marketSummaryProvider);
    final selectedSymbol = ref.watch(selectedMarketSymbolProvider);
    final readinessBoard = ref.watch(readinessBoardProvider);
    return summaryAsync.when(
      data: (summary) => _AnimatedSentimentShell(
        summary: summary,
        readinessBoard: readinessBoard,
        selectedSymbol: selectedSymbol,
        onSelectSymbol: (symbol) =>
            ref.read(selectedMarketSymbolProvider.notifier).state = symbol,
      ),
      loading: () => SectionCard(
        title: 'Market Sentiment',
        trailing: _gaugePill(),
        child: const SizedBox(
          height: 260,
          child: LoadingState(label: 'Scanning market sentiment'),
        ),
      ),
      error: (error, _) => SectionCard(
        title: 'Market Sentiment',
        trailing: _gaugePill(),
        child: ErrorState(message: error.toString()),
      ),
    );
  }
}

class _AnimatedSentimentShell extends StatefulWidget {
  const _AnimatedSentimentShell({
    required this.summary,
    required this.readinessBoard,
    required this.selectedSymbol,
    required this.onSelectSymbol,
  });

  final MarketSummaryModel summary;
  final List<ReadinessCardModel> readinessBoard;
  final String selectedSymbol;
  final ValueChanged<String> onSelectSymbol;

  @override
  State<_AnimatedSentimentShell> createState() => _AnimatedSentimentShellState();
}

class _AnimatedSentimentShellState extends State<_AnimatedSentimentShell>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scannerAverage = widget.summary.scanner.averagePotentialScore;
    final extremePulse = scannerAverage >= 85;
    final effectiveScore = _effectiveSentimentScore(
      sentimentScore: widget.summary.sentimentScore,
      scannerAverage: scannerAverage,
    );
    final effectiveLabel = _effectiveSentimentLabel(
      widget.summary.sentimentLabel,
      scannerAverage,
    );
    final sentimentColor = _sentimentColor(effectiveScore);

    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final pulse = extremePulse ? _controller.value : 0.0;
        final glowStrength = extremePulse ? (0.18 + (pulse * 0.16)) : 0.0;
        return SectionCard(
          title: 'Market Sentiment',
          trailing: _gaugePill(label: extremePulse ? 'Extreme Pulse' : 'AI Pulse Gauge'),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 320),
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(26),
              border: Border.all(
                color: extremePulse
                    ? TradingPalette.neonGreen.withOpacity(0.55 + (pulse * 0.25))
                    : Colors.transparent,
                width: extremePulse ? 1.5 : 0,
              ),
              boxShadow: extremePulse
                  ? <BoxShadow>[
                      BoxShadow(
                        color: TradingPalette.neonGreen.withOpacity(glowStrength),
                        blurRadius: 28 + (pulse * 10),
                        spreadRadius: 1 + (pulse * 2),
                      ),
                    ]
                  : const <BoxShadow>[],
            ),
            child: _GaugeBody(
              summary: widget.summary,
              readinessBoard: widget.readinessBoard,
              selectedSymbol: widget.selectedSymbol,
              onSelectSymbol: widget.onSelectSymbol,
              effectiveScore: effectiveScore,
              effectiveLabel: effectiveLabel,
              sentimentColor: sentimentColor,
              pulseValue: pulse,
              extremePulse: extremePulse,
            ),
          ),
        );
      },
    );
  }
}

class _GaugeBody extends StatelessWidget {
  const _GaugeBody({
    required this.summary,
    required this.readinessBoard,
    required this.selectedSymbol,
    required this.onSelectSymbol,
    required this.effectiveScore,
    required this.effectiveLabel,
    required this.sentimentColor,
    required this.pulseValue,
    required this.extremePulse,
  });

  final MarketSummaryModel summary;
  final List<ReadinessCardModel> readinessBoard;
  final String selectedSymbol;
  final ValueChanged<String> onSelectSymbol;
  final double effectiveScore;
  final String effectiveLabel;
  final Color sentimentColor;
  final double pulseValue;
  final bool extremePulse;

  @override
  Widget build(BuildContext context) {
    final scannerAccent = _scannerAverageColor(summary.scanner.averagePotentialScore);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          height: 180,
          child: Row(
            children: <Widget>[
              Expanded(
                flex: 5,
                child: CustomPaint(
                  painter: _GaugePainter(
                    score: effectiveScore,
                    accent: sentimentColor,
                    wobble: extremePulse ? ((pulseValue - 0.5) * 0.08) : 0.0,
                    pulse: pulseValue,
                    extremePulse: extremePulse,
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: <Widget>[
                        Text(
                          effectiveLabel,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                color: sentimentColor,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          effectiveScore.toStringAsFixed(0),
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: TradingPalette.textPrimary,
                              ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Scanner ${summary.scanner.averagePotentialScore.toStringAsFixed(0)}',
                          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                                color: scannerAccent,
                                fontWeight: FontWeight.w700,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 4,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    _MiniMetric(
                      label: 'Refresh',
                      value: _formatCountdown(summary.scanner.secondsUntilRotation),
                      accent: scannerAccent,
                    ),
                    const SizedBox(height: 12),
                    _MiniMetric(
                      label: 'Breadth',
                      value: '${(summary.marketBreadth * 100).toStringAsFixed(0)}%',
                    ),
                    const SizedBox(height: 12),
                    _MiniMetric(
                      label: 'Scanner Avg',
                      value: summary.scanner.averagePotentialScore.toStringAsFixed(0),
                      accent: scannerAccent,
                    ),
                    const SizedBox(height: 12),
                    _MiniMetric(
                      label: 'Confidence',
                      value: '${(summary.confidenceScore * 100).toStringAsFixed(0)}%',
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (summary.scanner.hasScannerData) ...<Widget>[
          Text(
            'Live scanner',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Scanner refreshing in ${_formatCountdown(summary.scanner.secondsUntilRotation)}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: summary.scanner.candidates
                  .take(10)
                  .map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(right: 12),
                      child: _ScannerCoinCard(
                        item: item,
                        history: _scannerHistoryForSymbol(
                          symbol: item.symbol,
                          readinessBoard: readinessBoard,
                          summaryHistory: summary.confidenceHistory,
                        ),
                        selected: item.symbol == selectedSymbol,
                        onTap: () => onSelectSymbol(item.symbol),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ),
          const SizedBox(height: 16),
        ],
        Text(
          'Live ticker',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: summary.ticker
                .map((item) => Padding(
                      padding: const EdgeInsets.only(right: 10),
                      child: _TickerChip(item: item),
                    ))
                .toList(),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'Heatmap pulse',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: summary.heatmap
              .map((item) => _HeatmapCell(item: item))
              .toList(),
        ),
      ],
    );
  }
}

class _MiniMetric extends StatelessWidget {
  const _MiniMetric({
    required this.label,
    required this.value,
    this.accent,
  });

  final String label;
  final String value;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: (accent ?? TradingPalette.panelBorder)
              .withOpacity(accent == null ? 1 : 0.35),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: accent ?? TradingPalette.textPrimary,
                ),
          ),
        ],
      ),
    );
  }
}

class _ScannerCoinCard extends StatelessWidget {
  const _ScannerCoinCard({
    required this.item,
    required this.history,
    required this.selected,
    required this.onTap,
  });

  final ScannerCandidateModel item;
  final List<ConfidenceHistoryPointModel> history;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final accent = _scannerAverageColor(item.potentialScore);
    final progress = (item.potentialScore / 100).clamp(0.0, 1.0);
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        width: 164,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? accent : TradingPalette.panelBorder,
          ),
          gradient: LinearGradient(
            colors: <Color>[
              selected ? accent.withOpacity(0.18) : TradingPalette.panelSoft,
              const Color(0xCC0E1630),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: accent.withOpacity(selected ? 0.18 : 0.08),
              blurRadius: selected ? 18 : 10,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    item.symbol,
                    style: const TextStyle(
                      color: TradingPalette.textPrimary,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                if (item.isHot)
                  const _BreathingHotBadge(accent: TradingPalette.neonRed),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              '${item.potentialScore.toStringAsFixed(0)} score',
              style: TextStyle(
                color: accent,
                fontSize: 18,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}% | Spike ${item.volumeSpikePct.toStringAsFixed(0)}%',
              style: const TextStyle(
                color: TradingPalette.textMuted,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (history.length >= 2) ...<Widget>[
              const SizedBox(height: 10),
              Row(
                children: <Widget>[
                  Expanded(
                    child: SizedBox(
                      height: 18,
                      child: _ScannerMicroSparkline(
                        history: history,
                        selected: selected,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    _microTrendLabel(history),
                    style: TextStyle(
                      color: _microTrendColor(history),
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 8,
                backgroundColor: TradingPalette.panelBorder,
                valueColor: AlwaysStoppedAnimation<Color>(accent),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              selected ? 'Tap active on chart' : 'Tap to load chart',
              style: TextStyle(
                color: selected ? accent : TradingPalette.textMuted,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ScannerMicroSparkline extends StatefulWidget {
  const _ScannerMicroSparkline({
    required this.history,
    required this.selected,
  });

  final List<ConfidenceHistoryPointModel> history;
  final bool selected;

  @override
  State<_ScannerMicroSparkline> createState() => _ScannerMicroSparklineState();
}

class _ScannerMicroSparklineState extends State<_ScannerMicroSparkline>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return CustomPaint(
          painter: _ScannerMicroSparklinePainter(
            history: widget.history,
            reveal: Curves.easeOutCubic.transform(_controller.value),
            selected: widget.selected,
          ),
          child: const SizedBox.expand(),
        );
      },
    );
  }
}

class _ScannerMicroSparklinePainter extends CustomPainter {
  const _ScannerMicroSparklinePainter({
    required this.history,
    required this.reveal,
    required this.selected,
  });

  final List<ConfidenceHistoryPointModel> history;
  final double reveal;
  final bool selected;

  @override
  void paint(Canvas canvas, Size size) {
    if (history.length < 2 || size.width <= 0 || size.height <= 0) {
      return;
    }
    final points = _historyLinePoints(history, size);
    if (points.length < 2) {
      return;
    }
    final accent = _microTrendColor(history);
    final linePath = Path()..moveTo(points.first.dx, points.first.dy);
    for (var index = 1; index < points.length; index += 1) {
      final previous = points[index - 1];
      final current = points[index];
      final controlX = (previous.dx + current.dx) / 2;
      linePath.quadraticBezierTo(controlX, previous.dy, current.dx, current.dy);
    }

    final clipWidth = size.width * reveal;
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, clipWidth, size.height));
    canvas.drawPath(
      linePath,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = selected ? 2.3 : 1.9
        ..strokeCap = StrokeCap.round
        ..color = accent,
    );
    canvas.restore();

    final lastVisibleX = math.min(points.last.dx, clipWidth);
    if (lastVisibleX >= points.first.dx) {
      final lastPoint = points.last;
      if (lastPoint.dx <= clipWidth) {
        canvas.drawCircle(
          lastPoint,
          selected ? 2.8 : 2.3,
          Paint()
            ..color = accent.withOpacity(0.9)
            ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _ScannerMicroSparklinePainter oldDelegate) {
    return oldDelegate.history != history ||
        oldDelegate.reveal != reveal ||
        oldDelegate.selected != selected;
  }
}

class _BreathingHotBadge extends StatefulWidget {
  const _BreathingHotBadge({required this.accent});

  final Color accent;

  @override
  State<_BreathingHotBadge> createState() => _BreathingHotBadgeState();
}

class _BreathingHotBadgeState extends State<_BreathingHotBadge>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final scale = 0.96 + (_controller.value * 0.12);
        return Transform.scale(
          scale: scale,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: widget.accent.withOpacity(0.14),
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: widget.accent.withOpacity(0.35)),
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: widget.accent.withOpacity(0.14 + (_controller.value * 0.12)),
                  blurRadius: 12 + (_controller.value * 6),
                ),
              ],
            ),
            child: const Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  Icons.local_fire_department_rounded,
                  size: 12,
                  color: TradingPalette.neonRed,
                ),
                SizedBox(width: 4),
                Text(
                  'Hot',
                  style: TextStyle(
                    color: TradingPalette.neonRed,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _TickerChip extends StatelessWidget {
  const _TickerChip({required this.item});

  final MarketTickerItemModel item;

  @override
  Widget build(BuildContext context) {
    final accent = _sentimentColor(item.changePct * 20);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(
            item.symbol,
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(width: 8),
          Text(
            item.price >= 1000
                ? item.price.toStringAsFixed(0)
                : item.price.toStringAsFixed(2),
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
          const SizedBox(width: 8),
          Text(
            '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
            style: TextStyle(
              color: accent,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _HeatmapCell extends StatelessWidget {
  const _HeatmapCell({required this.item});

  final MarketHeatmapItemModel item;

  @override
  Widget build(BuildContext context) {
    final positive = item.changePct >= 0;
    final base = positive ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final glow = (0.18 + (item.intensity * 0.34)).clamp(0.18, 0.52);
    return Container(
      width: 84,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(
        color: base.withOpacity(glow),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: base.withOpacity(0.45)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: base.withOpacity(0.18),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            item.symbol,
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _GaugePainter extends CustomPainter {
  const _GaugePainter({
    required this.score,
    required this.accent,
    required this.wobble,
    required this.pulse,
    required this.extremePulse,
  });

  final double score;
  final Color accent;
  final double wobble;
  final double pulse;
  final bool extremePulse;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height * 0.88);
    final radius = math.min(size.width * 0.42, size.height * 0.78);
    final rect = Rect.fromCircle(center: center, radius: radius);
    final background = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 16
      ..strokeCap = StrokeCap.round
      ..shader = const LinearGradient(
        colors: <Color>[
          TradingPalette.neonRed,
          TradingPalette.amber,
          TradingPalette.neonGreen,
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 18
      ..strokeCap = StrokeCap.round
      ..color = TradingPalette.panelBorder.withOpacity(0.55);
    final needle = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round
      ..color = accent;
    final glow = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = extremePulse ? 28 : 24
      ..strokeCap = StrokeCap.round
      ..color = accent.withOpacity(extremePulse ? 0.18 + (pulse * 0.08) : 0.12);
    canvas.drawArc(rect, math.pi, math.pi, false, track);
    canvas.drawArc(rect, math.pi, math.pi, false, background);

    final normalized = ((score + 100) / 200).clamp(0.0, 1.0);
    final angle = math.pi + (math.pi * normalized) + wobble;
    final needleLength = radius - 18;
    final needleEnd = Offset(
      center.dx + math.cos(angle) * needleLength,
      center.dy + math.sin(angle) * needleLength,
    );
    canvas.drawLine(center, needleEnd, glow);
    canvas.drawLine(center, needleEnd, needle);
    canvas.drawCircle(
      center,
      extremePulse ? 9 + pulse : 8,
      Paint()..color = TradingPalette.textPrimary,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.score != score ||
        oldDelegate.accent != accent ||
        oldDelegate.wobble != wobble ||
        oldDelegate.pulse != pulse ||
        oldDelegate.extremePulse != extremePulse;
  }
}

Widget _gaugePill({String label = 'AI Pulse Gauge'}) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    decoration: BoxDecoration(
      color: const Color(0x2214FFB8),
      borderRadius: BorderRadius.circular(999),
      border: Border.all(color: const Color(0x4414FFB8)),
    ),
    child: Text(
      label,
      style: const TextStyle(
        color: TradingPalette.textPrimary,
        fontWeight: FontWeight.w700,
        fontSize: 12,
      ),
    ),
  );
}

double _effectiveSentimentScore({
  required double sentimentScore,
  required double scannerAverage,
}) {
  final scannerBias = ((scannerAverage - 50) / 50) * 100;
  return (sentimentScore * 0.62) + (scannerBias * 0.38);
}

String _effectiveSentimentLabel(String baseLabel, double scannerAverage) {
  if (scannerAverage >= 85) {
    return 'EXTREME BULLISH';
  }
  if (scannerAverage >= 70) {
    return 'HIGH CONVICTION';
  }
  if (scannerAverage <= 20 && baseLabel == 'BEARISH') {
    return 'EXTREME BEARISH';
  }
  return baseLabel;
}

Color _sentimentColor(double score) {
  if (score >= 20) {
    return TradingPalette.neonGreen;
  }
  if (score <= -20) {
    return TradingPalette.neonRed;
  }
  return TradingPalette.amber;
}

Color _scannerAverageColor(double score) {
  if (score >= 70) {
    return TradingPalette.neonGreen;
  }
  if (score >= 45) {
    return TradingPalette.electricBlue;
  }
  return TradingPalette.textMuted;
}

String _formatCountdown(int totalSeconds) {
  final seconds = totalSeconds < 0 ? 0 : totalSeconds;
  final duration = Duration(seconds: seconds);
  final hours = duration.inHours;
  final minutes = duration.inMinutes.remainder(60);
  final secs = duration.inSeconds.remainder(60);
  if (hours > 0) {
    return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
  }
  return '${minutes.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}';
}

List<ConfidenceHistoryPointModel> _scannerHistoryForSymbol({
  required String symbol,
  required List<ReadinessCardModel> readinessBoard,
  required List<ConfidenceHistoryPointModel> summaryHistory,
}) {
  final readinessMatch = readinessBoard.cast<ReadinessCardModel?>().firstWhere(
        (item) => item?.symbol == symbol && (item?.confidenceHistory.length ?? 0) >= 2,
        orElse: () => null,
      );
  if (readinessMatch != null) {
    return readinessMatch.confidenceHistory;
  }
  final normalized = symbol.toUpperCase();
  final filtered = summaryHistory
      .where((item) => (item.symbol ?? '').toUpperCase() == normalized)
      .toList();
  if (filtered.length >= 2) {
    return filtered;
  }
  return const <ConfidenceHistoryPointModel>[];
}

String _microTrendLabel(List<ConfidenceHistoryPointModel> history) {
  final delta = _historyDelta(history);
  if (delta >= 0.015) {
    return 'UP';
  }
  if (delta <= -0.015) {
    return 'FADE';
  }
  return 'STDY';
}

Color _microTrendColor(List<ConfidenceHistoryPointModel> history) {
  final delta = _historyDelta(history);
  if (delta >= 0.015) {
    return TradingPalette.neonGreen;
  }
  if (delta <= -0.015) {
    return const Color(0xFF48C7C2);
  }
  return TradingPalette.amber;
}

double _historyDelta(List<ConfidenceHistoryPointModel> history) {
  if (history.length < 2) {
    return 0.0;
  }
  final sample = history.length >= 3 ? history.sublist(history.length - 3) : history;
  return sample.last.score - sample.first.score;
}

List<Offset> _historyLinePoints(
  List<ConfidenceHistoryPointModel> history,
  Size size,
) {
  final startMs = history.first.timestamp.millisecondsSinceEpoch.toDouble();
  final endMs = history.last.timestamp.millisecondsSinceEpoch.toDouble();
  final minScore = history.map((item) => item.score).reduce(math.min);
  final maxScore = history.map((item) => item.score).reduce(math.max);
  final timeRange = (endMs - startMs).abs() < 1e-6 ? 1.0 : (endMs - startMs);
  final scoreRange = (maxScore - minScore).abs() < 1e-6 ? 1.0 : (maxScore - minScore);
  return history.map((item) {
    final timeRatio =
        (item.timestamp.millisecondsSinceEpoch.toDouble() - startMs) / timeRange;
    final scoreRatio = (item.score - minScore) / scoreRange;
    return Offset(
      1 + (timeRatio * (size.width - 2)),
      size.height - 2 - (scoreRatio * math.max(size.height - 4, 1)),
    );
  }).toList();
}

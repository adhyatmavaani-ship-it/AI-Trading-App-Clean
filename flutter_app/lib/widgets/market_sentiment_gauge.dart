import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../models/market_summary.dart';
import 'section_card.dart';
import 'state_widgets.dart';

class MarketSentimentGauge extends ConsumerWidget {
  const MarketSentimentGauge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summaryAsync = ref.watch(marketSummaryProvider);
    final selectedSymbol = ref.watch(selectedMarketSymbolProvider);
    return SectionCard(
      title: 'Market Sentiment',
      trailing: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: const Color(0x2214FFB8),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: const Color(0x4414FFB8)),
        ),
        child: const Text(
          'AI Pulse Gauge',
          style: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 12,
          ),
        ),
      ),
      child: summaryAsync.when(
        data: (summary) => _GaugeBody(
          summary: summary,
          selectedSymbol: selectedSymbol,
          onSelectSymbol: (symbol) =>
              ref.read(selectedMarketSymbolProvider.notifier).state = symbol,
        ),
        loading: () => const SizedBox(
          height: 260,
          child: LoadingState(label: 'Scanning market sentiment'),
        ),
        error: (error, _) => ErrorState(message: error.toString()),
      ),
    );
  }
}

class _GaugeBody extends StatelessWidget {
  const _GaugeBody({
    required this.summary,
    required this.selectedSymbol,
    required this.onSelectSymbol,
  });

  final MarketSummaryModel summary;
  final String selectedSymbol;
  final ValueChanged<String> onSelectSymbol;

  @override
  Widget build(BuildContext context) {
    final sentimentColor = _sentimentColor(summary.sentimentScore);
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
                    score: summary.sentimentScore,
                    accent: sentimentColor,
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: <Widget>[
                        Text(
                          summary.sentimentLabel,
                          style:
                              Theme.of(context).textTheme.titleMedium?.copyWith(
                                    color: sentimentColor,
                                    fontWeight: FontWeight.w800,
                                  ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          summary.sentimentScore.toStringAsFixed(0),
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: TradingPalette.textPrimary,
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
                      value:
                          '${(summary.marketBreadth * 100).toStringAsFixed(0)}%',
                    ),
                    const SizedBox(height: 12),
                    _MiniMetric(
                      label: 'Participation',
                      value:
                          '${(summary.participationScore * 100).toStringAsFixed(0)}%',
                    ),
                    const SizedBox(height: 12),
                    _MiniMetric(
                      label: 'Confidence',
                      value:
                          '${(summary.confidenceScore * 100).toStringAsFixed(0)}%',
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
        border: Border.all(color: (accent ?? TradingPalette.panelBorder).withOpacity(accent == null ? 1 : 0.35)),
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
    required this.selected,
    required this.onTap,
  });

  final ScannerCandidateModel item;
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
              selected
                  ? accent.withOpacity(0.18)
                  : TradingPalette.panelSoft,
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
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: TradingPalette.neonRed.withOpacity(0.14),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: TradingPalette.neonRed.withOpacity(0.35)),
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
              '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%  •  Spike ${item.volumeSpikePct.toStringAsFixed(0)}%',
              style: const TextStyle(
                color: TradingPalette.textMuted,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
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
  });

  final double score;
  final Color accent;

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
      ..strokeWidth = 24
      ..strokeCap = StrokeCap.round
      ..color = accent.withOpacity(0.12);
    canvas.drawArc(rect, math.pi, math.pi, false, track);
    canvas.drawArc(rect, math.pi, math.pi, false, background);

    final normalized = ((score + 100) / 200).clamp(0.0, 1.0);
    final angle = math.pi + (math.pi * normalized);
    final needleLength = radius - 18;
    final needleEnd = Offset(
      center.dx + math.cos(angle) * needleLength,
      center.dy + math.sin(angle) * needleLength,
    );
    canvas.drawLine(center, needleEnd, glow);
    canvas.drawLine(center, needleEnd, needle);
    canvas.drawCircle(
      center,
      8,
      Paint()..color = TradingPalette.textPrimary,
    );
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.score != score || oldDelegate.accent != accent;
  }
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

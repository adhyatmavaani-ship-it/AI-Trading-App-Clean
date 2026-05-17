import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/ai_opportunity_engine.dart';
import '../core/trading_palette.dart';
import 'gradient_action_button.dart';
import 'status_badge.dart';

class ConfidencePulseRing extends StatefulWidget {
  const ConfidencePulseRing({
    super.key,
    required this.value,
    required this.color,
    this.label = 'AI',
    this.size = 132,
  });

  final double value;
  final Color color;
  final String label;
  final double size;

  @override
  State<ConfidencePulseRing> createState() => _ConfidencePulseRingState();
}

class _ConfidencePulseRingState extends State<ConfidencePulseRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox.square(
      dimension: widget.size,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            painter: _ConfidenceRingPainter(
              value: widget.value.clamp(0.0, 1.0),
              color: widget.color,
              pulse: _controller.value,
            ),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    '${(widget.value * 100).clamp(0, 99).toStringAsFixed(0)}%',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                          color: TradingPalette.textPrimary,
                        ),
                  ),
                  Text(
                    widget.label,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: widget.color,
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ConfidenceRingPainter extends CustomPainter {
  const _ConfidenceRingPainter({
    required this.value,
    required this.color,
    required this.pulse,
  });

  final double value;
  final Color color;
  final double pulse;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 8;
    final rect = Rect.fromCircle(center: center, radius: radius);
    canvas.drawCircle(
      center,
      radius + (pulse * 5),
      Paint()
        ..color = color.withOpacity(0.05 + (pulse * 0.05))
        ..style = PaintingStyle.stroke
        ..strokeWidth = 10,
    );
    canvas.drawCircle(
      center,
      radius,
      Paint()
        ..color = TradingPalette.panelBorder.withOpacity(0.38)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 9,
    );
    canvas.drawArc(
      rect,
      -math.pi / 2,
      math.pi * 2 * value,
      false,
      Paint()
        ..shader = SweepGradient(
          colors: <Color>[
            color.withOpacity(0.20),
            color,
            TradingPalette.electricBlue,
            color.withOpacity(0.20),
          ],
        ).createShader(rect)
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = 9,
    );
  }

  @override
  bool shouldRepaint(covariant _ConfidenceRingPainter oldDelegate) {
    return oldDelegate.value != value ||
        oldDelegate.color != color ||
        oldDelegate.pulse != pulse;
  }
}

class LiveEnergyBars extends StatefulWidget {
  const LiveEnergyBars({
    super.key,
    required this.color,
    this.height = 34,
    this.barCount = 18,
  });

  final Color color;
  final double height;
  final int barCount;

  @override
  State<LiveEnergyBars> createState() => _LiveEnergyBarsState();
}

class _LiveEnergyBarsState extends State<LiveEnergyBars>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1600),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            painter: _EnergyBarsPainter(
              color: widget.color,
              progress: _controller.value,
              barCount: widget.barCount,
            ),
            child: const SizedBox.expand(),
          );
        },
      ),
    );
  }
}

class _EnergyBarsPainter extends CustomPainter {
  const _EnergyBarsPainter({
    required this.color,
    required this.progress,
    required this.barCount,
  });

  final Color color;
  final double progress;
  final int barCount;

  @override
  void paint(Canvas canvas, Size size) {
    final gap = size.width / math.max(barCount, 1);
    final paint = Paint();
    for (var index = 0; index < barCount; index += 1) {
      final phase = (progress * math.pi * 2) + (index * 0.62);
      final heightFactor = 0.22 + ((math.sin(phase) + 1) / 2) * 0.72;
      final barHeight = size.height * heightFactor;
      final rect = Rect.fromLTWH(
        index * gap + 2,
        size.height - barHeight,
        math.max(gap - 4, 2),
        barHeight,
      );
      paint.color = color.withOpacity(0.18 + (heightFactor * 0.42));
      canvas.drawRRect(
        RRect.fromRectAndRadius(rect, const Radius.circular(5)),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _EnergyBarsPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.color != color ||
        oldDelegate.barCount != barCount;
  }
}

class MomentumWave extends StatefulWidget {
  const MomentumWave({
    super.key,
    required this.color,
    this.height = 52,
  });

  final Color color;
  final double height;

  @override
  State<MomentumWave> createState() => _MomentumWaveState();
}

class _MomentumWaveState extends State<MomentumWave>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            painter: _MomentumWavePainter(
              color: widget.color,
              progress: _controller.value,
            ),
            child: const SizedBox.expand(),
          );
        },
      ),
    );
  }
}

class _MomentumWavePainter extends CustomPainter {
  const _MomentumWavePainter({
    required this.color,
    required this.progress,
  });

  final Color color;
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final path = Path();
    for (var x = 0.0; x <= size.width; x += 6) {
      final normalized = x / math.max(size.width, 1);
      final y = size.height * 0.52 +
          math.sin((normalized * math.pi * 3.2) + progress * math.pi * 2) *
              size.height *
              0.18;
      if (x == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final fill = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[
            color.withOpacity(0.18),
            color.withOpacity(0.01),
          ],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withOpacity(0.75)
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _MomentumWavePainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.color != color;
  }
}

class OpportunityProgressRail extends StatelessWidget {
  const OpportunityProgressRail({
    super.key,
    required this.opportunity,
  });

  final SignalOpportunity opportunity;

  @override
  Widget build(BuildContext context) {
    final activeIndex = SignalOpportunity.progressionStages
        .indexOf(opportunity.progressionStage)
        .clamp(0, SignalOpportunity.progressionStages.length - 1);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                opportunity.progressionStage,
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: opportunity.accent,
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ),
            Text(
              '${(opportunity.stageProgress * 100).toStringAsFixed(0)}%',
              style: const TextStyle(
                color: TradingPalette.textMuted,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: <Widget>[
            for (var index = 0;
                index < SignalOpportunity.progressionStages.length;
                index += 1)
              Expanded(
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 420),
                  height: index == activeIndex ? 10 : 7,
                  margin: EdgeInsets.only(
                    right:
                        index == SignalOpportunity.progressionStages.length - 1
                            ? 0
                            : 5,
                  ),
                  decoration: BoxDecoration(
                    color: index <= activeIndex
                        ? opportunity.accent
                        : TradingPalette.panelBorder.withOpacity(0.55),
                    borderRadius: BorderRadius.circular(999),
                    boxShadow: index == activeIndex
                        ? <BoxShadow>[
                            BoxShadow(
                              color: opportunity.accent.withOpacity(0.35),
                              blurRadius: 14,
                            ),
                          ]
                        : null,
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class PremiumSignalSurface extends StatelessWidget {
  const PremiumSignalSurface({
    super.key,
    required this.opportunity,
    required this.autoModeEnabled,
    required this.onPrimary,
    required this.onAuto,
    required this.onChart,
  });

  final SignalOpportunity opportunity;
  final bool autoModeEnabled;
  final VoidCallback onPrimary;
  final VoidCallback onAuto;
  final VoidCallback onChart;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            opportunity.accent.withOpacity(0.22),
            TradingPalette.panel.withOpacity(0.94),
            const Color(0xF0050814),
          ],
        ),
        border: Border.all(color: opportunity.accent.withOpacity(0.28)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: opportunity.accent.withOpacity(0.22),
            blurRadius: 42,
            spreadRadius: -18,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: Stack(
          children: <Widget>[
            Positioned.fill(
              child: Opacity(
                opacity: 0.62,
                child: MomentumWave(color: opportunity.accent, height: 220),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      StatusBadge(
                        label: opportunity.statusLabel,
                        color: opportunity.accent,
                      ),
                      const SizedBox(width: 8),
                      StatusBadge(
                        label: opportunity.mode.label,
                        color: TradingPalette.violet,
                      ),
                      const Spacer(),
                      const Icon(
                        Icons.auto_awesome_rounded,
                        color: TradingPalette.electricBlue,
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final compact = constraints.maxWidth < 520;
                      final titleBlock = _HeroTitleBlock(
                        opportunity: opportunity,
                      );
                      final ring = ConfidencePulseRing(
                        value: opportunity.score / 100,
                        color: opportunity.accent,
                        size: compact ? 116 : 142,
                      );
                      if (compact) {
                        return Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Center(child: ring),
                            const SizedBox(height: 16),
                            titleBlock,
                          ],
                        );
                      }
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: <Widget>[
                          ring,
                          const SizedBox(width: 20),
                          Expanded(child: titleBlock),
                        ],
                      );
                    },
                  ),
                  const SizedBox(height: 18),
                  LiveEnergyBars(color: opportunity.accent),
                  const SizedBox(height: 18),
                  OpportunityProgressRail(opportunity: opportunity),
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: <Widget>[
                      _SignalInsightPill(
                        label: 'Move',
                        value: opportunity.expectedMoveLabel,
                        color: opportunity.accent,
                      ),
                      _SignalInsightPill(
                        label: 'Breakout',
                        value:
                            '${opportunity.breakoutProbability.toStringAsFixed(0)}%',
                        color: TradingPalette.electricBlue,
                      ),
                      _SignalInsightPill(
                        label: 'Whales',
                        value:
                            '${opportunity.whalePressure.toStringAsFixed(0)}%',
                        color: TradingPalette.violet,
                      ),
                      _SignalInsightPill(
                        label: 'Volatility',
                        value: opportunity.riskLabel,
                        color: TradingPalette.amber,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: opportunity.insights
                        .map(
                          (insight) => Chip(
                            label: Text(insight),
                            backgroundColor: TradingPalette.overlay,
                            side: BorderSide(
                              color: opportunity.accent.withOpacity(0.20),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 18),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: GradientActionButton(
                          label: opportunity.canAttemptExecution
                              ? 'Enter Trade'
                              : opportunity.primaryLabel,
                          icon: opportunity.bullish
                              ? Icons.north_east_rounded
                              : Icons.south_east_rounded,
                          gradient: opportunity.bullish
                              ? TradingPalette.profitGlow
                              : TradingPalette.lossGlow,
                          onPressed: onPrimary,
                          expanded: true,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: onAuto,
                          icon: Icon(
                            autoModeEnabled
                                ? Icons.pause_circle_outline_rounded
                                : Icons.bolt_rounded,
                          ),
                          label: Text(
                            autoModeEnabled
                                ? 'Auto Active'
                                : opportunity.secondaryLabel,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      IconButton.filledTonal(
                        onPressed: onChart,
                        icon: const Icon(Icons.candlestick_chart_rounded),
                        tooltip: 'View AI chart',
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroTitleBlock extends StatelessWidget {
  const _HeroTitleBlock({required this.opportunity});

  final SignalOpportunity opportunity;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          opportunity.heroTitle,
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.w900,
                color: TradingPalette.textPrimary,
              ),
        ),
        const SizedBox(height: 10),
        Text(
          '${opportunity.userFacingState}. Expected move ${opportunity.expectedMoveLabel}. ${opportunity.tradePlanLabel}',
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: TradingPalette.textPrimary,
                height: 1.28,
              ),
        ),
      ],
    );
  }
}

class _SignalInsightPill extends StatelessWidget {
  const _SignalInsightPill({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 94),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.24)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

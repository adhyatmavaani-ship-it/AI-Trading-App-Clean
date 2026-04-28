import 'dart:math' as math;
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/activity/providers/activity_providers.dart';
import '../features/market/providers/market_providers.dart';
import '../models/activity.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
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
    final summary = ref.watch(marketSummaryProvider).valueOrNull;
    final readinessBoard = ref.watch(readinessBoardProvider);
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
            data: (chart) => _ChartBody(
              chart: chart,
              selectedSymbol: selectedSymbol,
              scannerCandidates: summary?.scanner.candidates ?? const <ScannerCandidateModel>[],
              readinessBoard: readinessBoard,
              secondsUntilRotation: summary?.scanner.secondsUntilRotation ?? 0,
              rotationWindowSeconds: _rotationWindowSeconds(summary),
              onSelectSymbol: (symbol) =>
                  ref.read(selectedMarketSymbolProvider.notifier).state = symbol,
            ),
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

int _rotationWindowSeconds(MarketSummaryModel? summary) {
  final scanner = summary?.scanner;
  if (scanner == null || scanner.rotationStartedAt == null || scanner.nextRotationAt == null) {
    return 0;
  }
  final window = scanner.nextRotationAt!.difference(scanner.rotationStartedAt!).inSeconds;
  return window > 0 ? window : 0;
}

class _ChartBody extends StatelessWidget {
  const _ChartBody({
    required this.chart,
    required this.selectedSymbol,
    required this.scannerCandidates,
    required this.readinessBoard,
    required this.secondsUntilRotation,
    required this.rotationWindowSeconds,
    required this.onSelectSymbol,
  });

  final MarketChartModel chart;
  final String selectedSymbol;
  final List<ScannerCandidateModel> scannerCandidates;
  final List<ReadinessCardModel> readinessBoard;
  final int secondsUntilRotation;
  final int rotationWindowSeconds;
  final ValueChanged<String> onSelectSymbol;

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
    final scannerCandidate = scannerCandidates.cast<ScannerCandidateModel?>().firstWhere(
          (item) => item?.symbol == chart.symbol,
          orElse: () => scannerCandidates.isNotEmpty ? scannerCandidates.first : null,
        );
    final readinessCard = readinessBoard.cast<ReadinessCardModel?>().firstWhere(
          (item) => item?.symbol == chart.symbol,
          orElse: () => null,
        );
    final scoreAccent = _scannerAccent(scannerCandidate?.potentialScore ?? 0);
    final countdownProgress = rotationWindowSeconds <= 0
        ? 0.0
        : (secondsUntilRotation / rotationWindowSeconds).clamp(0.0, 1.0);
    final countdownColor = Color.lerp(
          TradingPalette.neonRed,
          TradingPalette.neonGreen,
          countdownProgress,
        ) ??
        TradingPalette.electricBlue;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: <Widget>[
                      Text(
                        chart.symbol,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      if (scannerCandidate != null)
                        _HeaderInfoChip(
                          label: 'Score ${scannerCandidate.potentialScore.toStringAsFixed(0)}',
                          accent: scoreAccent,
                        ),
                      ..._headerRiskBadges(readinessCard?.riskFlags ?? const <String, dynamic>{}),
                      _HeaderInfoChip(
                        label: _formatCountdown(secondsUntilRotation),
                        accent: countdownColor,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: countdownProgress,
                      minHeight: 5,
                      backgroundColor: TradingPalette.panelBorder.withOpacity(0.85),
                      valueColor: AlwaysStoppedAnimation<Color>(countdownColor),
                    ),
                  ),
                ],
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
          scannerCandidate == null
              ? 'TradingView-style market pulse with AI markers'
              : 'Scanner pulse ${scannerCandidate.volumeSpikePct.toStringAsFixed(0)}% spike | Vol ${scannerCandidate.volatilityPct.toStringAsFixed(1)}%',
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
                    child: _ChartCanvasWithDock(
                      geometry: geometry,
                      chart: chart,
                      minPrice: minPrice,
                      maxPrice: maxPrice,
                      scannerCandidates: scannerCandidates,
                      readinessBoard: readinessBoard,
                      selectedSymbol: selectedSymbol,
                      onSelectSymbol: onSelectSymbol,
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

class _ChartCanvasWithDock extends StatelessWidget {
  const _ChartCanvasWithDock({
    required this.geometry,
    required this.chart,
    required this.minPrice,
    required this.maxPrice,
    required this.scannerCandidates,
    required this.readinessBoard,
    required this.selectedSymbol,
    required this.onSelectSymbol,
  });

  final _ChartGeometry geometry;
  final MarketChartModel chart;
  final double minPrice;
  final double maxPrice;
  final List<ScannerCandidateModel> scannerCandidates;
  final List<ReadinessCardModel> readinessBoard;
  final String selectedSymbol;
  final ValueChanged<String> onSelectSymbol;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: <Widget>[
        Positioned.fill(
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapDown: (details) {
              final selectedMarker = _nearestDetailMarker(
                geometry: geometry,
                tap: details.localPosition,
                markers: chart.markers,
              );
              if (selectedMarker == null) {
                return;
              }
              _showMarkerDetailSheet(context, selectedMarker);
            },
            child: CustomPaint(
              painter: _CandlestickPainter(
                candles: chart.candles,
                minPrice: minPrice,
                maxPrice: maxPrice,
                markers: chart.markers,
                confidenceIntervals: chart.confidenceIntervals,
              ),
              child: const SizedBox.expand(),
            ),
          ),
        ),
        if (scannerCandidates.isNotEmpty)
          Positioned(
            top: 12,
            right: 10,
            bottom: 12,
            child: _ScannerQuickDock(
              candidates: scannerCandidates.take(5).toList(),
              readinessBoard: readinessBoard,
              selectedSymbol: selectedSymbol,
              onSelectSymbol: onSelectSymbol,
            ),
          ),
      ],
    );
  }
}

class _ScannerQuickDock extends StatefulWidget {
  const _ScannerQuickDock({
    required this.candidates,
    required this.readinessBoard,
    required this.selectedSymbol,
    required this.onSelectSymbol,
  });

  final List<ScannerCandidateModel> candidates;
  final List<ReadinessCardModel> readinessBoard;
  final String selectedSymbol;
  final ValueChanged<String> onSelectSymbol;

  @override
  State<_ScannerQuickDock> createState() => _ScannerQuickDockState();
}

class _ScannerQuickDockState extends State<_ScannerQuickDock> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutBack,
      width: _expanded ? 92 : 54,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xAA0F1730),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: TradingPalette.panelBorder.withOpacity(0.7)),
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: TradingPalette.midnight.withOpacity(0.22),
                  blurRadius: 18,
                  offset: const Offset(0, 10),
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: <Widget>[
                GestureDetector(
                  onTap: () => setState(() => _expanded = !_expanded),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: BoxDecoration(
                      color: TradingPalette.panelSoft,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: TradingPalette.panelBorder.withOpacity(0.7)),
                    ),
                    child: Icon(
                      _expanded ? Icons.chevron_right_rounded : Icons.chevron_left_rounded,
                      color: TradingPalette.textPrimary,
                      size: 18,
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      children: widget.candidates
                          .map(
                            (candidate) => Padding(
                              padding: const EdgeInsets.only(bottom: 10),
                              child: _QuickSwitchCoinButton(
                                candidate: candidate,
                                readinessCard: widget.readinessBoard.cast<ReadinessCardModel?>().firstWhere(
                                      (item) => item?.symbol == candidate.symbol,
                                      orElse: () => null,
                                    ),
                                expanded: _expanded,
                                selected: candidate.symbol == widget.selectedSymbol,
                                onTap: () => widget.onSelectSymbol(candidate.symbol),
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _QuickSwitchCoinButton extends StatelessWidget {
  const _QuickSwitchCoinButton({
    required this.candidate,
    required this.readinessCard,
    required this.expanded,
    required this.selected,
    required this.onTap,
  });

  final ScannerCandidateModel candidate;
  final ReadinessCardModel? readinessCard;
  final bool expanded;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final progress = (candidate.potentialScore / 100).clamp(0.0, 1.0);
    final accent = _scannerAccent(candidate.potentialScore);
    final shortName = _shortSymbol(candidate.symbol);
    return GestureDetector(
      onTap: onTap,
      onLongPress: () => _showScannerTooltip(
        context,
        candidate,
        readinessCard: readinessCard,
      ),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        width: double.infinity,
        padding: EdgeInsets.symmetric(
          horizontal: expanded ? 8 : 4,
          vertical: expanded ? 8 : 6,
        ),
        decoration: BoxDecoration(
          color: selected
              ? accent.withOpacity(0.16)
              : TradingPalette.panelSoft.withOpacity(0.78),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: selected ? accent : TradingPalette.panelBorder.withOpacity(0.55),
          ),
          boxShadow: selected
              ? <BoxShadow>[
                  BoxShadow(
                    color: accent.withOpacity(0.22),
                    blurRadius: 14,
                    spreadRadius: 1,
                  ),
                ]
              : const <BoxShadow>[],
        ),
        child: expanded
            ? Row(
                children: <Widget>[
                  _PotentialRing(
                    progress: progress,
                    accent: accent,
                    hot: candidate.isHot,
                    child: Text(
                      shortName,
                      style: const TextStyle(
                        color: TradingPalette.textPrimary,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          shortName,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: TradingPalette.textPrimary,
                            fontSize: 12,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          candidate.potentialScore.toStringAsFixed(0),
                          style: TextStyle(
                            color: accent,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              )
            : Center(
                child: _PotentialRing(
                  progress: progress,
                  accent: accent,
                  hot: candidate.isHot,
                  child: Text(
                    shortName,
                    style: const TextStyle(
                      color: TradingPalette.textPrimary,
                      fontSize: 10,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),
      ),
    );
  }
}

class _PotentialRing extends StatelessWidget {
  const _PotentialRing({
    required this.progress,
    required this.accent,
    required this.hot,
    required this.child,
  });

  final double progress;
  final Color accent;
  final bool hot;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return _HotPulseRing(
      active: hot,
      accent: accent,
      child: SizedBox(
        width: 30,
        height: 30,
        child: Stack(
          alignment: Alignment.center,
          children: <Widget>[
            CircularProgressIndicator(
              value: progress,
              strokeWidth: 3,
              backgroundColor: TradingPalette.panelBorder,
              valueColor: AlwaysStoppedAnimation<Color>(accent),
            ),
            child,
          ],
        ),
      ),
    );
  }
}

class _HotPulseRing extends StatefulWidget {
  const _HotPulseRing({
    required this.active,
    required this.accent,
    required this.child,
  });

  final bool active;
  final Color accent;
  final Widget child;

  @override
  State<_HotPulseRing> createState() => _HotPulseRingState();
}

class _HotPulseRingState extends State<_HotPulseRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    if (widget.active) {
      _controller.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(covariant _HotPulseRing oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.active && !_controller.isAnimating) {
      _controller.repeat(reverse: true);
    } else if (!widget.active && _controller.isAnimating) {
      _controller.stop();
      _controller.value = 0.0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.active) {
      return widget.child;
    }
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        final scale = 1.0 + (_controller.value * 0.18);
        return Transform.scale(
          scale: scale,
          child: Container(
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: widget.accent.withOpacity(0.10 + (_controller.value * 0.16)),
                  blurRadius: 10 + (_controller.value * 10),
                  spreadRadius: _controller.value * 3,
                ),
              ],
            ),
            child: child,
          ),
        );
      },
      child: widget.child,
    );
  }
}

class _HeaderInfoChip extends StatelessWidget {
  const _HeaderInfoChip({
    required this.label,
    required this.accent,
  });

  final String label;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: accent.withOpacity(0.35)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: accent,
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

void _showScannerTooltip(
  BuildContext context,
  ScannerCandidateModel candidate, {
  ReadinessCardModel? readinessCard,
}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  final strategyText = (readinessCard?.logicTags ?? _derivedScannerTags(candidate)).join(' ');
  messenger?.hideCurrentSnackBar();
  messenger?.showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      backgroundColor: const Color(0xEE0F1730),
      duration: const Duration(seconds: 3),
      content: Text(
        '${_shortSymbol(candidate.symbol)} | Volume Spike +${candidate.volumeSpikePct.toStringAsFixed(0)}% | Trend ${_trendLabel(candidate)}${strategyText.isEmpty ? '' : ' | $strategyText'}',
        style: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
  );
}

List<String> _derivedScannerTags(ScannerCandidateModel candidate) {
  if (candidate.potentialScore >= 80 && candidate.changePct >= 0) {
    return const <String>['#BreakoutHunter', '#TrendFollowing'];
  }
  if (candidate.volumeSpikePct >= 20 && candidate.changePct.abs() <= 2.5) {
    return const <String>['#MeanReversion'];
  }
  if (candidate.changePct < 0 && candidate.volatilityPct >= 4) {
    return const <String>['#RiskOff', '#FadeSetup'];
  }
  return const <String>['#ScannerWatch'];
}

String _shortSymbol(String symbol) {
  final normalized = symbol.toUpperCase();
  for (final suffix in const <String>['USDT', 'USDC', 'USD']) {
    if (normalized.endsWith(suffix) && normalized.length > suffix.length) {
      return normalized.substring(0, normalized.length - suffix.length);
    }
  }
  return normalized;
}

Color _scannerAccent(double score) {
  if (score >= 80) {
    return TradingPalette.neonGreen;
  }
  if (score >= 50) {
    return TradingPalette.electricBlue;
  }
  return TradingPalette.textMuted;
}

String _trendLabel(ScannerCandidateModel candidate) {
  if (candidate.changePct >= 4 || candidate.potentialScore >= 80) {
    return 'Strong Bullish';
  }
  if (candidate.changePct <= -4) {
    return 'Strong Bearish';
  }
  return 'Developing';
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

TradeMarkerModel? _nearestDetailMarker({
  required _ChartGeometry geometry,
  required Offset tap,
  required List<TradeMarkerModel> markers,
}) {
  TradeMarkerModel? best;
  double bestDistance = 30;
  for (final marker in markers) {
    if (marker.markerType == 'EXIT') {
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

void _showMarkerDetailSheet(BuildContext context, TradeMarkerModel marker) {
  final accent = _markerAccent(marker);
  final title = marker.markerStyle == 'ghost'
      ? 'Ghost Setup'
      : marker.markerType == 'ENTRY'
          ? 'AI Entry Logic'
          : 'Marker Detail';
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
                    color: accent,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: TradingPalette.textPrimary,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Text(
              marker.reason ??
                  marker.message ??
                  'AI attached contextual logic to this market marker.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
            if (marker.confluenceBreakdown.isNotEmpty) ...<Widget>[
              const SizedBox(height: 14),
              _SheetConfluencePanel(marker: marker),
            ],
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
            if (marker.logicTags.isNotEmpty) ...<Widget>[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: marker.logicTags
                    .map(
                      (tag) => _DetailTagChip(
                        label: tag,
                        accent: TradingPalette.violet,
                      ),
                    )
                    .toList(),
              ),
            ],
            if (marker.riskFlags.isNotEmpty) ...<Widget>[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: marker.riskFlags.entries
                    .map(
                      (entry) => _DetailTagChip(
                        label:
                            '${_titleCase(entry.key.replaceAll('_', ' '))}: ${entry.value}',
                        accent: _riskBadgeAccent(entry.value),
                      ),
                    )
                    .toList(),
              ),
            ],
          ],
        ),
      );
    },
  );
}

Color _markerAccent(TradeMarkerModel marker) {
  if (marker.markerStyle == 'ghost') {
    return TradingPalette.textMuted;
  }
  if (marker.markerType == 'ENTRY') {
    return TradingPalette.neonGreen;
  }
  return TradingPalette.neonRed;
}

List<Widget> _headerRiskBadges(Map<String, dynamic> riskFlags) {
  final badges = <Widget>[];
  final volatility = riskFlags['volatility']?.toString().toLowerCase() ?? '';
  final spread = riskFlags['spread']?.toString().toLowerCase() ?? '';
  final liquidityWarning = riskFlags['liquidity_warning'] == true;

  if (volatility.contains('high')) {
    badges.add(
      const _HeaderInfoChip(
        label: 'High Volatility',
        accent: TradingPalette.neonRed,
      ),
    );
  }
  if (spread.contains('tight') && !liquidityWarning) {
    badges.add(
      const _HeaderInfoChip(
        label: 'Safe Liquidity',
        accent: TradingPalette.neonGreen,
      ),
    );
  } else if (spread.contains('wide') || liquidityWarning) {
    badges.add(
      const _HeaderInfoChip(
        label: 'Wide Spread',
        accent: TradingPalette.amber,
      ),
    );
  }

  return badges;
}

Color _confluenceChipAccent(String value) => _confluenceAccent(value);

Color _riskBadgeAccent(dynamic value) => _riskAccent(value);

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
    required this.confidenceIntervals,
  });

  final List<MarketCandleModel> candles;
  final double minPrice;
  final double maxPrice;
  final List<TradeMarkerModel> markers;
  final List<ConfidenceIntervalModel> confidenceIntervals;

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

    _paintConfidenceBands(canvas, geometry, size);

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
        oldDelegate.confidenceIntervals != confidenceIntervals ||
        oldDelegate.minPrice != minPrice ||
        oldDelegate.maxPrice != maxPrice;
  }

  void _paintConfidenceBands(
    Canvas canvas,
    _ChartGeometry geometry,
    Size size,
  ) {
    for (final interval in confidenceIntervals) {
      final startIndex = _nearestCandleIndexForTs(interval.startTs);
      final endIndex = _nearestCandleIndexForTs(interval.endTs);
      if (startIndex == null || endIndex == null) {
        continue;
      }
      final leftIndex = math.min(startIndex, endIndex);
      final rightIndex = math.max(startIndex, endIndex);
      final left = math.max(0.0, leftIndex * geometry.gap);
      final right = math.min(size.width, (rightIndex + 1) * geometry.gap);
      final bandRect = Rect.fromLTRB(left, 0, right, size.height);
      final isStrong = interval.zoneType == 'STRONG_CONVICTION';
      final topColor = isStrong
          ? TradingPalette.neonGreen.withOpacity(0.12)
          : TradingPalette.electricBlue.withOpacity(0.08);
      final bottomColor = isStrong
          ? TradingPalette.neonGreen.withOpacity(0.02)
          : TradingPalette.electricBlue.withOpacity(0.015);
      final bandPaint = Paint()
        ..blendMode = BlendMode.srcOver
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[topColor, bottomColor],
        ).createShader(bandRect);
      canvas.drawRect(bandRect, bandPaint);
    }
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
      final confidence = math.max(
        startMarker.confidenceScore,
        endMarker.confidenceScore,
      );
      final bridgePaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.0 + (confidence * 2.5)
        ..strokeCap = StrokeCap.round
        ..color = TradingPalette.electricBlue.withOpacity(0.7);
      canvas.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = bridgePaint.strokeWidth + 2
          ..strokeCap = StrokeCap.round
          ..color = TradingPalette.electricBlue.withOpacity(0.12)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
      );
      canvas.drawPath(path, bridgePaint);
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

  int? _nearestCandleIndexForTs(int timestampMs) {
    if (timestampMs <= 0 || candles.isEmpty) {
      return null;
    }
    var bestIndex = 0;
    var bestDiff = (candles[0].timestampMs - timestampMs).abs();
    for (var index = 1; index < candles.length; index += 1) {
      final diff = (candles[index].timestampMs - timestampMs).abs();
      if (diff < bestDiff) {
        bestDiff = diff;
        bestIndex = index;
      }
    }
    return bestIndex;
  }
}

class _SheetConfluencePanel extends StatelessWidget {
  const _SheetConfluencePanel({required this.marker});

  final TradeMarkerModel marker;

  @override
  Widget build(BuildContext context) {
    final aligned = marker.confluenceAligned ?? marker.confluenceBreakdown.length;
    final total = marker.confluenceTotal ?? math.max(marker.confluenceBreakdown.length, 1);
    final progress = total <= 0 ? 0.0 : (aligned / total).clamp(0.0, 1.0);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            '$aligned/$total Indicators Aligned',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 6,
              backgroundColor: TradingPalette.panelBorder,
              valueColor: const AlwaysStoppedAnimation<Color>(TradingPalette.neonGreen),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: marker.confluenceBreakdown.entries
                .map(
                  (entry) => _DetailTagChip(
                    label: '${_titleCase(entry.key)}: ${entry.value}',
                    accent: _confluenceChipAccent(entry.value),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _DetailTagChip extends StatelessWidget {
  const _DetailTagChip({
    required this.label,
    required this.accent,
  });

  final String label;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: accent.withOpacity(0.34)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: accent,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

Color _confluenceAccent(String value) {
  final text = value.toLowerCase();
  if (text.contains('aligned') ||
      text.contains('spiking') ||
      text.contains('supportive') ||
      text.contains('bullish') ||
      text.contains('oversold') ||
      text.contains('breakout')) {
    return TradingPalette.neonGreen;
  }
  if (text.contains('forming') || text.contains('balanced') || text.contains('mixed')) {
    return TradingPalette.amber;
  }
  return TradingPalette.electricBlue;
}

Color _riskAccent(dynamic value) {
  final text = value.toString().toLowerCase();
  if (text == 'true' || text.contains('high') || text.contains('wide')) {
    return TradingPalette.neonRed;
  }
  if (text.contains('contained') || text.contains('tight') || text == 'false') {
    return TradingPalette.neonGreen;
  }
  return TradingPalette.amber;
}

String _titleCase(String raw) {
  return raw
      .split(' ')
      .where((part) => part.trim().isNotEmpty)
      .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
      .join(' ');
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

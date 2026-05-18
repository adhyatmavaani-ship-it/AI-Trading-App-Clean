import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_mapper.dart';
import '../core/error_presenter.dart';
import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import '../models/user_pnl.dart';
import '../providers/app_providers.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/state_widgets.dart';

class AiTradeCenterScreen extends ConsumerStatefulWidget {
  const AiTradeCenterScreen({
    super.key,
    required this.onOpenChart,
    required this.onOpenTradeSignal,
  });

  final VoidCallback onOpenChart;
  final ValueChanged<SignalModel> onOpenTradeSignal;

  @override
  ConsumerState<AiTradeCenterScreen> createState() =>
      _AiTradeCenterScreenState();
}

class _AiTradeCenterScreenState extends ConsumerState<AiTradeCenterScreen> {
  String? _syncedChartSymbol;

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(activeUserIdProvider);
    final signalFeed = ref.watch(signalFeedProvider);
    final initialSignals = ref.watch(initialSignalsProvider);
    final marketSummary = ref.watch(marketSummaryProvider);
    final marketUniverse = ref.watch(marketUniverseProvider);
    final activeTrades = ref.watch(activeTradesProvider(userId));
    final pnl = ref.watch(userPnLProvider(userId));
    final signals = signalFeed.items.isNotEmpty
        ? signalFeed.items
        : (initialSignals.valueOrNull ?? const <SignalModel>[]);
    final bestTrade = _bestVerifiedTrade(signals);

    _syncChartSymbol(bestTrade?.symbol);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(initialSignalsProvider);
        ref.invalidate(marketSummaryProvider);
        ref.invalidate(activeTradesProvider(userId));
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: <Widget>[
          _TickerTape(
            summary: marketSummary,
            onTapSymbol: _openChartForSymbol,
          ),
          const SizedBox(height: 14),
          _MarketMovers(
            universe: marketUniverse,
            onTapSymbol: _openChartForSymbol,
          ),
          const SizedBox(height: 18),
          _MarketBrief(summary: marketSummary),
          const SizedBox(height: 18),
          if (signalFeed.lastError != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: _ConnectionNotice(error: signalFeed.lastError),
            ),
          _BestTradeHero(
            signal: bestTrade,
            chart: ref.watch(marketChartProvider).valueOrNull,
            onExecute: bestTrade == null
                ? null
                : () => widget.onOpenTradeSignal(bestTrade),
            onPaper: bestTrade == null
                ? null
                : () => widget.onOpenTradeSignal(bestTrade),
            onExplain: bestTrade == null
                ? null
                : () => _showExplanation(context, bestTrade),
            onAuto: () async {
              await ref
                  .read(tradingRepositoryProvider)
                  .setAssistantMode('FULL_AUTO');
              ref.invalidate(assistantModeProvider);
              ref.invalidate(marketChartProvider);
              widget.onOpenChart();
            },
            onOpenChart: widget.onOpenChart,
          ),
          const SizedBox(height: 18),
          _ProtectionShield(pnl: pnl, activeTrades: activeTrades),
          const SizedBox(height: 18),
          _SectionHeader(
            title: 'AI Watchlist',
            actionLabel: 'Chart',
            onAction: widget.onOpenChart,
          ),
          const SizedBox(height: 10),
          _OpportunityList(
            signals: signals
                .where((item) => item.signalId != bestTrade?.signalId)
                .take(4)
                .toList(growable: false),
            onTap: widget.onOpenTradeSignal,
          ),
          const SizedBox(height: 18),
          const _SectionHeader(title: 'Active Positions'),
          const SizedBox(height: 10),
          activeTrades.when(
            data: (items) => _ActivePositionList(trades: items),
            loading: () => const LoadingState(label: 'Loading positions...'),
            error: (error, _) =>
                ErrorState(message: userMessageForError(error)),
          ),
        ],
      ),
    );
  }

  void _syncChartSymbol(String? symbol) {
    if (symbol == null || symbol == _syncedChartSymbol) {
      return;
    }
    _syncedChartSymbol = symbol;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref.read(selectedMarketSymbolProvider.notifier).state = symbol;
    });
  }

  void _showExplanation(BuildContext context, SignalModel signal) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: TradingPalette.panel,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => _TradeExplanationSheet(signal: signal),
    );
  }

  void _openChartForSymbol(String symbol) {
    ref.read(selectedMarketSymbolProvider.notifier).state = symbol;
    widget.onOpenChart();
  }
}

SignalModel? _bestVerifiedTrade(List<SignalModel> signals) {
  final verified = signals
      .where((signal) =>
          signal.executionAllowed &&
          !signal.marketDataStale &&
          signal.price > 0 &&
          (signal.action == 'BUY' || signal.action == 'SELL'))
      .toList()
    ..sort((a, b) {
      final quality = b.qualityScore.compareTo(a.qualityScore);
      if (quality != 0) {
        return quality;
      }
      return b.confidence.compareTo(a.confidence);
    });
  return verified.isEmpty ? null : verified.first;
}

class _MarketBrief extends StatelessWidget {
  const _MarketBrief({required this.summary});

  final AsyncValue<MarketSummaryModel> summary;

  @override
  Widget build(BuildContext context) {
    return summary.when(
      data: (market) {
        final sentiment = market.sentimentLabel.toUpperCase();
        final bullish = sentiment.contains('BULL');
        final bearish = sentiment.contains('BEAR');
        final color = bullish
            ? TradingPalette.neonGreen
            : bearish
                ? TradingPalette.neonRed
                : TradingPalette.amber;
        return GlassPanel(
          glowColor: color,
          child: Row(
            children: <Widget>[
              _SignalDot(color: color),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      sentiment.isEmpty ? 'NEUTRAL MARKET' : sentiment,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w900,
                            color: TradingPalette.textPrimary,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Breadth ${market.marketBreadth.toStringAsFixed(0)}% | Volatility ${market.avgVolatilityPct.toStringAsFixed(1)}% | Confidence ${market.confidenceScore.toStringAsFixed(0)}%',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              _MetricPill(
                label: 'Fear/Greed',
                value: market.sentimentScore.toStringAsFixed(0),
                color: color,
              ),
            ],
          ),
        );
      },
      loading: () => const LoadingState(label: 'Reading market state...'),
      error: (error, _) => _ConnectionNotice(error: error),
    );
  }
}

class _TickerTape extends StatefulWidget {
  const _TickerTape({
    required this.summary,
    required this.onTapSymbol,
  });

  final AsyncValue<MarketSummaryModel> summary;
  final ValueChanged<String> onTapSymbol;

  @override
  State<_TickerTape> createState() => _TickerTapeState();
}

class _TickerTapeState extends State<_TickerTape>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 24),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final tickerMap = {
      for (final item in widget.summary.valueOrNull?.ticker ??
          const <MarketTickerItemModel>[])
        _displayAsset(item.symbol): item,
    };
    const ordered = <String>[
      'BTC',
      'ETH',
      'SOL',
      'BNB',
      'XRP',
      'GOLD',
      'NASDAQ'
    ];
    final cells = ordered
        .map((asset) => _TickerCell(
              asset: asset,
              item: tickerMap[asset],
              onTap: tickerMap[asset] == null
                  ? null
                  : () => widget.onTapSymbol(tickerMap[asset]!.symbol),
            ))
        .toList();
    return ClipRect(
      child: SizedBox(
        height: 42,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final repeated = <Widget>[...cells, ...cells];
            return AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                return Transform.translate(
                  offset: Offset(-_controller.value * constraints.maxWidth, 0),
                  child: child,
                );
              },
              child: OverflowBox(
                alignment: Alignment.centerLeft,
                maxWidth: double.infinity,
                child: Row(children: repeated),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _TickerCell extends StatelessWidget {
  const _TickerCell({
    required this.asset,
    required this.item,
    required this.onTap,
  });

  final String asset;
  final MarketTickerItemModel? item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final change = item?.changePct ?? 0;
    final color = item == null
        ? TradingPalette.textFaint
        : change >= 0
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.035),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: TradingPalette.panelBorder),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(
              asset,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: TradingPalette.textPrimary,
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(width: 8),
            Text(
              item == null
                  ? 'No live feed'
                  : '${_priceOrPending(item!.price)} ${change >= 0 ? '+' : ''}${change.toStringAsFixed(2)}%',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: color,
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MarketMovers extends StatelessWidget {
  const _MarketMovers({
    required this.universe,
    required this.onTapSymbol,
  });

  final AsyncValue<MarketUniverseModel> universe;
  final ValueChanged<String> onTapSymbol;

  @override
  Widget build(BuildContext context) {
    return universe.when(
      data: (data) {
        final gainers = data.topGainers.take(3).toList();
        final losers = data.topLosers.take(3).toList();
        if (gainers.isEmpty && losers.isEmpty) {
          return const GlassPanel(
            child: Text('Market scanner is waiting for verified live candles.'),
          );
        }
        return LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 760;
            final sections = <Widget>[
              _MoverColumn(
                title: 'Top Gainers',
                items: gainers,
                positive: true,
                onTapSymbol: onTapSymbol,
              ),
              _MoverColumn(
                title: 'Top Losers',
                items: losers,
                positive: false,
                onTapSymbol: onTapSymbol,
              ),
            ];
            return wide
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(child: sections.first),
                      const SizedBox(width: 12),
                      Expanded(child: sections.last),
                    ],
                  )
                : Column(
                    children: <Widget>[
                      sections.first,
                      const SizedBox(height: 12),
                      sections.last,
                    ],
                  );
          },
        );
      },
      loading: () => const LoadingState(label: 'Scanning live movers...'),
      error: (error, _) => _ConnectionNotice(error: error),
    );
  }
}

class _MoverColumn extends StatelessWidget {
  const _MoverColumn({
    required this.title,
    required this.items,
    required this.positive,
    required this.onTapSymbol,
  });

  final String title;
  final List<MarketUniverseEntryModel> items;
  final bool positive;
  final ValueChanged<String> onTapSymbol;

  @override
  Widget build(BuildContext context) {
    final color = positive ? TradingPalette.neonGreen : TradingPalette.neonRed;
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 10),
          for (final item in items)
            _MoverTile(
                item: item,
                color: color,
                onTap: () => onTapSymbol(item.symbol)),
        ],
      ),
    );
  }
}

class _MoverTile extends StatelessWidget {
  const _MoverTile({
    required this.item,
    required this.color,
    required this.onTap,
  });

  final MarketUniverseEntryModel item;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final confidence = item.potentialScore > 0
        ? item.potentialScore.clamp(0, 100)
        : (50 + item.volumeRatio * 12 + item.volatilityPct * 2).clamp(0, 100);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    item.symbol,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  Text(
                    '${_priceOrPending(item.price)}  ${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: color,
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 74,
              height: 26,
              child: CustomPaint(
                painter: _SparklinePainter(
                  values: item.sparkline,
                  color: color,
                ),
              ),
            ),
            const SizedBox(width: 8),
            _MetricPill(
              label: 'AI',
              value: '${confidence.toStringAsFixed(0)}%',
              color: color,
            ),
          ],
        ),
      ),
    );
  }
}

class _ProtectionShield extends StatelessWidget {
  const _ProtectionShield({
    required this.pnl,
    required this.activeTrades,
  });

  final AsyncValue<UserPnLModel> pnl;
  final AsyncValue<List<ActiveTradeModel>> activeTrades;

  @override
  Widget build(BuildContext context) {
    return pnl.when(
      data: (snapshot) {
        final drawdownPct = snapshot.rollingDrawdown <= 1
            ? snapshot.rollingDrawdown * 100
            : snapshot.rollingDrawdown;
        final exposurePct = snapshot.currentEquity <= 0
            ? 0.0
            : (snapshot.grossExposure / snapshot.currentEquity) * 100;
        final tradeCount =
            activeTrades.valueOrNull?.length ?? snapshot.activeTrades;
        return GlassPanel(
          glowColor: TradingPalette.electricBlue,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  const Icon(Icons.shield_rounded,
                      color: TradingPalette.electricBlue),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'AI Protection Active',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                  ),
                  _MetricPill(
                    label: 'State',
                    value: snapshot.protectionState,
                    color: TradingPalette.electricBlue,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: <Widget>[
                  Expanded(
                    child: _MetricPill(
                      label: 'Daily Risk',
                      value: '${drawdownPct.toStringAsFixed(2)}% / 3%',
                      color: TradingPalette.amber,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricPill(
                      label: 'Exposure',
                      value: '${exposurePct.toStringAsFixed(1)}%',
                      color: TradingPalette.electricBlue,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _MetricPill(
                      label: 'Loss Guard',
                      value: '$tradeCount active / 3 max',
                      color: TradingPalette.neonGreen,
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
      loading: () => const LoadingState(label: 'Loading protection shield...'),
      error: (error, _) => _ConnectionNotice(error: error),
    );
  }
}

class _BestTradeHero extends StatelessWidget {
  const _BestTradeHero({
    required this.signal,
    required this.chart,
    required this.onExecute,
    required this.onPaper,
    required this.onExplain,
    required this.onAuto,
    required this.onOpenChart,
  });

  final SignalModel? signal;
  final MarketChartModel? chart;
  final VoidCallback? onExecute;
  final VoidCallback? onPaper;
  final VoidCallback? onExplain;
  final VoidCallback? onAuto;
  final VoidCallback onOpenChart;

  @override
  Widget build(BuildContext context) {
    final signal = this.signal;
    final bullish = signal?.action == 'BUY';
    final color = signal == null
        ? TradingPalette.textMuted
        : bullish
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed;
    final guide =
        chart?.symbol == signal?.symbol ? chart?.executionGuide : null;
    final entry = _entryText(signal, guide);
    final stop = _priceOrPending(guide?.stopLoss);
    final tp1 = _priceOrPending(guide?.tp1);
    final tp2 = _priceOrPending(guide?.tp2);
    final riskReward = guide?.riskReward ?? 0;

    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'BEST AI TRADE NOW',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: TradingPalette.textMuted,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0,
                      ),
                ),
              ),
              _TrustBadge(signal: signal, chart: chart),
            ],
          ),
          const SizedBox(height: 18),
          if (signal == null)
            const _NoTradeState()
          else ...<Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        signal.symbol,
                        style:
                            Theme.of(context).textTheme.displaySmall?.copyWith(
                                  fontWeight: FontWeight.w900,
                                  color: TradingPalette.textPrimary,
                                  letterSpacing: 0,
                                ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: <Widget>[
                          _DirectionBadge(side: signal.action, color: color),
                          const SizedBox(width: 8),
                          Flexible(
                            child: Text(
                              signal.strategy.replaceAll('_', ' '),
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                _ConfidenceRing(
                  confidence: signal.confidence,
                  color: color,
                ),
              ],
            ),
            const SizedBox(height: 20),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              childAspectRatio: 2.35,
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              children: <Widget>[
                _TradeMetric(label: 'Entry', value: entry),
                _TradeMetric(label: 'Stoploss', value: stop),
                _TradeMetric(label: 'TP1', value: tp1),
                _TradeMetric(label: 'TP2', value: tp2),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: <Widget>[
                Expanded(
                  child: _MetricPill(
                    label: 'Risk',
                    value: _riskLabel(signal, guide),
                    color: color,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _MetricPill(
                    label: 'R:R',
                    value: riskReward > 0
                        ? riskReward.toStringAsFixed(2)
                        : 'Plan pending',
                    color: TradingPalette.electricBlue,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              _reasonSummary(signal),
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: TradingPalette.textMuted,
                    height: 1.35,
                  ),
            ),
            const SizedBox(height: 18),
            Row(
              children: <Widget>[
                Expanded(
                  child: GradientActionButton(
                    label: 'BUY',
                    icon: Icons.trending_up_rounded,
                    gradient: TradingPalette.profitGlow,
                    onPressed: bullish ? onExecute : null,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: GradientActionButton(
                    label: 'SELL',
                    icon: Icons.trending_down_rounded,
                    gradient: TradingPalette.lossGlow,
                    onPressed: bullish ? null : onExecute,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: <Widget>[
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onPaper,
                    icon: const Icon(Icons.science_rounded),
                    label: const Text('PAPER TRADE'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextButton.icon(
                    onPressed: onExplain,
                    icon: const Icon(Icons.psychology_alt_rounded),
                    label: const Text('ASK AI'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextButton.icon(
                    onPressed: onAuto,
                    icon: const Icon(Icons.auto_mode_rounded),
                    label: const Text('AUTO'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _NoTradeState extends StatelessWidget {
  const _NoTradeState();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          'No verified trade right now',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 8),
        Text(
          'The AI desk is waiting for a setup with live price, fresh market data, and risk approval. Watching is a valid decision.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      ],
    );
  }
}

class _OpportunityList extends StatelessWidget {
  const _OpportunityList({
    required this.signals,
    required this.onTap,
  });

  final List<SignalModel> signals;
  final ValueChanged<SignalModel> onTap;

  @override
  Widget build(BuildContext context) {
    if (signals.isEmpty) {
      return const GlassPanel(
        child: Text('No secondary opportunities. Waiting for live signals.'),
      );
    }
    return Column(
      children: signals
          .map(
            (signal) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _OpportunityTile(signal: signal, onTap: onTap),
            ),
          )
          .toList(),
    );
  }
}

class _OpportunityTile extends StatelessWidget {
  const _OpportunityTile({
    required this.signal,
    required this.onTap,
  });

  final SignalModel signal;
  final ValueChanged<SignalModel> onTap;

  @override
  Widget build(BuildContext context) {
    final approved = signal.executionAllowed &&
        !signal.marketDataStale &&
        signal.price > 0 &&
        !signal.lowConfidence;
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: approved ? () => onTap(signal) : null,
      child: GlassPanel(
        padding: const EdgeInsets.all(16),
        glowColor: signal.action == 'SELL'
            ? TradingPalette.neonRed
            : TradingPalette.neonGreen,
        child: Row(
          children: <Widget>[
            _DirectionBadge(
              side: signal.action,
              color: signal.action == 'SELL'
                  ? TradingPalette.neonRed
                  : TradingPalette.neonGreen,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    signal.symbol,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    approved
                        ? '${signal.strategy.replaceAll('_', ' ')} | ${signal.price.toStringAsFixed(signal.price >= 100 ? 2 : 4)}'
                        : 'Watchlist only | waiting for verified market data',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            Text(
              signal.qualityScore.toStringAsFixed(0),
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ActivePositionList extends StatelessWidget {
  const _ActivePositionList({required this.trades});

  final List<ActiveTradeModel> trades;

  @override
  Widget build(BuildContext context) {
    if (trades.isEmpty) {
      return const GlassPanel(
        child: Text('No open exposure. Capital is protected.'),
      );
    }
    return Column(
      children: trades
          .take(4)
          .map(
            (trade) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: GlassPanel(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: <Widget>[
                    _DirectionBadge(
                      side: trade.side,
                      color: trade.side == 'SELL'
                          ? TradingPalette.neonRed
                          : TradingPalette.neonGreen,
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            trade.symbol,
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.w800,
                                ),
                          ),
                          Text(
                            'Entry ${_priceOrPending(trade.entry)} | SL ${_priceOrPending(trade.stopLoss)} | TP ${_priceOrPending(trade.takeProfit)}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          )
          .toList(),
    );
  }
}

class _ConnectionNotice extends StatelessWidget {
  const _ConnectionNotice({required this.error});

  final Object? error;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.amber,
      child: Row(
        children: <Widget>[
          const Icon(Icons.cloud_sync_rounded, color: TradingPalette.amber),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              ErrorMapper.isRecoverableBackend(error)
                  ? 'Backend reconnecting. No live execution until data is verified.'
                  : userMessageForError(error),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _TradeExplanationSheet extends StatelessWidget {
  const _TradeExplanationSheet({required this.signal});

  final SignalModel signal;

  @override
  Widget build(BuildContext context) {
    final reasons = signal.reasons.take(5).toList();
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(22, 18, 22, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Why this trade?',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                IconButton(
                  tooltip: 'Close',
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close_rounded),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _ExplainLine(
              label: 'Trend direction',
              value:
                  '${signal.symbol} is ${signal.action == 'BUY' ? 'long-biased' : 'short-biased'} under ${signal.regime.toLowerCase()} conditions.',
            ),
            _ExplainLine(
              label: 'Liquidity behavior',
              value: signal.marketDataSources.isEmpty
                  ? 'Order book confirmation is pending; execution remains conservative.'
                  : 'Price, order book, and candle checks are sourced from ${signal.marketDataSources.values.join(', ')}.',
            ),
            _ExplainLine(
              label: 'Volume confirmation',
              value:
                  'The quality score is ${signal.qualityScore.toStringAsFixed(0)} and confidence is ${(signal.confidence * 100).toStringAsFixed(0)}%.',
            ),
            _ExplainLine(
              label: 'Risk engine',
              value: signal.executionAllowed
                  ? 'Risk engine approved this setup for guided execution.'
                  : 'Risk engine has not approved live execution.',
            ),
            _ExplainLine(
              label: 'Meta engine',
              value:
                  'The selected strategy is ${signal.strategy.replaceAll('_', ' ')} because it currently outranks weaker alternatives.',
            ),
            if (reasons.isNotEmpty) ...<Widget>[
              const SizedBox(height: 8),
              Text(
                'Evidence',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 8),
              ...reasons.map((reason) => _EvidenceBullet(text: reason)),
            ],
          ],
        ),
      ),
    );
  }
}

class _ExplainLine extends StatelessWidget {
  const _ExplainLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 3),
          Text(value),
        ],
      ),
    );
  }
}

class _EvidenceBullet extends StatelessWidget {
  const _EvidenceBullet({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.only(top: 7),
            child: _SignalDot(color: TradingPalette.electricBlue, size: 6),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(text)),
        ],
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({
    required this.title,
    this.actionLabel,
    this.onAction,
  });

  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Text(
            title,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
        if (actionLabel != null)
          TextButton(onPressed: onAction, child: Text(actionLabel!)),
      ],
    );
  }
}

class _TrustBadge extends StatelessWidget {
  const _TrustBadge({required this.signal, required this.chart});

  final SignalModel? signal;
  final MarketChartModel? chart;

  @override
  Widget build(BuildContext context) {
    final verified = signal != null &&
        !signal!.marketDataStale &&
        signal!.price > 0 &&
        (chart == null || chart!.candles.isNotEmpty);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
      decoration: BoxDecoration(
        color: (verified ? TradingPalette.neonGreen : TradingPalette.amber)
            .withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: (verified ? TradingPalette.neonGreen : TradingPalette.amber)
              .withOpacity(0.35),
        ),
      ),
      child: Text(
        verified ? 'LIVE DATA' : 'WAITING',
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              fontWeight: FontWeight.w900,
              color: verified ? TradingPalette.neonGreen : TradingPalette.amber,
            ),
      ),
    );
  }
}

class _DirectionBadge extends StatelessWidget {
  const _DirectionBadge({required this.side, required this.color});

  final String side;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final normalized = side == 'SELL' || side == 'SHORT' ? 'SHORT' : 'LONG';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.16),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.36)),
      ),
      child: Text(
        normalized,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: color,
              fontWeight: FontWeight.w900,
            ),
      ),
    );
  }
}

class _ConfidenceRing extends StatelessWidget {
  const _ConfidenceRing({required this.confidence, required this.color});

  final double confidence;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final pct = confidence <= 1 ? confidence * 100 : confidence;
    return Container(
      width: 82,
      height: 82,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(color: color.withOpacity(0.42), width: 4),
      ),
      alignment: Alignment.center,
      child: Text(
        '${pct.clamp(0, 100).toStringAsFixed(0)}%',
        style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              color: TradingPalette.textPrimary,
            ),
      ),
    );
  }
}

class _TradeMetric extends StatelessWidget {
  const _TradeMetric({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.04),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 5),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ],
      ),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _SignalDot extends StatelessWidget {
  const _SignalDot({required this.color, this.size = 12});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color, shape: BoxShape.circle),
    );
  }
}

class _SparklinePainter extends CustomPainter {
  const _SparklinePainter({
    required this.values,
    required this.color,
  });

  final List<double> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) {
      final paint = Paint()
        ..color = TradingPalette.panelBorder
        ..strokeWidth = 1.2
        ..style = PaintingStyle.stroke;
      canvas.drawLine(
        Offset(0, size.height / 2),
        Offset(size.width, size.height / 2),
        paint,
      );
      return;
    }
    final minValue = values.reduce((a, b) => a < b ? a : b);
    final maxValue = values.reduce((a, b) => a > b ? a : b);
    final range =
        (maxValue - minValue).abs() < 0.0000001 ? 1.0 : maxValue - minValue;
    final path = Path();
    for (var index = 0; index < values.length; index++) {
      final x = size.width * index / (values.length - 1);
      final normalized = (values[index] - minValue) / range;
      final y = size.height - normalized * size.height;
      if (index == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.7
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter oldDelegate) {
    return oldDelegate.values != values || oldDelegate.color != color;
  }
}

String _displayAsset(String symbol) {
  final normalized = symbol.toUpperCase();
  for (final quote in const <String>['USDT', 'USD', 'BUSD']) {
    if (normalized.endsWith(quote) && normalized.length > quote.length) {
      return normalized.substring(0, normalized.length - quote.length);
    }
  }
  return normalized;
}

String _entryText(SignalModel? signal, ChartExecutionGuideModel? guide) {
  if (guide != null && guide.entryLow > 0 && guide.entryHigh > 0) {
    if ((guide.entryHigh - guide.entryLow).abs() < 0.0000001) {
      return _priceOrPending(guide.entryHigh);
    }
    return '${_priceOrPending(guide.entryLow)} - ${_priceOrPending(guide.entryHigh)}';
  }
  return _priceOrPending(signal?.price);
}

String _priceOrPending(double? value) {
  final price = value ?? 0;
  if (price <= 0) {
    return 'Plan pending';
  }
  return price >= 100 ? price.toStringAsFixed(2) : price.toStringAsFixed(4);
}

String _riskLabel(SignalModel signal, ChartExecutionGuideModel? guide) {
  final risk = guide?.riskPct ?? 0;
  if (risk > 0) {
    return '${risk.toStringAsFixed(2)}%';
  }
  if (signal.qualityScore >= 85) {
    return 'Low';
  }
  if (signal.qualityScore >= 70) {
    return 'Medium';
  }
  return 'High';
}

String _reasonSummary(SignalModel signal) {
  final reason = signal.reasons.firstOrNull;
  if (reason == null) {
    return 'AI selected this setup because live market structure and risk filters currently align.';
  }
  return reason;
}

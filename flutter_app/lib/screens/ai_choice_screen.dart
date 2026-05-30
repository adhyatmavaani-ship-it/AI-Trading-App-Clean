import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';

class AiChoiceScreen extends ConsumerStatefulWidget {
  const AiChoiceScreen({
    super.key,
    required this.onOpenManualTrade,
    required this.onOpenAiTrade,
  });

  final ValueChanged<String> onOpenManualTrade;
  final ValueChanged<SignalModel> onOpenAiTrade;

  @override
  ConsumerState<AiChoiceScreen> createState() => _AiChoiceScreenState();
}

class _AiChoiceScreenState extends ConsumerState<AiChoiceScreen> {
  String? _selectedSymbol;

  @override
  Widget build(BuildContext context) {
    final signalState = ref.watch(signalFeedProvider);
    final universeAsync = ref.watch(marketUniverseProvider);
    final summaryAsync = ref.watch(marketSummaryProvider);
    final universe = universeAsync.valueOrNull;
    final summary = summaryAsync.valueOrNull;
    final picks = _buildChoicePicks(
      signals: signalState.items,
      universe: universe,
      summary: summary,
    );
    final buyPicks =
        picks.where((item) => item.side == _ChoiceSide.buy).take(8).toList();
    final sellPicks =
        picks.where((item) => item.side == _ChoiceSide.sell).take(8).toList();
    final selected = _selectedPick(picks);

    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 1180;
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(4, 0, 4, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              _ChoiceHero(
                buyCount: buyPicks.length,
                sellCount: sellPicks.length,
                marketBias: summary?.sentimentLabel ?? 'SCANNING',
                confidence:
                    summary?.confidenceScore ?? _averageConfidence(picks),
              ),
              const SizedBox(height: 16),
              if (wide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(
                      flex: 6,
                      child: _ChoiceColumns(
                        buyPicks: buyPicks,
                        sellPicks: sellPicks,
                        selectedSymbol: selected?.symbol,
                        onSelect: _selectPick,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      flex: 5,
                      child: _ChoiceDetail(
                        pick: selected,
                        summary: summary,
                        onOpenManualTrade: () => _openManual(selected),
                        onOpenAiTrade: () => _openAi(selected),
                      ),
                    ),
                  ],
                )
              else
                Column(
                  children: <Widget>[
                    _ChoiceColumns(
                      buyPicks: buyPicks,
                      sellPicks: sellPicks,
                      selectedSymbol: selected?.symbol,
                      onSelect: _selectPick,
                    ),
                    const SizedBox(height: 16),
                    _ChoiceDetail(
                      pick: selected,
                      summary: summary,
                      onOpenManualTrade: () => _openManual(selected),
                      onOpenAiTrade: () => _openAi(selected),
                    ),
                  ],
                ),
            ],
          ),
        );
      },
    );
  }

  _ChoicePick? _selectedPick(List<_ChoicePick> picks) {
    if (picks.isEmpty) {
      return null;
    }
    final selectedSymbol = _selectedSymbol;
    if (selectedSymbol != null) {
      for (final pick in picks) {
        if (pick.symbol == selectedSymbol) {
          return pick;
        }
      }
    }
    return picks.first;
  }

  void _selectPick(_ChoicePick pick) {
    setState(() {
      _selectedSymbol = pick.symbol;
    });
  }

  void _openManual(_ChoicePick? pick) {
    if (pick == null) {
      return;
    }
    widget.onOpenManualTrade(pick.symbol);
  }

  void _openAi(_ChoicePick? pick) {
    if (pick == null) {
      return;
    }
    final signal = pick.signal ?? pick.toSyntheticSignal();
    widget.onOpenAiTrade(signal);
  }
}

class _ChoiceHero extends StatelessWidget {
  const _ChoiceHero({
    required this.buyCount,
    required this.sellCount,
    required this.marketBias,
    required this.confidence,
  });

  final int buyCount;
  final int sellCount;
  final String marketBias;
  final double confidence;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        children: <Widget>[
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(18),
              gradient: TradingPalette.profitGlow,
              boxShadow: <BoxShadow>[
                BoxShadow(
                  color: TradingPalette.neonGreen.withOpacity(0.24),
                  blurRadius: 28,
                ),
              ],
            ),
            child: const Icon(Icons.psychology_alt, color: Colors.black),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'AI Choice',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Crypto-wide buy and sell candidates ranked from live signals, momentum, liquidity, volatility, and risk discipline.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: TradingPalette.textMuted,
                      ),
                ),
              ],
            ),
          ),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            alignment: WrapAlignment.end,
            children: <Widget>[
              _HeroPill(
                  label: 'BUY',
                  value: buyCount.toString(),
                  color: TradingPalette.neonGreen),
              _HeroPill(
                  label: 'SELL',
                  value: sellCount.toString(),
                  color: TradingPalette.neonRed),
              _HeroPill(
                  label: marketBias.toUpperCase(),
                  value: '${confidence.toStringAsFixed(0)}%',
                  color: TradingPalette.electricBlue),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeroPill extends StatelessWidget {
  const _HeroPill({
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
      constraints: const BoxConstraints(minWidth: 92),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.34)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ],
      ),
    );
  }
}

class _ChoiceColumns extends StatelessWidget {
  const _ChoiceColumns({
    required this.buyPicks,
    required this.sellPicks,
    required this.selectedSymbol,
    required this.onSelect,
  });

  final List<_ChoicePick> buyPicks;
  final List<_ChoicePick> sellPicks;
  final String? selectedSymbol;
  final ValueChanged<_ChoicePick> onSelect;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final twoColumns = constraints.maxWidth >= 760;
        if (!twoColumns) {
          return Column(
            children: <Widget>[
              _PickColumn(
                title: 'AI Buy List',
                subtitle: 'Long setups waiting for risk confirmation',
                sideColor: TradingPalette.neonGreen,
                items: buyPicks,
                selectedSymbol: selectedSymbol,
                onSelect: onSelect,
              ),
              const SizedBox(height: 16),
              _PickColumn(
                title: 'AI Sell List',
                subtitle: 'Short or exit-pressure setups',
                sideColor: TradingPalette.neonRed,
                items: sellPicks,
                selectedSymbol: selectedSymbol,
                onSelect: onSelect,
              ),
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Expanded(
              child: _PickColumn(
                title: 'AI Buy List',
                subtitle: 'Long setups waiting for risk confirmation',
                sideColor: TradingPalette.neonGreen,
                items: buyPicks,
                selectedSymbol: selectedSymbol,
                onSelect: onSelect,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _PickColumn(
                title: 'AI Sell List',
                subtitle: 'Short or exit-pressure setups',
                sideColor: TradingPalette.neonRed,
                items: sellPicks,
                selectedSymbol: selectedSymbol,
                onSelect: onSelect,
              ),
            ),
          ],
        );
      },
    );
  }
}

class _PickColumn extends StatelessWidget {
  const _PickColumn({
    required this.title,
    required this.subtitle,
    required this.sideColor,
    required this.items,
    required this.selectedSymbol,
    required this.onSelect,
  });

  final String title;
  final String subtitle;
  final Color sideColor;
  final List<_ChoicePick> items;
  final String? selectedSymbol;
  final ValueChanged<_ChoicePick> onSelect;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 10,
                height: 36,
                decoration: BoxDecoration(
                  color: sideColor,
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: TradingPalette.textMuted,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (items.isEmpty)
            const _EmptyChoiceState()
          else
            ...items.map(
              (item) => Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _PickTile(
                  pick: item,
                  selected: selectedSymbol == item.symbol,
                  color: sideColor,
                  onTap: () => onSelect(item),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _PickTile extends StatelessWidget {
  const _PickTile({
    required this.pick,
    required this.selected,
    required this.color,
    required this.onTap,
  });

  final _ChoicePick pick;
  final bool selected;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final score = pick.confidence.clamp(0, 99.0);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: selected ? color.withOpacity(0.13) : TradingPalette.panel,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color:
                selected ? color.withOpacity(0.58) : TradingPalette.panelBorder,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    pick.symbol,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                _SideBadge(label: pick.side.label, color: color),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    _priceLabel(pick.price),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: TradingPalette.textMuted,
                        ),
                  ),
                ),
                Text(
                  '${pick.changePct >= 0 ? '+' : ''}${pick.changePct.toStringAsFixed(2)}%',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: pick.changePct >= 0
                            ? TradingPalette.neonGreen
                            : TradingPalette.neonRed,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                minHeight: 6,
                value: score / 100,
                backgroundColor: Colors.white.withOpacity(0.08),
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${score.toStringAsFixed(0)}% confidence - ${pick.source}',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: TradingPalette.textMuted,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChoiceDetail extends StatelessWidget {
  const _ChoiceDetail({
    required this.pick,
    required this.summary,
    required this.onOpenManualTrade,
    required this.onOpenAiTrade,
  });

  final _ChoicePick? pick;
  final MarketSummaryModel? summary;
  final VoidCallback onOpenManualTrade;
  final VoidCallback onOpenAiTrade;

  @override
  Widget build(BuildContext context) {
    final item = pick;
    if (item == null) {
      return const _EmptyChoiceState();
    }
    final sideColor = item.side == _ChoiceSide.buy
        ? TradingPalette.neonGreen
        : TradingPalette.neonRed;
    final pillars = _pillarsFor(item, summary);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      item.symbol,
                      style:
                          Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w900,
                              ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.side == _ChoiceSide.buy
                          ? 'AI selected this as a buy candidate.'
                          : 'AI selected this as a sell or short candidate.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: TradingPalette.textMuted,
                          ),
                    ),
                  ],
                ),
              ),
              _SideBadge(label: item.side.label, color: sideColor),
            ],
          ),
          const SizedBox(height: 16),
          _MessagePanel(
            title: 'Why this coin',
            body: item.reason,
            color: sideColor,
          ),
          const SizedBox(height: 12),
          _MessagePanel(
            title:
                item.side == _ChoiceSide.buy ? 'When to buy' : 'When to sell',
            body: item.timingMessage,
            color: TradingPalette.electricBlue,
          ),
          const SizedBox(height: 16),
          Text(
            '7-pillar pro trader check',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 10),
          ...pillars.map(
            (pillar) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: _PillarRow(pillar: pillar),
            ),
          ),
          const SizedBox(height: 16),
          _ModeChooser(
            sideColor: sideColor,
            onOpenManualTrade: onOpenManualTrade,
            onOpenAiTrade: onOpenAiTrade,
          ),
        ],
      ),
    );
  }
}

class _ModeChooser extends StatelessWidget {
  const _ModeChooser({
    required this.sideColor,
    required this.onOpenManualTrade,
    required this.onOpenAiTrade,
  });

  final Color sideColor;
  final VoidCallback onOpenManualTrade;
  final VoidCallback onOpenAiTrade;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final stacked = constraints.maxWidth < 520;
        final manual = _ModeCard(
          icon: Icons.touch_app_outlined,
          title: 'Manual Trade',
          body:
              'Open chart with AI intent cleared. You decide buy, sell, stop, and size.',
          color: TradingPalette.textMuted,
          buttonLabel: 'Open Chart',
          onPressed: onOpenManualTrade,
        );
        final aiPlan = _ModeCard(
          icon: Icons.auto_mode,
          title: 'AI Trade Plan',
          body:
              'AI waits for the perfect setup, then existing backend risk validation must approve SL, TP, and trailing stop handling.',
          color: sideColor,
          buttonLabel: 'Arm AI Plan',
          onPressed: onOpenAiTrade,
        );
        if (stacked) {
          return Column(
            children: <Widget>[
              SizedBox(width: double.infinity, child: manual),
              const SizedBox(height: 12),
              SizedBox(width: double.infinity, child: aiPlan),
            ],
          );
        }
        return Row(
          children: <Widget>[
            Expanded(child: manual),
            const SizedBox(width: 12),
            Expanded(child: aiPlan),
          ],
        );
      },
    );
  }
}

class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.icon,
    required this.title,
    required this.body,
    required this.color,
    required this.buttonLabel,
    required this.onPressed,
  });

  final IconData icon;
  final String title;
  final String body;
  final Color color;
  final String buttonLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: TradingPalette.panel,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.30)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, color: color),
          const SizedBox(height: 10),
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: onPressed,
              style: FilledButton.styleFrom(
                backgroundColor: color,
                foregroundColor: color == TradingPalette.textMuted
                    ? Colors.white
                    : Colors.black,
              ),
              child: Text(buttonLabel),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessagePanel extends StatelessWidget {
  const _MessagePanel({
    required this.title,
    required this.body,
    required this.color,
  });

  final String title;
  final String body;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            title,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            body,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  height: 1.45,
                ),
          ),
        ],
      ),
    );
  }
}

class _PillarRow extends StatelessWidget {
  const _PillarRow({required this.pillar});

  final _PillarStatus pillar;

  @override
  Widget build(BuildContext context) {
    final color = pillar.color;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: TradingPalette.panel,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(pillar.icon, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  pillar.title,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const SizedBox(height: 3),
                Text(
                  pillar.detail,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.textMuted,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            pillar.state,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
          ),
        ],
      ),
    );
  }
}

class _SideBadge extends StatelessWidget {
  const _SideBadge({
    required this.label,
    required this.color,
  });

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.36)),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w900,
            ),
      ),
    );
  }
}

class _EmptyChoiceState extends StatelessWidget {
  const _EmptyChoiceState();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: TradingPalette.panel,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Text(
        'AI is waiting for enough live market evidence before ranking coins.',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: TradingPalette.textMuted,
            ),
      ),
    );
  }
}

enum _ChoiceSide {
  buy('BUY'),
  sell('SELL');

  const _ChoiceSide(this.label);
  final String label;
}

class _ChoicePick {
  const _ChoicePick({
    required this.symbol,
    required this.side,
    required this.price,
    required this.changePct,
    required this.volumeRatio,
    required this.volatilityPct,
    required this.confidence,
    required this.score,
    required this.source,
    required this.reason,
    required this.timingMessage,
    this.signal,
  });

  final String symbol;
  final _ChoiceSide side;
  final double price;
  final double changePct;
  final double volumeRatio;
  final double volatilityPct;
  final double confidence;
  final double score;
  final String source;
  final String reason;
  final String timingMessage;
  final SignalModel? signal;

  SignalModel toSyntheticSignal() {
    return SignalModel(
      signalId: 'ai-choice-${symbol.toLowerCase()}-${side.label.toLowerCase()}',
      symbol: symbol,
      action: side.label,
      strategy: 'AI_CHOICE_ADVISORY',
      confidence: confidence,
      alphaScore: score,
      regime: changePct >= 0 ? 'MOMENTUM' : 'DISTRIBUTION',
      price: price,
      signalVersion: 1,
      publishedAt: DateTime.now(),
      decisionReason: reason,
      degradedMode: false,
      requiredTier: 'free',
      minBalance: 0,
      rejectionReason: null,
      lowConfidence: confidence < 70,
      quality: confidence >= 70 ? 'approved' : 'watchlist',
      qualityScore: confidence,
      qualityReasons: <String>[timingMessage],
      executionAllowed: false,
      marketDataStale: false,
      marketDataSources: const <String, String>{'source': 'ai_choice'},
    );
  }
}

class _PillarStatus {
  const _PillarStatus({
    required this.title,
    required this.detail,
    required this.state,
    required this.icon,
    required this.color,
  });

  final String title;
  final String detail;
  final String state;
  final IconData icon;
  final Color color;
}

List<_ChoicePick> _buildChoicePicks({
  required List<SignalModel> signals,
  required MarketUniverseModel? universe,
  required MarketSummaryModel? summary,
}) {
  final picks = <_ChoicePick>[];
  final seen = <String>{};

  void addPick(_ChoicePick pick) {
    final key = '${pick.side.label}:${pick.symbol}';
    if (pick.symbol.trim().isEmpty || seen.contains(key)) {
      return;
    }
    seen.add(key);
    picks.add(pick);
  }

  for (final signal in signals) {
    final side = signal.action.toUpperCase() == 'SELL'
        ? _ChoiceSide.sell
        : _ChoiceSide.buy;
    final confidence = _clampScore(
      math.max(signal.confidence, signal.qualityScore),
    );
    addPick(
      _ChoicePick(
        symbol: signal.symbol,
        side: side,
        price: signal.price,
        changePct: side == _ChoiceSide.buy ? 0.8 : -0.8,
        volumeRatio: 1.2,
        volatilityPct: 1.8,
        confidence: confidence,
        score: _clampScore(signal.alphaScore + (signal.isApproved ? 6 : 0)),
        source: signal.isApproved ? 'verified signal' : 'watchlist signal',
        reason: signal.reasons.take(3).join(' '),
        timingMessage: _timingMessage(side, confidence, signal.symbol),
        signal: signal,
      ),
    );
  }

  final buyEntries = <MarketUniverseEntryModel>[
    ...?universe?.aiPicks,
    ...?universe?.topGainers,
    ...?universe?.highVolatility.where((item) => item.changePct >= 0),
  ];
  final sellEntries = <MarketUniverseEntryModel>[
    ...?universe?.topLosers,
    ...?universe?.highVolatility.where((item) => item.changePct < 0),
  ];

  for (final entry in buyEntries) {
    final confidence = _entryConfidence(entry, summary, _ChoiceSide.buy);
    addPick(_pickFromEntry(entry, _ChoiceSide.buy, confidence));
  }
  for (final entry in sellEntries) {
    final confidence = _entryConfidence(entry, summary, _ChoiceSide.sell);
    addPick(_pickFromEntry(entry, _ChoiceSide.sell, confidence));
  }

  final scanner =
      summary?.scanner.candidates ?? const <ScannerCandidateModel>[];
  for (final candidate in scanner.take(12)) {
    final side = candidate.changePct >= 0 ? _ChoiceSide.buy : _ChoiceSide.sell;
    final confidence = _clampScore(
      54 + candidate.potentialScore * 0.38 + candidate.volumeRatio * 4,
    );
    addPick(
      _ChoicePick(
        symbol: candidate.symbol,
        side: side,
        price: candidate.price,
        changePct: candidate.changePct,
        volumeRatio: candidate.volumeRatio,
        volatilityPct: candidate.volatilityPct,
        confidence: confidence,
        score: _clampScore(candidate.potentialScore),
        source: 'market scanner',
        reason: _reasonFor(
          side: side,
          changePct: candidate.changePct,
          volumeRatio: candidate.volumeRatio,
          volatilityPct: candidate.volatilityPct,
          confidence: confidence,
        ),
        timingMessage: _timingMessage(side, confidence, candidate.symbol),
      ),
    );
  }

  picks.sort((a, b) => b.score.compareTo(a.score));
  return picks;
}

_ChoicePick _pickFromEntry(
  MarketUniverseEntryModel entry,
  _ChoiceSide side,
  double confidence,
) {
  return _ChoicePick(
    symbol: entry.symbol,
    side: side,
    price: entry.price,
    changePct: entry.changePct,
    volumeRatio: entry.volumeRatio,
    volatilityPct: entry.volatilityPct,
    confidence: confidence,
    score: _clampScore(entry.potentialScore + confidence * 0.28),
    source: entry.category.replaceAll('_', ' '),
    reason: _reasonFor(
      side: side,
      changePct: entry.changePct,
      volumeRatio: entry.volumeRatio,
      volatilityPct: entry.volatilityPct,
      confidence: confidence,
    ),
    timingMessage: _timingMessage(side, confidence, entry.symbol),
  );
}

List<_PillarStatus> _pillarsFor(_ChoicePick pick, MarketSummaryModel? summary) {
  final marketRisk = (summary?.avgVolatilityPct ?? pick.volatilityPct) > 4.5;
  final leaderAligned = pick.side == _ChoiceSide.buy
      ? (summary?.sentimentScore ?? 50) >= 48
      : (summary?.sentimentScore ?? 50) <= 58;
  final liquid = pick.volumeRatio >= 1.05 || pick.score >= 70;
  final momentumAligned = pick.side == _ChoiceSide.buy
      ? pick.changePct >= -0.3
      : pick.changePct <= 0.3;
  final highConfidence = pick.confidence >= 72;

  return <_PillarStatus>[
    _pillar(
      title: 'BTC and ETH leader direction',
      good: leaderAligned,
      warning: !leaderAligned && !marketRisk,
      detail: leaderAligned
          ? 'Market leader bias is compatible with this setup.'
          : 'Leader bias is not fully aligned, so AI keeps this conservative.',
      icon: Icons.account_tree_outlined,
    ),
    _pillar(
      title: 'Order book, liquidity, slippage',
      good: liquid,
      warning: pick.volumeRatio >= 0.8,
      detail:
          'Volume ratio ${pick.volumeRatio.toStringAsFixed(2)}x. Avoid size that can create slippage.',
      icon: Icons.waterfall_chart,
    ),
    _pillar(
      title: 'OI and funding rates',
      good: highConfidence && !marketRisk,
      warning: true,
      detail:
          'Derivatives confirmation is treated as required before live execution approval.',
      icon: Icons.balance_outlined,
    ),
    _pillar(
      title: 'Price action and liquidity sweeps',
      good: momentumAligned,
      warning: pick.changePct.abs() < 2.8,
      detail:
          'Current move is ${pick.changePct.toStringAsFixed(2)}%; wait for reclaim or breakdown confirmation.',
      icon: Icons.timeline,
    ),
    _pillar(
      title: 'VWAP, EMA, RSI, MACD momentum',
      good: highConfidence,
      warning: pick.confidence >= 62,
      detail:
          'AI confidence ${pick.confidence.toStringAsFixed(0)}%; momentum still needs chart confirmation.',
      icon: Icons.show_chart,
    ),
    _pillar(
      title: 'Strict risk math',
      good: true,
      warning: false,
      detail:
          'Use 1-2% max risk, hard invalidation, backend SL/TP, and trailing stop only after approval.',
      icon: Icons.shield_outlined,
    ),
    _pillar(
      title: 'Social and whale tracker',
      good: false,
      warning: true,
      detail:
          'News and whale data are not trusted unless confirmed by backend sources.',
      icon: Icons.radar_outlined,
    ),
  ];
}

_PillarStatus _pillar({
  required String title,
  required String detail,
  required IconData icon,
  required bool good,
  required bool warning,
}) {
  final color = good
      ? TradingPalette.neonGreen
      : warning
          ? TradingPalette.amber
          : TradingPalette.neonRed;
  return _PillarStatus(
    title: title,
    detail: detail,
    state: good
        ? 'PASS'
        : warning
            ? 'WAIT'
            : 'RISK',
    icon: icon,
    color: color,
  );
}

String _reasonFor({
  required _ChoiceSide side,
  required double changePct,
  required double volumeRatio,
  required double volatilityPct,
  required double confidence,
}) {
  final direction =
      side == _ChoiceSide.buy ? 'upside continuation' : 'downside pressure';
  return 'AI sees $direction with ${changePct.toStringAsFixed(2)}% move, ${volumeRatio.toStringAsFixed(2)}x liquidity participation, and ${volatilityPct.toStringAsFixed(2)}% volatility. Confidence is ${confidence.toStringAsFixed(0)}%, so execution still waits for chart and risk validation.';
}

String _timingMessage(_ChoiceSide side, double confidence, String symbol) {
  final action = side == _ChoiceSide.buy ? 'Buy' : 'Sell';
  final trigger = side == _ChoiceSide.buy
      ? 'price reclaims VWAP or breaks the nearest resistance with volume'
      : 'price rejects VWAP or loses the nearest support with volume';
  return '$action $symbol only after $trigger. If confirmation is weak, stay flat. In AI Trade Plan, the app waits for risk approval before any backend execution.';
}

double _entryConfidence(
  MarketUniverseEntryModel entry,
  MarketSummaryModel? summary,
  _ChoiceSide side,
) {
  final sentiment = summary?.confidenceScore ?? 55;
  final directional =
      side == _ChoiceSide.buy ? entry.changePct : -entry.changePct;
  return _clampScore(
    48 +
        entry.potentialScore * 0.25 +
        entry.volumeRatio * 4 +
        directional * 1.8 +
        sentiment * 0.16 -
        math.max(0, entry.volatilityPct - 5) * 2,
  );
}

double _averageConfidence(List<_ChoicePick> picks) {
  if (picks.isEmpty) {
    return 0;
  }
  return picks.take(8).fold<double>(0, (sum, item) => sum + item.confidence) /
      math.min(8, picks.length);
}

double _clampScore(double value) {
  if (value.isNaN || !value.isFinite) {
    return 0;
  }
  return value.clamp(0, 99).toDouble();
}

String _priceLabel(double price) {
  if (price <= 0 || !price.isFinite) {
    return 'price waiting';
  }
  if (price >= 100) {
    return price.toStringAsFixed(2);
  }
  if (price >= 1) {
    return price.toStringAsFixed(4);
  }
  return price.toStringAsFixed(6);
}

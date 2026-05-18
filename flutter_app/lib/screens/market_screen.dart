import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../models/market_chart.dart';
import '../widgets/glass_panel.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';

class MarketScreen extends ConsumerStatefulWidget {
  const MarketScreen({super.key, required this.onOpenChart});

  final ValueChanged<String> onOpenChart;

  @override
  ConsumerState<MarketScreen> createState() => _MarketScreenState();
}

class _MarketScreenState extends ConsumerState<MarketScreen> {
  String _query = '';
  final TextEditingController _searchController = TextEditingController();
  final Set<String> _favorites = <String>{'BTCUSDT', 'ETHUSDT', 'SOLUSDT'};

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final universeAsync = ref.watch(marketUniverseProvider);
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(marketUniverseProvider);
        ref.invalidate(marketSummaryProvider);
      },
      child: universeAsync.when(
        data: (universe) {
          final items = _filteredItems(universe.items);
          final favorites = universe.items
              .where((item) => _favorites.contains(item.symbol.toUpperCase()))
              .toList();
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
            children: <Widget>[
              _SearchHeader(
                controller: _searchController,
                query: _query,
                onChanged: (value) => setState(() => _query = value),
              ),
              if (favorites.isNotEmpty) ...<Widget>[
                const SizedBox(height: 14),
                _AssetRail(
                  title: 'Watchlist',
                  items: favorites,
                  onTap: _openChart,
                  onFavorite: _toggleFavorite,
                  favorites: _favorites,
                ),
              ],
              const SizedBox(height: 14),
              _DiscoveryGrid(
                gainers: universe.topGainers,
                losers: universe.topLosers,
                trending: universe.aiPicks.isNotEmpty
                    ? universe.aiPicks
                    : universe.highVolatility,
                onTap: _openChart,
                onFavorite: _toggleFavorite,
                favorites: _favorites,
              ),
              const SizedBox(height: 14),
              _RankedList(
                title:
                    _query.trim().isEmpty ? 'Volume Ranking' : 'Search Results',
                items: items,
                onTap: _openChart,
                onFavorite: _toggleFavorite,
                favorites: _favorites,
              ),
            ],
          );
        },
        loading: () => ListView(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
          children: const <Widget>[
            LoadingState(label: 'Loading live market universe...'),
          ],
        ),
        error: (error, _) => ListView(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 32),
          children: const <Widget>[
            ErrorState(
              message:
                  'Live market feed unavailable. No prices or signals are being invented.',
            ),
          ],
        ),
      ),
    );
  }

  List<MarketUniverseEntryModel> _filteredItems(
    List<MarketUniverseEntryModel> items,
  ) {
    final normalized = _query.trim().toUpperCase();
    final source = normalized.isEmpty
        ? items
        : items
            .where((item) => item.symbol.toUpperCase().contains(normalized))
            .toList();
    return [...source]..sort((a, b) {
        final score = b.potentialScore.compareTo(a.potentialScore);
        if (score != 0) {
          return score;
        }
        return b.quoteVolume.compareTo(a.quoteVolume);
      });
  }

  void _openChart(String symbol) {
    ref.read(selectedMarketSymbolProvider.notifier).state = symbol;
    widget.onOpenChart(symbol);
  }

  void _toggleFavorite(String symbol) {
    setState(() {
      final normalized = symbol.toUpperCase();
      if (_favorites.contains(normalized)) {
        _favorites.remove(normalized);
      } else {
        _favorites.add(normalized);
      }
    });
  }
}

class _SearchHeader extends StatelessWidget {
  const _SearchHeader({
    required this.controller,
    required this.query,
    required this.onChanged,
  });

  final TextEditingController controller;
  final String query;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.all(14),
      glowColor: TradingPalette.electricBlue,
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        decoration: InputDecoration(
          prefixIcon: const Icon(Icons.search_rounded),
          suffixIcon: query.isEmpty
              ? null
              : IconButton(
                  tooltip: 'Clear search',
                  onPressed: () {
                    controller.clear();
                    onChanged('');
                  },
                  icon: const Icon(Icons.close_rounded),
                ),
          hintText: 'Search BTC, ETH, SOL...',
          border: InputBorder.none,
        ),
      ),
    );
  }
}

class _DiscoveryGrid extends StatelessWidget {
  const _DiscoveryGrid({
    required this.gainers,
    required this.losers,
    required this.trending,
    required this.onTap,
    required this.onFavorite,
    required this.favorites,
  });

  final List<MarketUniverseEntryModel> gainers;
  final List<MarketUniverseEntryModel> losers;
  final List<MarketUniverseEntryModel> trending;
  final ValueChanged<String> onTap;
  final ValueChanged<String> onFavorite;
  final Set<String> favorites;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 900;
        final sections = <Widget>[
          _AssetRail(
            title: 'Top Gainers',
            items: gainers,
            onTap: onTap,
            onFavorite: onFavorite,
            favorites: favorites,
          ),
          _AssetRail(
            title: 'Top Losers',
            items: losers,
            onTap: onTap,
            onFavorite: onFavorite,
            favorites: favorites,
          ),
          _AssetRail(
            title: 'AI Trending',
            items: trending,
            onTap: onTap,
            onFavorite: onFavorite,
            favorites: favorites,
          ),
        ];
        return wide
            ? Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: sections
                    .map(
                      (section) => Expanded(
                        child: Padding(
                          padding: const EdgeInsets.only(right: 10),
                          child: section,
                        ),
                      ),
                    )
                    .toList(),
              )
            : Column(
                children: sections
                    .map(
                      (section) => Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: section,
                      ),
                    )
                    .toList(),
              );
      },
    );
  }
}

class _AssetRail extends StatelessWidget {
  const _AssetRail({
    required this.title,
    required this.items,
    required this.onTap,
    required this.onFavorite,
    required this.favorites,
  });

  final String title;
  final List<MarketUniverseEntryModel> items;
  final ValueChanged<String> onTap;
  final ValueChanged<String> onFavorite;
  final Set<String> favorites;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const SizedBox.shrink();
    }
    return GlassPanel(
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
          for (final item in items.take(5))
            _MarketAssetTile(
              item: item,
              compact: true,
              favorite: favorites.contains(item.symbol.toUpperCase()),
              onTap: () => onTap(item.symbol),
              onFavorite: () => onFavorite(item.symbol),
            ),
        ],
      ),
    );
  }
}

class _RankedList extends StatelessWidget {
  const _RankedList({
    required this.title,
    required this.items,
    required this.onTap,
    required this.onFavorite,
    required this.favorites,
  });

  final String title;
  final List<MarketUniverseEntryModel> items;
  final ValueChanged<String> onTap;
  final ValueChanged<String> onFavorite;
  final Set<String> favorites;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.violet,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              const StatusBadge(label: 'LIVE'),
            ],
          ),
          const SizedBox(height: 12),
          if (items.isEmpty)
            Text(
              'No matching live assets. The app is not filling this list with placeholders.',
              style: Theme.of(context).textTheme.bodySmall,
            )
          else
            for (final item in items.take(30))
              _MarketAssetTile(
                item: item,
                favorite: favorites.contains(item.symbol.toUpperCase()),
                onTap: () => onTap(item.symbol),
                onFavorite: () => onFavorite(item.symbol),
              ),
        ],
      ),
    );
  }
}

class _MarketAssetTile extends StatelessWidget {
  const _MarketAssetTile({
    required this.item,
    required this.favorite,
    required this.onTap,
    required this.onFavorite,
    this.compact = false,
  });

  final MarketUniverseEntryModel item;
  final bool favorite;
  final VoidCallback onTap;
  final VoidCallback onFavorite;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final changeColor =
        item.changePct >= 0 ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final score = item.potentialScore > 0
        ? item.potentialScore
        : (50 + item.volumeRatio * 12 + item.volatilityPct * 2).clamp(0, 100);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Padding(
        padding: EdgeInsets.only(bottom: compact ? 10 : 12),
        child: Row(
          children: <Widget>[
            IconButton(
              tooltip: favorite ? 'Remove favorite' : 'Add favorite',
              onPressed: onFavorite,
              icon: Icon(
                favorite ? Icons.star_rounded : Icons.star_border_rounded,
                color:
                    favorite ? TradingPalette.amber : TradingPalette.textMuted,
              ),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    item.symbol,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  Text(
                    'Vol ${_compactNumber(item.quoteVolume)}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            ),
            SizedBox(
              width: compact ? 64 : 84,
              height: 28,
              child: CustomPaint(
                painter: _MarketSparklinePainter(
                  values: item.sparkline,
                  color: changeColor,
                ),
              ),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: <Widget>[
                Text(
                  _formatMarketPrice(item.price),
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
                Text(
                  '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: changeColor,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
            const SizedBox(width: 10),
            StatusBadge(
              label: 'AI ${score.toStringAsFixed(0)}',
              color: score >= 70
                  ? TradingPalette.neonGreen
                  : score >= 50
                      ? TradingPalette.amber
                      : TradingPalette.textMuted,
            ),
          ],
        ),
      ),
    );
  }
}

class _MarketSparklinePainter extends CustomPainter {
  const _MarketSparklinePainter({required this.values, required this.color});

  final List<double> values;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) {
      canvas.drawLine(
        Offset(0, size.height / 2),
        Offset(size.width, size.height / 2),
        Paint()
          ..color = TradingPalette.panelBorder
          ..strokeWidth = 1.2,
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
      final y =
          size.height - ((values[index] - minValue) / range) * size.height;
      if (index == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 1.8
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _MarketSparklinePainter oldDelegate) {
    return oldDelegate.values != values || oldDelegate.color != color;
  }
}

String _formatMarketPrice(double price) {
  if (price <= 0) {
    return 'No live price';
  }
  return price >= 100 ? price.toStringAsFixed(2) : price.toStringAsFixed(4);
}

String _compactNumber(double value) {
  if (value >= 1000000000) {
    return '${(value / 1000000000).toStringAsFixed(1)}B';
  }
  if (value >= 1000000) {
    return '${(value / 1000000).toStringAsFixed(1)}M';
  }
  if (value >= 1000) {
    return '${(value / 1000).toStringAsFixed(1)}K';
  }
  return value.toStringAsFixed(0);
}

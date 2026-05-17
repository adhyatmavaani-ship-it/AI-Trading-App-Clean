import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../features/retention/providers/retention_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../models/signal.dart';
import '../widgets/live_pulse_indicator.dart';
import 'ai_copilot_screen.dart';
import 'ai_trade_center_screen.dart';
import 'onboarding_screen.dart';
import 'portfolio_screen.dart';
import 'trade_screen.dart';

enum AppDestination { tradeCenter, chart, portfolio, copilot }

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  AppDestination _destination = AppDestination.tradeCenter;

  @override
  Widget build(BuildContext context) {
    final onboardingCompleted = ref.watch(onboardingCompletedProvider);
    if (!onboardingCompleted) {
      return const OnboardingScreen();
    }
    return LayoutBuilder(
      builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 1080;
        final content = AnimatedSwitcher(
          duration: const Duration(milliseconds: 320),
          switchInCurve: Curves.easeOutCubic,
          switchOutCurve: Curves.easeInCubic,
          child: KeyedSubtree(
            key: ValueKey<AppDestination>(_destination),
            child: _buildScreen(),
          ),
        );
        if (desktop) {
          return Scaffold(
            body: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: <Color>[
                    TradingPalette.midnight,
                    Color(0xFF0F1324),
                    TradingPalette.midnight,
                  ],
                ),
              ),
              child: SafeArea(
                child: Row(
                  children: <Widget>[
                    _DesktopSidebar(
                      current: _destination,
                      onSelect: _selectDestination,
                    ),
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(10, 18, 18, 18),
                        child: Column(
                          children: <Widget>[
                            _ShellHeader(
                              title: _titleFor(_destination),
                              subtitle: _subtitleFor(_destination),
                            ),
                            const SizedBox(height: 18),
                            Expanded(child: content),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }

        return Scaffold(
          appBar: AppBar(
            title: Text(_titleFor(_destination)),
            bottom: PreferredSize(
              preferredSize: const Size.fromHeight(24),
              child: Padding(
                padding: const EdgeInsets.only(left: 16, right: 16, bottom: 12),
                child: Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    _subtitleFor(_destination),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              ),
            ),
          ),
          body: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: <Color>[
                  TradingPalette.midnight,
                  Color(0xFF0F1324),
                  TradingPalette.midnight,
                ],
              ),
            ),
            child: SafeArea(child: content),
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: AppDestination.values.indexOf(_destination),
            onDestinationSelected: (index) =>
                _selectDestination(AppDestination.values[index]),
            destinations: const <NavigationDestination>[
              NavigationDestination(
                icon: Icon(Icons.auto_awesome_outlined),
                selectedIcon: Icon(Icons.auto_awesome),
                label: 'AI Trade',
              ),
              NavigationDestination(
                icon: Icon(Icons.candlestick_chart_outlined),
                selectedIcon: Icon(Icons.candlestick_chart),
                label: 'Chart',
              ),
              NavigationDestination(
                icon: Icon(Icons.account_balance_wallet_outlined),
                selectedIcon: Icon(Icons.account_balance_wallet),
                label: 'Portfolio',
              ),
              NavigationDestination(
                icon: Icon(Icons.psychology_alt_outlined),
                selectedIcon: Icon(Icons.psychology_alt),
                label: 'Copilot',
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildScreen() {
    switch (_destination) {
      case AppDestination.tradeCenter:
        return AiTradeCenterScreen(
          onOpenChart: () => _selectDestination(AppDestination.chart),
          onOpenTradeSignal: _openTradeWithSignal,
        );
      case AppDestination.chart:
        return const TradeScreen();
      case AppDestination.portfolio:
        return const PortfolioScreen();
      case AppDestination.copilot:
        return const AiCopilotScreen();
    }
  }

  void _openTradeWithSignal(SignalModel signal) {
    ref.read(selectedMarketSymbolProvider.notifier).state = signal.symbol;
    ref.read(selectedTradeIntentProvider.notifier).state =
        TradeIntent.fromSignal(signal);
    ref.read(localAiMemoryProvider.notifier).recordAsset(signal.symbol);
    ref.read(localAiMemoryProvider.notifier).recordMode(signal.strategy);
    _selectDestination(AppDestination.chart);
  }

  void _selectDestination(AppDestination destination) {
    setState(() {
      _destination = destination;
    });
  }

  String _titleFor(AppDestination destination) {
    return switch (destination) {
      AppDestination.tradeCenter => 'AI Trade Center',
      AppDestination.chart => 'Advanced Chart',
      AppDestination.portfolio => 'Portfolio',
      AppDestination.copilot => 'AI Copilot',
    };
  }

  String _subtitleFor(AppDestination destination) {
    return switch (destination) {
      AppDestination.tradeCenter =>
        'Best verified setup, entry plan, risk, and AI reasoning in one view.',
      AppDestination.chart =>
        'Live candles, execution guide, market structure, and orderflow context.',
      AppDestination.portfolio =>
        'Equity, PnL, drawdown, exposure, positions, and trade discipline.',
      AppDestination.copilot =>
        'Ask market and risk questions in plain language.',
    };
  }
}

class _DesktopSidebar extends StatelessWidget {
  const _DesktopSidebar({
    required this.current,
    required this.onSelect,
  });

  final AppDestination current;
  final ValueChanged<AppDestination> onSelect;

  @override
  Widget build(BuildContext context) {
    final items = <({AppDestination value, IconData icon, String label})>[
      (
        value: AppDestination.tradeCenter,
        icon: Icons.auto_awesome,
        label: 'AI Trade Center'
      ),
      (
        value: AppDestination.chart,
        icon: Icons.candlestick_chart,
        label: 'Advanced Chart'
      ),
      (
        value: AppDestination.portfolio,
        icon: Icons.account_balance_wallet,
        label: 'Portfolio'
      ),
      (
        value: AppDestination.copilot,
        icon: Icons.psychology_alt,
        label: 'AI Copilot'
      ),
    ];

    return Container(
      width: 260,
      margin: const EdgeInsets.all(18),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _BrandLockup(),
          const SizedBox(height: 28),
          ...items.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _SidebarTile(
                selected: current == item.value,
                icon: item.icon,
                label: item.label,
                onTap: () => onSelect(item.value),
              ),
            ),
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: <Color>[
                  TradingPalette.violet.withOpacity(0.18),
                  TradingPalette.electricBlue.withOpacity(0.10),
                ],
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: TradingPalette.panelBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Decision Desk',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Verified trade ideas only. No execution without backend risk approval.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ShellHeader extends StatelessWidget {
  const _ShellHeader({
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 18),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 4),
                Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          const LivePulseIndicator(
            label: 'LIVE',
            color: TradingPalette.electricBlue,
          ),
        ],
      ),
    );
  }
}

class _BrandLockup extends StatelessWidget {
  const _BrandLockup();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            gradient: TradingPalette.primaryGlow,
          ),
          child: const Icon(Icons.auto_graph_rounded, color: Colors.white),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'AI Trading App',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text(
              'Institutional AI terminal',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ],
    );
  }
}

class _SidebarTile extends StatelessWidget {
  const _SidebarTile({
    required this.selected,
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final bool selected;
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: selected
              ? LinearGradient(
                  colors: <Color>[
                    TradingPalette.violet.withOpacity(0.22),
                    TradingPalette.electricBlue.withOpacity(0.14),
                  ],
                )
              : null,
          border: Border.all(
            color: selected
                ? TradingPalette.violet.withOpacity(0.30)
                : Colors.transparent,
          ),
        ),
        child: Row(
          children: <Widget>[
            Icon(
              icon,
              color: selected
                  ? TradingPalette.textPrimary
                  : TradingPalette.textMuted,
            ),
            const SizedBox(width: 12),
            Text(
              label,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: selected
                        ? TradingPalette.textPrimary
                        : TradingPalette.textMuted,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

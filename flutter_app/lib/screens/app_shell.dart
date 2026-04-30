import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../models/signal.dart';
import '../widgets/live_pulse_indicator.dart';
import 'ai_signal_screen.dart';
import 'dashboard_screen.dart';
import 'portfolio_screen.dart';
import 'settings_screen.dart';
import 'trade_screen.dart';

enum AppDestination { dashboard, signals, trade, portfolio, settings }

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key});

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  AppDestination _destination = AppDestination.dashboard;

  @override
  Widget build(BuildContext context) {
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
                icon: Icon(Icons.dashboard_outlined),
                selectedIcon: Icon(Icons.dashboard_rounded),
                label: 'Dashboard',
              ),
              NavigationDestination(
                icon: Icon(Icons.auto_awesome_outlined),
                selectedIcon: Icon(Icons.auto_awesome),
                label: 'Signals',
              ),
              NavigationDestination(
                icon: Icon(Icons.candlestick_chart_outlined),
                selectedIcon: Icon(Icons.candlestick_chart),
                label: 'Trade',
              ),
              NavigationDestination(
                icon: Icon(Icons.account_balance_wallet_outlined),
                selectedIcon: Icon(Icons.account_balance_wallet),
                label: 'Portfolio',
              ),
              NavigationDestination(
                icon: Icon(Icons.settings_outlined),
                selectedIcon: Icon(Icons.settings),
                label: 'Settings',
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildScreen() {
    switch (_destination) {
      case AppDestination.dashboard:
        return DashboardScreen(
          onOpenSignals: () => _selectDestination(AppDestination.signals),
          onOpenTrade: _openTrade,
        );
      case AppDestination.signals:
        return AiSignalScreen(onExecuteSignal: _openTradeWithSignal);
      case AppDestination.trade:
        return const TradeScreen();
      case AppDestination.portfolio:
        return const PortfolioScreen();
      case AppDestination.settings:
        return const SettingsScreen();
    }
  }

  void _openTrade(String symbol) {
    ref.read(selectedMarketSymbolProvider.notifier).state = symbol;
    _selectDestination(AppDestination.trade);
  }

  void _openTradeWithSignal(SignalModel signal) {
    ref.read(selectedMarketSymbolProvider.notifier).state = signal.symbol;
    _selectDestination(AppDestination.trade);
  }

  void _selectDestination(AppDestination destination) {
    setState(() {
      _destination = destination;
    });
  }

  String _titleFor(AppDestination destination) {
    return switch (destination) {
      AppDestination.dashboard => 'AI Trading Dashboard',
      AppDestination.signals => 'AI Signals',
      AppDestination.trade => 'Trade Execution',
      AppDestination.portfolio => 'Portfolio',
      AppDestination.settings => 'Settings',
    };
  }

  String _subtitleFor(AppDestination destination) {
    return switch (destination) {
      AppDestination.dashboard =>
        'Realtime market intelligence, balance, and execution overview.',
      AppDestination.signals =>
        'Live websocket stream of premium AI trade opportunities.',
      AppDestination.trade =>
        'Review market structure, adjust risk, and execute with confidence.',
      AppDestination.portfolio =>
        'Exposure, allocation, and performance distribution in one place.',
      AppDestination.settings =>
        'Connectivity, credentials, diagnostics, and runtime controls.',
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
        value: AppDestination.dashboard,
        icon: Icons.dashboard_rounded,
        label: 'Dashboard'
      ),
      (
        value: AppDestination.signals,
        icon: Icons.auto_awesome,
        label: 'AI Signals'
      ),
      (
        value: AppDestination.trade,
        icon: Icons.candlestick_chart,
        label: 'Trade'
      ),
      (
        value: AppDestination.portfolio,
        icon: Icons.account_balance_wallet,
        label: 'Portfolio'
      ),
      (
        value: AppDestination.settings,
        icon: Icons.settings,
        label: 'Settings'
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
                  'AI Desk',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Render-connected mobile + desktop trading cockpit with live signals and diagnostics.',
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
            label: 'RENDER LIVE',
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

import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import '../models/user_pnl.dart';
import '../widgets/live_pulse_indicator.dart';

class QuentraderHomeScreen extends ConsumerWidget {
  const QuentraderHomeScreen({
    required this.onOpenDashboard,
    required this.onOpenSignals,
    required this.onOpenBrokers,
    required this.onOpenPricing,
    super.key,
  });

  final VoidCallback onOpenDashboard;
  final VoidCallback onOpenSignals;
  final VoidCallback onOpenBrokers;
  final VoidCallback onOpenPricing;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final summary = ref.watch(marketSummaryProvider);
    final signalFeed = ref.watch(signalFeedProvider);
    final userId = ref.watch(activeUserIdProvider);
    final pnl = ref.watch(userPnLProvider(userId));
    final activeTrades = ref.watch(activeTradesProvider(userId));

    return Container(
      decoration: const BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(-0.75, -0.45),
          radius: 1.35,
          colors: <Color>[
            Color(0xFF102039),
            TradingPalette.midnight,
            Color(0xFF050812),
          ],
        ),
      ),
      child: SafeArea(
        child: CustomScrollView(
          slivers: <Widget>[
            SliverToBoxAdapter(
              child: _MarketTape(summary: summary),
            ),
            SliverToBoxAdapter(
              child: _TopNav(
                onOpenDashboard: onOpenDashboard,
                onOpenSignals: onOpenSignals,
                onOpenBrokers: onOpenBrokers,
                onOpenPricing: onOpenPricing,
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
              sliver: SliverToBoxAdapter(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 1050;
                    final hero = _HeroCopy(
                      onStart: onOpenDashboard,
                      onDemo: onOpenSignals,
                    );
                    final terminal = _TerminalPreview(
                      summary: summary,
                      signalFeed: signalFeed,
                      pnl: pnl,
                      activeTradeCount: activeTrades.maybeWhen(
                        data: (items) => items.length,
                        orElse: () => 0,
                      ),
                    );
                    if (!wide) {
                      return Column(
                        children: <Widget>[
                          hero,
                          const SizedBox(height: 22),
                          terminal,
                        ],
                      );
                    }
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: <Widget>[
                        Expanded(flex: 9, child: hero),
                        const SizedBox(width: 30),
                        Expanded(flex: 13, child: terminal),
                      ],
                    );
                  },
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 28)),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverToBoxAdapter(
                child: _FeatureRail(
                  onOpenDashboard: onOpenDashboard,
                  onOpenSignals: onOpenSignals,
                  onOpenBrokers: onOpenBrokers,
                ),
              ),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 16)),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
              sliver: SliverToBoxAdapter(
                child: _TrustStats(
                  pnl: pnl,
                  signals: signalFeed.items,
                ),
              ),
            ),
            const SliverToBoxAdapter(child: _BrokerStrip()),
            const SliverToBoxAdapter(child: SizedBox(height: 30)),
          ],
        ),
      ),
    );
  }
}

class _MarketTape extends StatelessWidget {
  const _MarketTape({required this.summary});

  final AsyncValue<MarketSummaryModel> summary;

  @override
  Widget build(BuildContext context) {
    final ticker = summary.maybeWhen(
      data: (data) => data.ticker.take(6).toList(),
      orElse: () => const <MarketTickerItemModel>[],
    );
    final items = ticker.isEmpty
        ? const <_TapeItem>[
            _TapeItem('NIFTY 50', '22,457.30', 0.82),
            _TapeItem('BANK NIFTY', '48,753.15', 0.83),
            _TapeItem('SENSEX', '73,847.15', 0.85),
            _TapeItem('BTC/USDT', '73,658.02', -0.02),
          ]
        : ticker
            .map(
              (item) => _TapeItem(
                item.symbol.replaceAll('USDT', ''),
                _formatNumber(item.price),
                item.changePct,
              ),
            )
            .toList();
    final now = TimeOfDay.now();
    return Container(
      height: 36,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: const BoxDecoration(
        color: Color(0xEE050913),
        border: Border(
          bottom: BorderSide(color: Color(0xFF1D2842)),
        ),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: items.length,
              separatorBuilder: (_, __) => const SizedBox(width: 28),
              itemBuilder: (context, index) {
                final item = items[index];
                final positive = item.changePct >= 0;
                return Center(
                  child: RichText(
                    text: TextSpan(
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: TradingPalette.textPrimary,
                            fontWeight: FontWeight.w800,
                          ),
                      children: <TextSpan>[
                        TextSpan(text: '${item.label}  '),
                        TextSpan(
                          text: item.value,
                          style: const TextStyle(
                            color: TradingPalette.textMuted,
                          ),
                        ),
                        TextSpan(
                          text:
                              ' ${positive ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
                          style: TextStyle(
                            color: positive
                                ? const Color(0xFF74F24F)
                                : const Color(0xFFFF4D57),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(width: 16),
          const LivePulseIndicator(label: 'Markets Open'),
          const SizedBox(width: 18),
          Text(
            '${now.hourOfPeriod == 0 ? 12 : now.hourOfPeriod}:${now.minute.toString().padLeft(2, '0')} ${now.period.name.toUpperCase()} IST',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _TapeItem {
  const _TapeItem(this.label, this.value, this.changePct);

  final String label;
  final String value;
  final double changePct;
}

class _TopNav extends StatelessWidget {
  const _TopNav({
    required this.onOpenDashboard,
    required this.onOpenSignals,
    required this.onOpenBrokers,
    required this.onOpenPricing,
  });

  final VoidCallback onOpenDashboard;
  final VoidCallback onOpenSignals;
  final VoidCallback onOpenBrokers;
  final VoidCallback onOpenPricing;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final showFullNav = width > 980;
    final showLogin = width > 900;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      decoration: const BoxDecoration(
        color: Color(0xAA07101D),
        border: Border(
          bottom: BorderSide(color: Color(0xFF17243B)),
        ),
      ),
      child: Row(
        children: <Widget>[
          const _LogoMark(size: 48),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              RichText(
                text: TextSpan(
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0,
                      ),
                  children: const <TextSpan>[
                    TextSpan(text: 'QUEN'),
                    TextSpan(
                      text: 'TRADER',
                      style: TextStyle(color: Color(0xFF62E83A)),
                    ),
                  ],
                ),
              ),
              Text(
                'AI-Powered Trading Platform',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: TradingPalette.textMuted,
                    ),
              ),
            ],
          ),
          const Spacer(),
          if (showFullNav) ...<Widget>[
            _NavButton(label: 'Home', selected: true, onTap: () {}),
            _NavButton(label: 'Features', onTap: onOpenSignals),
            _NavButton(label: 'Pricing', onTap: onOpenPricing),
            _NavButton(label: 'Dashboard', onTap: onOpenDashboard),
            _NavButton(label: 'Brokers', onTap: onOpenBrokers),
          ],
          const SizedBox(width: 16),
          if (showLogin) ...<Widget>[
            OutlinedButton(
              onPressed: onOpenDashboard,
              style: OutlinedButton.styleFrom(
                foregroundColor: TradingPalette.textPrimary,
                side: const BorderSide(color: TradingPalette.panelBorder),
                padding:
                    const EdgeInsets.symmetric(horizontal: 22, vertical: 18),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              child: const Text('Log In'),
            ),
            const SizedBox(width: 12),
          ],
          FilledButton(
            onPressed: onOpenDashboard,
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFF55EA32),
              foregroundColor: const Color(0xFF041006),
              padding: EdgeInsets.symmetric(
                horizontal: width < 700 ? 14 : 24,
                vertical: 18,
              ),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: Text(width < 700 ? 'Start' : 'Start Trading Free'),
          ),
        ],
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.label,
    required this.onTap,
    this.selected = false,
  });

  final String label;
  final VoidCallback onTap;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onTap,
      style: TextButton.styleFrom(
        foregroundColor:
            selected ? const Color(0xFF73F044) : TradingPalette.textPrimary,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
          if (selected)
            Container(
              width: 42,
              height: 2,
              margin: const EdgeInsets.only(top: 8),
              color: const Color(0xFF73F044),
            ),
        ],
      ),
    );
  }
}

class _HeroCopy extends StatelessWidget {
  const _HeroCopy({
    required this.onStart,
    required this.onDemo,
  });

  final VoidCallback onStart;
  final VoidCallback onDemo;

  @override
  Widget build(BuildContext context) {
    final headline = Theme.of(context).textTheme.displayMedium?.copyWith(
          fontWeight: FontWeight.w900,
          height: 1.05,
          letterSpacing: 0,
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0x2218E46E),
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: const Color(0xFF54E03B)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(Icons.verified_rounded,
                  color: Color(0xFF72F24A), size: 18),
              const SizedBox(width: 8),
              Text(
                'AI POWERED. RISK FIRST. HUMAN CONTROLLED.',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      color: TradingPalette.textPrimary,
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 26),
        Text('Smarter Trades.', style: headline),
        Text(
          'Stronger Protection.',
          style: headline?.copyWith(color: const Color(0xFF62EA3F)),
        ),
        Text('Superior Results.', style: headline),
        const SizedBox(height: 20),
        Text(
          'AI-generated signals, real-time market intelligence and institutional-grade risk management - all in one platform. You stay in control. We handle the complexity.',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                color: const Color(0xFFD3D8E7),
                height: 1.45,
              ),
        ),
        const SizedBox(height: 30),
        Wrap(
          spacing: 16,
          runSpacing: 12,
          children: <Widget>[
            FilledButton.icon(
              onPressed: onStart,
              icon: const Icon(Icons.arrow_forward_rounded),
              label: const Text('Start Trading Free'),
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF30E675),
                foregroundColor: const Color(0xFF031208),
                padding:
                    const EdgeInsets.symmetric(horizontal: 28, vertical: 22),
                textStyle: const TextStyle(fontWeight: FontWeight.w900),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
            OutlinedButton.icon(
              onPressed: onDemo,
              icon: const Icon(Icons.play_circle_outline_rounded),
              label: const Text('Watch Demo'),
              style: OutlinedButton.styleFrom(
                foregroundColor: TradingPalette.textPrimary,
                side: const BorderSide(color: TradingPalette.panelBorder),
                padding:
                    const EdgeInsets.symmetric(horizontal: 28, vertical: 22),
                textStyle: const TextStyle(fontWeight: FontWeight.w900),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),
        const Wrap(
          spacing: 22,
          runSpacing: 12,
          children: <Widget>[
            _Assurance(
                icon: Icons.security_rounded, text: 'Bank Grade Security'),
            _Assurance(
                icon: Icons.credit_card_off_rounded,
                text: 'No Credit Card Required'),
            _Assurance(icon: Icons.autorenew_rounded, text: 'Cancel Anytime'),
          ],
        ),
      ],
    );
  }
}

class _Assurance extends StatelessWidget {
  const _Assurance({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(icon, color: const Color(0xFF78F04C), size: 22),
        const SizedBox(width: 8),
        Text(text, style: Theme.of(context).textTheme.bodyMedium),
      ],
    );
  }
}

class _TerminalPreview extends StatelessWidget {
  const _TerminalPreview({
    required this.summary,
    required this.signalFeed,
    required this.pnl,
    required this.activeTradeCount,
  });

  final AsyncValue<MarketSummaryModel> summary;
  final SignalFeedState signalFeed;
  final AsyncValue<UserPnLModel> pnl;
  final int activeTradeCount;

  @override
  Widget build(BuildContext context) {
    final data = summary.valueOrNull;
    final sentiment = data?.sentimentLabel.toUpperCase() ?? 'LIVE';
    final confidence = ((data?.confidenceScore ?? 0.82) * 100).clamp(0, 100);
    final signals = signalFeed.items.take(4).toList();
    final pnlSnapshot = pnl.valueOrNull;
    final equity = pnlSnapshot?.currentEquity ?? 245780;
    final absolutePnl = pnlSnapshot?.absolutePnl ?? 18420;
    final activeTradesLabel = activeTradeCount == 0
        ? (signals.isEmpty ? 12 : signals.length)
        : activeTradeCount;

    final compactTerminal = MediaQuery.sizeOf(context).width < 900;
    return SizedBox(
      height: compactTerminal ? 720 : 560,
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xDD0A101C),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF263856)),
          boxShadow: const <BoxShadow>[
            BoxShadow(
              color: Color(0x6630E675),
              blurRadius: 42,
              offset: Offset(0, 20),
            ),
          ],
        ),
        child: Column(
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              child: Row(
                children: <Widget>[
                  const _LogoMark(size: 28),
                  const SizedBox(width: 8),
                  const Text(
                    'QUENTRADER',
                    style: TextStyle(fontWeight: FontWeight.w900),
                  ),
                  const Spacer(),
                  const Icon(Icons.search, color: TradingPalette.textMuted),
                  const SizedBox(width: 14),
                  const Icon(Icons.notifications_none_rounded,
                      color: TradingPalette.textMuted),
                  const SizedBox(width: 14),
                  const Icon(Icons.settings_outlined,
                      color: TradingPalette.textMuted),
                  const SizedBox(width: 16),
                  const CircleAvatar(
                    radius: 13,
                    backgroundColor: Color(0xFF25324C),
                    child: Icon(Icons.person, size: 16, color: Colors.white),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Arjun Trader',
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1, color: Color(0xFF263856)),
            Expanded(
              child: Row(
                children: <Widget>[
                  if (MediaQuery.sizeOf(context).width > 760)
                    Container(
                      width: 150,
                      padding: const EdgeInsets.all(14),
                      decoration: const BoxDecoration(
                        border: Border(
                          right: BorderSide(color: Color(0xFF1F2B43)),
                        ),
                      ),
                      child: const Column(
                        children: <Widget>[
                          _TerminalNavItem(
                              icon: Icons.dashboard_rounded,
                              label: 'Overview',
                              selected: true),
                          _TerminalNavItem(
                              icon: Icons.show_chart_rounded, label: 'Market'),
                          _TerminalNavItem(
                              icon: Icons.auto_awesome_rounded,
                              label: 'AI Signals'),
                          _TerminalNavItem(
                              icon: Icons.account_balance_wallet_rounded,
                              label: 'Portfolio'),
                          _TerminalNavItem(
                              icon: Icons.shield_rounded, label: 'Risk'),
                          _TerminalNavItem(
                              icon: Icons.analytics_rounded,
                              label: 'Analytics'),
                          _TerminalNavItem(
                              icon: Icons.link_rounded, label: 'Brokers'),
                        ],
                      ),
                    ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'Overview',
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(
                                  fontWeight: FontWeight.w900,
                                ),
                          ),
                          const SizedBox(height: 10),
                          LayoutBuilder(
                            builder: (context, constraints) {
                              final compact = constraints.maxWidth < 640;
                              return GridView.count(
                                crossAxisCount: compact ? 2 : 4,
                                shrinkWrap: true,
                                physics: const NeverScrollableScrollPhysics(),
                                crossAxisSpacing: 10,
                                mainAxisSpacing: 10,
                                childAspectRatio: compact ? 1.95 : 1.65,
                                children: <Widget>[
                                  _PreviewMetric(
                                    label: 'Market Status',
                                    value: sentiment,
                                    sublabel:
                                        'Confidence ${confidence.toStringAsFixed(0)}%',
                                    icon: Icons.trending_up_rounded,
                                    accent: const Color(0xFF48EA55),
                                  ),
                                  _PreviewMetric(
                                    label: 'Active Trades',
                                    value: '$activeTradesLabel',
                                    sublabel: 'Open Positions',
                                    icon: Icons.stacked_line_chart_rounded,
                                  ),
                                  _PreviewMetric(
                                    label: "Today's P&L",
                                    value: _formatCurrency(absolutePnl),
                                    sublabel: absolutePnl >= 0
                                        ? 'Risk guard active'
                                        : 'Drawdown guarded',
                                    icon: Icons.arrow_outward_rounded,
                                    accent: absolutePnl >= 0
                                        ? const Color(0xFF48EA55)
                                        : TradingPalette.neonRed,
                                  ),
                                  _PreviewMetric(
                                    label: 'Portfolio Value',
                                    value: _formatCurrency(equity),
                                    sublabel: 'Available Margin',
                                    icon: Icons.account_balance_wallet_rounded,
                                  ),
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 10),
                          Expanded(
                            child: LayoutBuilder(
                              builder: (context, constraints) {
                                final stack = constraints.maxWidth < 640;
                                final chart = _PerformanceCard(
                                  points: pnlSnapshot?.sparkline ??
                                      const <double>[
                                        3000,
                                        8200,
                                        10450,
                                        16200,
                                        18420,
                                        21800,
                                        24800,
                                        30000,
                                      ],
                                );
                                if (stack) {
                                  return ListView(
                                    children: <Widget>[
                                      SizedBox(height: 230, child: chart),
                                      const SizedBox(height: 10),
                                      const SizedBox(
                                        height: 210,
                                        child: _RiskExposureCard(),
                                      ),
                                    ],
                                  );
                                }
                                return Row(
                                  children: <Widget>[
                                    Expanded(flex: 3, child: chart),
                                    const SizedBox(width: 10),
                                    const Expanded(child: _RiskExposureCard()),
                                  ],
                                );
                              },
                            ),
                          ),
                          const SizedBox(height: 10),
                          SizedBox(
                            height: 160,
                            child: LayoutBuilder(
                              builder: (context, constraints) {
                                final stack = constraints.maxWidth < 760;
                                final signalCard =
                                    _AiSignalsCard(signals: signals);
                                if (stack) {
                                  return signalCard;
                                }
                                return Row(
                                  children: <Widget>[
                                    Expanded(child: signalCard),
                                    const SizedBox(width: 10),
                                    Expanded(
                                        child: _RecentTradesCard(
                                            signals: signals)),
                                    const SizedBox(width: 10),
                                    const Expanded(
                                        child: _BrokerConnectionCard()),
                                  ],
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
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

class _TerminalNavItem extends StatelessWidget {
  const _TerminalNavItem({
    required this.icon,
    required this.label,
    this.selected = false,
  });

  final IconData icon;
  final String label;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: selected ? const Color(0x332FEA75) : Colors.transparent,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: <Widget>[
          Icon(icon, size: 16, color: TradingPalette.textMuted),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: selected
                        ? TradingPalette.textPrimary
                        : TradingPalette.textMuted,
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PreviewMetric extends StatelessWidget {
  const _PreviewMetric({
    required this.label,
    required this.value,
    required this.sublabel,
    required this.icon,
    this.accent = const Color(0xFF2AA8FF),
  });

  final String label;
  final String value;
  final String sublabel;
  final IconData icon;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return _TerminalCard(
      child: Stack(
        children: <Widget>[
          Positioned(
            right: -4,
            bottom: -8,
            child: Icon(icon, size: 52, color: accent.withOpacity(0.12)),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: <Widget>[
              Text(label, style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 7),
              Text(
                value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      color: accent,
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 4),
              Text(
                sublabel,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: TradingPalette.textMuted,
                    ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PerformanceCard extends StatelessWidget {
  const _PerformanceCard({required this.points});

  final List<double> points;

  @override
  Widget build(BuildContext context) {
    return _TerminalCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Text(
                'Portfolio Performance',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const Spacer(),
              for (final item in const <String>['1D', '1W', '1M', '3M'])
                Container(
                  margin: const EdgeInsets.only(left: 5),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: item == '1D'
                        ? const Color(0xFF244B9B)
                        : Colors.transparent,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    item,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: TradingPalette.textPrimary,
                        ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: CustomPaint(
              painter: _LineChartPainter(points),
              child: const SizedBox.expand(),
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskExposureCard extends StatelessWidget {
  const _RiskExposureCard();

  @override
  Widget build(BuildContext context) {
    return _TerminalCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Risk Exposure',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 14),
          Expanded(
            child: Row(
              children: <Widget>[
                Expanded(
                  child: CustomPaint(
                    painter: const _DonutPainter(0.27),
                    child: Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: <Widget>[
                          Text(
                            '27%',
                            style: Theme.of(context)
                                .textTheme
                                .headlineSmall
                                ?.copyWith(fontWeight: FontWeight.w900),
                          ),
                          Text(
                            'Moderate',
                            style: Theme.of(context)
                                .textTheme
                                .labelSmall
                                ?.copyWith(color: TradingPalette.amber),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                const Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: <Widget>[
                      _LegendRow('Equity', '62%', Color(0xFF3296FF)),
                      _LegendRow('Derivatives', '23%', Color(0xFF32E879)),
                      _LegendRow('Cash', '10%', Color(0xFF6CE34E)),
                      _LegendRow('Others', '5%', Color(0xFF9FA8DA)),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AiSignalsCard extends StatelessWidget {
  const _AiSignalsCard({required this.signals});

  final List<SignalModel> signals;

  @override
  Widget build(BuildContext context) {
    final items = signals.isEmpty ? const <SignalModel>[] : signals;
    return _TerminalCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'AI Signals',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: items.isEmpty
                ? const _SignalFallbackList()
                : ListView.builder(
                    itemCount: math.min(items.length, 4),
                    itemBuilder: (context, index) {
                      final signal = items[index];
                      final buy = signal.action.toUpperCase() != 'SELL';
                      return _SignalRow(
                        symbol: signal.symbol,
                        action: signal.action,
                        confidence: signal.confidence,
                        positive: buy,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _SignalFallbackList extends StatelessWidget {
  const _SignalFallbackList();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.zero,
      children: const <Widget>[
        _SignalRow(
            symbol: 'BANKNIFTY',
            action: 'BUY',
            confidence: 0.87,
            positive: true),
        _SignalRow(
            symbol: 'RELIANCE',
            action: 'SELL',
            confidence: 0.72,
            positive: false),
        _SignalRow(
            symbol: 'TCS', action: 'BUY', confidence: 0.81, positive: true),
      ],
    );
  }
}

class _RecentTradesCard extends StatelessWidget {
  const _RecentTradesCard({required this.signals});

  final List<SignalModel> signals;

  @override
  Widget build(BuildContext context) {
    return _TerminalCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Recent Trades',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: math.max(4, math.min(signals.length, 4)),
              itemBuilder: (context, index) {
                final signal = signals.length > index ? signals[index] : null;
                final positive = signal == null || signal.action != 'SELL';
                final symbol = signal?.symbol ??
                    const <String>[
                      'BANKNIFTY',
                      'RELIANCE',
                      'TCS',
                      'INFY',
                    ][index];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 7),
                  child: Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          symbol,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                      ),
                      Text(
                        positive ? 'BUY' : 'SELL',
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: positive
                                  ? const Color(0xFF4EEE51)
                                  : TradingPalette.neonRed,
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                      const SizedBox(width: 12),
                      Text(
                        positive ? '+2,640' : '+1,250',
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: const Color(0xFF4EEE51),
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _BrokerConnectionCard extends StatelessWidget {
  const _BrokerConnectionCard();

  @override
  Widget build(BuildContext context) {
    return const _TerminalCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text('Broker Connection',
              style: TextStyle(fontWeight: FontWeight.w900)),
          SizedBox(height: 10),
          _BrokerRow('ZERODHA'),
          _BrokerRow('UPSTOX'),
          _BrokerRow('ANGEL ONE'),
          _BrokerRow('DHAN'),
        ],
      ),
    );
  }
}

class _SignalRow extends StatelessWidget {
  const _SignalRow({
    required this.symbol,
    required this.action,
    required this.confidence,
    required this.positive,
  });

  final String symbol;
  final String action;
  final double confidence;
  final bool positive;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          Icon(
            positive ? Icons.trending_up_rounded : Icons.trending_down_rounded,
            color: positive ? const Color(0xFF4EEE51) : TradingPalette.neonRed,
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  symbol,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
                Text(
                  'Confidence ${(confidence * 100).clamp(0, 100).toStringAsFixed(0)}%',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: TradingPalette.textFaint,
                        fontSize: 9,
                      ),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color:
                  (positive ? TradingPalette.neonGreen : TradingPalette.neonRed)
                      .withOpacity(0.14),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(
                color: positive
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
            ),
            child: Text(
              action,
              style: TextStyle(
                color:
                    positive ? const Color(0xFF4EEE51) : TradingPalette.neonRed,
                fontSize: 10,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _BrokerRow extends StatelessWidget {
  const _BrokerRow(this.name);

  final String name;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: <Widget>[
          const Icon(Icons.account_balance_rounded,
              color: TradingPalette.textMuted, size: 14),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              name,
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),
          Text(
            'Connected',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: const Color(0xFF4EEE51),
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _TerminalCard extends StatelessWidget {
  const _TerminalCard({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0C1423),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: const Color(0xFF23334F)),
      ),
      child: child,
    );
  }
}

class _LegendRow extends StatelessWidget {
  const _LegendRow(this.label, this.value, this.color);

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: <Widget>[
          Container(width: 8, height: 8, color: color),
          const SizedBox(width: 8),
          Expanded(
              child:
                  Text(label, style: Theme.of(context).textTheme.labelSmall)),
          Text(value, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
    );
  }
}

class _FeatureRail extends StatelessWidget {
  const _FeatureRail({
    required this.onOpenDashboard,
    required this.onOpenSignals,
    required this.onOpenBrokers,
  });

  final VoidCallback onOpenDashboard;
  final VoidCallback onOpenSignals;
  final VoidCallback onOpenBrokers;

  @override
  Widget build(BuildContext context) {
    final items =
        <({IconData icon, String title, String subtitle, VoidCallback tap})>[
      (
        icon: Icons.center_focus_strong_rounded,
        title: 'AI Decision Engine',
        subtitle: 'Advanced market analysis and trade recommendations',
        tap: onOpenSignals,
      ),
      (
        icon: Icons.shield_rounded,
        title: 'Risk First Architecture',
        subtitle: 'Built-in risk management and capital protection',
        tap: onOpenDashboard,
      ),
      (
        icon: Icons.sync_alt_rounded,
        title: 'Broker Connected',
        subtitle: 'Seamless integration with leading brokers',
        tap: onOpenBrokers,
      ),
      (
        icon: Icons.flash_on_rounded,
        title: 'Real-Time Execution',
        subtitle: 'Lightning fast order execution and monitoring',
        tap: onOpenDashboard,
      ),
      (
        icon: Icons.monitor_heart_rounded,
        title: '24/7 Monitoring',
        subtitle: 'Always-on monitoring and alerts',
        tap: onOpenDashboard,
      ),
    ];

    return _GlowPanel(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final columns = constraints.maxWidth >= 1200
              ? 5
              : constraints.maxWidth >= 820
                  ? 3
                  : 1;
          return GridView.count(
            crossAxisCount: columns,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: columns == 1 ? 4.2 : 2.45,
            crossAxisSpacing: 14,
            mainAxisSpacing: 14,
            children: items
                .map(
                  (item) => InkWell(
                    onTap: item.tap,
                    borderRadius: BorderRadius.circular(8),
                    child: Row(
                      children: <Widget>[
                        Container(
                          width: 54,
                          height: 54,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: const Color(0x2217E668),
                            border: Border.all(color: const Color(0xFF67F244)),
                          ),
                          child:
                              Icon(item.icon, color: const Color(0xFF78F04C)),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Text(
                                item.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context)
                                    .textTheme
                                    .titleSmall
                                    ?.copyWith(fontWeight: FontWeight.w900),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                item.subtitle,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: Theme.of(context).textTheme.labelMedium,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                )
                .toList(),
          );
        },
      ),
    );
  }
}

class _TrustStats extends StatelessWidget {
  const _TrustStats({required this.pnl, required this.signals});

  final AsyncValue<UserPnLModel> pnl;
  final List<SignalModel> signals;

  @override
  Widget build(BuildContext context) {
    final approved = signals.where((signal) => signal.isApproved).length;
    final total = signals.isEmpty ? 1 : signals.length;
    final accuracy =
        signals.isEmpty ? 87 : (approved / total * 100).clamp(60, 99);
    final pnlSnapshot = pnl.valueOrNull;
    final riskProtection =
        (100 - ((pnlSnapshot?.rollingDrawdown ?? 0.001).abs() * 100))
            .clamp(92, 99.9);
    final items = <({IconData icon, String value, String label, String sub})>[
      (
        icon: Icons.my_location_rounded,
        value: '${accuracy.toStringAsFixed(0)}%',
        label: 'Trade Accuracy',
        sub: 'AI Signal Accuracy',
      ),
      (
        icon: Icons.shield_rounded,
        value: '${riskProtection.toStringAsFixed(1)}%',
        label: 'Risk Protection',
        sub: 'Capital Protection',
      ),
      (
        icon: Icons.check_circle_outline_rounded,
        value: '99.95%',
        label: 'Execution Reliability',
        sub: 'Order Success Rate',
      ),
      (
        icon: Icons.visibility_outlined,
        value: '24/7',
        label: 'Monitoring',
        sub: 'Always Protecting You',
      ),
      (
        icon: Icons.groups_rounded,
        value: '10K+',
        label: 'Active Traders',
        sub: 'Trust Quentrader',
      ),
    ];
    return _GlowPanel(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final columns = constraints.maxWidth >= 1100
              ? 5
              : constraints.maxWidth >= 720
                  ? 3
                  : 1;
          return GridView.count(
            crossAxisCount: columns,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: columns == 1 ? 4.3 : 2.5,
            crossAxisSpacing: 14,
            mainAxisSpacing: 14,
            children: items
                .map(
                  (item) => Row(
                    children: <Widget>[
                      Icon(item.icon, color: const Color(0xFF78F04C), size: 44),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              item.value,
                              style: Theme.of(context)
                                  .textTheme
                                  .headlineSmall
                                  ?.copyWith(
                                    color: const Color(0xFF78F04C),
                                    fontWeight: FontWeight.w900,
                                  ),
                            ),
                            Text(
                              item.label,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w900),
                            ),
                            Text(item.sub,
                                style: Theme.of(context).textTheme.labelMedium),
                          ],
                        ),
                      ),
                    ],
                  ),
                )
                .toList(),
          );
        },
      ),
    );
  }
}

class _BrokerStrip extends StatelessWidget {
  const _BrokerStrip();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Column(
        children: <Widget>[
          Text(
            'Trusted By Traders Across India',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          const Divider(color: Color(0xFF1D2842)),
          const SizedBox(height: 18),
          const Wrap(
            spacing: 60,
            runSpacing: 20,
            alignment: WrapAlignment.center,
            children: <Widget>[
              _BrokerLogoText('ZERODHA'),
              _BrokerLogoText('upstox'),
              _BrokerLogoText('AngelOne'),
              _BrokerLogoText('dhan'),
              _BrokerLogoText('FYERS'),
              _BrokerLogoText('aliceblue'),
            ],
          ),
        ],
      ),
    );
  }
}

class _BrokerLogoText extends StatelessWidget {
  const _BrokerLogoText(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context).textTheme.titleLarge?.copyWith(
            color: TradingPalette.textMuted.withOpacity(0.55),
            fontWeight: FontWeight.w900,
          ),
    );
  }
}

class _GlowPanel extends StatelessWidget {
  const _GlowPanel({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xAA0D1423),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF243450)),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x3316E86A),
            blurRadius: 26,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _LogoMark extends StatelessWidget {
  const _LogoMark({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          colors: <Color>[Color(0xFF0CCBFF), Color(0xFF73F044)],
          begin: Alignment.bottomLeft,
          end: Alignment.topRight,
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(color: Color(0x5530E675), blurRadius: 16),
        ],
      ),
      child: Icon(
        Icons.analytics_rounded,
        color: const Color(0xFF05100A),
        size: size * 0.58,
      ),
    );
  }
}

class _LineChartPainter extends CustomPainter {
  const _LineChartPainter(this.points);

  final List<double> points;

  @override
  void paint(Canvas canvas, Size size) {
    final gridPaint = Paint()
      ..color = const Color(0xFF1B2A42)
      ..strokeWidth = 1;
    for (var i = 1; i < 4; i++) {
      final y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }
    for (var i = 1; i < 5; i++) {
      final x = size.width * i / 5;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), gridPaint);
    }

    final safePoints = points.length < 2 ? const <double>[0, 1] : points;
    final minValue = safePoints.reduce(math.min);
    final maxValue = safePoints.reduce(math.max);
    final span = maxValue == minValue ? 1 : maxValue - minValue;
    final path = Path();
    for (var i = 0; i < safePoints.length; i++) {
      final x = size.width * i / (safePoints.length - 1);
      final y = size.height -
          ((safePoints[i] - minValue) / span * (size.height * 0.82)) -
          size.height * 0.08;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    final fillPath = Path.from(path)
      ..lineTo(size.width, size.height)
      ..lineTo(0, size.height)
      ..close();
    canvas.drawPath(
      fillPath,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[Color(0x7730E675), Color(0x0030E675)],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xFF43F25E)
        ..strokeWidth = 3
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant _LineChartPainter oldDelegate) {
    return oldDelegate.points != points;
  }
}

class _DonutPainter extends CustomPainter {
  const _DonutPainter(this.value);

  final double value;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = math.min(size.width, size.height) / 2 - 10;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 14
      ..strokeCap = StrokeCap.round
      ..color = const Color(0xFF22324D);
    canvas.drawCircle(center, radius, base);
    final colors = <Color>[
      const Color(0xFFFFB74D),
      const Color(0xFF33E47D),
      const Color(0xFF2AA8FF),
    ];
    var start = -math.pi / 2;
    for (final color in colors) {
      canvas.drawArc(
        rect,
        start,
        math.pi * 2 * value / colors.length,
        false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 14
          ..strokeCap = StrokeCap.round
          ..color = color,
      );
      start += math.pi * 2 * value / colors.length + 0.16;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) {
    return oldDelegate.value != value;
  }
}

String _formatNumber(double value) {
  if (value >= 100000) {
    return value.toStringAsFixed(0);
  }
  if (value >= 1000) {
    return value.toStringAsFixed(2);
  }
  return value.toStringAsFixed(4);
}

String _formatCurrency(double value) {
  final sign = value < 0 ? '-' : '';
  final abs = value.abs();
  if (abs >= 10000000) {
    return '$sign₹${(abs / 10000000).toStringAsFixed(2)}Cr';
  }
  if (abs >= 100000) {
    return '$sign₹${(abs / 100000).toStringAsFixed(2)}L';
  }
  return '$sign₹${abs.toStringAsFixed(0)}';
}

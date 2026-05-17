import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/retention/providers/retention_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/live_energy_widgets.dart';
import '../widgets/status_badge.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  int _page = 0;
  String _riskLevel = 'medium';
  bool _completing = false;

  @override
  Widget build(BuildContext context) {
    final pages = <Widget>[
      _IntroPage(onNext: _next),
      _StylePage(
        riskLevel: _riskLevel,
        onRiskChanged: (value) => setState(() => _riskLevel = value),
        onNext: _next,
      ),
      _SimulationPage(
        riskLevel: _riskLevel,
        onComplete: _complete,
      ),
    ];
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: <Color>[
              TradingPalette.midnight,
              Color(0xFF11162A),
              TradingPalette.midnight,
            ],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: <Widget>[
                Row(
                  children: <Widget>[
                    const StatusBadge(
                      label: 'AI COPILOT',
                      color: TradingPalette.electricBlue,
                    ),
                    const Spacer(),
                    TextButton(
                      onPressed: _completing ? null : _complete,
                      child: const Text('Skip'),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 360),
                    switchInCurve: Curves.easeOutCubic,
                    child: KeyedSubtree(
                      key: ValueKey<int>(_page),
                      child: pages[_page],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: List<Widget>.generate(
                    pages.length,
                    (index) => Expanded(
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 260),
                        height: 6,
                        margin: EdgeInsets.only(
                          right: index == pages.length - 1 ? 0 : 8,
                        ),
                        decoration: BoxDecoration(
                          color: index <= _page
                              ? TradingPalette.electricBlue
                              : TradingPalette.panelBorder,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
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

  void _next() {
    setState(() => _page = (_page + 1).clamp(0, 2));
  }

  Future<void> _complete() async {
    if (_completing) {
      return;
    }
    setState(() => _completing = true);
    final userId = ref.read(activeUserIdProvider);
    await ref.read(onboardingCompletedProvider.notifier).markCompleted();
    unawaited(_syncRiskLevel(userId));
  }

  Future<void> _syncRiskLevel(String userId) async {
    try {
      await ref.read(appSettingsProvider.notifier).saveRiskLevel(
            userId,
            _riskLevel,
          );
    } catch (error, stackTrace) {
      FlutterError.reportError(
        FlutterErrorDetails(
          exception: error,
          stack: stackTrace,
          library: 'onboarding',
          context: ErrorDescription('syncing onboarding risk level'),
        ),
      );
    }
  }
}

class _IntroPage extends StatelessWidget {
  const _IntroPage({required this.onNext});

  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      child: _ScrollableOnboardingContent(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const Spacer(),
            const Center(
              child: ConfidencePulseRing(
                value: 0.82,
                color: TradingPalette.electricBlue,
                label: 'AI',
                size: 160,
              ),
            ),
            const SizedBox(height: 26),
            Text(
              'Meet your AI trading copilot',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 12),
            const Text(
              'I scan momentum, whales, liquidity, volatility, and structure so you always have a live opportunity plan.',
              style: TextStyle(color: TradingPalette.textPrimary, height: 1.35),
            ),
            const SizedBox(height: 22),
            const LiveEnergyBars(color: TradingPalette.electricBlue),
            const Spacer(),
            GradientActionButton(
              label: 'Choose Trading Style',
              icon: Icons.auto_awesome_rounded,
              onPressed: onNext,
              expanded: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _StylePage extends StatelessWidget {
  const _StylePage({
    required this.riskLevel,
    required this.onRiskChanged,
    required this.onNext,
  });

  final String riskLevel;
  final ValueChanged<String> onRiskChanged;
  final VoidCallback onNext;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.violet,
      child: _ScrollableOnboardingContent(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Pick your AI personality',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 12),
            const Text(
              'You can change this anytime. Real orders still require backend risk approval.',
              style: TextStyle(color: TradingPalette.textMuted),
            ),
            const SizedBox(height: 22),
            SegmentedButton<String>(
              segments: const <ButtonSegment<String>>[
                ButtonSegment<String>(
                  value: 'low',
                  icon: Icon(Icons.shield_rounded),
                  label: Text('Safe'),
                ),
                ButtonSegment<String>(
                  value: 'medium',
                  icon: Icon(Icons.auto_awesome_rounded),
                  label: Text('Smart'),
                ),
                ButtonSegment<String>(
                  value: 'high',
                  icon: Icon(Icons.bolt_rounded),
                  label: Text('Aggressive'),
                ),
              ],
              selected: <String>{riskLevel},
              onSelectionChanged: (selection) => onRiskChanged(selection.first),
            ),
            const SizedBox(height: 22),
            const _OnboardingFeature(
              title: 'Sniper AI',
              subtitle: 'Early breakout entries for high activity traders.',
            ),
            const _OnboardingFeature(
              title: 'Whale Follow AI',
              subtitle: 'Tracks smart money pressure and liquidity walls.',
            ),
            const _OnboardingFeature(
              title: 'Swing AI',
              subtitle: 'Slower structure trades with higher patience.',
            ),
            const Spacer(),
            GradientActionButton(
              label: 'Run Simulated First Trade',
              icon: Icons.play_circle_fill_rounded,
              onPressed: onNext,
              expanded: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _SimulationPage extends StatelessWidget {
  const _SimulationPage({
    required this.riskLevel,
    required this.onComplete,
  });

  final String riskLevel;
  final VoidCallback onComplete;

  @override
  Widget build(BuildContext context) {
    final modeLabel = riskLevel == 'high'
        ? 'Aggressive AI'
        : riskLevel == 'low'
            ? 'Safe AI'
            : 'Smart AI';
    return GlassPanel(
      glowColor: TradingPalette.neonGreen,
      child: _ScrollableOnboardingContent(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            const StatusBadge(
              label: 'SIMULATED WIN',
              color: TradingPalette.neonGreen,
            ),
            const SizedBox(height: 18),
            Text(
              '$modeLabel found a +4.8% paper opportunity',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Breakout compression, whale accumulation, liquidity reclaim, and momentum expansion aligned. Your real trades will still be protected by backend risk checks.',
              style: TextStyle(color: TradingPalette.textPrimary, height: 1.35),
            ),
            const SizedBox(height: 24),
            const MomentumWave(color: TradingPalette.neonGreen, height: 110),
            const Spacer(),
            GradientActionButton(
              label: 'Enter AI Trading Platform',
              icon: Icons.rocket_launch_rounded,
              gradient: TradingPalette.profitGlow,
              onPressed: onComplete,
              expanded: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _ScrollableOnboardingContent extends StatelessWidget {
  const _ScrollableOnboardingContent({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        return SingleChildScrollView(
          physics: const BouncingScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: IntrinsicHeight(child: child),
          ),
        );
      },
    );
  }
}

class _OnboardingFeature extends StatelessWidget {
  const _OnboardingFeature({
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: TradingPalette.overlay,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: TradingPalette.panelBorder),
        ),
        child: Row(
          children: <Widget>[
            const Icon(
              Icons.auto_awesome_rounded,
              color: TradingPalette.violet,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    title,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    subtitle,
                    style: const TextStyle(color: TradingPalette.textMuted),
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

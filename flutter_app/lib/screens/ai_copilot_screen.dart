import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/market/providers/market_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../models/market_summary.dart';
import '../models/signal.dart';
import '../widgets/glass_panel.dart';

class AiCopilotScreen extends ConsumerStatefulWidget {
  const AiCopilotScreen({super.key});

  @override
  ConsumerState<AiCopilotScreen> createState() => _AiCopilotScreenState();
}

class _AiCopilotScreenState extends ConsumerState<AiCopilotScreen> {
  String _selectedQuestion = 'Best setup right now?';

  @override
  Widget build(BuildContext context) {
    final signals = ref.watch(signalFeedProvider).items;
    final initialSignals = ref.watch(initialSignalsProvider).valueOrNull;
    final market = ref.watch(marketSummaryProvider).valueOrNull;
    final best = _bestSignal(
        signals.isEmpty ? initialSignals ?? const <SignalModel>[] : signals);

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
      children: <Widget>[
        Text(
          'AI Copilot',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 6),
        Text(
          'Ask trading questions. Answers stay tied to verified market data and risk rules.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        const SizedBox(height: 18),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <String>[
            'Best setup right now?',
            'Can I long BTC?',
            'How risky is this market?',
            'Why market falling?',
            'High probability setup?',
          ]
              .map(
                (question) => ChoiceChip(
                  selected: _selectedQuestion == question,
                  label: Text(question),
                  onSelected: (_) {
                    setState(() => _selectedQuestion = question);
                  },
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 18),
        GlassPanel(
          glowColor: TradingPalette.electricBlue,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  const Icon(
                    Icons.psychology_alt_rounded,
                    color: TradingPalette.electricBlue,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      _selectedQuestion,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                _answerFor(_selectedQuestion, best, market),
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: TradingPalette.textMuted,
                      height: 1.42,
                    ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        GlassPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Risk Manager Rule',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 8),
              const Text(
                'If there is no verified entry, stoploss, target, and backend risk approval, the correct action is to wait or paper trade only.',
              ),
            ],
          ),
        ),
      ],
    );
  }
}

SignalModel? _bestSignal(List<SignalModel> signals) {
  final verified = signals
      .where((signal) =>
          signal.executionAllowed &&
          !signal.marketDataStale &&
          signal.price > 0 &&
          !signal.lowConfidence)
      .toList()
    ..sort((a, b) => b.qualityScore.compareTo(a.qualityScore));
  return verified.isEmpty ? null : verified.first;
}

String _answerFor(
  String question,
  SignalModel? signal,
  MarketSummaryModel? market,
) {
  final sentiment = market?.sentimentLabel.toLowerCase() ?? 'neutral';
  final volatility = market?.avgVolatilityPct.toStringAsFixed(1) ?? 'unknown';
  if (signal == null) {
    return 'There is no approved high-quality trade right now. Market sentiment is $sentiment and volatility is $volatility%. The disciplined action is to wait until the backend confirms live data, risk, and strategy alignment.';
  }
  final side = signal.action == 'SELL' ? 'short' : 'long';
  if (question.contains('risk')) {
    return '${signal.symbol} is the current $side candidate, but position size should stay conservative. Confidence is ${(signal.confidence * 100).toStringAsFixed(0)}%, quality is ${signal.qualityScore.toStringAsFixed(0)}, and volatility is $volatility%. No trade should execute without the backend risk gate.';
  }
  if (question.contains('BTC') && signal.symbol != 'BTCUSDT') {
    return 'BTC is not the strongest approved setup in the current AI ranking. ${signal.symbol} is currently higher quality, so forcing a BTC trade would reduce discipline.';
  }
  if (question.contains('falling')) {
    return 'The market is reading $sentiment. If price is falling, wait for liquidity confirmation and avoid revenge entries. The current approved candidate is ${signal.symbol} $side only because meta and risk filters currently align.';
  }
  return '${signal.symbol} $side is the best approved setup now. Entry reference is ${signal.price.toStringAsFixed(signal.price >= 100 ? 2 : 4)}, strategy is ${signal.strategy.replaceAll('_', ' ')}, and the main reason is: ${signal.reasons.first}.';
}

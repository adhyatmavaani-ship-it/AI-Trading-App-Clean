import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_mapper.dart';
import '../core/error_presenter.dart';
import '../core/trading_palette.dart';
import '../features/signals/providers/signal_providers.dart';
import '../models/signal.dart';
import '../widgets/ai_signal_card.dart';
import '../widgets/glass_panel.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pulse_wrapper.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';

class AiSignalScreen extends ConsumerWidget {
  const AiSignalScreen({
    super.key,
    required this.onExecuteSignal,
  });

  final ValueChanged<SignalModel> onExecuteSignal;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signalFeed = ref.watch(signalFeedProvider);
    final initialSignalsAsync = ref.watch(initialSignalsProvider);
    final signals = signalFeed.items.isNotEmpty
        ? signalFeed.items
        : (initialSignalsAsync.valueOrNull ?? const <SignalModel>[]);

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(initialSignalsProvider),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
        children: <Widget>[
          if (signalFeed.lastError != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
                child: GlassPanel(
                  glowColor: TradingPalette.amber,
                  child: Text(
                    ErrorMapper.typeOf(signalFeed.lastError) ==
                            AppErrorType.network
                        ? 'Offline mode. Showing last known signals.'
                        : userMessageForError(signalFeed.lastError),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: TradingPalette.textPrimary,
                        ),
                ),
              ),
            ),
          SectionCard(
            title: 'Live AI Signal',
            subtitle: 'Realtime BUY and SELL intelligence from the websocket stream.',
            trailing: const LivePulseIndicator(
              label: 'WEBSOCKET',
              color: TradingPalette.electricBlue,
            ),
            glowColor: TradingPalette.violet,
            child: signals.isEmpty
                ? const EmptyState(
                    title: 'No signal available',
                    subtitle:
                        'The AI engine is connected but no trade-grade setup has been published yet.',
                  )
                : PulseWrapper(
                    child: AiSignalCard(
                      signal: signals.first,
                      onExecute: () => onExecuteSignal(signals.first),
                    ),
                  ),
          ),
          const SizedBox(height: 18),
          SectionCard(
            title: 'Signal Queue',
            subtitle: 'Recent live signals with confidence, alpha score, and execution access.',
            trailing: StatusBadge(label: '${signals.length} live'),
            child: signals.isEmpty
                ? const LoadingState(label: 'Waiting for signals')
                : Column(
                    children: signals
                        .map(
                          (signal) => Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: _SignalListTile(
                              signal: signal,
                              onTap: () => onExecuteSignal(signal),
                            ),
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _SignalListTile extends StatelessWidget {
  const _SignalListTile({
    required this.signal,
    required this.onTap,
  });

  final SignalModel signal;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final bullish = signal.action.toUpperCase() == 'BUY';
    final accent = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Ink(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          color: TradingPalette.overlay,
          border: Border.all(color: TradingPalette.panelBorder),
        ),
        child: Row(
          children: <Widget>[
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: accent.withOpacity(0.16),
              ),
              child: Icon(
                bullish ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded,
                color: accent,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Text(
                        signal.symbol,
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(width: 8),
                      StatusBadge(label: signal.action, color: accent),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    signal.decisionReason,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: TradingPalette.textMuted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: <Widget>[
                Text(
                  '${(signal.confidence * 100).toStringAsFixed(0)}%',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  'Alpha ${signal.alphaScore.toStringAsFixed(0)}',
                  style: const TextStyle(color: TradingPalette.textFaint),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/error_presenter.dart';
import '../features/meta/providers/meta_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../widgets/meta_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/timeline_event_tile.dart';

class TradeTimelineScreen extends ConsumerStatefulWidget {
  const TradeTimelineScreen({super.key});

  @override
  ConsumerState<TradeTimelineScreen> createState() =>
      _TradeTimelineScreenState();
}

class _TradeTimelineScreenState extends ConsumerState<TradeTimelineScreen> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: ref.read(selectedTradeIdProvider) ?? '',
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final selectedTradeId = ref.watch(selectedTradeIdProvider);
    final timelineAsync = selectedTradeId == null || selectedTradeId.isEmpty
        ? null
        : ref.watch(tradeTimelineProvider(selectedTradeId));
    final metaAsync = selectedTradeId == null || selectedTradeId.isEmpty
        ? null
        : ref.watch(metaDecisionProvider(selectedTradeId));

    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        SectionCard(
          title: 'Trade Lookup',
          child: Column(
            children: <Widget>[
              TextField(
                controller: _controller,
                decoration: const InputDecoration(
                  labelText: 'Trade ID',
                  hintText:
                      'Enter a trade id or tap a live signal to preload one',
                ),
                onSubmitted: (value) {
                  ref.read(selectedTradeIdProvider.notifier).state =
                      value.trim();
                },
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: FilledButton(
                  onPressed: () {
                    ref.read(selectedTradeIdProvider.notifier).state =
                        _controller.text.trim();
                  },
                  child: const Text('Load Timeline'),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        if (timelineAsync == null)
          const EmptyState(
            title: 'No trade selected',
            subtitle:
                'Enter a trade id or select a live signal to inspect lifecycle events.',
          )
        else ...<Widget>[
          if (metaAsync != null)
            metaAsync.when(
              loading: () => const SectionCard(
                title: 'Meta Decision',
                child: LoadingState(label: 'Loading meta decision'),
              ),
              error: (error, _) => SectionCard(
                title: 'Meta Decision',
                child: ErrorState(message: userMessageForError(error)),
              ),
              data: (metaDecision) => MetaDecisionCard(
                metaDecision: metaDecision,
              ),
            ),
          const SizedBox(height: 20),
          timelineAsync.when(
            loading: () => const SectionCard(
              title: 'Timeline',
              child: LoadingState(label: 'Loading trade timeline'),
            ),
            error: (error, _) => SectionCard(
              title: 'Timeline',
              child: ErrorState(message: userMessageForError(error)),
            ),
            data: (timeline) => SectionCard(
              title: 'Trade ${timeline.tradeId}',
              trailing: Chip(label: Text(timeline.currentStatus)),
              child: timeline.events.isEmpty
                  ? const EmptyState(
                      title: 'No events available',
                      subtitle:
                          'The backend has not exposed lifecycle events for this trade yet.',
                    )
                  : Column(
                      children: timeline.events
                          .asMap()
                          .entries
                          .map(
                            (entry) => TimelineEventTile(
                              event: entry.value,
                              isLast: entry.key == timeline.events.length - 1,
                            ),
                          )
                          .toList(),
                    ),
            ),
          ),
        ],
      ],
    );
  }
}

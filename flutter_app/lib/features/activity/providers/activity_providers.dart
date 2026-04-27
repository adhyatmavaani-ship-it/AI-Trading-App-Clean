import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/activity.dart';
import '../../../providers/app_providers.dart';

class ActivityFeedState {
  const ActivityFeedState({
    this.items = const <ActivityItemModel>[],
    this.lastError,
  });

  final List<ActivityItemModel> items;
  final Object? lastError;

  ActivityFeedState copyWith({
    List<ActivityItemModel>? items,
    Object? lastError,
  }) {
    return ActivityFeedState(
      items: items ?? this.items,
      lastError: lastError ?? this.lastError,
    );
  }

  ActivityItemModel? get latest => items.isEmpty ? null : items.first;
}

class ActivityFeedNotifier extends StateNotifier<ActivityFeedState> {
  ActivityFeedNotifier() : super(const ActivityFeedState());

  void hydrate(List<ActivityItemModel> initial) {
    state = state.copyWith(
      items: _dedupe(initial).take(AppConstants.maxSignalCacheSize).toList(),
    );
  }

  void ingest(ActivityItemModel item) {
    final current = <ActivityItemModel>[item, ...state.items];
    state = state.copyWith(
      items: _dedupe(current).take(AppConstants.maxSignalCacheSize).toList(),
    );
  }

  void setError(Object error) {
    state = state.copyWith(lastError: error);
  }

  List<ActivityItemModel> _dedupe(List<ActivityItemModel> items) {
    final seen = <String>{};
    final ordered = <ActivityItemModel>[];
    for (final item in items) {
      if (seen.contains(item.dedupeKey)) {
        continue;
      }
      seen.add(item.dedupeKey);
      ordered.add(item);
    }
    ordered.sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return ordered;
  }
}

class ReadinessBoardNotifier extends StateNotifier<List<ReadinessCardModel>> {
  ReadinessBoardNotifier() : super(const <ReadinessCardModel>[]);

  void hydrate(List<ReadinessCardModel> cards) {
    state = _sortAndLimit(cards);
  }

  void ingest(ActivityItemModel item) {
    final symbol = item.symbol;
    if (symbol == null || symbol.isEmpty) {
      return;
    }
    final updated = <ReadinessCardModel>[
      ReadinessCardModel.fromActivity(item),
      ...state.where((card) => card.symbol != symbol),
    ];
    state = _sortAndLimit(updated);
  }

  List<ReadinessCardModel> _sortAndLimit(List<ReadinessCardModel> items) {
    final cards = List<ReadinessCardModel>.from(items);
    cards.sort((a, b) {
      final readinessComparison = b.readiness.compareTo(a.readiness);
      if (readinessComparison != 0) {
        return readinessComparison;
      }
      return b.updatedAt.compareTo(a.updatedAt);
    });
    return cards.take(8).toList();
  }
}

final initialActivityHistoryProvider = FutureProvider<List<ActivityItemModel>>(
  (ref) async {
    return ref.watch(tradingRepositoryProvider).fetchActivityHistory(limit: 40);
  },
);

final initialReadinessBoardProvider =
    FutureProvider<List<ReadinessCardModel>>((ref) async {
  return ref.watch(tradingRepositoryProvider).fetchReadinessBoard(limit: 8);
});

final activityStreamProvider = StreamProvider<ActivityItemModel>((ref) {
  return ref.watch(tradingRepositoryProvider).watchActivity();
});

final activityFeedProvider =
    StateNotifierProvider<ActivityFeedNotifier, ActivityFeedState>((ref) {
  return ActivityFeedNotifier();
});

final readinessBoardProvider =
    StateNotifierProvider<ReadinessBoardNotifier, List<ReadinessCardModel>>(
  (ref) {
    return ReadinessBoardNotifier();
  },
);

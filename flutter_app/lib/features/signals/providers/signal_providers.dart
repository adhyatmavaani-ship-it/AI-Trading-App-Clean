import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../models/signal.dart';
import '../../../providers/app_providers.dart';

class SignalFeedState {
  const SignalFeedState({
    this.items = const <SignalModel>[],
    this.lastError,
  });

  final List<SignalModel> items;
  final Object? lastError;

  SignalFeedState copyWith({
    List<SignalModel>? items,
    Object? lastError,
  }) {
    return SignalFeedState(
      items: items ?? this.items,
      lastError: lastError ?? this.lastError,
    );
  }
}

class SignalFeedNotifier extends StateNotifier<SignalFeedState> {
  SignalFeedNotifier() : super(const SignalFeedState());

  void hydrate(List<SignalModel> initial) {
    final deduped = _dedupe(initial);
    state = state.copyWith(
        items: deduped.take(AppConstants.maxSignalCacheSize).toList());
  }

  void ingest(SignalModel signal) {
    final current = <SignalModel>[signal, ...state.items];
    state = state.copyWith(
      items: _dedupe(current).take(AppConstants.maxSignalCacheSize).toList(),
    );
  }

  void setError(Object error) {
    state = state.copyWith(lastError: error);
  }

  List<SignalModel> _dedupe(List<SignalModel> items) {
    final seen = <String>{};
    final ordered = <SignalModel>[];
    for (final item in items) {
      if (item.signalId.isEmpty || seen.contains(item.signalId)) {
        continue;
      }
      seen.add(item.signalId);
      ordered.add(item);
    }
    ordered.sort((a, b) => b.publishedAt.compareTo(a.publishedAt));
    return ordered;
  }
}

final initialSignalsProvider = FutureProvider<List<SignalModel>>((ref) async {
  return ref.watch(tradingRepositoryProvider).fetchSignals(limit: 40);
});

final signalStreamProvider = StreamProvider<SignalModel>((ref) {
  return ref.watch(tradingRepositoryProvider).watchSignals();
});

final signalFeedProvider =
    StateNotifierProvider<SignalFeedNotifier, SignalFeedState>((ref) {
  return SignalFeedNotifier();
});

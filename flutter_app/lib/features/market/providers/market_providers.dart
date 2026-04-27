import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/market_chart.dart';
import '../../../providers/app_providers.dart';
import '../../pnl/providers/pnl_providers.dart';

final selectedMarketSymbolProvider =
    StateProvider<String>((ref) => 'BTCUSDT');

final selectedMarketIntervalProvider = StateProvider<String>((ref) => '5m');

final marketChartProvider = StreamProvider<MarketChartModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  final symbol = ref.watch(selectedMarketSymbolProvider);
  final interval = ref.watch(selectedMarketIntervalProvider);
  final userId = ref.watch(activeUserIdProvider);
  yield await repository.fetchMarketCandles(
    symbol: symbol,
    interval: interval,
    userId: userId,
  );
  while (true) {
    await Future<void>.delayed(const Duration(seconds: 5));
    yield await repository.fetchMarketCandles(
      symbol: symbol,
      interval: interval,
      userId: userId,
    );
  }
});

final marketUniverseProvider = StreamProvider<MarketUniverseModel>((ref) async* {
  final repository = ref.watch(tradingRepositoryProvider);
  yield await repository.fetchMarketUniverse();
  while (true) {
    await Future<void>.delayed(const Duration(seconds: 10));
    yield await repository.fetchMarketUniverse();
  }
});

import 'package:flutter_test/flutter_test.dart';

import 'package:ai_trading_app/features/trade/providers/trade_providers.dart';

void main() {
  test('local paper positions mark to live market prices and close on TP', () {
    final controller = LocalPaperTradingController();

    final position = controller.execute(
      symbol: 'BTCUSDT',
      side: 'BUY',
      notional: 1000,
      price: 100,
      reason: 'test paper fill',
    );

    expect(controller.state.cashBalance, 9000);
    expect(controller.state.positions, hasLength(1));
    expect(position.unrealizedPnl, 0);

    controller.markToMarket(
      symbol: 'BTCUSDT',
      price: 101,
      source: 'live_market',
    );

    final marked = controller.state.positions.single;
    expect(marked.currentPrice, 101);
    expect(marked.marketDataSource, 'live_market');
    expect(marked.unrealizedPnl, closeTo(10, 0.0001));
    expect(controller.state.equity, closeTo(10010, 0.0001));

    controller.markToMarket(
      symbol: 'BTCUSDT',
      price: 103,
      source: 'live_market',
    );

    expect(controller.state.positions, isEmpty);
    expect(controller.state.realizedPnl, closeTo(30, 0.0001));
    expect(controller.state.cashBalance, closeTo(10030, 0.0001));
    expect(controller.state.closedTrades, hasLength(1));
    expect(controller.state.closedTrades.first.result, 'TARGET HIT');
    expect(controller.state.closedTradeCount, 1);
    expect(controller.state.winRate, 1.0);

    controller.acknowledgeLesson(
      tradeId: controller.state.closedTrades.first.tradeId,
      lesson: controller.state.closedTrades.first.lessonTags.first,
      acknowledged: true,
    );

    expect(controller.state.closedTrades.first.acknowledged, isTrue);
  });
}

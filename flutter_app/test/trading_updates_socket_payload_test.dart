import 'package:ai_trading_app/models/realtime_event.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('chart order action parses authenticated websocket payload', () {
    final action = ChartOrderActionModel.fromJson(
      <String, dynamic>{
        'event': 'chart_order_action',
        'timestamp': '2026-05-30T17:23:00Z',
        'data': <String, dynamic>{
          'symbol': 'BTC/USDT',
          'action_id': 'action-1',
          'chart_order_id': 'chart-order-1',
          'type': 'LIMIT_BUY',
          'status': 'MOCK_FILLED',
          'price': 68420.5,
          'quantity': 0.025,
          'is_ai_trailing': false,
          'live_broker_submission': false,
          'mode': 'mock',
          'reason': 'Chart sync accepted in mock bridge.',
        },
      },
    );

    expect(action.symbol, 'BTC/USDT');
    expect(action.actionId, 'action-1');
    expect(action.chartOrderId, 'chart-order-1');
    expect(action.type, 'LIMIT_BUY');
    expect(action.status, 'MOCK_FILLED');
    expect(action.price, 68420.5);
    expect(action.quantity, 0.025);
    expect(action.isBuy, isTrue);
    expect(action.isSell, isFalse);
    expect(action.isMockFilled, isTrue);
    expect(action.liveBrokerSubmission, isFalse);
    expect(action.matchesSymbol('btc/usdt'), isTrue);
    expect(action.matchesSymbol('BTCUSDT'), isTrue);
  });

  test('strategy performance update parses advisory analytics payload', () {
    final update = StrategyPerformanceUpdateModel.fromJson(
      <String, dynamic>{
        'event': 'strategy_performance_update',
        'timestamp': '2026-05-30T17:24:00Z',
        'data': <String, dynamic>{
          'user_id': 'alice',
          'advisory_only': true,
          'simulation_only': true,
          'live_broker_submission': false,
          'rolling_window': 12,
          'action_count': 12,
          'accepted_count': 11,
          'rejected_count': 1,
          'win_loss_ratio': 0.7,
          'loss_ratio': 0.3,
          'sharpe_estimate': 1.25,
          'time_decay_risk': 0.18,
          'slippage_pressure': 0.22,
          'ai_trailing_ratio': 0.5,
          'symbol_breakdown': <String, dynamic>{
            'BTCUSDT': <String, dynamic>{'actions': 8},
          },
          'stress_simulation': <String, dynamic>{
            'advisory_only': true,
            'simulation_only': true,
            'worst_case_drawdown': 42.0,
          },
        },
      },
    );

    expect(update.userId, 'alice');
    expect(update.advisoryOnly, isTrue);
    expect(update.simulationOnly, isTrue);
    expect(update.liveBrokerSubmission, isFalse);
    expect(update.actionCount, 12);
    expect(update.sharpeEstimate, 1.25);
    expect(update.symbolBreakdown['BTCUSDT'], isA<Map>());
    expect(update.stressSimulation['worst_case_drawdown'], 42.0);
  });
}

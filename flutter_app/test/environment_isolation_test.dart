import 'package:ai_trading_app/core/constants.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('default endpoints use local sandbox unless supplied by build flags', () {
    expect(AppConstants.defaultApiBaseUrl, 'http://127.0.0.1:8000');
    expect(AppConstants.defaultSignalsWebSocketUrl,
        'ws://127.0.0.1:8000/ws/signals');
    expect(
        AppConstants.defaultMarketWebSocketUrl, 'ws://127.0.0.1:8000/ws/market');
    expect(AppConstants.defaultApiBaseUrl, isNot(contains('srv1664694')));
    expect(AppConstants.defaultSignalsWebSocketUrl, isNot(contains('hstgr')));
    expect(AppConstants.defaultMarketWebSocketUrl, isNot(contains('hstgr')));
  });
}

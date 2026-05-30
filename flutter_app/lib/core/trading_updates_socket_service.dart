import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/realtime_event.dart';
import 'api_exception.dart';
import 'constants.dart';
import 'error_mapper.dart';
import 'websocket_channel_factory.dart';
import 'websocket_service.dart';

class TradingUpdatesSocketService {
  TradingUpdatesSocketService({
    String? baseUrl,
    String? apiKey,
  })  : _baseUrl = baseUrl ?? AppConstants.defaultTradingUpdatesWebSocketUrl,
        _apiKey = apiKey ?? AppConstants.requiredApiKey {
    debugPrint('[TRADING UPDATES WS URL] $_baseUrl');
  }

  final String _baseUrl;
  final String _apiKey;
  final StreamController<Map<String, dynamic>> _eventController =
      StreamController<Map<String, dynamic>>.broadcast();
  final ValueNotifier<WsState> _state =
      ValueNotifier<WsState>(WsState.disconnected);

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  bool _disposed = false;
  bool _connectionRequested = false;
  bool _connectInFlight = false;
  int _reconnectAttempt = 0;

  String get baseUrl => _connectUri.toString();
  ValueListenable<WsState> get stateListenable => _state;

  Stream<ChartOrderActionModel> connectChartOrderActions() {
    return connectEvents()
        .where((event) => event['event'] == 'chart_order_action')
        .map(
          (event) => ChartOrderActionModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<StrategyPerformanceUpdateModel> connectStrategyPerformanceUpdates() {
    return connectEvents()
        .where((event) => event['event'] == 'strategy_performance_update')
        .map(
          (event) => StrategyPerformanceUpdateModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<Map<String, dynamic>> connectEvents() {
    if (!_connectionRequested) {
      _connectionRequested = true;
      unawaited(_connect());
    }
    return _eventController.stream;
  }

  void reconnectNow() {
    _reconnectTimer?.cancel();
    _reconnectAttempt = 0;
    _setState(WsState.connecting);
    unawaited(_connect());
  }

  Future<void> dispose() async {
    _disposed = true;
    _setState(WsState.disconnected);
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    await _subscription?.cancel();
    await _channel?.sink.close();
    await _eventController.close();
    _state.dispose();
  }

  Future<void> _connect() async {
    if (_disposed || _connectInFlight) {
      return;
    }
    _connectInFlight = true;
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    await _subscription?.cancel();
    await _channel?.sink.close();
    _setState(_reconnectAttempt == 0 ? WsState.connecting : WsState.degraded);
    try {
      final channel = connectTradingWebSocket(
        _connectUri,
        apiKey: _apiKey,
      );
      _channel = channel;
      await channel.ready.timeout(AppConstants.websocketConnectTimeout);
      _reconnectAttempt = 0;
      _setState(WsState.connected);
      _startHeartbeat();
      _subscription = channel.stream.listen(
        _handleRawMessage,
        onError: (Object error, StackTrace stackTrace) {
          logError(error, stackTrace: stackTrace);
          _eventController.addError(_toSocketException(error), stackTrace);
          _scheduleReconnect();
        },
        onDone: _scheduleReconnect,
        cancelOnError: false,
      );
    } catch (error, stackTrace) {
      logError(error, stackTrace: stackTrace);
      _eventController.addError(_toSocketException(error), stackTrace);
      _scheduleReconnect();
    } finally {
      _connectInFlight = false;
    }
  }

  void _handleRawMessage(dynamic raw) {
    try {
      final decoded = jsonDecode(raw as String);
      if (decoded is! Map<String, dynamic>) {
        return;
      }
      if (decoded['event'] == 'pong' || decoded['event'] == 'heartbeat') {
        if (_state.value == WsState.degraded) {
          _setState(WsState.connected);
        }
        return;
      }
      _eventController.add(Map<String, dynamic>.from(decoded));
    } catch (error, stackTrace) {
      logError(error, stackTrace: stackTrace);
      _eventController.addError(error, stackTrace);
    }
  }

  void _scheduleReconnect() {
    if (_disposed) {
      return;
    }
    _setState(WsState.degraded);
    _heartbeatTimer?.cancel();
    _reconnectTimer?.cancel();
    _reconnectAttempt += 1;
    _reconnectTimer = Timer(
      _reconnectDelayForAttempt(_reconnectAttempt),
      () => unawaited(_connect()),
    );
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    void sendPing() {
      if (_disposed || _state.value == WsState.disconnected) {
        return;
      }
      try {
        _channel?.sink.add('ping');
      } catch (error, stackTrace) {
        logError(error, stackTrace: stackTrace);
        _scheduleReconnect();
      }
    }

    sendPing();
    _heartbeatTimer = Timer.periodic(
      AppConstants.websocketPingInterval,
      (_) => sendPing(),
    );
  }

  Uri get _connectUri {
    final uri = Uri.parse(_baseUrl);
    final token = _apiKey.trim();
    if (token.isEmpty) {
      return uri;
    }
    return uri.replace(
      queryParameters: <String, String>{
        ...uri.queryParameters,
        'token': token,
      },
    );
  }

  Duration _reconnectDelayForAttempt(int attempt) {
    final exponent = attempt <= 1 ? 0 : (attempt - 1).clamp(0, 3);
    final computed = AppConstants.websocketReconnectBaseDelay * (1 << exponent);
    return computed > AppConstants.websocketReconnectMaxDelay
        ? AppConstants.websocketReconnectMaxDelay
        : computed;
  }

  ApiException _toSocketException(Object? error) {
    final message = error?.toString().toLowerCase() ?? '';
    if (message.contains('401') ||
        message.contains('403') ||
        message.contains('1008')) {
      return const ApiException(
        'Trading updates websocket authentication failed.',
        code: 'unauthorized',
      );
    }
    return const ApiException(
      'Trading updates stream dropped. The app will retry automatically.',
      code: 'socket_error',
      retryable: true,
    );
  }

  void _setState(WsState next) {
    if (_state.value == next) {
      return;
    }
    _state.value = next;
    debugPrint('[TRADING UPDATES WS STATE] ${next.name.toUpperCase()}');
  }
}

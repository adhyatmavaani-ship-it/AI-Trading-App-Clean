import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../features/risk_coach/models/risk_coach_models.dart';
import '../models/activity.dart';
import 'auth_credentials_store.dart';
import 'error_mapper.dart';
import '../models/signal.dart';
import 'constants.dart';
import 'retry.dart';
import 'websocket_channel_factory.dart';

enum WsState { connecting, connected, degraded, disconnected }

class WebSocketService {
  WebSocketService({
    required AuthCredentialsStore credentialsStore,
    String? baseUrl,
  })  : _credentialsStore = credentialsStore,
        _baseUrl = baseUrl ?? AppConstants.defaultWsBaseUrl;

  final AuthCredentialsStore _credentialsStore;
  final String _baseUrl;
  final StreamController<Map<String, dynamic>> _eventController =
      StreamController<Map<String, dynamic>>.broadcast();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSubscription;
  Timer? _reconnectTimer;
  bool _isDisposed = false;
  bool _connectionRequested = false;
  int _reconnectAttempt = 0;
  final ValueNotifier<WsState> _state = ValueNotifier<WsState>(
    WsState.disconnected,
  );

  String get baseUrl => _baseUrl;
  ValueListenable<WsState> get stateListenable => _state;

  Stream<SignalModel> connectSignals() {
    return connectEvents()
        .where((event) => (event['type'] as String?) != 'activity')
        .map(SignalModel.fromJson);
  }

  Stream<ActivityItemModel> connectActivity() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'activity')
        .map(ActivityItemModel.fromJson);
  }

  Stream<RiskCoachStreamEvent> connectRiskCoachMarket() async* {
    final uri = Uri.parse(_baseUrl).resolve('/ws/market');
    final channel = connectTradingWebSocket(uri);
    try {
      await for (final dynamic raw in channel.stream) {
        final decoded = jsonDecode(raw as String);
        if (decoded is! Map<String, dynamic>) {
          continue;
        }
        if (decoded['type'] != null) {
          continue;
        }
        yield RiskCoachStreamEvent.fromJson(decoded);
      }
    } finally {
      await channel.sink.close();
    }
  }

  Stream<Map<String, dynamic>> connectEvents() {
    if (!_connectionRequested) {
      _connectionRequested = true;
      unawaited(_connect());
    }
    return _eventController.stream;
  }

  Future<Map<String, dynamic>> probeSignals({
    Duration timeout = const Duration(seconds: 12),
  }) async {
    return retry<Map<String, dynamic>>(
      () async {
        final session = await _credentialsStore.loadSession();
        final uri = Uri.parse(_baseUrl).resolve('/ws/signals');
        final accessToken = session?.accessToken.trim() ?? '';
        final channel = connectTradingWebSocket(
          uri,
          bearerToken: accessToken.isEmpty ? null : accessToken,
        );
        try {
          final firstMessage = channel.stream.first.timeout(timeout);
          channel.sink.add('ping');
          final raw = await firstMessage;
          final decoded = jsonDecode(raw as String);
          if (decoded is Map<String, dynamic>) {
            return decoded;
          }
          throw const FormatException('Invalid websocket payload');
        } finally {
          await channel.sink.close();
        }
      },
    );
  }

  Future<void> _connect() async {
    if (_isDisposed) {
      return;
    }
    _state.value = _reconnectAttempt == 0
        ? WsState.connecting
        : WsState.degraded;
    _channelSubscription?.cancel();
    final session = await _credentialsStore.loadSession();
    final uri = Uri.parse(_baseUrl).resolve('/ws/signals');
    final accessToken = session?.accessToken.trim() ?? '';
    _channel = connectTradingWebSocket(
      uri,
      bearerToken: accessToken.isEmpty ? null : accessToken,
    );
    _channelSubscription = _channel!.stream.listen(
      (dynamic data) {
        _reconnectAttempt = 0;
        _state.value = WsState.connected;
        try {
          final decoded = jsonDecode(data as String) as Map<String, dynamic>;
          _eventController.add(decoded);
        } catch (error, stackTrace) {
          logError(error, stackTrace: stackTrace);
          _eventController.addError(error, stackTrace);
        }
      },
      onError: (Object error, StackTrace stackTrace) {
        logError(error, stackTrace: stackTrace);
        _eventController.addError(error, stackTrace);
        _scheduleReconnect();
      },
      onDone: _scheduleReconnect,
      cancelOnError: false,
    );
  }

  void _scheduleReconnect() {
    if (_isDisposed) {
      return;
    }
    _state.value = WsState.degraded;
    _reconnectTimer?.cancel();
    final exponentialSeconds =
        AppConstants.websocketReconnectBaseDelay.inSeconds *
            (_reconnectAttempt + 1);
    final delay = Duration(
      seconds: exponentialSeconds.clamp(
        AppConstants.websocketReconnectBaseDelay.inSeconds,
        AppConstants.websocketMaxReconnectDelay.inSeconds,
      ),
    );
    _reconnectAttempt += 1;
    track('ws_reconnect', <String, dynamic>{'attempt': _reconnectAttempt});
    _reconnectTimer = Timer(delay, () {
      unawaited(_connect());
    });
  }

  void reconnectNow() {
    _reconnectTimer?.cancel();
    _reconnectAttempt = 0;
    _state.value = WsState.connecting;
    unawaited(_connect());
  }

  Future<void> dispose() async {
    _isDisposed = true;
    _state.value = WsState.disconnected;
    await _channelSubscription?.cancel();
    await _channel?.sink.close();
    _reconnectTimer?.cancel();
    await _eventController.close();
    _state.dispose();
  }
}

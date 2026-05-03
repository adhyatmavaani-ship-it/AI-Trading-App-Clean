import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../features/risk_coach/models/risk_coach_models.dart';
import '../models/activity.dart';
import '../models/signal.dart';
import 'api_exception.dart';
import 'auth_credentials_store.dart';
import 'constants.dart';
import 'error_mapper.dart';
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
  int _signalTargetIndex = 0;
  final ValueNotifier<WsState> _state = ValueNotifier<WsState>(
    WsState.disconnected,
  );

  String get baseUrl => _signalTargets.first.toString();
  ValueListenable<WsState> get stateListenable => _state;

  Stream<SignalModel> connectSignals() {
    return connectEvents()
        .where((event) => (event['type'] as String?) != 'activity')
        .map((event) => SignalModel.fromJson(Map<String, dynamic>.from(event)));
  }

  Stream<ActivityItemModel> connectActivity() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'activity')
        .map(
          (event) =>
              ActivityItemModel.fromJson(Map<String, dynamic>.from(event)),
        );
  }

  Stream<RiskCoachStreamEvent> connectRiskCoachMarket() async* {
    final uri = _rootUri.replace(path: '/ws/market', query: null);
    final auth = await _resolveSocketAuth();
    final channel = connectTradingWebSocket(
      uri,
      apiKey: auth.apiKey,
      bearerToken: auth.bearerToken,
    );
    try {
      await channel.ready.timeout(AppConstants.requestTimeout);
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
    Duration timeout = AppConstants.requestTimeout,
  }) async {
    Object? lastError;
    StackTrace? lastStackTrace;
    final auth = await _resolveSocketAuth();
    for (final uri in _signalTargets) {
      WebSocketChannel? channel;
      try {
        channel = connectTradingWebSocket(
          uri,
          apiKey: auth.apiKey,
          bearerToken: auth.bearerToken,
        );
        await channel.ready.timeout(timeout);
        channel.sink.add('ping');
        final raw = await channel.stream.first.timeout(timeout);
        final decoded = jsonDecode(raw as String);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
        throw const FormatException('Invalid websocket payload');
      } catch (error, stackTrace) {
        lastError = error;
        lastStackTrace = stackTrace;
      } finally {
        await channel?.sink.close();
      }
    }
    logError(lastError, stackTrace: lastStackTrace);
    throw _toWebSocketException(lastError);
  }

  Future<void> _connect() async {
    if (_isDisposed) {
      return;
    }
    _reconnectTimer?.cancel();
    await _channelSubscription?.cancel();
    await _channel?.sink.close();

    _state.value =
        _reconnectAttempt == 0 ? WsState.connecting : WsState.degraded;
    final uri = _currentSignalTarget;
    final auth = await _resolveSocketAuth();
    try {
      final channel = connectTradingWebSocket(
        uri,
        apiKey: auth.apiKey,
        bearerToken: auth.bearerToken,
      );
      _channel = channel;
      await channel.ready.timeout(AppConstants.requestTimeout);
      _reconnectAttempt = 0;
      _state.value = WsState.connected;
      track('ws_connected', <String, dynamic>{'uri': uri.toString()});
      _channelSubscription = channel.stream.listen(
        (dynamic data) {
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
          _eventController.addError(_toWebSocketException(error), stackTrace);
          _scheduleReconnect();
        },
        onDone: _scheduleReconnect,
        cancelOnError: false,
      );
    } catch (error, stackTrace) {
      logError(error, stackTrace: stackTrace);
      _eventController.addError(_toWebSocketException(error), stackTrace);
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_isDisposed) {
      return;
    }
    _state.value = WsState.degraded;
    _reconnectTimer?.cancel();
    if (_signalTargets.length > 1) {
      _signalTargetIndex = (_signalTargetIndex + 1) % _signalTargets.length;
    }
    _reconnectAttempt += 1;
    track(
      'ws_reconnect',
      <String, dynamic>{
        'attempt': _reconnectAttempt,
        'delay_seconds': AppConstants.websocketReconnectDelay.inSeconds,
        'target': _currentSignalTarget.toString(),
      },
    );
    _reconnectTimer = Timer(
      AppConstants.websocketReconnectDelay,
      () => unawaited(_connect()),
    );
  }

  void reconnectNow() {
    _reconnectTimer?.cancel();
    _signalTargetIndex = 0;
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

  Uri get _rootUri {
    final configured = Uri.parse(_baseUrl);
    if (configured.path.isEmpty || configured.path == '/') {
      return configured.replace(path: '', query: null, fragment: null);
    }
    return configured.replace(path: '', query: null, fragment: null);
  }

  List<Uri> get _signalTargets {
    final configured = Uri.parse(_baseUrl);
    final primary = (configured.path.isEmpty || configured.path == '/')
        ? configured.replace(path: '/ws', query: null, fragment: null)
        : configured.replace(query: null, fragment: null);
    final fallback =
        configured.replace(path: '/ws/signals', query: null, fragment: null);
    if (primary.toString() == fallback.toString()) {
      return <Uri>[primary];
    }
    return <Uri>[primary, fallback];
  }

  Uri get _currentSignalTarget {
    final targets = _signalTargets;
    final index = _signalTargetIndex.clamp(0, targets.length - 1);
    return targets[index];
  }

  Future<_SocketAuth> _resolveSocketAuth() async {
    final session = await _credentialsStore.loadSession();
    final configuredApiKey = AppConstants.requiredApiKey;
    if (session == null || session.accessToken.trim().isEmpty) {
      return _SocketAuth(apiKey: configuredApiKey);
    }
    return _SocketAuth(
      apiKey: configuredApiKey,
      bearerToken: session.scheme == AuthScheme.bearer
          ? session.accessToken.trim()
          : null,
    );
  }

  ApiException _toWebSocketException(Object? error) {
    final message = error?.toString().toLowerCase() ?? '';
    if (message.contains('timed out') || message.contains('timeout')) {
      return const ApiException(
        'WebSocket connection timed out while the Render backend was waking up.',
        code: 'timeout',
        retryable: true,
      );
    }
    if (message.contains('403') ||
        message.contains('401') ||
        message.contains('1008') ||
        message.contains('missing api key')) {
      return const ApiException(
        'WebSocket authentication failed. Check the configured X-API-Key.',
        code: 'unauthorized',
      );
    }
    return const ApiException(
      'Live connection dropped. The app will retry automatically.',
      code: 'socket_error',
      retryable: true,
    );
  }
}

class _SocketAuth {
  const _SocketAuth({
    this.apiKey,
    this.bearerToken,
  });

  final String? apiKey;
  final String? bearerToken;
}

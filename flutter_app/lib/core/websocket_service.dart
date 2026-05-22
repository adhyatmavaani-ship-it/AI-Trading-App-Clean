import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../features/risk_coach/models/risk_coach_models.dart';
import '../models/activity.dart';
import '../models/realtime_event.dart';
import '../models/signal.dart';
import 'api_exception.dart';
import 'constants.dart';
import 'error_mapper.dart';
import 'realtime_integrity.dart';
import 'websocket_channel_factory.dart';

enum WsState { connecting, connected, degraded, disconnected }

class WebSocketService {
  WebSocketService({
    String? baseUrl,
  }) : _baseUrl = baseUrl ?? AppConstants.defaultSignalsWebSocketUrl {
    debugPrint('[WS BASE URL] $_baseUrl');
    track('ws_url_resolved', <String, dynamic>{'url': _baseUrl});
  }

  final String _baseUrl;
  final StreamController<Map<String, dynamic>> _eventController =
      StreamController<Map<String, dynamic>>.broadcast();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSubscription;
  Timer? _heartbeatTimer;
  Timer? _reconnectTimer;
  Timer? _staleFeedTimer;
  bool _isDisposed = false;
  bool _connectionRequested = false;
  bool _connectInFlight = false;
  int _reconnectAttempt = 0;
  String _lastReconnectReason = 'initial_connect';
  final ValueNotifier<WsState> _state = ValueNotifier<WsState>(
    WsState.disconnected,
  );
  final RealtimeIntegrityGate _integrityGate = RealtimeIntegrityGate();

  String get baseUrl => _signalUri.toString();
  ValueListenable<WsState> get stateListenable => _state;

  Stream<SignalModel> connectSignals() {
    return connectEvents().where((event) {
      final type = event['type'] as String?;
      return type == null || type == 'signal';
    }).map((event) => SignalModel.fromJson(Map<String, dynamic>.from(event)));
  }

  Stream<ActivityItemModel> connectActivity() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'activity')
        .map(
          (event) =>
              ActivityItemModel.fromJson(Map<String, dynamic>.from(event)),
        );
  }

  Stream<RealtimeTradeUpdateModel> connectTradeUpdates() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'trade_update')
        .map(
          (event) => RealtimeTradeUpdateModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<RealtimePortfolioUpdateModel> connectPortfolioUpdates() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'portfolio_update')
        .map(
          (event) => RealtimePortfolioUpdateModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<DashboardRealtimeSummaryModel> connectDashboardSummaries() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'dashboard_summary')
        .map(
          (event) => DashboardRealtimeSummaryModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<ChartRealtimeSnapshotModel> connectChartSnapshots() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'chart_snapshot')
        .map(
          (event) => ChartRealtimeSnapshotModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<AiTradeFeedRealtimeModel> connectAiTradeFeed() {
    return connectEvents()
        .where((event) => (event['type'] as String?) == 'ai_trade_feed')
        .map(
          (event) => AiTradeFeedRealtimeModel.fromJson(
            Map<String, dynamic>.from(event),
          ),
        );
  }

  Stream<RiskCoachStreamEvent> connectRiskCoachMarket() async* {
    final uri = Uri.parse(AppConstants.defaultMarketWebSocketUrl);
    final channel = connectTradingWebSocket(
      uri,
      apiKey: AppConstants.requiredApiKey,
    );
    debugPrint('[WS AUTH] required_api_key');
    debugPrint('[WS AUTH HEADER] X-API-Key=present');
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
    Duration timeout = AppConstants.websocketProbeTimeout,
  }) async {
    WebSocketChannel? channel;
    try {
      channel = connectTradingWebSocket(
        _signalUri,
        apiKey: AppConstants.requiredApiKey,
      );
      debugPrint('[WS AUTH] required_api_key');
      debugPrint('[WS AUTH HEADER] X-API-Key=present');
      await channel.ready.timeout(timeout);
      channel.sink.add('ping');
      final raw = await channel.stream.first.timeout(timeout);
      final decoded = jsonDecode(raw as String);
      if (decoded is Map<String, dynamic>) {
        return decoded;
      }
      throw const FormatException('Invalid websocket payload');
    } catch (error, stackTrace) {
      logError(error, stackTrace: stackTrace);
      throw _toWebSocketException(error);
    } finally {
      await channel?.sink.close();
    }
  }

  Future<void> _connect() async {
    if (_isDisposed || _connectInFlight) {
      return;
    }
    _connectInFlight = true;
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    await _channelSubscription?.cancel();
    await _channel?.sink.close();

    _setState(
      _reconnectAttempt == 0 ? WsState.connecting : WsState.degraded,
    );
    final uri = _signalUri;
    try {
      final channel = connectTradingWebSocket(
        uri,
        apiKey: AppConstants.requiredApiKey,
      );
      debugPrint('[WS AUTH] required_api_key');
      debugPrint('[WS AUTH HEADER] X-API-Key=present');
      _channel = channel;
      await channel.ready.timeout(AppConstants.websocketConnectTimeout);
      _reconnectAttempt = 0;
      _setState(WsState.connected);
      _startHeartbeat();
      _startStaleFeedMonitor();
      track(
        'ws_connected',
        <String, dynamic>{
          'uri': uri.toString(),
          'via_proxy': true,
        },
      );
      _channelSubscription = channel.stream.listen(
        (dynamic data) {
          try {
            final decoded = jsonDecode(data as String) as Map<String, dynamic>;
            if (decoded['type'] == 'pong') {
              _integrityGate.evaluate(decoded);
              if (_state.value == WsState.degraded) {
                _setState(WsState.connected);
              }
              track('ws_pong', <String, dynamic>{'target': uri.toString()});
              return;
            }
            if (decoded['type'] == 'replay_response') {
              track('ws_replay_response', decoded);
              if (decoded['recovery'] == 'snapshot_required') {
                _eventController.add(Map<String, dynamic>.from(decoded));
              }
              return;
            }
            final decision = _integrityGate.evaluate(decoded);
            if (!decision.accepted) {
              track(
                'ws_event_dropped',
                <String, dynamic>{
                  'reason': decision.reason,
                  'type': decoded['type'],
                  'sequence_id': decoded['sequence_id'],
                },
              );
              if (decision.reason == 'sequence_gap' &&
                  decision.stream != null &&
                  decision.missingFrom != null &&
                  decision.missingTo != null) {
                _setState(WsState.degraded);
                _requestReplay(
                  stream: decision.stream!,
                  fromSequence: decision.missingFrom!,
                  toSequence: decision.missingTo!,
                );
              }
              return;
            }
            if (decision.latencyMs != null) {
              track(
                'ws_event_latency',
                <String, dynamic>{
                  'latency_ms': decision.latencyMs,
                  'type': decoded['type'],
                  'sequence_id': decoded['sequence_id'],
                },
              );
            }
            if (_state.value == WsState.degraded) {
              _setState(WsState.connected);
            }
            _eventController.add(decision.payload);
          } catch (error, stackTrace) {
            logError(error, stackTrace: stackTrace);
            _eventController.addError(error, stackTrace);
          }
        },
        onError: (Object error, StackTrace stackTrace) {
          logError(error, stackTrace: stackTrace);
          debugPrint('[WS ERROR] $error');
          _eventController.addError(_toWebSocketException(error), stackTrace);
          _scheduleReconnect(reason: 'stream_error:${error.runtimeType}');
        },
        onDone: () {
          debugPrint('[WS CLOSED] stream completed by backend or network');
          _scheduleReconnect(reason: 'stream_closed');
        },
        cancelOnError: false,
      );
    } catch (error, stackTrace) {
      logError(error, stackTrace: stackTrace);
      debugPrint('[WS CONNECT FAILED] $error');
      track(
        'ws_connect_failed',
        <String, dynamic>{
          'reason': error.toString(),
          'uri': uri.toString(),
          'via_proxy': true,
        },
      );
      _eventController.addError(_toWebSocketException(error), stackTrace);
      _scheduleReconnect(reason: 'connect_failed:${error.runtimeType}');
    } finally {
      _connectInFlight = false;
    }
  }

  void _scheduleReconnect({required String reason}) {
    if (_isDisposed) {
      return;
    }
    _setState(WsState.degraded);
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _staleFeedTimer?.cancel();
    _reconnectAttempt += 1;
    _lastReconnectReason = reason;
    final delay = _reconnectDelayForAttempt(_reconnectAttempt);
    debugPrint(
      '[WS RECONNECT] attempt=$_reconnectAttempt delay=${delay.inSeconds}s reason=$reason target=$_signalUri',
    );
    track(
      'ws_reconnect',
      <String, dynamic>{
        'attempt': _reconnectAttempt,
        'delay_seconds': delay.inSeconds,
        'target': _signalUri.toString(),
        'reason': reason,
      },
    );
    _reconnectTimer = Timer(
      delay,
      () => unawaited(_connect()),
    );
  }

  void reconnectNow() {
    _reconnectTimer?.cancel();
    _reconnectAttempt = 0;
    _lastReconnectReason = 'manual_retry';
    _setState(WsState.connecting);
    debugPrint('[WS RETRY] manual reconnect requested for $_signalUri');
    unawaited(_connect());
  }

  void _requestReplay({
    required String stream,
    required int fromSequence,
    required int toSequence,
  }) {
    final channel = _channel;
    if (channel == null || fromSequence <= 0 || toSequence < fromSequence) {
      return;
    }
    final request = <String, dynamic>{
      'type': 'replay_request',
      'stream': stream,
      'from_sequence': fromSequence,
      'to_sequence': toSequence,
    };
    debugPrint(
      '[WS GAP] stream=$stream missing=$fromSequence-$toSequence requesting replay',
    );
    track(
      'ws_sequence_gap',
      <String, dynamic>{
        'stream': stream,
        'from_sequence': fromSequence,
        'to_sequence': toSequence,
      },
    );
    channel.sink.add(jsonEncode(request));
  }

  Future<void> dispose() async {
    _isDisposed = true;
    _setState(WsState.disconnected);
    await _channelSubscription?.cancel();
    await _channel?.sink.close();
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _staleFeedTimer?.cancel();
    await _eventController.close();
    _state.dispose();
  }

  Uri get _signalUri => Uri.parse(_baseUrl);

  Duration _reconnectDelayForAttempt(int attempt) {
    final exponent = attempt <= 1 ? 0 : (attempt - 1).clamp(0, 2);
    final factor = 1 << exponent;
    final computed = AppConstants.websocketReconnectBaseDelay * factor;
    if (computed > AppConstants.websocketReconnectMaxDelay) {
      return AppConstants.websocketReconnectMaxDelay;
    }
    return computed;
  }

  ApiException _toWebSocketException(Object? error) {
    final message = error?.toString().toLowerCase() ?? '';
    if (message.contains('timed out') || message.contains('timeout')) {
      return const ApiException(
        'WebSocket connection timed out while contacting nginx or the VPS backend.',
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
    return ApiException(
      'Live connection dropped. The app will retry automatically.',
      code: 'socket_error',
      retryable: true,
      details: <String, dynamic>{'reason': _lastReconnectReason},
    );
  }

  void _startStaleFeedMonitor() {
    _staleFeedTimer?.cancel();
    _staleFeedTimer = Timer.periodic(
      AppConstants.websocketIntegrityCheckInterval,
      (_) {
        if (_isDisposed || _state.value != WsState.connected) {
          return;
        }
        if (_integrityGate.isStale(AppConstants.websocketStaleAfter)) {
          _setState(WsState.degraded);
          track(
            'ws_feed_stale',
            <String, dynamic>{
              'target': _signalUri.toString(),
              'stale_after_seconds': AppConstants.websocketStaleAfter.inSeconds,
            },
          );
        }
      },
    );
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    void sendPing() {
      if (_isDisposed || _state.value == WsState.disconnected) {
        return;
      }
      try {
        _channel?.sink.add('ping');
      } catch (error, stackTrace) {
        logError(error, stackTrace: stackTrace);
        _scheduleReconnect(reason: 'heartbeat_failed:${error.runtimeType}');
      }
    }

    sendPing();
    _heartbeatTimer = Timer.periodic(
      AppConstants.websocketPingInterval,
      (_) => sendPing(),
    );
  }

  void _setState(WsState nextState) {
    if (_state.value == nextState) {
      return;
    }
    _state.value = nextState;
    debugPrint('[WS STATE] ${nextState.name.toUpperCase()} $_signalUri');
  }
}

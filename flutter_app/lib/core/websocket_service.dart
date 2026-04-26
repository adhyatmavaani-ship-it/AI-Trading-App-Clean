import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import 'auth_credentials_store.dart';
import '../models/signal.dart';
import 'constants.dart';
import 'websocket_channel_factory.dart';

class WebSocketService {
  WebSocketService({
    required AuthCredentialsStore credentialsStore,
    String? baseUrl,
  })  : _credentialsStore = credentialsStore,
        _baseUrl = baseUrl ?? AppConstants.defaultWsBaseUrl;

  final AuthCredentialsStore _credentialsStore;
  final String _baseUrl;
  final StreamController<SignalModel> _controller =
      StreamController<SignalModel>.broadcast();

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _channelSubscription;
  Timer? _reconnectTimer;
  bool _isDisposed = false;
  int _reconnectAttempt = 0;

  Stream<SignalModel> connectSignals() {
    unawaited(_connect());
    return _controller.stream;
  }

  Future<void> _connect() async {
    if (_isDisposed) {
      return;
    }
    _channelSubscription?.cancel();
    final session = await _credentialsStore.loadSession();
    final uri = Uri.parse('$_baseUrl/ws/signals');
    final accessToken = session?.accessToken.trim() ?? '';
    _channel = connectTradingWebSocket(
      uri,
      bearerToken: accessToken.isEmpty ? null : accessToken,
    );
    _channelSubscription = _channel!.stream.listen(
      (dynamic data) {
        _reconnectAttempt = 0;
        try {
          final decoded = jsonDecode(data as String) as Map<String, dynamic>;
          _controller.add(SignalModel.fromJson(decoded));
        } catch (error, stackTrace) {
          _controller.addError(error, stackTrace);
        }
      },
      onError: (Object error, StackTrace stackTrace) {
        _controller.addError(error, stackTrace);
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
    _reconnectTimer = Timer(delay, () {
      unawaited(_connect());
    });
  }

  Future<void> dispose() async {
    _isDisposed = true;
    await _channelSubscription?.cancel();
    await _channel?.sink.close();
    _reconnectTimer?.cancel();
    await _controller.close();
  }
}

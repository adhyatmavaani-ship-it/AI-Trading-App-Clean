import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'constants.dart';

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? apiKey,
}) {
  final headers = <String, dynamic>{};
  if (apiKey != null && apiKey.isNotEmpty) {
    headers['X-API-Key'] = apiKey;
  }
  return IOWebSocketChannel.connect(
    uri,
    headers: headers,
    pingInterval: AppConstants.websocketPingInterval,
    connectTimeout: AppConstants.websocketConnectTimeout,
  );
}

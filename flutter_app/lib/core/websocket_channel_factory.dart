import 'package:web_socket_channel/web_socket_channel.dart';

import 'websocket_channel_factory_io.dart'
    if (dart.library.html) 'websocket_channel_factory_web.dart' as platform;

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? apiKey,
  String? bearerToken,
}) {
  return platform.connectTradingWebSocket(
    uri,
    apiKey: apiKey,
    bearerToken: bearerToken,
  );
}

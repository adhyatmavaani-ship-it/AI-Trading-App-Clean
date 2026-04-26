import 'package:web_socket_channel/html.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? bearerToken,
}) {
  // Browsers cannot attach arbitrary websocket headers, so keep the legacy
  // query-string fallback temporarily for web builds only.
  final connectUri = (bearerToken != null && bearerToken.isNotEmpty)
      ? uri.replace(queryParameters: <String, String>{'api_key': bearerToken})
      : uri;
  return HtmlWebSocketChannel.connect(connectUri.toString());
}

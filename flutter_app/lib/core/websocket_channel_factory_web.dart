import 'package:web_socket_channel/html.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? apiKey,
  String? bearerToken,
}) {
  final queryParameters = <String, String>{...uri.queryParameters};
  if (apiKey != null && apiKey.isNotEmpty) {
    queryParameters['api_key'] = apiKey;
  } else if (bearerToken != null && bearerToken.isNotEmpty) {
    queryParameters['api_key'] = bearerToken;
  }
  if (bearerToken != null && bearerToken.isNotEmpty) {
    queryParameters.putIfAbsent('token', () => bearerToken);
  }
  final connectUri = uri.replace(
    queryParameters: queryParameters.isEmpty ? null : queryParameters,
  );
  return HtmlWebSocketChannel.connect(connectUri.toString());
}

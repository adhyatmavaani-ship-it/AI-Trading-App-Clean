import 'package:web_socket_channel/html.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? apiKey,
}) {
  final queryParameters = <String, String>{...uri.queryParameters};
  if (apiKey != null && apiKey.isNotEmpty) {
    queryParameters['api_key'] = apiKey;
  }
  final connectUri = uri.replace(
    queryParameters: queryParameters.isEmpty ? null : queryParameters,
  );
  return HtmlWebSocketChannel.connect(connectUri.toString());
}

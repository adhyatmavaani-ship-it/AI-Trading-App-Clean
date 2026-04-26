import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

WebSocketChannel connectTradingWebSocket(
  Uri uri, {
  String? bearerToken,
}) {
  final headers = <String, dynamic>{};
  if (bearerToken != null && bearerToken.isNotEmpty) {
    headers['Authorization'] = 'Bearer $bearerToken';
  }
  return IOWebSocketChannel.connect(uri, headers: headers);
}

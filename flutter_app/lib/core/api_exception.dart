class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.code,
  });

  final String message;
  final int? statusCode;
  final String? code;

  bool get isTimeout => code == 'timeout';
  bool get isSocketError => code == 'socket_error';
  bool get isInvalidResponse => code == 'invalid_response';

  @override
  String toString() => message;
}

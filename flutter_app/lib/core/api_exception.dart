class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.code,
    this.details = const <String, dynamic>{},
    this.method,
    this.uri,
    this.retryable = false,
  });

  final String message;
  final int? statusCode;
  final String? code;
  final Map<String, dynamic> details;
  final String? method;
  final String? uri;
  final bool retryable;

  bool get isTimeout => code == 'timeout';
  bool get isSocketError => code == 'socket_error' || code == 'network_error';
  bool get isInvalidResponse => code == 'invalid_response';
  bool get isAuthError => code == 'unauthorized' || code == 'forbidden';

  Map<String, dynamic> toJson() {
    return <String, dynamic>{
      'message': message,
      'status_code': statusCode,
      'code': code,
      'method': method,
      'uri': uri,
      'retryable': retryable,
      'details': details,
    };
  }

  @override
  String toString() => message;
}

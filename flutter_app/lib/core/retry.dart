import 'dart:async';

Future<T> retry<T>(
  Future<T> Function() fn, {
  int maxAttempts = 3,
  Duration baseDelay = const Duration(milliseconds: 400),
  bool Function(Object error)? shouldRetry,
}) async {
  var attempts = 0;
  while (true) {
    try {
      return await fn();
    } catch (error) {
      attempts += 1;
      final allowed = shouldRetry?.call(error) ?? true;
      if (!allowed || attempts >= maxAttempts) {
        rethrow;
      }
      await Future<void>.delayed(baseDelay * attempts);
    }
  }
}

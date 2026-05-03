import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'api_exception.dart';

enum AppErrorType {
  network,
  timeout,
  auth,
  server,
  unknown,
}

class ErrorMapper {
  const ErrorMapper._();

  static String map(
    dynamic error, {
    String fallback = 'Something went wrong. Please try again.',
  }) {
    final type = typeOf(error);
    switch (type) {
      case AppErrorType.network:
        return 'Network issue. Check your internet connection.';
      case AppErrorType.timeout:
        return 'Server is taking too long. Please try again.';
      case AppErrorType.auth:
        return _authMessage(error);
      case AppErrorType.server:
        return _serverMessage(error);
      case AppErrorType.unknown:
        return _matchText(error?.toString().toLowerCase() ?? '', fallback);
    }
  }

  static AppErrorType typeOf(dynamic error) {
    if (error is ApiException) {
      return _typeFromApiException(error);
    }

    if (error is SocketException) {
      return AppErrorType.network;
    }

    if (error is http.ClientException) {
      return AppErrorType.network;
    }

    if (error is TimeoutException) {
      return AppErrorType.timeout;
    }

    return _typeFromText(error?.toString().toLowerCase() ?? '');
  }

  static IconData iconFor(dynamic error) {
    switch (typeOf(error)) {
      case AppErrorType.network:
        return Icons.wifi_tethering_error_rounded;
      case AppErrorType.timeout:
        return Icons.timer_off_rounded;
      case AppErrorType.auth:
        return Icons.lock_outline_rounded;
      case AppErrorType.server:
        return Icons.warning_amber_rounded;
      case AppErrorType.unknown:
        return Icons.error_outline_rounded;
    }
  }

  static AppErrorType _typeFromApiException(ApiException error) {
    switch (error.code) {
      case 'socket_error':
      case 'network_error':
        return AppErrorType.network;
      case 'timeout':
        return AppErrorType.timeout;
      case 'unauthorized':
      case 'forbidden':
        return AppErrorType.auth;
      case 'server_error':
      case 'invalid_response':
      case 'region_restricted':
      case 'http_error':
        return AppErrorType.server;
    }

    final statusCode = error.statusCode;
    if (statusCode == 401 || statusCode == 403) {
      return AppErrorType.auth;
    }
    if (statusCode != null && statusCode >= 500) {
      return AppErrorType.server;
    }
    return _typeFromText(error.message.toLowerCase());
  }

  static AppErrorType _typeFromText(String text) {
    if (text.contains('socket') || text.contains('network')) {
      return AppErrorType.network;
    }
    if (text.contains('timeout')) {
      return AppErrorType.timeout;
    }
    if (text.contains('401') || text.contains('unauthorized')) {
      return AppErrorType.auth;
    }
    if (text.contains('403')) {
      return AppErrorType.auth;
    }
    if (text.contains('500') ||
        text.contains('server') ||
        text.contains('invalid') ||
        text.contains('json')) {
      return AppErrorType.server;
    }
    return AppErrorType.unknown;
  }

  static String _authMessage(dynamic error) {
    final text = error?.toString().toLowerCase() ?? '';
    if (text.contains('403') || text.contains('forbidden')) {
      return 'Access denied.';
    }
    return 'Session expired. Please login again.';
  }

  static String _serverMessage(dynamic error) {
    final text = error?.toString().toLowerCase() ?? '';
    if (text.contains('invalid') || text.contains('json')) {
      return 'Unexpected response from server.';
    }
    return 'Server error. Try again shortly.';
  }

  static String _matchText(String text, String fallback) {
    if (text.contains('socket') || text.contains('network')) {
      return 'Network issue. Check your internet connection.';
    }
    if (text.contains('timeout')) {
      return 'Server is taking too long. Please try again.';
    }
    if (text.contains('401') || text.contains('unauthorized')) {
      return 'Session expired. Please login again.';
    }
    if (text.contains('403')) {
      return 'Access denied.';
    }
    if (text.contains('500')) {
      return 'Server error. Try again shortly.';
    }
    if (text.contains('invalid') || text.contains('json')) {
      return 'Unexpected response from server.';
    }
    return fallback;
  }
}

String newErrorId() => DateTime.now().millisecondsSinceEpoch.toString();

String userFacingMsg(String msg, String id) => '$msg (ref: $id)';

void logError(
  dynamic error, {
  StackTrace? stackTrace,
}) {
  logErrorWithId(error, stackTrace: stackTrace);
}

void logErrorWithId(
  dynamic error, {
  StackTrace? stackTrace,
  String? errorId,
}) {
  final id = errorId ?? newErrorId();
  debugPrint('ERR[$id]: $error');
  if (stackTrace != null) {
    debugPrint('$stackTrace');
  }
  // Future:
  // send to backend / firebase / sentry
}

void track(String name, [Map<String, dynamic>? props]) {
  debugPrint('EVENT: $name ${props ?? const <String, dynamic>{}}');
}

void showSafeError(
  BuildContext context,
  dynamic error, {
  String fallback = 'Something went wrong. Please try again.',
  VoidCallback? onRetry,
  VoidCallback? onAuthAction,
}) {
  final errorId = newErrorId();
  logErrorWithId(error, errorId: errorId);
  final msg = userFacingMsg(
    ErrorMapper.map(error, fallback: fallback),
    errorId,
  );
  final type = ErrorMapper.typeOf(error);
  final icon = ErrorMapper.iconFor(error);
  final messenger = ScaffoldMessenger.of(context);

  messenger.hideCurrentSnackBar();

  if (type == AppErrorType.auth || type == AppErrorType.server) {
    messenger.clearMaterialBanners();
    messenger.showMaterialBanner(
      MaterialBanner(
        backgroundColor: type == AppErrorType.auth
            ? const Color(0xFF2A1620)
            : const Color(0xFF2A1D16),
        leading: Icon(icon, color: Colors.white),
        content: Text(msg),
        actions: <Widget>[
          if (type == AppErrorType.auth && onAuthAction != null)
            TextButton(
              onPressed: () {
                messenger.hideCurrentMaterialBanner();
                onAuthAction();
              },
              child: const Text('Review'),
            )
          else if (type == AppErrorType.server && onRetry != null)
            TextButton(
              onPressed: () {
                messenger.hideCurrentMaterialBanner();
                onRetry();
              },
              child: const Text('Retry'),
            )
          else
            TextButton(
              onPressed: messenger.hideCurrentMaterialBanner,
              child: const Text('Dismiss'),
            ),
        ],
      ),
    );
    return;
  }

  messenger.showSnackBar(
    SnackBar(
      backgroundColor: Colors.redAccent,
      action: type == AppErrorType.network && onRetry != null
          ? SnackBarAction(
              label: 'Retry',
              textColor: Colors.white,
              onPressed: onRetry,
            )
          : null,
      content: Row(
        children: <Widget>[
          Icon(icon, color: Colors.white),
          const SizedBox(width: 8),
          Expanded(child: Text(msg)),
        ],
      ),
    ),
  );
}

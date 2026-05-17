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

  static const String backendReconnectingMessage =
      'Backend is reconnecting. Paper trading and AI advisory mode remain available.';

  static String map(
    dynamic error, {
    String fallback = 'Something went wrong. Please try again.',
  }) {
    if (error is ApiException) {
      final backendMessage = _backendExecutionMessage(error);
      if (backendMessage != null) {
        return backendMessage;
      }
    }
    final type = typeOf(error);
    switch (type) {
      case AppErrorType.network:
        return backendReconnectingMessage;
      case AppErrorType.timeout:
        return backendReconnectingMessage;
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
        return Icons.cloud_off_rounded;
      case AppErrorType.unknown:
        return Icons.error_outline_rounded;
    }
  }

  static bool isRecoverableBackend(dynamic error) {
    if (error is ApiException && _isBusinessExecutionCode(error.code)) {
      return false;
    }
    final type = typeOf(error);
    return type == AppErrorType.network ||
        type == AppErrorType.timeout ||
        type == AppErrorType.server;
  }

  static bool isRecoverableBackendMessage(String message) {
    final text = message.toLowerCase();
    return text.contains('backend is reconnecting') ||
        text.contains('paper trading and ai advisory mode remain available') ||
        text.contains('offline mode') ||
        text.contains('showing last known');
  }

  static AppErrorType _typeFromApiException(ApiException error) {
    if (_isBusinessExecutionCode(error.code)) {
      return AppErrorType.server;
    }
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
      case 'server_unavailable':
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
      return 'Live execution is temporarily locked. Paper trading and AI advisory mode are still available.';
    }
    return 'Realtime connection is reconnecting. Paper trading and charts remain available.';
  }

  static String _serverMessage(dynamic error) {
    if (error is ApiException) {
      final backendMessage = _backendExecutionMessage(error);
      if (backendMessage != null) {
        return backendMessage;
      }
    }
    final text = error?.toString().toLowerCase() ?? '';
    if (text.contains('invalid') || text.contains('json')) {
      return backendReconnectingMessage;
    }
    return backendReconnectingMessage;
  }

  static String _matchText(String text, String fallback) {
    if (text.contains('socket') || text.contains('network')) {
      return backendReconnectingMessage;
    }
    if (text.contains('timeout')) {
      return backendReconnectingMessage;
    }
    if (text.contains('401') || text.contains('unauthorized')) {
      return 'Realtime connection is reconnecting. Paper trading and charts remain available.';
    }
    if (text.contains('403')) {
      return 'Live execution is temporarily locked. Paper trading and AI advisory mode are still available.';
    }
    if (text.contains('500')) {
      return backendReconnectingMessage;
    }
    if (text.contains('invalid') || text.contains('json')) {
      return backendReconnectingMessage;
    }
    return fallback;
  }

  static bool _isBusinessExecutionCode(String? code) {
    const executionCodes = <String>{
      'CONFIDENCE_TOO_LOW',
      'SLIPPAGE_UNSAFE',
      'EXPOSURE_EXCEEDED',
      'SIDE_EXPOSURE_EXCEEDED',
      'THEME_EXPOSURE_EXCEEDED',
      'CLUSTER_EXPOSURE_EXCEEDED',
      'BETA_BUCKET_EXCEEDED',
      'BROKER_UNAVAILABLE',
      'COOLDOWN_ACTIVE',
      'DAILY_LOSS_LIMIT_REACHED',
      'SYMBOL_NOT_ALLOWED',
      'SYMBOL_NOT_TRADABLE',
      'META_CONTROLLER_BLOCKED',
      'STRICT_GATE_BLOCKED',
      'LIQUIDITY_INSUFFICIENT',
      'VOLATILITY_TOO_HIGH',
      'MIN_NOTIONAL_NOT_MET',
      'EXECUTION_DEGRADED',
      'MAX_ACTIVE_TRADES_REACHED',
      'DUPLICATE_ACTIVE_SYMBOL',
      'PORTFOLIO_CONCENTRATION_LIMIT',
      'TRADE_PROBABILITY_TOO_LOW',
      'INSUFFICIENT_ALLOCATABLE_BALANCE',
      'MICRO_MODE_BLOCKED',
      'CAPITAL_PROTECTION_DISABLED',
      'WHALE_CONFLICT_VETO',
      'EMERGENCY_STOP_ACTIVE',
      'DRAWDOWN_PAUSE_ACTIVE',
    };
    return executionCodes.contains(code);
  }

  static String? _backendExecutionMessage(ApiException error) {
    switch (error.code) {
      case 'CONFIDENCE_TOO_LOW':
        return 'Confidence too low. Wait for a stronger setup before executing.';
      case 'SLIPPAGE_UNSAFE':
        return 'Slippage is unsafe right now. Reduce size or wait for tighter liquidity.';
      case 'EXPOSURE_EXCEEDED':
      case 'SIDE_EXPOSURE_EXCEEDED':
      case 'THEME_EXPOSURE_EXCEEDED':
      case 'CLUSTER_EXPOSURE_EXCEEDED':
      case 'BETA_BUCKET_EXCEEDED':
      case 'PORTFOLIO_CONCENTRATION_LIMIT':
        return 'Portfolio exposure is already too high for this trade.';
      case 'BROKER_UNAVAILABLE':
        return 'Broker routing is unavailable right now. Retry after backend connectivity stabilizes.';
      case 'COOLDOWN_ACTIVE':
        return 'Cooldown is active after recent losses. Trading is temporarily paused.';
      case 'DAILY_LOSS_LIMIT_REACHED':
        return 'Daily loss protection is active. New trades are blocked for now.';
      case 'SYMBOL_NOT_ALLOWED':
      case 'SYMBOL_NOT_TRADABLE':
        return 'This symbol is not currently approved for execution.';
      case 'META_CONTROLLER_BLOCKED':
        return 'The meta engine blocked this trade because the setup quality is not good enough.';
      case 'STRICT_GATE_BLOCKED':
        return 'The strict execution gate rejected this trade. Wait for better confluence.';
      case 'LIQUIDITY_INSUFFICIENT':
        return 'Liquidity is too thin for a safe fill right now.';
      case 'VOLATILITY_TOO_HIGH':
        return 'Volatility is too high for safe execution right now.';
      case 'MIN_NOTIONAL_NOT_MET':
        return 'Order size is below the minimum tradable amount.';
      case 'EXECUTION_DEGRADED':
        return 'Execution is paused because backend latency is degraded.';
      case 'MAX_ACTIVE_TRADES_REACHED':
        return 'Maximum active trades reached. Close an existing position before opening a new one.';
      case 'DUPLICATE_ACTIVE_SYMBOL':
        return 'An active trade already exists for this symbol.';
      case 'TRADE_PROBABILITY_TOO_LOW':
        return 'Trade probability is too low. The AI engine does not approve this setup.';
      case 'INSUFFICIENT_ALLOCATABLE_BALANCE':
        return 'Available balance after risk controls is too low for this trade.';
      case 'MICRO_MODE_BLOCKED':
        return 'Micro-account safety rules blocked this trade.';
      case 'CAPITAL_PROTECTION_DISABLED':
      case 'DRAWDOWN_PAUSE_ACTIVE':
      case 'EMERGENCY_STOP_ACTIVE':
        return 'Risk protection is active. Trading is temporarily paused.';
      case 'WHALE_CONFLICT_VETO':
        return 'Order flow conflicts with the trade direction. Wait for alignment.';
    }
    return null;
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

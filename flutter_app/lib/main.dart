import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/api_exception.dart';
import 'core/backend_warmup_state.dart';
import 'providers/app_providers.dart';
import 'screens/auth_gate.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final container = ProviderContainer();
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const TradingApp(),
    ),
  );
  unawaited(_primeBackend(container));
}

Future<void> _primeBackend(ProviderContainer container) async {
  try {
    await container
        .read(apiClientProvider)
        .getHealthStatus()
        .timeout(const Duration(seconds: 6));
  } on ApiException {
    // Allow the app to open even if the first VPS health check fails.
  } catch (_) {
    // Keep startup resilient; normal in-app retry handling still applies.
  } finally {
    if (backendWarmupState.value != BackendWarmupState.ready) {
      markBackendSlow();
    }
  }
}

class TradingApp extends StatelessWidget {
  const TradingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Trading Platform',
      debugShowCheckedModeBanner: false,
      theme: TradingAppTheme.darkTheme,
      home: const AuthGate(),
    );
  }
}

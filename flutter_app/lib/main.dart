import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/api_exception.dart';
import 'core/auth_credentials_store.dart';
import 'core/constants.dart';
import 'providers/app_providers.dart';
import 'screens/auth_gate.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _bootstrapLocalAuth();
  final container = ProviderContainer();
  await _primeBackend(container);
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const TradingApp(),
    ),
  );
}

Future<void> _primeBackend(ProviderContainer container) async {
  try {
    await container.read(apiClientProvider).getHealthStatus();
  } on ApiException {
    // Allow the app to open even if the first Render warmup request fails.
  } catch (_) {
    // Keep startup resilient; normal in-app retry handling still applies.
  }
}

Future<void> _bootstrapLocalAuth() async {
  const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: AppConstants.productionApiBaseUrl,
  );
  const localDevApiKey = String.fromEnvironment(
    'LOCAL_DEV_API_KEY',
    defaultValue: 'local-dev-token',
  );
  final isLocalBackend =
      apiBaseUrl.contains('127.0.0.1') || apiBaseUrl.contains('localhost');
  if (!isLocalBackend || localDevApiKey.trim().isEmpty) {
    return;
  }
  final store = AuthCredentialsStore();
  await store.saveApiKey(localDevApiKey, scheme: AuthScheme.apiKey);
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

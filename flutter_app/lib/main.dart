import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth_credentials_store.dart';
import 'core/constants.dart';
import 'providers/app_bootstrap_provider.dart';
import 'providers/app_providers.dart';
import 'screens/app_shell.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _bootstrapLocalAuth();
  final container = ProviderContainer();
  unawaited(Future<void>.microtask(() {
    container.read(apiClientProvider).warmUpServer();
    container.read(appBootstrapProvider.future);
  }));
  runApp(
    UncontrolledProviderScope(
      container: container,
      child: const TradingApp(),
    ),
  );
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
      home: const AppShell(),
    );
  }
}

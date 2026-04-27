import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth_credentials_store.dart';
import 'screens/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _bootstrapLocalAuth();
  runApp(const ProviderScope(child: TradingApp()));
}

Future<void> _bootstrapLocalAuth() async {
  const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.84.86.111:8000',
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
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF157A6E),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF081217),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF081217),
          elevation: 0,
          centerTitle: false,
        ),
        useMaterial3: true,
      ),
      home: const AppShell(),
    );
  }
}

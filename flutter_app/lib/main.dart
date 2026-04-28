import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/auth_credentials_store.dart';
import 'core/trading_palette.dart';
import 'providers/app_providers.dart';
import 'screens/app_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await _bootstrapLocalAuth();
  final container = ProviderContainer();
  unawaited(Future<void>.microtask(() {
    container.read(apiClientProvider).warmUpServer();
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
        colorScheme: const ColorScheme.dark(
          primary: TradingPalette.neonGreen,
          secondary: TradingPalette.electricBlue,
          surface: TradingPalette.panelSoft,
          error: TradingPalette.neonRed,
          onPrimary: TradingPalette.midnight,
          onSecondary: TradingPalette.textPrimary,
          onSurface: TradingPalette.textPrimary,
          onError: TradingPalette.textPrimary,
        ),
        scaffoldBackgroundColor: TradingPalette.midnight,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          elevation: 0,
          centerTitle: false,
        ),
        cardColor: TradingPalette.panel,
        dividerColor: TradingPalette.panelBorder,
        textTheme: const TextTheme(
          headlineSmall: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w700,
          ),
          titleLarge: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w700,
          ),
          titleMedium: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w600,
          ),
          bodyMedium: TextStyle(
            color: TradingPalette.textMuted,
          ),
          labelLarge: TextStyle(
            color: TradingPalette.textMuted,
            fontWeight: FontWeight.w600,
          ),
          labelMedium: TextStyle(
            color: TradingPalette.textMuted,
          ),
          labelSmall: TextStyle(
            color: TradingPalette.textMuted,
          ),
        ),
        chipTheme: ChipThemeData(
          backgroundColor: TradingPalette.panelSoft,
          disabledColor: TradingPalette.panelSoft,
          selectedColor: TradingPalette.deepNavy,
          secondarySelectedColor: TradingPalette.deepNavy,
          side: const BorderSide(color: TradingPalette.panelBorder),
          labelStyle: const TextStyle(color: TradingPalette.textPrimary),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(999),
          ),
        ),
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: TradingPalette.deepNavy.withOpacity(0.94),
          indicatorColor: TradingPalette.panelBorder,
          labelTextStyle: WidgetStateProperty.all(
            const TextStyle(
              color: TradingPalette.textMuted,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
        useMaterial3: true,
      ),
      home: const AppShell(),
    );
  }
}

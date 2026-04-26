import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'screens/app_shell.dart';

void main() {
  runApp(const ProviderScope(child: TradingApp()));
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

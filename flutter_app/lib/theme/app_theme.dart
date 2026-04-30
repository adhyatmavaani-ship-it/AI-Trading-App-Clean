import 'package:flutter/material.dart';

import '../core/trading_palette.dart';

class TradingAppTheme {
  static ThemeData get darkTheme {
    final base = ThemeData.dark(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: TradingPalette.midnight,
      colorScheme: const ColorScheme.dark(
        primary: TradingPalette.violet,
        secondary: TradingPalette.electricBlue,
        surface: TradingPalette.panel,
        error: TradingPalette.neonRed,
        onPrimary: TradingPalette.textPrimary,
        onSecondary: TradingPalette.textPrimary,
        onSurface: TradingPalette.textPrimary,
        onError: TradingPalette.textPrimary,
      ),
      textTheme: base.textTheme.copyWith(
        headlineLarge: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w800,
          letterSpacing: -1.1,
        ),
        headlineMedium: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.7,
        ),
        headlineSmall: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w700,
          letterSpacing: -0.4,
        ),
        titleLarge: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w700,
        ),
        titleMedium: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w600,
        ),
        bodyLarge: const TextStyle(
          color: TradingPalette.textPrimary,
          height: 1.45,
        ),
        bodyMedium: const TextStyle(
          color: TradingPalette.textMuted,
          height: 1.45,
        ),
        bodySmall: const TextStyle(
          color: TradingPalette.textFaint,
          height: 1.35,
        ),
        labelLarge: const TextStyle(
          color: TradingPalette.textPrimary,
          fontWeight: FontWeight.w700,
        ),
        labelMedium: const TextStyle(
          color: TradingPalette.textMuted,
          fontWeight: FontWeight.w600,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        scrolledUnderElevation: 0,
        foregroundColor: TradingPalette.textPrimary,
      ),
      cardColor: Colors.transparent,
      dividerColor: TradingPalette.panelBorder,
      iconTheme: const IconThemeData(color: TradingPalette.textPrimary),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: TradingPalette.deepNavy.withOpacity(0.96),
        contentTextStyle: const TextStyle(color: TradingPalette.textPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: const BorderSide(color: TradingPalette.panelBorder),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: TradingPalette.panelSoft,
        labelStyle: const TextStyle(color: TradingPalette.textMuted),
        hintStyle: const TextStyle(color: TradingPalette.textFaint),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: TradingPalette.panelBorder),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: TradingPalette.panelBorder),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(18),
          borderSide: const BorderSide(color: TradingPalette.electricBlue),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          foregroundColor: TradingPalette.textPrimary,
          backgroundColor: TradingPalette.violet,
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: TradingPalette.textPrimary,
          side: const BorderSide(color: TradingPalette.panelBorder),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: TradingPalette.deepNavy.withOpacity(0.92),
        indicatorColor: TradingPalette.violet.withOpacity(0.18),
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(
            color: TradingPalette.textMuted,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

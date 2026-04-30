import 'package:flutter/material.dart';

class TradingPalette {
  static const Color midnight = Color(0xFF0B0F1A);
  static const Color deepNavy = Color(0xFF10172A);
  static const Color panel = Color(0xCC151C2E);
  static const Color panelBorder = Color(0xFF2B3655);
  static const Color panelSoft = Color(0xB3151C2E);
  static const Color textPrimary = Color(0xFFE6EAF2);
  static const Color textMuted = Color(0xFF94A3C3);
  static const Color textFaint = Color(0xFF667494);
  static const Color violet = Color(0xFF7C4DFF);
  static const Color electricBlue = Color(0xFF00E5FF);
  static const Color neonGreen = Color(0xFF00C853);
  static const Color neonRed = Color(0xFFFF3D00);
  static const Color amber = Color(0xFFFFB74D);
  static const Color glassHighlight = Color(0x33FFFFFF);
  static const Color overlay = Color(0x66101523);

  static const LinearGradient primaryGlow = LinearGradient(
    colors: <Color>[violet, electricBlue],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient profitGlow = LinearGradient(
    colors: <Color>[Color(0xFF00E676), neonGreen],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient lossGlow = LinearGradient(
    colors: <Color>[Color(0xFFFF7043), neonRed],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}

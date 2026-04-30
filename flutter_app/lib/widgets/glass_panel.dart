import 'dart:ui';

import 'package:flutter/material.dart';

import '../core/trading_palette.dart';

class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.radius = 20,
    this.glowColor,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;
  final Color? glowColor;

  @override
  Widget build(BuildContext context) {
    final resolvedGlow = glowColor ?? TradingPalette.violet;
    return DecoratedBox(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius + 2),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: resolvedGlow.withOpacity(0.12),
            blurRadius: 26,
            spreadRadius: -8,
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(radius),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
          child: Container(
            padding: padding,
            decoration: BoxDecoration(
              color: TradingPalette.panel,
              borderRadius: BorderRadius.circular(radius),
              border: Border.all(
                color: TradingPalette.glassHighlight.withOpacity(0.12),
              ),
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: <Color>[
                  TradingPalette.glassHighlight.withOpacity(0.08),
                  TradingPalette.panelSoft.withOpacity(0.88),
                ],
              ),
            ),
            child: child,
          ),
        ),
      ),
    );
  }
}

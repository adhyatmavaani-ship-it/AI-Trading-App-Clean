import 'package:flutter/material.dart';

import '../core/trading_palette.dart';

class GradientActionButton extends StatelessWidget {
  const GradientActionButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.icon,
    this.gradient = TradingPalette.primaryGlow,
    this.expanded = false,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final Gradient gradient;
  final bool expanded;

  @override
  Widget build(BuildContext context) {
    final button = DecoratedBox(
      decoration: BoxDecoration(
        gradient: onPressed == null
            ? const LinearGradient(
                colors: <Color>[Color(0xFF46506A), Color(0xFF2C3348)],
              )
            : gradient,
        borderRadius: BorderRadius.circular(18),
        boxShadow: onPressed == null
            ? const <BoxShadow>[]
            : <BoxShadow>[
                BoxShadow(
                  color: TradingPalette.violet.withOpacity(0.24),
                  blurRadius: 22,
                  spreadRadius: -10,
                ),
              ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(18),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              mainAxisSize:
                  expanded ? MainAxisSize.max : MainAxisSize.min,
              children: <Widget>[
                if (icon != null) ...<Widget>[
                  Icon(icon, color: TradingPalette.textPrimary, size: 18),
                  const SizedBox(width: 10),
                ],
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: TradingPalette.textPrimary,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
    return expanded ? SizedBox(width: double.infinity, child: button) : button;
  }
}

import 'package:flutter/material.dart';

import '../core/trading_palette.dart';

class MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData? icon;

  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 160),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: TradingPalette.panelBorder),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF141A35), Color(0xCC0B0F25)],
        ),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x2200FFA3),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              if (icon != null) ...<Widget>[
                Icon(icon, size: 18, color: TradingPalette.neonGreen),
                const SizedBox(width: 8),
              ],
              Expanded(
                child:
                    Text(label, style: Theme.of(context).textTheme.labelLarge),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(value, style: Theme.of(context).textTheme.headlineSmall),
        ],
      ),
    );
  }
}

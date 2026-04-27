import 'package:flutter/material.dart';

import '../models/signal.dart';

class SignalTile extends StatelessWidget {
  const SignalTile({
    super.key,
    required this.signal,
    this.onTap,
  });

  final SignalModel signal;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final accent = signal.isForcedPaperTrade
        ? const Color(0xFFFFB14A)
        : signal.degradedMode
        ? Colors.orangeAccent
        : signal.alphaScore >= 80
            ? const Color(0xFF4DE2B1)
            : const Color(0xFF7BC6FF);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      title: Row(
        children: <Widget>[
          Expanded(child: Text('${signal.symbol} - ${signal.strategy}')),
          if (signal.isForcedPaperTrade)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0xFF4A2E12),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: const Color(0xFFFFB14A)),
              ),
              child: const Text(
                'HIGH PRIORITY',
                style: TextStyle(
                  color: Color(0xFFFFD28A),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Text(signal.decisionReason),
          const SizedBox(height: 4),
          Text(
            '${signal.action}  |  Confidence ${(signal.confidence * 100).toStringAsFixed(1)}%'
            '${signal.rejectionReason != null ? '  |  ${signal.rejectionReason}' : ''}',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: <Widget>[
          Text(
            signal.alphaScore.toStringAsFixed(1),
            style: TextStyle(
              color: accent,
              fontWeight: FontWeight.bold,
            ),
          ),
          Text(
            signal.regime,
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

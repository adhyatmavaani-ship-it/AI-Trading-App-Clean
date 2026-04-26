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
    final accent = signal.degradedMode
        ? Colors.orangeAccent
        : signal.alphaScore >= 80
            ? const Color(0xFF4DE2B1)
            : const Color(0xFF7BC6FF);
    return ListTile(
      contentPadding: EdgeInsets.zero,
      onTap: onTap,
      title: Text('${signal.symbol} - ${signal.strategy}'),
      subtitle: Text(signal.decisionReason),
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

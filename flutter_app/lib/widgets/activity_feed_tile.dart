import 'package:flutter/material.dart';

import '../models/activity.dart';

class ActivityFeedTile extends StatelessWidget {
  const ActivityFeedTile({
    super.key,
    required this.activity,
  });

  final ActivityItemModel activity;

  Color _accentColor() {
    switch (activity.status) {
      case 'executed':
        return const Color(0xFF4DE2B1);
      case 'almost_trade':
        return const Color(0xFFFFD28A);
      case 'opportunity_found':
        return const Color(0xFF7BC6FF);
      default:
        return const Color(0xFF93A9BD);
    }
  }

  @override
  Widget build(BuildContext context) {
    final accent = _accentColor();
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Container(
        width: 10,
        height: 10,
        margin: const EdgeInsets.only(top: 8),
        decoration: BoxDecoration(
          color: accent,
          shape: BoxShape.circle,
        ),
      ),
      title: Text(activity.message),
      subtitle: Text(
        activity.intent ?? activity.reason ?? activity.botState,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: const Color(0xFF9CB3C8),
            ),
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: <Widget>[
          if (activity.symbol != null && activity.symbol!.isNotEmpty)
            Text(
              activity.symbol!,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: accent,
                  ),
            ),
          Text(
            '${activity.timestamp.hour.toString().padLeft(2, '0')}:${activity.timestamp.minute.toString().padLeft(2, '0')}',
            style: Theme.of(context).textTheme.labelSmall,
          ),
        ],
      ),
    );
  }
}

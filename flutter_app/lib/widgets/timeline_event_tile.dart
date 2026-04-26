import 'package:flutter/material.dart';

import '../models/trade_timeline.dart';

class TimelineEventTile extends StatelessWidget {
  const TimelineEventTile({
    super.key,
    required this.event,
    required this.isLast,
  });

  final TradeTimelineEventModel event;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Column(
          children: <Widget>[
            Container(
              width: 12,
              height: 12,
              decoration: const BoxDecoration(
                color: Color(0xFF67D5B5),
                shape: BoxShape.circle,
              ),
            ),
            if (!isLast)
              Container(
                width: 2,
                height: 60,
                color: const Color(0xFF29414B),
              ),
          ],
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(event.stage,
                    style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                Text(event.description),
                const SizedBox(height: 4),
                Text(
                  event.status,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

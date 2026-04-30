import 'package:flutter/material.dart';

import 'glass_panel.dart';
import 'status_badge.dart';

class SectionCard extends StatelessWidget {
  const SectionCard({
    super.key,
    required this.title,
    this.trailing,
    required this.child,
    this.subtitle,
    this.glowColor,
  });

  final String title;
  final Widget? trailing;
  final Widget child;
  final String? subtitle;
  final Color? glowColor;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: glowColor,
      radius: 20,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      title,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                    if (subtitle != null) ...<Widget>[
                      const SizedBox(height: 6),
                      Text(
                        subtitle!,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null) trailing! else const StatusBadge(label: 'LIVE'),
            ],
          ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

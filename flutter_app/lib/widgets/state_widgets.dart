import 'package:flutter/material.dart';

import '../core/backend_warmup_state.dart';
import '../core/error_mapper.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'gradient_action_button.dart';
import 'skeleton_block.dart';

class ShimmerBox extends StatelessWidget {
  const ShimmerBox({
    super.key,
    this.height = 120,
  });

  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: LinearGradient(
          colors: <Color>[
            Colors.white.withOpacity(0.05),
            Colors.white.withOpacity(0.08),
            Colors.white.withOpacity(0.05),
          ],
        ),
      ),
    );
  }
}

class LoadingState extends StatelessWidget {
  const LoadingState({super.key, this.label = 'Loading...'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<BackendWarmupState>(
      valueListenable: backendWarmupState,
      builder: (context, warmupState, _) {
        final resolvedLabel = switch (warmupState) {
          BackendWarmupState.waking => 'Server waking up... retrying',
          BackendWarmupState.connecting ||
          BackendWarmupState.idle =>
            'Connecting to trading engine...',
          BackendWarmupState.slow => 'Server waking up... retrying',
          BackendWarmupState.ready => label,
        };
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 360),
            child: GlassPanel(
              glowColor: TradingPalette.electricBlue,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  const SkeletonBlock(height: 12, width: 120, radius: 999),
                  const SizedBox(height: 16),
                  const ShimmerBox(height: 76),
                  const SizedBox(height: 12),
                  const SkeletonBlock(height: 14, width: 220),
                  const SizedBox(height: 16),
                  Text(
                    resolvedLabel,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class ErrorState extends StatelessWidget {
  const ErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<BackendWarmupState>(
      valueListenable: backendWarmupState,
      builder: (context, warmupState, _) {
        final waking = warmupState == BackendWarmupState.waking;
        final errorType = ErrorMapper.typeOf(message);
        final resolvedMessage = waking
            ? 'Server waking up... retrying'
            : switch (errorType) {
                AppErrorType.auth => 'Authentication Required',
                AppErrorType.server => 'Server Issue Detected',
                AppErrorType.timeout => 'Request Timed Out',
                AppErrorType.network => 'Connection Issue Detected',
                AppErrorType.unknown => 'Something Went Wrong',
              };
        final resolvedIcon = waking
            ? Icons.hourglass_top_rounded
            : ErrorMapper.iconFor(message);
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: GlassPanel(
              glowColor: TradingPalette.neonRed,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    resolvedIcon,
                    size: 42,
                    color: TradingPalette.neonRed,
                  ),
                  const SizedBox(height: 14),
                  Text(
                    resolvedMessage,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  if (!waking && message.trim().isNotEmpty) ...<Widget>[
                    const SizedBox(height: 10),
                    Text(
                      message,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  if (onRetry != null) ...<Widget>[
                    const SizedBox(height: 18),
                    GradientActionButton(
                      label: errorType == AppErrorType.auth
                          ? 'Review Credentials'
                          : 'Retry Connection',
                      icon: Icons.refresh_rounded,
                      onPressed: onRetry,
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.title,
    required this.subtitle,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: GlassPanel(
          glowColor: TradingPalette.violet,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              const Icon(
                Icons.grid_view_rounded,
                size: 42,
                color: TradingPalette.violet,
              ),
              const SizedBox(height: 14),
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              Text(subtitle, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}

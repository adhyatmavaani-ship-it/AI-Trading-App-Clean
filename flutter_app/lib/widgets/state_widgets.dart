import 'package:flutter/material.dart';

import '../core/backend_warmup_state.dart';

class LoadingState extends StatelessWidget {
  const LoadingState({super.key, this.label = 'Loading...'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          const CircularProgressIndicator(),
          const SizedBox(height: 12),
          Text(label),
        ],
      ),
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
        final waking = warmupState == BackendWarmupState.waking &&
            _looksLikeConnectivityMessage(message);
        final resolvedMessage = waking
            ? 'Waking up AI Engine... \nThe backend is resuming from cold start. Please wait a few seconds.'
            : message;
        return Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  waking ? Icons.hourglass_top_rounded : Icons.error_outline,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(resolvedMessage, textAlign: TextAlign.center),
                if (onRetry != null) ...<Widget>[
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: onRetry,
                    child: Text(waking ? 'Check Again' : 'Retry'),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  bool _looksLikeConnectivityMessage(String value) {
    final normalized = value.toLowerCase();
    return normalized.contains('timed out') ||
        normalized.contains('unable to reach') ||
        normalized.contains('connection') ||
        normalized.contains('cold start') ||
        normalized.contains('waking up ai engine');
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
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(Icons.inbox_outlined, size: 40),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(subtitle, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

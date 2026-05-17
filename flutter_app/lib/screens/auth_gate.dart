import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/backend_warmup_state.dart';
import '../core/trading_palette.dart';
import '../features/auth/providers/auth_provider.dart';
import 'app_shell.dart';

class AuthGate extends ConsumerWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    if (auth.isLoading) {
      return Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: <Color>[
                TradingPalette.midnight,
                Color(0xFF0F1324),
                TradingPalette.midnight,
              ],
            ),
          ),
          child: SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: ValueListenableBuilder<BackendWarmupState>(
                  valueListenable: backendWarmupState,
                  builder: (context, state, _) {
                    return Column(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        const CircularProgressIndicator(),
                        const SizedBox(height: 18),
                        Text(
                          'Preparing Production Session',
                          style: Theme.of(context)
                              .textTheme
                              .headlineSmall
                              ?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          _warmupMessage(state),
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ),
      );
    }
    return const AppShell();
  }
}

String _warmupMessage(BackendWarmupState state) {
  return switch (state) {
    BackendWarmupState.idle =>
      'Starting the embedded production authentication flow.',
    BackendWarmupState.connecting =>
      'Connecting to the VPS backend and restoring realtime state.',
    BackendWarmupState.waking =>
      'Backend is waking up. The app will continue automatically.',
    BackendWarmupState.retrying =>
      'Retrying the production backend after a transient network failure.',
    BackendWarmupState.slow =>
      'Backend is slow right now, but the app will still open with retry support.',
    BackendWarmupState.ready => 'Production backend is ready.',
  };
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth_credentials_store.dart';
import '../core/constants.dart';
import '../core/trading_palette.dart';
import '../features/auth/providers/auth_provider.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authControllerProvider);
    final theme = Theme.of(context);

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
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 460),
                child: GlassPanel(
                  glowColor: TradingPalette.violet,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Text(
                        'Production Trading Access',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'This app uses the embedded VPS production X-API-Key for every REST and WebSocket request. Local bearer tokens and saved session overrides are ignored.',
                        style: theme.textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 22),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: TradingPalette.overlay,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: TradingPalette.panelBorder),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            const Text(
                              'Production auth source',
                              style: TextStyle(fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Header: X-API-Key present\nUser context: ${AppConstants.requiredUserId}\nMode: required_api_key',
                              style: theme.textTheme.bodySmall,
                            ),
                          ],
                        ),
                      ),
                      if (auth.errorMessage != null &&
                          auth.errorMessage!.trim().isNotEmpty) ...<Widget>[
                        const SizedBox(height: 16),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: TradingPalette.neonRed.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(
                              color: TradingPalette.neonRed.withOpacity(0.45),
                            ),
                          ),
                          child: Text(
                            auth.errorMessage!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: TradingPalette.textPrimary,
                            ),
                          ),
                        ),
                      ],
                      const SizedBox(height: 20),
                      GradientActionButton(
                        label: auth.isSubmitting
                            ? 'Verifying production auth...'
                            : 'Continue With Production Auth',
                        icon: Icons.verified_user_rounded,
                        expanded: true,
                        onPressed: auth.isSubmitting
                            ? null
                            : () => ref
                                .read(authControllerProvider.notifier)
                                .signIn(
                                  credential: AppConstants.requiredApiKey,
                                  scheme: AuthScheme.apiKey,
                                ),
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Use Settings if you want to clear stale local auth cache and re-run production diagnostics.',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

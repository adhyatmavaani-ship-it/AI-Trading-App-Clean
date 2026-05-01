import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth_credentials_store.dart';
import '../core/trading_palette.dart';
import '../features/auth/providers/auth_provider.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  late final TextEditingController _credentialController;
  AuthScheme _authScheme = AuthScheme.apiKey;

  @override
  void initState() {
    super.initState();
    _credentialController = TextEditingController();
  }

  @override
  void dispose() {
    _credentialController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                        'Secure Trading Access',
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 10),
                      Text(
                        'Enter the backend credential configured for your trading account. The app supports both X-API-Key and bearer token flows.',
                        style: theme.textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 22),
                      TextField(
                        controller: _credentialController,
                        obscureText: true,
                        enabled: !auth.isSubmitting,
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _submit(),
                        decoration: const InputDecoration(
                          labelText: 'API key or bearer token',
                          hintText: 'Paste your trading credential',
                        ),
                      ),
                      const SizedBox(height: 14),
                      DropdownButtonFormField<AuthScheme>(
                        value: _authScheme,
                        decoration: const InputDecoration(
                          labelText: 'Authentication scheme',
                        ),
                        items: const <DropdownMenuItem<AuthScheme>>[
                          DropdownMenuItem<AuthScheme>(
                            value: AuthScheme.apiKey,
                            child: Text('X-API-Key'),
                          ),
                          DropdownMenuItem<AuthScheme>(
                            value: AuthScheme.bearer,
                            child: Text('Authorization Bearer'),
                          ),
                        ],
                        onChanged: auth.isSubmitting
                            ? null
                            : (value) {
                                if (value == null) {
                                  return;
                                }
                                setState(() {
                                  _authScheme = value;
                                });
                              },
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
                            ? 'Verifying credential...'
                            : 'Unlock Trading Workspace',
                        icon: Icons.lock_open_rounded,
                        expanded: true,
                        onPressed: auth.isSubmitting ? null : _submit,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        'Tip: if your backend is waking up on Render, the first verification can take a little longer.',
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

  Future<void> _submit() async {
    final success = await ref.read(authControllerProvider.notifier).signIn(
          credential: _credentialController.text,
          scheme: _authScheme,
        );
    if (success) {
      _credentialController.clear();
    }
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth_credentials_store.dart';
import '../features/settings/providers/settings_provider.dart';
import '../widgets/section_card.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _apiKeyController;
  AuthScheme _authScheme = AuthScheme.apiKey;

  @override
  void initState() {
    super.initState();
    _apiKeyController = TextEditingController();
  }

  @override
  void dispose() {
    _apiKeyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(appSettingsProvider);
    final controller = ref.read(appSettingsProvider.notifier);

    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        SectionCard(
          title: 'Risk Controls',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'Risk appetite ${(settings.riskSlider * 100).toStringAsFixed(0)}%',
              ),
              Slider(
                value: settings.riskSlider,
                min: 0.2,
                max: 1.0,
                divisions: 8,
                onChanged: controller.updateRisk,
              ),
              const Text(
                'UI only for now. This control can later bind to backend risk preferences.',
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        SectionCard(
          title: 'Backend Authentication',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              TextField(
                controller: _apiKeyController,
                obscureText: true,
                enableSuggestions: false,
                autocorrect: false,
                decoration: InputDecoration(
                  labelText: 'API key or bearer token',
                  helperText: settings.hasStoredApiKey
                      ? 'A backend credential is already stored securely.'
                      : 'Stored in secure storage and attached automatically.',
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<AuthScheme>(
                // ignore: deprecated_member_use
                value: _authScheme,
                decoration: const InputDecoration(labelText: 'Header type'),
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
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _authScheme = value;
                  });
                },
              ),
              const SizedBox(height: 12),
              Row(
                children: <Widget>[
                  FilledButton(
                    onPressed: () async {
                      final messenger = ScaffoldMessenger.of(context);
                      await controller.saveApiKey(
                        _apiKeyController.text,
                        scheme: _authScheme,
                      );
                      if (!mounted) {
                        return;
                      }
                      _apiKeyController.clear();
                      messenger.showSnackBar(
                        const SnackBar(
                          content: Text('Credential saved securely'),
                        ),
                      );
                    },
                    child: const Text('Save'),
                  ),
                  const SizedBox(width: 12),
                  TextButton(
                    onPressed: settings.hasStoredApiKey
                        ? () async {
                            final messenger = ScaffoldMessenger.of(context);
                            await controller.clearApiKey();
                            if (!mounted) {
                              return;
                            }
                            messenger.showSnackBar(
                              const SnackBar(
                                content: Text('Stored credential removed'),
                              ),
                            );
                          }
                        : null,
                    child: const Text('Clear'),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        SectionCard(
          title: 'Runtime Preferences',
          child: Column(
            children: <Widget>[
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Autoplay live signals'),
                subtitle: const Text(
                  'Follow incoming websocket updates automatically.',
                ),
                value: settings.autoplayEnabled,
                onChanged: controller.toggleAutoplay,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Push notifications'),
                subtitle: const Text(
                  'Enable mobile alerts for major signal changes.',
                ),
                value: settings.notificationsEnabled,
                onChanged: controller.toggleNotifications,
              ),
            ],
          ),
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth_credentials_store.dart';
import '../core/constants.dart';
import '../core/error_mapper.dart';
import '../core/trading_palette.dart';
import '../features/auth/providers/auth_provider.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../providers/app_providers.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/section_card.dart';
import '../widgets/status_badge.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _apiKeyController;
  AuthScheme _authScheme = AuthScheme.apiKey;
  bool _connectivityBusy = false;
  Map<String, dynamic>? _connectivitySnapshot;
  String? _connectivityError;

  @override
  void initState() {
    super.initState();
    _apiKeyController = TextEditingController();
    Future<void>.microtask(() {
      final userId = ref.read(activeUserIdProvider);
      ref.read(appSettingsProvider.notifier).loadTradingControls(userId);
    });
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
    final userId = ref.watch(activeUserIdProvider);
    return RefreshIndicator(
      onRefresh: () async {
        await controller.loadTradingControls(userId);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
        children: <Widget>[
          SectionCard(
            title: 'Backend Credentials',
            subtitle:
                'Securely store the Render API key used by protected backend routes.',
            trailing: StatusBadge(
              label: settings.hasStoredApiKey ? 'SAVED' : 'MISSING',
              color: settings.hasStoredApiKey
                  ? TradingPalette.neonGreen
                  : TradingPalette.amber,
            ),
            glowColor: TradingPalette.violet,
            child: Column(
              children: <Widget>[
                TextField(
                  controller: _apiKeyController,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'API key or bearer token',
                    hintText: 'Paste Render credential here',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<AuthScheme>(
                  value: _authScheme,
                  decoration: const InputDecoration(labelText: 'Auth scheme'),
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
                    setState(() => _authScheme = value);
                  },
                ),
                const SizedBox(height: 14),
                Row(
                  children: <Widget>[
                    Expanded(
                      child: GradientActionButton(
                        label: 'Save Credential',
                        icon: Icons.lock_rounded,
                        onPressed: () async {
                          await controller.saveApiKey(
                            _apiKeyController.text,
                            scheme: _authScheme,
                          );
                          await ref
                              .read(authControllerProvider.notifier)
                              .refresh();
                          if (!context.mounted) {
                            return;
                          }
                          _apiKeyController.clear();
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Credential saved securely'),
                            ),
                          );
                        },
                        expanded: true,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: settings.hasStoredApiKey
                            ? () async {
                                await controller.clearApiKey();
                                await ref
                                    .read(authControllerProvider.notifier)
                                    .signOut();
                                if (!context.mounted) {
                                  return;
                                }
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Stored credential removed'),
                                  ),
                                );
                              }
                            : null,
                        icon: const Icon(Icons.delete_outline_rounded),
                        label: const Text('Clear'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          SectionCard(
            title: 'E2E Diagnostics',
            subtitle:
                'Run a phone-to-Render connectivity test covering REST health, authenticated root, websocket, and latency.',
            trailing: const StatusBadge(label: 'CHECK'),
            glowColor: TradingPalette.electricBlue,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _DiagnosticRow(
                  label: 'REST base URL',
                  value: ref.read(apiClientProvider).baseUrl,
                ),
                const SizedBox(height: 8),
                _DiagnosticRow(
                  label: 'WebSocket URL',
                  value: ref.read(webSocketServiceProvider).baseUrl,
                ),
                const SizedBox(height: 8),
                _DiagnosticRow(
                  label: 'Polling interval',
                  value: '${AppConstants.pollingInterval.inSeconds}s',
                ),
                const SizedBox(height: 16),
                GradientActionButton(
                  label: _connectivityBusy
                      ? 'Running diagnostics...'
                      : 'Run E2E Connectivity Check',
                  icon: Icons.wifi_tethering_rounded,
                  onPressed: _connectivityBusy
                      ? null
                      : () => _runConnectivityCheck(context),
                  expanded: true,
                ),
                if (_connectivityBusy) ...<Widget>[
                  const SizedBox(height: 14),
                  const LinearProgressIndicator(),
                ],
                if (_connectivityError != null) ...<Widget>[
                  const SizedBox(height: 14),
                  GlassPanel(
                    glowColor: TradingPalette.neonRed,
                    child: Text(
                      _connectivityError!,
                      style: const TextStyle(color: TradingPalette.textPrimary),
                    ),
                  ),
                ],
                if (_connectivitySnapshot != null) ...<Widget>[
                  const SizedBox(height: 14),
                  _ConnectivitySnapshotCard(snapshot: _connectivitySnapshot!),
                ],
              ],
            ),
          ),
          const SizedBox(height: 18),
          SectionCard(
            title: 'Runtime Controls',
            subtitle:
                'Client-side experience settings plus backend toggles already exposed by the app.',
            trailing: const StatusBadge(label: 'RUNTIME'),
            glowColor: TradingPalette.violet,
            child: Column(
              children: <Widget>[
                SwitchListTile(
                  value: settings.autoplayEnabled,
                  onChanged: controller.toggleAutoplay,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Autoplay live signals'),
                  subtitle: const Text(
                    'Automatically keep the dashboard synchronized with websocket signals.',
                  ),
                ),
                SwitchListTile(
                  value: settings.notificationsEnabled,
                  onChanged: controller.toggleNotifications,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Push notification preference'),
                  subtitle: const Text(
                    'Local app preference for surfacing major market changes.',
                  ),
                ),
                SwitchListTile(
                  value: settings.engineEnabled,
                  onChanged: (value) async {
                    await controller.saveEngineState(userId, enabled: value);
                  },
                  contentPadding: EdgeInsets.zero,
                  title: const Text('AI trading engine'),
                  subtitle: const Text(
                    'Backend control that enables or pauses new AI trade execution.',
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _runConnectivityCheck(BuildContext context) async {
    final apiClient = ref.read(apiClientProvider);
    final webSocketService = ref.read(webSocketServiceProvider);
    final startedAt = DateTime.now();
    setState(() {
      _connectivityBusy = true;
      _connectivityError = null;
    });
    try {
      final health = await apiClient.getHealthStatus();
      final root = await apiClient.getRootStatus();
      final websocket = await webSocketService.probeSignals();
      if (!context.mounted) {
        return;
      }
      setState(() {
        _connectivitySnapshot = <String, dynamic>{
          'rest_health': health['status'] == 'ok',
          'auth_status': root['status'] == 'running',
          'websocket_status': websocket['type'] == 'pong',
          'latency_ms': DateTime.now().difference(startedAt).inMilliseconds,
          'backend_version': health['version'],
          'environment': root['environment'],
        };
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('E2E connectivity check passed')),
      );
    } catch (error) {
      if (!context.mounted) {
        return;
      }
      final message = ErrorMapper.map(
        error,
        fallback: 'Connectivity check failed. Please try again.',
      );
      setState(() {
        _connectivityError = message;
        _connectivitySnapshot = null;
      });
      showSafeError(
        context,
        error,
        fallback: 'Connectivity check failed. Please try again.',
        onRetry: () {
          _runConnectivityCheck(context);
        },
      );
    } finally {
      if (mounted) {
        setState(() => _connectivityBusy = false);
      }
    }
  }
}

class _ConnectivitySnapshotCard extends StatelessWidget {
  const _ConnectivitySnapshotCard({required this.snapshot});

  final Map<String, dynamic> snapshot;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.neonGreen,
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        children: <Widget>[
          _DiagnosticStatusTile(
            label: 'REST health',
            ok: snapshot['rest_health'] == true,
          ),
          _DiagnosticStatusTile(
            label: 'Auth status',
            ok: snapshot['auth_status'] == true,
          ),
          _DiagnosticStatusTile(
            label: 'WebSocket status',
            ok: snapshot['websocket_status'] == true,
          ),
          _DiagnosticTextTile(
            label: 'Latency',
            value: '${snapshot['latency_ms']} ms',
          ),
          _DiagnosticTextTile(
            label: 'Version',
            value: (snapshot['backend_version'] ?? '-').toString(),
          ),
          _DiagnosticTextTile(
            label: 'Environment',
            value: (snapshot['environment'] ?? '-').toString(),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticStatusTile extends StatelessWidget {
  const _DiagnosticStatusTile({
    required this.label,
    required this.ok,
  });

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            ok ? 'OK' : 'FAILED',
            style: TextStyle(
              color: ok ? TradingPalette.neonGreen : TradingPalette.neonRed,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticTextTile extends StatelessWidget {
  const _DiagnosticTextTile({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticRow extends StatelessWidget {
  const _DiagnosticRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          width: 116,
          child: Text(label, style: Theme.of(context).textTheme.bodySmall),
        ),
        Expanded(
          child: Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: TradingPalette.textPrimary,
                ),
          ),
        ),
      ],
    );
  }
}

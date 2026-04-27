import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/auth_credentials_store.dart';
import '../features/monitoring/providers/diagnostic_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  late final TextEditingController _apiKeyController;
  AuthScheme _authScheme = AuthScheme.apiKey;
  String _debugSymbol = 'BTCUSDT';
  bool _debugBusy = false;
  Map<String, dynamic>? _lastDebugResult;

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
    final diagnosticsAsync = ref.watch(exchangeDiagnosticsProvider);
    final userId = ref.watch(activeUserIdProvider);
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));

    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        SectionCard(
          title: 'System Health',
          child: diagnosticsAsync.when(
            data: (diagnostics) => Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    Chip(
                      label: Text(
                        'Mode ${diagnostics.resolvedMode.toUpperCase()}',
                      ),
                      backgroundColor: diagnostics.usingMockData
                          ? const Color(0xFF4A2A14)
                          : const Color(0xFF173A2F),
                    ),
                    Chip(
                      label: Text(
                        diagnostics.forceExecutionOverrideEnabled
                            ? 'Force Paper ON'
                            : 'Force Paper OFF',
                      ),
                      backgroundColor: diagnostics.forceExecutionOverrideEnabled
                          ? const Color(0xFF4A2A14)
                          : const Color(0xFF153540),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ...diagnostics.exchangeStatuses.map(
                  (exchange) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      Icons.circle,
                      size: 12,
                      color: exchange.isHealthy
                          ? const Color(0xFF4DE2B1)
                          : const Color(0xFFFF8E72),
                    ),
                    title: Text(exchange.name.toUpperCase()),
                    subtitle: Text(
                      exchange.lastError?.isNotEmpty == true
                          ? exchange.lastError!
                          : 'Connected successfully',
                    ),
                    trailing: Text(exchange.status.toUpperCase()),
                  ),
                ),
              ],
            ),
            loading: () => const LoadingState(label: 'Checking exchange health'),
            error: (error, _) => ErrorState(message: error.toString()),
          ),
        ),
        const SizedBox(height: 20),
        SectionCard(
          title: 'Trading Controls',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('AI Trading Engine'),
                subtitle: Text(
                  settings.engineEnabled
                      ? 'Engine is active. The system can scan and execute within your risk rules.'
                      : 'Engine is paused by user control. No new trades should execute.',
                ),
                value: settings.engineEnabled,
                onChanged: (value) async {
                  final messenger = ScaffoldMessenger.of(context);
                  await controller.saveEngineState(userId, enabled: value);
                  if (!mounted) {
                    return;
                  }
                  messenger.showSnackBar(
                    SnackBar(
                      content: Text(
                        value ? 'Trading engine enabled' : 'Trading engine paused',
                      ),
                    ),
                  );
                },
              ),
              const SizedBox(height: 16),
              Text(
                'Risk profile',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 8),
              SegmentedButton<String>(
                segments: const <ButtonSegment<String>>[
                  ButtonSegment<String>(value: 'low', label: Text('Low')),
                  ButtonSegment<String>(value: 'medium', label: Text('Medium')),
                  ButtonSegment<String>(value: 'high', label: Text('High')),
                ],
                selected: <String>{settings.riskLevel},
                onSelectionChanged: (selection) async {
                  final messenger = ScaffoldMessenger.of(context);
                  final userId = ref.read(activeUserIdProvider);
                  final selected = selection.first;
                  await controller.saveRiskLevel(userId, selected);
                  if (!mounted) {
                    return;
                  }
                  messenger.showSnackBar(
                    SnackBar(
                      content: Text(
                          'Risk profile updated to ${selected.toUpperCase()}'),
                    ),
                  );
                },
              ),
              const SizedBox(height: 12),
              Text(
                settings.riskLevel == 'low'
                    ? 'Sniper mode: 0.85 confidence floor, tight loss control, BTC/ETH focus.'
                    : settings.riskLevel == 'high'
                        ? 'Aggressive mode: 0.60 confidence floor, higher drawdown allowance, wider asset set.'
                        : 'Balanced mode: 0.70 confidence floor with standard trend-following rules.',
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        SectionCard(
          title: 'Admin Debug',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'God mode controls for deterministic demos and exit validation.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _debugSymbol,
                decoration: const InputDecoration(labelText: 'Debug symbol'),
                items: const <DropdownMenuItem<String>>[
                  DropdownMenuItem<String>(
                    value: 'BTCUSDT',
                    child: Text('BTCUSDT'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'ETHUSDT',
                    child: Text('ETHUSDT'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'SOLUSDT',
                    child: Text('SOLUSDT'),
                  ),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _debugSymbol = value;
                  });
                },
              ),
              const SizedBox(height: 12),
              activeTradesAsync.when(
                data: (trades) => Text(
                  'Tracked active positions: ${trades.length} | current risk tier: ${settings.riskLevel.toUpperCase()}',
                ),
                loading: () => const Text('Checking active positions...'),
                error: (error, _) => Text('Active position check failed: $error'),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: <Widget>[
                  FilledButton.icon(
                    onPressed: _debugBusy
                        ? null
                        : () => _runMockMove(
                              context,
                              controller,
                              userId: userId,
                              symbol: _debugSymbol,
                              change: -0.02,
                            ),
                    icon: const Icon(Icons.trending_down_rounded),
                    label: const Text('-2% crash'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _debugBusy
                        ? null
                        : () => _runMockMove(
                              context,
                              controller,
                              userId: userId,
                              symbol: _debugSymbol,
                              change: 0.02,
                            ),
                    icon: const Icon(Icons.trending_up_rounded),
                    label: const Text('+2% spike'),
                  ),
                ],
              ),
              if (_debugBusy) ...<Widget>[
                const SizedBox(height: 16),
                const LinearProgressIndicator(),
              ],
              if (_lastDebugResult != null) ...<Widget>[
                const SizedBox(height: 16),
                Builder(
                  builder: (context) {
                    final closedTradeIds = ((_lastDebugResult!['closed_trade_ids']
                                    as List<dynamic>?) ??
                                const [])
                            .map((item) => item.toString())
                            .where((item) => item.trim().isNotEmpty)
                            .toList();
                    final closedTradeLabel = closedTradeIds.isEmpty
                        ? '-'
                        : closedTradeIds.join(', ');
                    return Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: const Color(0xFF10242C),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: const Color(0xFF1B3741)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Text(
                            'Last debug result',
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          const SizedBox(height: 8),
                          Text(
                            '${_lastDebugResult!['symbol']} | active before ${_lastDebugResult!['before_active_count']} -> after ${_lastDebugResult!['after_active_count']}',
                          ),
                          const SizedBox(height: 4),
                          Text('Closed trades: $closedTradeLabel'),
                          const SizedBox(height: 4),
                          Text(
                            'Monitor ran: ${_lastDebugResult!['monitor_ran'] == true ? 'yes' : 'no'}',
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
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

  Future<void> _runMockMove(
    BuildContext context,
    AppSettingsNotifier controller, {
    required String userId,
    required String symbol,
    required double change,
  }) async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() {
      _debugBusy = true;
    });
    try {
      final result = await controller.triggerMockPriceMove(
        symbol: symbol,
        change: change,
        userId: userId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _lastDebugResult = result;
      });
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            '${symbol.toUpperCase()} debug move sent. Closed ${((result['closed_trade_ids'] as List<dynamic>?) ?? const []).length} trade(s).',
          ),
        ),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      messenger.showSnackBar(
        SnackBar(
          content: Text('Debug move failed: $error'),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _debugBusy = false;
        });
      }
    }
  }
}

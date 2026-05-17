import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/backend_warmup_state.dart';
import '../core/constants.dart';
import '../core/error_mapper.dart';
import '../core/platformization_engine.dart';
import '../core/production_infrastructure_engine.dart';
import '../core/retention_engine.dart';
import '../core/trading_palette.dart';
import '../features/auth/providers/auth_provider.dart';
import '../features/monitoring/providers/diagnostic_providers.dart';
import '../features/monitoring/providers/monitoring_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/retention/providers/retention_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../features/signals/providers/signal_providers.dart';
import '../core/websocket_service.dart';
import '../providers/app_providers.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/platformization_widgets.dart';
import '../widgets/production_infrastructure_widgets.dart';
import '../widgets/retention_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/status_badge.dart';
import 'analytics_screen.dart';
import 'pulse_screen.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _connectivityBusy = false;
  bool _quantMode = false;
  PlatformExperienceMode _experienceMode = PlatformExperienceMode.pro;
  ReleaseChannel _releaseChannel = ReleaseChannel.stable;
  Map<String, dynamic>? _connectivitySnapshot;
  String? _connectivityError;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(() {
      final userId = ref.read(activeUserIdProvider);
      ref.read(appSettingsProvider.notifier).loadTradingControls(userId);
    });
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(appSettingsProvider);
    final controller = ref.read(appSettingsProvider.notifier);
    final userId = ref.watch(activeUserIdProvider);
    final diagnosticsAsync = ref.watch(productionDiagnosticsProvider);
    final infrastructureAsync = ref.watch(infrastructureSnapshotProvider);
    final retention = ref.watch(retentionSnapshotProvider);
    final tier = ref.watch(selectedPlanTierProvider);
    final signalFeed = ref.watch(signalFeedProvider);
    final socketService = ref.watch(webSocketServiceProvider);
    const infrastructureEngine = ProductionInfrastructureEngine();
    const platformEngine = PlatformizationEngine();
    final platform = platformEngine.evaluate(
      tier: tier,
      mode: _experienceMode,
      channel: _releaseChannel,
      signals: signalFeed.items,
    );
    return RefreshIndicator(
      onRefresh: () async {
        await controller.loadTradingControls(userId);
        ref.invalidate(productionDiagnosticsProvider);
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
        children: <Widget>[
          SectionCard(
            title: 'AI Trading Experience',
            subtitle:
                'Choose how active the assistant should be. Backend risk checks remain final for every real order.',
            trailing: StatusBadge(
              label: settings.riskLevel.toUpperCase(),
              color: TradingPalette.violet,
            ),
            glowColor: TradingPalette.violet,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SegmentedButton<String>(
                  segments: const <ButtonSegment<String>>[
                    ButtonSegment<String>(
                      value: 'low',
                      icon: Icon(Icons.shield_rounded),
                      label: Text('Safe'),
                    ),
                    ButtonSegment<String>(
                      value: 'medium',
                      icon: Icon(Icons.auto_awesome_rounded),
                      label: Text('Smart'),
                    ),
                    ButtonSegment<String>(
                      value: 'high',
                      icon: Icon(Icons.bolt_rounded),
                      label: Text('Aggressive'),
                    ),
                  ],
                  selected: <String>{settings.riskLevel},
                  onSelectionChanged: (selection) async {
                    await controller.saveRiskLevel(userId, selection.first);
                  },
                ),
                const SizedBox(height: 16),
                SwitchListTile(
                  value: settings.engineEnabled,
                  onChanged: (value) async {
                    await controller.saveEngineState(userId, enabled: value);
                  },
                  contentPadding: EdgeInsets.zero,
                  title: const Text('AI auto-trading engine'),
                  subtitle: const Text(
                    'Controls paper/semi-auto/full-auto readiness while preserving backend risk validation.',
                  ),
                ),
                const Divider(height: 26),
                SwitchListTile(
                  value: _quantMode,
                  onChanged: (value) {
                    setState(() => _quantMode = value);
                  },
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Quant / Dev diagnostics'),
                  subtitle: const Text(
                    'Show infrastructure, auth, websocket, Redis, and replay diagnostics.',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          FeatureGatePanel(gate: retention.featureGate),
          const SizedBox(height: 18),
          SectionCard(
            title: 'Plan Preview',
            subtitle:
                'Feature gating architecture is ready. Payment gateway is intentionally not wired yet.',
            trailing: StatusBadge(label: tier.name.toUpperCase()),
            glowColor: TradingPalette.amber,
            child: SegmentedButton<PlanTier>(
              segments: const <ButtonSegment<PlanTier>>[
                ButtonSegment<PlanTier>(
                  value: PlanTier.free,
                  icon: Icon(Icons.public_rounded),
                  label: Text('Free'),
                ),
                ButtonSegment<PlanTier>(
                  value: PlanTier.pro,
                  icon: Icon(Icons.workspace_premium_rounded),
                  label: Text('Pro'),
                ),
                ButtonSegment<PlanTier>(
                  value: PlanTier.vip,
                  icon: Icon(Icons.diamond_rounded),
                  label: Text('VIP'),
                ),
              ],
              selected: <PlanTier>{tier},
              onSelectionChanged: (selection) {
                ref.read(selectedPlanTierProvider.notifier).state =
                    selection.first;
              },
            ),
          ),
          const SizedBox(height: 18),
          SectionCard(
            title: 'User Experience Mode',
            subtitle:
                'Simple keeps users focused, Pro adds probabilities, Institutional exposes research and governance.',
            trailing: StatusBadge(label: _experienceMode.name.toUpperCase()),
            glowColor: TradingPalette.electricBlue,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SegmentedButton<PlatformExperienceMode>(
                  segments: const <ButtonSegment<PlatformExperienceMode>>[
                    ButtonSegment<PlatformExperienceMode>(
                      value: PlatformExperienceMode.simple,
                      icon: Icon(Icons.mobile_friendly_rounded),
                      label: Text('Simple'),
                    ),
                    ButtonSegment<PlatformExperienceMode>(
                      value: PlatformExperienceMode.pro,
                      icon: Icon(Icons.analytics_rounded),
                      label: Text('Pro'),
                    ),
                    ButtonSegment<PlatformExperienceMode>(
                      value: PlatformExperienceMode.institutional,
                      icon: Icon(Icons.account_tree_rounded),
                      label: Text('Institutional'),
                    ),
                  ],
                  selected: <PlatformExperienceMode>{_experienceMode},
                  onSelectionChanged: (selection) {
                    setState(() => _experienceMode = selection.first);
                  },
                ),
                const SizedBox(height: 16),
                ExperienceModePanel(read: platform.experienceMode),
              ],
            ),
          ),
          const SizedBox(height: 18),
          EntitlementArchitecturePanel(read: platform.entitlements),
          const SizedBox(height: 18),
          ExchangeConnectivityPanel(read: platform.exchangeConnectivity),
          const SizedBox(height: 18),
          OfflineDegradedPanel(read: platform.offlineDegraded),
          const SizedBox(height: 18),
          if (_quantMode) ...<Widget>[
            SectionCard(
              title: 'Release Channel',
              subtitle:
                  'Controls staged platform surfaces only. Execution remains backend-approved.',
              trailing: StatusBadge(label: _releaseChannel.name.toUpperCase()),
              glowColor: TradingPalette.amber,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  SegmentedButton<ReleaseChannel>(
                    segments: const <ButtonSegment<ReleaseChannel>>[
                      ButtonSegment<ReleaseChannel>(
                        value: ReleaseChannel.stable,
                        icon: Icon(Icons.verified_rounded),
                        label: Text('Stable'),
                      ),
                      ButtonSegment<ReleaseChannel>(
                        value: ReleaseChannel.beta,
                        icon: Icon(Icons.science_rounded),
                        label: Text('Beta'),
                      ),
                      ButtonSegment<ReleaseChannel>(
                        value: ReleaseChannel.experimental,
                        icon: Icon(Icons.biotech_rounded),
                        label: Text('Experimental'),
                      ),
                    ],
                    selected: <ReleaseChannel>{_releaseChannel},
                    onSelectionChanged: (selection) {
                      setState(() => _releaseChannel = selection.first);
                    },
                  ),
                  const SizedBox(height: 16),
                  ReleaseChannelPanel(read: platform.releaseChannel),
                ],
              ),
            ),
            const SizedBox(height: 18),
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 820;
                final left = CloudDeploymentFoundationPanel(
                  read: platform.cloudDeployment,
                );
                final right = ProductionOpsPanel(read: platform.productionOps);
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(child: left),
                      const SizedBox(width: 16),
                      Expanded(child: right),
                    ],
                  );
                }
                return Column(
                  children: <Widget>[
                    left,
                    const SizedBox(height: 16),
                    right,
                  ],
                );
              },
            ),
            const SizedBox(height: 18),
            LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 820;
                final left = MobilePerformancePanel(
                  read: platform.mobilePerformance,
                );
                final right = PlatformAnalyticsPanel(
                  read: platform.platformAnalytics,
                );
                if (wide) {
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Expanded(child: left),
                      const SizedBox(width: 16),
                      Expanded(child: right),
                    ],
                  );
                }
                return Column(
                  children: <Widget>[
                    left,
                    const SizedBox(height: 16),
                    right,
                  ],
                );
              },
            ),
            const SizedBox(height: 18),
            SectionCard(
              title: 'Production Auth',
              subtitle:
                  'This build is locked to the embedded production X-API-Key. Local bearer tokens, saved sessions, and manual overrides are ignored.',
              trailing: const StatusBadge(
                label: 'LOCKED',
                color: TradingPalette.neonGreen,
              ),
              glowColor: TradingPalette.violet,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  const _DiagnosticRow(
                    label: 'Auth mode',
                    value: 'X-API-Key only',
                  ),
                  const SizedBox(height: 8),
                  _DiagnosticRow(
                    label: 'API key',
                    value: AppConstants.requiredApiKey.isNotEmpty
                        ? 'configured'
                        : 'missing',
                  ),
                  const SizedBox(height: 8),
                  _DiagnosticRow(
                    label: 'Backend user',
                    value: AppConstants.requiredUserId,
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: GradientActionButton(
                          label: 'Clear Local Auth Cache',
                          icon: Icons.cleaning_services_rounded,
                          onPressed: () async {
                            await controller.clearLegacyAuthCache();
                            await ref
                                .read(authControllerProvider.notifier)
                                .refresh();
                            if (!context.mounted) {
                              return;
                            }
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Local auth cache cleared'),
                              ),
                            );
                          },
                          expanded: true,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () async {
                            await ref
                                .read(authControllerProvider.notifier)
                                .refresh();
                          },
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('Re-check'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            SectionCard(
              title: 'Production Runtime',
              subtitle:
                  'Live VPS, Redis, websocket, and backend health view for mobile operations.',
              trailing: const StatusBadge(label: 'OPS'),
              glowColor: TradingPalette.neonGreen,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: <Widget>[
                      _RuntimeListenTile(
                        builder: (context) {
                          final service = ref.read(webSocketServiceProvider);
                          return ValueListenableBuilder<WsState>(
                            valueListenable: service.stateListenable,
                            builder: (context, state, _) {
                              final color = switch (state) {
                                WsState.connected => TradingPalette.neonGreen,
                                WsState.connecting ||
                                WsState.degraded =>
                                  TradingPalette.amber,
                                WsState.disconnected => TradingPalette.neonRed,
                              };
                              return _DiagnosticStatusTile(
                                label: 'WebSocket',
                                ok: state == WsState.connected,
                                valueOverride: state.name.toUpperCase(),
                                accent: color,
                              );
                            },
                          );
                        },
                      ),
                      _RuntimeListenTile(
                        builder: (context) {
                          return ValueListenableBuilder<BackendWarmupState>(
                            valueListenable: backendWarmupState,
                            builder: (context, state, _) {
                              final ready = state == BackendWarmupState.ready;
                              final color = ready
                                  ? TradingPalette.neonGreen
                                  : state == BackendWarmupState.slow
                                      ? TradingPalette.neonRed
                                      : TradingPalette.amber;
                              return _DiagnosticStatusTile(
                                label: 'Backend',
                                ok: ready,
                                valueOverride: state.name.toUpperCase(),
                                accent: color,
                              );
                            },
                          );
                        },
                      ),
                      diagnosticsAsync.when(
                        data: (snapshot) => _DiagnosticStatusTile(
                          label: 'API health',
                          ok: snapshot.apiHealthy && snapshot.apiReady,
                          valueOverride: snapshot.apiStatus,
                          accent: snapshot.apiHealthy && snapshot.apiReady
                              ? TradingPalette.neonGreen
                              : TradingPalette.amber,
                        ),
                        loading: () => const _DiagnosticSkeletonTile(
                          label: 'API health',
                        ),
                        error: (error, _) => const _DiagnosticStatusTile(
                          label: 'API health',
                          ok: false,
                          valueOverride: 'FAILED',
                          accent: TradingPalette.neonRed,
                        ),
                      ),
                      diagnosticsAsync.when(
                        data: (snapshot) => _DiagnosticStatusTile(
                          label: 'Redis',
                          ok: snapshot.redisState.contains('READY'),
                          valueOverride: snapshot.redisState,
                          accent: snapshot.redisState.contains('READY')
                              ? TradingPalette.neonGreen
                              : snapshot.redisState.contains('DEGRADED')
                                  ? TradingPalette.amber
                                  : TradingPalette.neonRed,
                        ),
                        loading: () => const _DiagnosticSkeletonTile(
                          label: 'Redis',
                        ),
                        error: (error, _) => const _DiagnosticStatusTile(
                          label: 'Redis',
                          ok: false,
                          valueOverride: 'FAILED',
                          accent: TradingPalette.neonRed,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  diagnosticsAsync.when(
                    data: (snapshot) => GlassPanel(
                      glowColor: TradingPalette.electricBlue,
                      child: Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: <Widget>[
                          _DiagnosticTextTile(
                            label: 'Environment',
                            value: snapshot.deploymentMode,
                          ),
                          _DiagnosticTextTile(
                            label: 'Latency',
                            value: '${snapshot.latencyMs} ms',
                          ),
                          _DiagnosticTextTile(
                            label: 'Version',
                            value: snapshot.backendVersion,
                          ),
                          _DiagnosticTextTile(
                            label: 'Build',
                            value: snapshot.buildTimestamp,
                          ),
                          _DiagnosticTextTile(
                            label: 'Market data',
                            value: snapshot.marketDataMode,
                          ),
                          _DiagnosticTextTile(
                            label: 'Exchanges',
                            value: snapshot.activeExchanges.isEmpty
                                ? 'none'
                                : snapshot.activeExchanges.join(', '),
                          ),
                          _DiagnosticTextTile(
                            label: 'Mock data',
                            value: snapshot.usingMockData ? 'ON' : 'OFF',
                          ),
                        ],
                      ),
                    ),
                    loading: () => const GlassPanel(
                      glowColor: TradingPalette.electricBlue,
                      child: SizedBox(
                        height: 72,
                        child: Center(child: CircularProgressIndicator()),
                      ),
                    ),
                    error: (error, _) => GlassPanel(
                      glowColor: TradingPalette.neonRed,
                      child: Text(
                        ErrorMapper.map(
                          error,
                          fallback:
                              'Unable to load runtime diagnostics from the VPS.',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  infrastructureAsync.when(
                    data: (snapshot) {
                      final realtime = infrastructureEngine.realtimeResilience(
                        websocketState: socketService.stateListenable.value,
                        infrastructure: snapshot,
                      );
                      final dataIntegrity =
                          infrastructureEngine.marketDataIntegrity(
                        infrastructure: snapshot,
                      );
                      final telemetry = infrastructureEngine.telemetry(
                        infrastructure: snapshot,
                      );
                      final recovery = infrastructureEngine.stateRecovery(
                        infrastructure: snapshot,
                      );
                      final backgroundSync =
                          infrastructureEngine.backgroundSync(
                        hasWatchlist: retention.shadowTrades.isNotEmpty,
                        hasAiMemory: retention.achievements.isNotEmpty,
                        infrastructure: snapshot,
                      );
                      final performance =
                          infrastructureEngine.performanceStability(
                        infrastructure: snapshot,
                      );
                      final failsafe = infrastructureEngine.failsafe(
                        realtime: realtime,
                        data: dataIntegrity,
                        execution: const ExecutionReconciliationRead(
                          consistencyScore: 72,
                          requestedOrderTracked: true,
                          approvedOrderAligned: true,
                          exchangeAcknowledged: true,
                          fillStatus: 'MONITORING',
                          partialFillRisk: false,
                          rejectedFillRisk: false,
                          timeoutRisk: false,
                          orphanedStateRisk: false,
                          summary:
                              'Quant dashboard baseline reconciliation is available.',
                        ),
                      );
                      final failure = infrastructureEngine.failureHandling(
                        realtime: realtime,
                        failsafe: failsafe,
                      );
                      final multiDevice =
                          infrastructureEngine.multiDeviceConsistency(
                        watchlistReady: retention.shadowTrades.isNotEmpty,
                        replayReady: snapshot.replayCheckpointValid,
                        executionStateReady: true,
                      );
                      return Column(
                        children: <Widget>[
                          LayoutBuilder(
                            builder: (context, constraints) {
                              final wide = constraints.maxWidth >= 820;
                              final left = RealtimeResiliencePanel(
                                read: realtime,
                              );
                              final right = InfrastructureTelemetryPanel(
                                read: telemetry,
                              );
                              if (wide) {
                                return Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Expanded(child: left),
                                    const SizedBox(width: 16),
                                    Expanded(child: right),
                                  ],
                                );
                              }
                              return Column(
                                children: <Widget>[
                                  left,
                                  const SizedBox(height: 16),
                                  right,
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 16),
                          LayoutBuilder(
                            builder: (context, constraints) {
                              final wide = constraints.maxWidth >= 820;
                              final left = MarketDataIntegrityPanel(
                                read: dataIntegrity,
                              );
                              final right = StateRecoveryPanel(read: recovery);
                              if (wide) {
                                return Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Expanded(child: left),
                                    const SizedBox(width: 16),
                                    Expanded(child: right),
                                  ],
                                );
                              }
                              return Column(
                                children: <Widget>[
                                  left,
                                  const SizedBox(height: 16),
                                  right,
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 16),
                          LayoutBuilder(
                            builder: (context, constraints) {
                              final wide = constraints.maxWidth >= 820;
                              final left = FailsafeExecutionPanel(
                                read: failsafe,
                              );
                              final right = BackgroundSyncPanel(
                                read: backgroundSync,
                              );
                              if (wide) {
                                return Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Expanded(child: left),
                                    const SizedBox(width: 16),
                                    Expanded(child: right),
                                  ],
                                );
                              }
                              return Column(
                                children: <Widget>[
                                  left,
                                  const SizedBox(height: 16),
                                  right,
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 16),
                          LayoutBuilder(
                            builder: (context, constraints) {
                              final wide = constraints.maxWidth >= 820;
                              final left = PerformanceStabilityPanel(
                                read: performance,
                              );
                              final right = MultiDeviceConsistencyPanel(
                                read: multiDevice,
                              );
                              if (wide) {
                                return Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Expanded(child: left),
                                    const SizedBox(width: 16),
                                    Expanded(child: right),
                                  ],
                                );
                              }
                              return Column(
                                children: <Widget>[
                                  left,
                                  const SizedBox(height: 16),
                                  right,
                                ],
                              );
                            },
                          ),
                          const SizedBox(height: 16),
                          FailureHandlingPanel(read: failure),
                          const SizedBox(height: 16),
                          GlassPanel(
                            glowColor: TradingPalette.violet,
                            child: Wrap(
                              spacing: 12,
                              runSpacing: 12,
                              children: <Widget>[
                                _DiagnosticTextTile(
                                  label: 'WS gaps',
                                  value:
                                      snapshot.websocketSequenceGaps.toString(),
                                ),
                                _DiagnosticTextTile(
                                  label: 'Replay',
                                  value: snapshot.websocketReplayFrequency
                                      .toString(),
                                ),
                                _DiagnosticTextTile(
                                  label: 'Stale feeds',
                                  value: snapshot.staleFeedCount.toString(),
                                ),
                                _DiagnosticTextTile(
                                  label: 'AI queue',
                                  value: snapshot.aiQueueDepth.toString(),
                                ),
                                _DiagnosticTextTile(
                                  label: 'AI latency',
                                  value:
                                      '${snapshot.aiWorkerLatencyMs.toStringAsFixed(0)} ms',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Render FPS',
                                  value: snapshot.renderFps <= 0
                                      ? '-'
                                      : snapshot.renderFps.toStringAsFixed(0),
                                ),
                                _DiagnosticTextTile(
                                  label: 'Overlay pressure',
                                  value: snapshot.overlayPressure
                                      .toStringAsFixed(1),
                                ),
                                _DiagnosticTextTile(
                                  label: 'Event bus',
                                  value:
                                      '${snapshot.marketThroughput}/${snapshot.aiThroughput}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'GPU queue',
                                  value: snapshot.gpuQueueDepth.toString(),
                                ),
                                _DiagnosticTextTile(
                                  label: 'GPU runtime',
                                  value: snapshot.gpuRuntime,
                                ),
                                _DiagnosticTextTile(
                                  label: 'HA mode',
                                  value: snapshot.haMode,
                                ),
                                _DiagnosticTextTile(
                                  label: 'SLO',
                                  value:
                                      '${snapshot.sloMode} ${snapshot.sloScore.toStringAsFixed(0)}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Replay checkpoint',
                                  value: snapshot.replayCheckpointValid
                                      ? 'OK'
                                      : 'MISS',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Incident',
                                  value:
                                      '${snapshot.incidentSeverity} ${snapshot.incidentStatus}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Retention',
                                  value: snapshot.retentionMode,
                                ),
                                _DiagnosticTextTile(
                                  label: 'Capacity',
                                  value:
                                      '${snapshot.capacityScaleMode} W${snapshot.recommendedWebsocketInstances}/A${snapshot.recommendedAiWorkers}/G${snapshot.recommendedGpuWorkers}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Runbook',
                                  value: snapshot.runbookSteps.isEmpty
                                      ? 'none'
                                      : '${snapshot.runbookSteps.length} steps',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Release',
                                  value:
                                      '${snapshot.releaseStatus} (${snapshot.releaseBlockerCount})',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Canary',
                                  value: snapshot.canarySteps.isEmpty
                                      ? snapshot.canaryMode
                                      : '${snapshot.canaryMode} ${snapshot.canarySteps.join('/')}%',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Rollback',
                                  value: snapshot.rollbackRecommended
                                      ? snapshot.rollbackStrategy
                                      : 'not needed',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Backup',
                                  value: snapshot.backupStatus,
                                ),
                                _DiagnosticTextTile(
                                  label: 'Compliance',
                                  value:
                                      '${snapshot.complianceState} (${snapshot.complianceGapCount})',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Drift',
                                  value:
                                      '${snapshot.configDriftState} (${snapshot.configDriftCount})',
                                ),
                                _DiagnosticTextTile(
                                  label: 'DR',
                                  value: snapshot.disasterRecoveryDrillRequired
                                      ? '${snapshot.disasterRecoveryState} drill'
                                      : snapshot.disasterRecoveryState,
                                ),
                                _DiagnosticTextTile(
                                  label: 'Probes',
                                  value:
                                      '${snapshot.syntheticProbeMode} ${snapshot.syntheticProbeCount}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Readiness',
                                  value:
                                      '${snapshot.readinessStatus} ${snapshot.readinessScore.toStringAsFixed(0)}',
                                ),
                                _DiagnosticTextTile(
                                  label: 'Brokers',
                                  value: snapshot.brokers.isEmpty
                                      ? 'paper'
                                      : snapshot.brokers.join(', '),
                                ),
                              ],
                            ),
                          ),
                        ],
                      );
                    },
                    loading: () => const GlassPanel(
                      glowColor: TradingPalette.violet,
                      child: SizedBox(
                        height: 72,
                        child: Center(child: CircularProgressIndicator()),
                      ),
                    ),
                    error: (error, _) => GlassPanel(
                      glowColor: TradingPalette.amber,
                      child: Text(
                        ErrorMapper.map(
                          error,
                          fallback:
                              'Infrastructure dashboard is not available yet.',
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            ref.read(webSocketServiceProvider).reconnectNow();
                          },
                          icon: const Icon(Icons.sync_rounded),
                          label: const Text('Reconnect WebSocket'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () {
                            ref.invalidate(productionDiagnosticsProvider);
                          },
                          icon: const Icon(Icons.health_and_safety_rounded),
                          label: const Text('Refresh Runtime'),
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
                  'Run a production connectivity test covering /v1/health, /v1/public/performance, /v1/signals/live, websocket, and latency.',
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
                  const _DiagnosticRow(
                    label: 'Auth mode',
                    value: 'required_api_key',
                  ),
                  const SizedBox(height: 8),
                  _DiagnosticRow(
                    label: 'Fallback polling',
                    value:
                        '${AppConstants.realtimeFallbackPollingInterval.inSeconds}s',
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
                        style:
                            const TextStyle(color: TradingPalette.textPrimary),
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
              title: 'Advanced Views',
              subtitle:
                  'Surface the hidden operator views without overloading the main navigation.',
              trailing: const StatusBadge(label: 'TOOLS'),
              glowColor: TradingPalette.electricBlue,
              child: Column(
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const PulseScreen(),
                            ),
                          ),
                          icon: const Icon(Icons.monitor_heart_rounded),
                          label: const Text('Realtime Monitor'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (_) => const AnalyticsScreen(),
                            ),
                          ),
                          icon: const Icon(Icons.insights_rounded),
                          label: const Text('Meta Analytics'),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
          ],
          if (_quantMode)
            SectionCard(
              title: 'Runtime Controls',
              subtitle:
                  'Only controls with real backend effect stay visible here.',
              trailing: const StatusBadge(label: 'RUNTIME'),
              glowColor: TradingPalette.violet,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Risk profile',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                  const SizedBox(height: 10),
                  SegmentedButton<String>(
                    segments: const <ButtonSegment<String>>[
                      ButtonSegment<String>(value: 'low', label: Text('Low')),
                      ButtonSegment<String>(
                        value: 'medium',
                        label: Text('Medium'),
                      ),
                      ButtonSegment<String>(value: 'high', label: Text('High')),
                    ],
                    selected: <String>{settings.riskLevel},
                    onSelectionChanged: (selection) async {
                      await controller.saveRiskLevel(userId, selection.first);
                    },
                  ),
                  const SizedBox(height: 18),
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
      final performance = await apiClient.getPublicPerformance();
      final signals = await apiClient.getSignals(limit: 1);
      final websocket = await webSocketService.probeSignals();
      if (!context.mounted) {
        return;
      }
      setState(() {
        _connectivitySnapshot = <String, dynamic>{
          'rest_health': health['status'] == 'ok',
          'public_performance': performance.totalTrades >= 0,
          'signals_count': signals.length,
          'websocket_status': websocket['type'] == 'pong',
          'latency_ms': DateTime.now().difference(startedAt).inMilliseconds,
          'backend_version': health['version'],
          'api_base_url': apiClient.baseUrl,
          'auth_mode': 'required_api_key',
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

class _RuntimeListenTile extends StatelessWidget {
  const _RuntimeListenTile({
    required this.builder,
  });

  final WidgetBuilder builder;

  @override
  Widget build(BuildContext context) {
    return builder(context);
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
            label: 'Public route',
            ok: snapshot['public_performance'] == true,
          ),
          _DiagnosticStatusTile(
            label: 'Signals route',
            ok: (snapshot['signals_count'] as int? ?? -1) >= 0,
          ),
          _DiagnosticTextTile(
            label: 'WebSocket',
            value: snapshot['websocket_status'] == true ? 'OK' : 'FAILED',
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
            label: 'API base',
            value: (snapshot['api_base_url'] ?? '-').toString(),
          ),
          _DiagnosticTextTile(
            label: 'Auth',
            value: (snapshot['auth_mode'] ?? '-').toString(),
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
    this.valueOverride,
    this.accent,
  });

  final String label;
  final bool ok;
  final String? valueOverride;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final resolvedAccent =
        accent ?? (ok ? TradingPalette.neonGreen : TradingPalette.neonRed);
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
            valueOverride ?? (ok ? 'OK' : 'FAILED'),
            style: TextStyle(
              color: resolvedAccent,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}

class _DiagnosticSkeletonTile extends StatelessWidget {
  const _DiagnosticSkeletonTile({
    required this.label,
  });

  final String label;

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
          const SizedBox(height: 10),
          Container(
            width: 72,
            height: 10,
            decoration: BoxDecoration(
              color: TradingPalette.panelBorder,
              borderRadius: BorderRadius.circular(999),
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

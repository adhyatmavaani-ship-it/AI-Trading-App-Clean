import 'package:flutter/material.dart';

import '../core/platformization_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class ExchangeConnectivityPanel extends StatelessWidget {
  const ExchangeConnectivityPanel({super.key, required this.read});

  final ExchangeConnectivityRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Exchange Ecosystem',
      badge: read.ecosystemReady ? 'READY' : 'FOUNDATION',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet(read.summary),
        _KeyValue('Primary venue', read.healthiestExchange),
        const SizedBox(height: 8),
        ...read.adapters.map(
          (adapter) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _ExchangeRow(adapter: adapter),
          ),
        ),
        _LabelBlock(
            title: 'Execution constraints', lines: read.executionConstraints),
      ],
    );
  }
}

class CloudDeploymentFoundationPanel extends StatelessWidget {
  const CloudDeploymentFoundationPanel({super.key, required this.read});

  final CloudDeploymentRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Cloud Foundation',
      badge: '${read.deploymentScore.toStringAsFixed(0)} score',
      color: _scoreColor(read.deploymentScore),
      children: <Widget>[
        _MetricLine('Deployment score', read.deploymentScore),
        _Bullet(read.summary),
        _CheckRow(label: 'Cloud profile sync', ok: read.cloudSyncReady),
        _CheckRow(label: 'Remote config', ok: read.remoteConfigReady),
        _CheckRow(label: 'Feature rollout', ok: read.featureRolloutReady),
        _CheckRow(label: 'AI model config delivery', ok: read.modelConfigReady),
        _CheckRow(
            label: 'Telemetry aggregation', ok: read.telemetryAggregationReady),
        _CheckRow(label: 'Replay upload', ok: read.replayUploadReady),
        _CheckRow(label: 'Crash reporting hooks', ok: read.crashReportingReady),
      ],
    );
  }
}

class EntitlementArchitecturePanel extends StatelessWidget {
  const EntitlementArchitecturePanel({super.key, required this.read});

  final EntitlementRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Entitlements',
      badge: read.tier.name.toUpperCase(),
      color: TradingPalette.amber,
      children: <Widget>[
        _KeyValue('Daily scans', read.dailyScanLimit.toString()),
        _CheckRow(label: 'Replay access', ok: read.replayAccess),
        _CheckRow(label: 'Advanced analytics', ok: read.analyticsAccess),
        _CheckRow(
          label: 'Institutional dashboard',
          ok: read.institutionalDashboardAccess,
        ),
        _CheckRow(
            label: 'Premium watchtower', ok: read.premiumWatchtowerAlerts),
        const SizedBox(height: 8),
        _LabelBlock(title: 'AI modes', lines: read.aiModes),
        _LabelBlock(title: 'Enabled', lines: read.enabledFeatures),
        if (read.lockedFeatures.isNotEmpty)
          _LabelBlock(title: 'Locked', lines: read.lockedFeatures),
        _Bullet(read.conversionPrompt),
      ],
    );
  }
}

class ExperienceModePanel extends StatelessWidget {
  const ExperienceModePanel({super.key, required this.read});

  final ExperienceModeRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Experience Mode',
      badge: read.mode.name.toUpperCase(),
      color: _scoreColor(100 - read.complexityScore),
      children: <Widget>[
        _MetricLine('Complexity', read.complexityScore),
        _Bullet(read.summary),
        _KeyValue('Primary flow', read.primaryUserFlow),
        const SizedBox(height: 8),
        _LabelBlock(title: 'Visible', lines: read.visibleSections),
        if (read.hiddenSections.isNotEmpty)
          _LabelBlock(
              title: 'Hidden from this mode', lines: read.hiddenSections),
      ],
    );
  }
}

class ProductionOpsPanel extends StatelessWidget {
  const ProductionOpsPanel({super.key, required this.read});

  final ProductionOpsRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Production Ops',
      badge: read.adminReady ? 'ADMIN' : 'PARTIAL',
      color: TradingPalette.violet,
      children: <Widget>[
        _KeyValue('Rollout', read.rolloutVisibility),
        _KeyValue('AI health', read.aiHealthStatus),
        _KeyValue('Incident', read.incidentOverview),
        _KeyValue('Replay', read.replayIntegrityStatus),
        _Bullet(read.telemetrySummary),
        _Bullet(read.deploymentPosture),
        _LabelBlock(
          title: 'Feature flags',
          lines: read.featureFlags.entries
              .map((entry) => '${entry.key}: ${entry.value ? 'on' : 'off'}')
              .toList(growable: false),
        ),
      ],
    );
  }
}

class MobilePerformancePanel extends StatelessWidget {
  const MobilePerformancePanel({super.key, required this.read});

  final MobilePerformanceRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Mobile Performance',
      badge: '${read.performanceScore.toStringAsFixed(0)} perf',
      color: _scoreColor(read.performanceScore),
      children: <Widget>[
        _MetricLine('Performance score', read.performanceScore),
        _KeyValue('Startup budget', '${read.startupBudgetMs} ms'),
        _KeyValue('Memory budget', '${read.memoryBudgetMb} MB'),
        _KeyValue('Chart mode', read.chartRenderMode),
        _KeyValue('Provider scope', read.providerInvalidationScope),
        _KeyValue('Realtime batching', '${read.realtimeBatchingMs} ms'),
        _KeyValue('Motion policy', read.animationPolicy),
        _LabelBlock(title: 'Optimization rules', lines: read.recommendations),
      ],
    );
  }
}

class OfflineDegradedPanel extends StatelessWidget {
  const OfflineDegradedPanel({super.key, required this.read});

  final OfflineDegradedRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Offline + Degraded',
      badge: '${read.degradedScore.toStringAsFixed(0)} recovery',
      color: _scoreColor(read.degradedScore),
      children: <Widget>[
        _MetricLine('Degraded score', read.degradedScore),
        _Bullet(read.userMessage),
        _CheckRow(
            label: 'Cached signal viewing', ok: read.cachedSignalsAvailable),
        _CheckRow(
            label: 'Offline replay browsing', ok: read.offlineReplayBrowsing),
        _CheckRow(
            label: 'Advisory-only degraded AI', ok: read.degradedAiAdvisory),
        _CheckRow(label: 'Stale data indicator', ok: read.staleDataIndicator),
        _CheckRow(
            label: 'Reconnect orchestration', ok: read.reconnectOrchestration),
      ],
    );
  }
}

class PlatformAnalyticsPanel extends StatelessWidget {
  const PlatformAnalyticsPanel({super.key, required this.read});

  final PlatformAnalyticsRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Platform Analytics',
      badge: read.privacySafe ? 'PRIVACY SAFE' : 'REVIEW',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _MetricLine('Signal interaction', read.signalInteractionQuality),
        _MetricLine('Onboarding', read.onboardingCompletion),
        _MetricLine('Retention pattern', read.retentionPatternScore),
        _MetricLine('Replay engagement', read.replayEngagement),
        _MetricLine('Watchtower engagement', read.watchtowerEngagement),
        _LabelBlock(
          title: 'Usage events',
          lines: read.featureUsageEvents.entries
              .map((entry) => '${entry.key}: ${entry.value}')
              .toList(growable: false),
        ),
        _LabelBlock(
          title: 'Mode adoption',
          lines: read.aiModeAdoption.entries
              .map(
                  (entry) => '${entry.key}: ${entry.value.toStringAsFixed(0)}%')
              .toList(growable: false),
        ),
      ],
    );
  }
}

class ReleaseChannelPanel extends StatelessWidget {
  const ReleaseChannelPanel({super.key, required this.read});

  final ReleaseChannelRead read;

  @override
  Widget build(BuildContext context) {
    return _PlatformPanel(
      title: 'Release Channel',
      badge: read.channel.name.toUpperCase(),
      color: read.channel == ReleaseChannel.stable
          ? TradingPalette.neonGreen
          : TradingPalette.amber,
      children: <Widget>[
        _Bullet(read.channelSummary),
        _CheckRow(
            label: 'Experimental builds', ok: read.experimentalBuildsEnabled),
        _CheckRow(
            label: 'Beta intelligence layers', ok: read.betaIntelligenceLayers),
        _CheckRow(label: 'Staged release', ok: read.stagedRelease),
        _CheckRow(label: 'Rollback readiness', ok: read.rollbackReadiness),
        _LabelBlock(
          title: 'Config snapshot',
          lines: read.configurationSnapshot.entries
              .map((entry) => '${entry.key}: ${entry.value}')
              .toList(growable: false),
        ),
      ],
    );
  }
}

class _ExchangeRow extends StatelessWidget {
  const _ExchangeRow({required this.adapter});

  final ExchangeCapabilityRead adapter;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.all(12),
      radius: 14,
      glowColor: _scoreColor(adapter.healthScore),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  adapter.exchange,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
              StatusBadge(
                label: adapter.enabled ? 'FOUNDATION' : 'STAGED',
                color: adapter.enabled
                    ? TradingPalette.neonGreen
                    : TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 8),
          _MetricLine('Health', adapter.healthScore),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              StatusBadge(label: adapter.spot ? 'SPOT' : 'NO SPOT'),
              StatusBadge(label: adapter.futures ? 'FUTURES' : 'NO FUTURES'),
              StatusBadge(label: adapter.paper ? 'PAPER' : 'NO PAPER'),
            ],
          ),
          const SizedBox(height: 8),
          _KeyValue('Min notional', adapter.minNotional.toStringAsFixed(0)),
          _KeyValue('Precision',
              'p${adapter.pricePrecision} / q${adapter.quantityPrecision}'),
          _KeyValue('Rate limit', '${adapter.rateLimitPerMinute}/min'),
        ],
      ),
    );
  }
}

class _PlatformPanel extends StatelessWidget {
  const _PlatformPanel({
    required this.title,
    required this.badge,
    required this.color,
    required this.children,
  });

  final String title;
  final String badge;
  final Color color;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: badge, color: color),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _MetricLine extends StatelessWidget {
  const _MetricLine(this.label, this.value);

  final String label;
  final double value;

  @override
  Widget build(BuildContext context) {
    final color = _scoreColor(value);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: <Widget>[
          SizedBox(width: 132, child: Text(label)),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: (value / 100).clamp(0.0, 1.0),
                minHeight: 7,
                backgroundColor: TradingPalette.overlay,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 42,
            child: Text(
              value.toStringAsFixed(0),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(
            width: 118,
            child: Text(label, style: Theme.of(context).textTheme.labelMedium),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.label, required this.ok});

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return _Bullet('${ok ? 'Ready' : 'Review'}: $label');
  }
}

class _LabelBlock extends StatelessWidget {
  const _LabelBlock({required this.title, required this.lines});

  final String title;
  final List<String> lines;

  @override
  Widget build(BuildContext context) {
    if (lines.isEmpty) {
      return const SizedBox.shrink();
    }
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          ...lines.map(_Bullet.new),
        ],
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(top: 7),
            decoration: const BoxDecoration(
              color: TradingPalette.electricBlue,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: TradingPalette.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

Color _scoreColor(double value) {
  if (value >= 74) {
    return TradingPalette.neonGreen;
  }
  if (value >= 54) {
    return TradingPalette.amber;
  }
  return TradingPalette.neonRed;
}

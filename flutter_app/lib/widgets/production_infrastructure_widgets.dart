import 'package:flutter/material.dart';

import '../core/production_infrastructure_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class RealtimeResiliencePanel extends StatelessWidget {
  const RealtimeResiliencePanel({super.key, required this.read});

  final RealtimeResilienceRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Realtime Resilience',
      badge: read.degradedMode ? 'RECOVERY' : 'STABLE',
      color: _scoreColor(read.streamHealthScore),
      children: <Widget>[
        _MetricLine('Stream health', read.streamHealthScore),
        _CheckRow(label: 'Heartbeat', ok: read.heartbeatHealthy),
        _CheckRow(label: 'Event dedupe', ok: read.deduplicationActive),
        _CheckRow(label: 'Ordering', ok: read.orderingValid),
        _CheckRow(label: 'Fresh data', ok: !read.staleDataDetected),
        _Bullet('Refresh cadence ${read.adaptiveRefreshCadenceMs}ms'),
        _Bullet(read.guidance),
      ],
    );
  }
}

class ExecutionReconciliationPanel extends StatelessWidget {
  const ExecutionReconciliationPanel({super.key, required this.read});

  final ExecutionReconciliationRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Execution Reconciliation',
      badge: read.fillStatus,
      color: _scoreColor(read.consistencyScore),
      children: <Widget>[
        _MetricLine('Consistency', read.consistencyScore),
        _CheckRow(label: 'Request tracked', ok: read.requestedOrderTracked),
        _CheckRow(label: 'Approval aligned', ok: read.approvedOrderAligned),
        _CheckRow(label: 'Exchange ack', ok: read.exchangeAcknowledged),
        _CheckRow(label: 'No timeout', ok: !read.timeoutRisk),
        _CheckRow(label: 'No orphan state', ok: !read.orphanedStateRisk),
        _Bullet(read.summary),
      ],
    );
  }
}

class MarketDataIntegrityPanel extends StatelessWidget {
  const MarketDataIntegrityPanel({super.key, required this.read});

  final MarketDataIntegrityRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Market Data Integrity',
      badge: '${read.reliabilityScore.toStringAsFixed(0)}%',
      color: _scoreColor(read.reliabilityScore),
      children: <Widget>[
        _MetricLine('Reliability', read.reliabilityScore),
        _CheckRow(label: 'Fresh candles', ok: !read.staleCandles),
        _CheckRow(label: 'Spread normal', ok: !read.abnormalSpread),
        _CheckRow(label: 'Depth updates', ok: !read.missingDepthUpdates),
        _CheckRow(label: 'No duplicate pressure', ok: !read.duplicatedEvents),
        _Bullet('Timestamp gaps: ${read.timestampGaps}'),
        _Bullet(read.summary),
      ],
    );
  }
}

class StateRecoveryPanel extends StatelessWidget {
  const StateRecoveryPanel({super.key, required this.read});

  final StateRecoveryRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'State Recovery',
      badge: '${read.recoveryScore.toStringAsFixed(0)}%',
      color: _scoreColor(read.recoveryScore),
      children: <Widget>[
        _MetricLine('Recovery', read.recoveryScore),
        _CheckRow(label: 'Crash recovery', ok: read.crashRecoveryReady),
        _CheckRow(label: 'Websocket recovery', ok: read.websocketRecoveryReady),
        _CheckRow(label: 'Portfolio resync', ok: read.portfolioResyncReady),
        _CheckRow(label: 'Replay timeline', ok: read.replayTimelineReady),
        _CheckRow(label: 'Session restore', ok: read.sessionRestorationReady),
        const SizedBox(height: 8),
        ...read.recoveryPlan.take(4).map(_Bullet.new),
      ],
    );
  }
}

class InfrastructureTelemetryPanel extends StatelessWidget {
  const InfrastructureTelemetryPanel({super.key, required this.read});

  final InfrastructureTelemetryRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Infrastructure Telemetry',
      badge: read.status,
      color: _scoreColor(read.healthScore),
      children: <Widget>[
        _MetricLine('Health', read.healthScore),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _Pill('WS latency',
                '${read.websocketLatencyMs.toStringAsFixed(0)}ms'),
            _Pill(
                'Render', '${read.chartRenderLatencyMs.toStringAsFixed(1)}ms'),
            _Pill('Queue', read.eventQueuePressure.toStringAsFixed(0)),
            _Pill('Dropped', read.droppedUpdates.toString()),
            _Pill('Memory', '${read.memoryPressure.toStringAsFixed(0)}%'),
            _Pill('Exec', '${read.executionTimingMs.toStringAsFixed(0)}ms'),
          ],
        ),
      ],
    );
  }
}

class FailsafeExecutionPanel extends StatelessWidget {
  const FailsafeExecutionPanel({super.key, required this.read});

  final FailsafeExecutionRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Failsafe Execution',
      badge: read.advisoryOnly ? 'ADVISORY' : 'READY',
      color: _scoreColor(read.failsafeScore),
      children: <Widget>[
        _MetricLine('Failsafe', read.failsafeScore),
        _CheckRow(label: 'Websocket', ok: read.websocketHealthy),
        _CheckRow(label: 'Market data', ok: read.marketDataFresh),
        _CheckRow(label: 'Execution sync', ok: read.executionSyncHealthy),
        _CheckRow(label: 'Portfolio sync', ok: read.portfolioSyncHealthy),
        _CheckRow(
          label: 'Backend confirmation',
          ok: read.backendConfirmationConsistent,
        ),
        _Bullet(read.verdict),
      ],
    );
  }
}

class BackgroundSyncPanel extends StatelessWidget {
  const BackgroundSyncPanel({super.key, required this.read});

  final BackgroundSyncRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Background Synchronization',
      badge: read.batteryMode,
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet('Portfolio cadence ${read.portfolioRefreshCadenceSeconds}s'),
        _CheckRow(label: 'Lazy recovery', ok: read.lazyRecoveryEnabled),
        _CheckRow(label: 'Staged hydration', ok: read.stagedHydrationEnabled),
        _CheckRow(label: 'Replay sync', ok: read.replaySyncReady),
        _CheckRow(label: 'Watchlist sync', ok: read.watchlistSyncReady),
        _CheckRow(label: 'AI memory sync', ok: read.aiMemorySyncReady),
        const SizedBox(height: 8),
        ...read.syncPlan.take(3).map(_Bullet.new),
      ],
    );
  }
}

class PerformanceStabilityPanel extends StatelessWidget {
  const PerformanceStabilityPanel({super.key, required this.read});

  final PerformanceStabilityRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Performance Stability',
      badge: read.fpsStatus,
      color: _scoreColor(read.stabilityScore),
      children: <Widget>[
        _MetricLine('Stability', read.stabilityScore),
        _Bullet(read.memoryAllocationMode),
        _Bullet('Chart pressure ${read.chartPressure.toStringAsFixed(1)}'),
        _Bullet(read.rebuildFrequencyMode),
        _Bullet(read.websocketBatchingMode),
        _Bullet(read.providerInvalidationScope),
      ],
    );
  }
}

class FailureHandlingPanel extends StatelessWidget {
  const FailureHandlingPanel({super.key, required this.read});

  final FailureHandlingRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Graceful Failure Handling',
      badge: read.silentRecovery ? 'RECOVERY' : 'NORMAL',
      color:
          read.silentRecovery ? TradingPalette.amber : TradingPalette.neonGreen,
      children: <Widget>[
        _Bullet(read.userMessage),
        _Bullet('Retry: ${read.retryStrategy}'),
        _Bullet(read.operationalGuidance),
      ],
    );
  }
}

class MultiDeviceConsistencyPanel extends StatelessWidget {
  const MultiDeviceConsistencyPanel({super.key, required this.read});

  final MultiDeviceConsistencyRead read;

  @override
  Widget build(BuildContext context) {
    return _InfraPanel(
      title: 'Multi-Device Consistency',
      badge: 'FOUNDATION',
      color: TradingPalette.violet,
      children: <Widget>[
        _CheckRow(label: 'Device sync', ok: read.deviceSyncReady),
        _CheckRow(label: 'Session continuity', ok: read.sessionContinuityReady),
        _CheckRow(
          label: 'Cloud execution state',
          ok: read.cloudExecutionStateReady,
        ),
        _CheckRow(
            label: 'Watchlist continuity', ok: read.watchlistContinuityReady),
        _CheckRow(label: 'Replay continuity', ok: read.replayContinuityReady),
        _Bullet(read.consistencyNote),
      ],
    );
  }
}

class _InfraPanel extends StatelessWidget {
  const _InfraPanel({
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
          SizedBox(width: 130, child: Text(label)),
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

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.label, required this.ok});

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return _Bullet('${ok ? 'OK' : 'Watch'}: $label');
  }
}

class _Pill extends StatelessWidget {
  const _Pill(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 88),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 3),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
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
  if (value >= 78) {
    return TradingPalette.neonGreen;
  }
  if (value >= 58) {
    return TradingPalette.amber;
  }
  return TradingPalette.neonRed;
}

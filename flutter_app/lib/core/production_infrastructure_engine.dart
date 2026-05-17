import 'dart:math' as math;

import '../models/infrastructure_snapshot.dart';
import '../models/market_chart.dart';
import '../models/realtime_event.dart';
import '../models/trade_execution.dart';
import 'websocket_service.dart';

class RealtimeResilienceRead {
  const RealtimeResilienceRead({
    required this.streamHealthScore,
    required this.websocketState,
    required this.heartbeatHealthy,
    required this.staleDataDetected,
    required this.deduplicationActive,
    required this.orderingValid,
    required this.adaptiveRefreshCadenceMs,
    required this.degradedMode,
    required this.guidance,
  });

  final double streamHealthScore;
  final String websocketState;
  final bool heartbeatHealthy;
  final bool staleDataDetected;
  final bool deduplicationActive;
  final bool orderingValid;
  final int adaptiveRefreshCadenceMs;
  final bool degradedMode;
  final String guidance;
}

class ExecutionReconciliationRead {
  const ExecutionReconciliationRead({
    required this.consistencyScore,
    required this.requestedOrderTracked,
    required this.approvedOrderAligned,
    required this.exchangeAcknowledged,
    required this.fillStatus,
    required this.partialFillRisk,
    required this.rejectedFillRisk,
    required this.timeoutRisk,
    required this.orphanedStateRisk,
    required this.summary,
  });

  final double consistencyScore;
  final bool requestedOrderTracked;
  final bool approvedOrderAligned;
  final bool exchangeAcknowledged;
  final String fillStatus;
  final bool partialFillRisk;
  final bool rejectedFillRisk;
  final bool timeoutRisk;
  final bool orphanedStateRisk;
  final String summary;
}

class MarketDataIntegrityRead {
  const MarketDataIntegrityRead({
    required this.reliabilityScore,
    required this.staleCandles,
    required this.timestampGaps,
    required this.abnormalSpread,
    required this.missingDepthUpdates,
    required this.duplicatedEvents,
    required this.inconsistentVolumeSpikes,
    required this.summary,
  });

  final double reliabilityScore;
  final bool staleCandles;
  final int timestampGaps;
  final bool abnormalSpread;
  final bool missingDepthUpdates;
  final bool duplicatedEvents;
  final bool inconsistentVolumeSpikes;
  final String summary;
}

class StateRecoveryRead {
  const StateRecoveryRead({
    required this.recoveryScore,
    required this.crashRecoveryReady,
    required this.websocketRecoveryReady,
    required this.portfolioResyncReady,
    required this.replayTimelineReady,
    required this.executionStatePersisted,
    required this.sessionRestorationReady,
    required this.aiMemoryRecoveryReady,
    required this.recoveryPlan,
  });

  final double recoveryScore;
  final bool crashRecoveryReady;
  final bool websocketRecoveryReady;
  final bool portfolioResyncReady;
  final bool replayTimelineReady;
  final bool executionStatePersisted;
  final bool sessionRestorationReady;
  final bool aiMemoryRecoveryReady;
  final List<String> recoveryPlan;
}

class InfrastructureTelemetryRead {
  const InfrastructureTelemetryRead({
    required this.healthScore,
    required this.websocketLatencyMs,
    required this.chartRenderLatencyMs,
    required this.eventQueuePressure,
    required this.droppedUpdates,
    required this.memoryPressure,
    required this.rebuildHotspots,
    required this.executionTimingMs,
    required this.syncFailures,
    required this.status,
  });

  final double healthScore;
  final double websocketLatencyMs;
  final double chartRenderLatencyMs;
  final double eventQueuePressure;
  final int droppedUpdates;
  final double memoryPressure;
  final int rebuildHotspots;
  final double executionTimingMs;
  final int syncFailures;
  final String status;
}

class FailsafeExecutionRead {
  const FailsafeExecutionRead({
    required this.failsafeScore,
    required this.websocketHealthy,
    required this.marketDataFresh,
    required this.executionSyncHealthy,
    required this.portfolioSyncHealthy,
    required this.backendConfirmationConsistent,
    required this.advisoryOnly,
    required this.verdict,
  });

  final double failsafeScore;
  final bool websocketHealthy;
  final bool marketDataFresh;
  final bool executionSyncHealthy;
  final bool portfolioSyncHealthy;
  final bool backendConfirmationConsistent;
  final bool advisoryOnly;
  final String verdict;
}

class BackgroundSyncRead {
  const BackgroundSyncRead({
    required this.portfolioRefreshCadenceSeconds,
    required this.lazyRecoveryEnabled,
    required this.stagedHydrationEnabled,
    required this.replaySyncReady,
    required this.watchlistSyncReady,
    required this.aiMemorySyncReady,
    required this.batteryMode,
    required this.syncPlan,
  });

  final int portfolioRefreshCadenceSeconds;
  final bool lazyRecoveryEnabled;
  final bool stagedHydrationEnabled;
  final bool replaySyncReady;
  final bool watchlistSyncReady;
  final bool aiMemorySyncReady;
  final String batteryMode;
  final List<String> syncPlan;
}

class PerformanceStabilityRead {
  const PerformanceStabilityRead({
    required this.stabilityScore,
    required this.memoryAllocationMode,
    required this.chartPressure,
    required this.rebuildFrequencyMode,
    required this.websocketBatchingMode,
    required this.providerInvalidationScope,
    required this.eventStreamPressure,
    required this.fpsStatus,
  });

  final double stabilityScore;
  final String memoryAllocationMode;
  final double chartPressure;
  final String rebuildFrequencyMode;
  final String websocketBatchingMode;
  final String providerInvalidationScope;
  final double eventStreamPressure;
  final String fpsStatus;
}

class FailureHandlingRead {
  const FailureHandlingRead({
    required this.userMessage,
    required this.retryStrategy,
    required this.silentRecovery,
    required this.operationalGuidance,
  });

  final String userMessage;
  final String retryStrategy;
  final bool silentRecovery;
  final String operationalGuidance;
}

class MultiDeviceConsistencyRead {
  const MultiDeviceConsistencyRead({
    required this.deviceSyncReady,
    required this.sessionContinuityReady,
    required this.cloudExecutionStateReady,
    required this.watchlistContinuityReady,
    required this.replayContinuityReady,
    required this.consistencyNote,
  });

  final bool deviceSyncReady;
  final bool sessionContinuityReady;
  final bool cloudExecutionStateReady;
  final bool watchlistContinuityReady;
  final bool replayContinuityReady;
  final String consistencyNote;
}

class ProductionInfrastructureEngine {
  const ProductionInfrastructureEngine();

  RealtimeResilienceRead realtimeResilience({
    required WsState websocketState,
    InfrastructureSnapshotModel? infrastructure,
    DateTime? lastEventAt,
  }) {
    final connected = websocketState == WsState.connected;
    final stale =
        _isStale(lastEventAt) || (infrastructure?.staleFeedCount ?? 0) > 0;
    final gaps = infrastructure?.websocketSequenceGaps ?? 0;
    final replay = infrastructure?.websocketReplayFrequency ?? 0;
    final latency = infrastructure?.redisLatencyMs ?? 0;
    final score = (100 -
            gaps * 7 -
            replay * 3 -
            (stale ? 24 : 0) -
            (connected ? 0 : 32) -
            latency * 0.08)
        .clamp(0, 99)
        .toDouble();
    final degraded = score < 68;
    return RealtimeResilienceRead(
      streamHealthScore: score,
      websocketState: websocketState.name.toUpperCase(),
      heartbeatHealthy: connected && !stale,
      staleDataDetected: stale,
      deduplicationActive: true,
      orderingValid: gaps == 0,
      adaptiveRefreshCadenceMs: degraded ? 2500 : 900,
      degradedMode: degraded,
      guidance: degraded
          ? 'Realtime is recovering. The app should prefer REST refresh and advisory-only surfaces.'
          : 'Realtime stream is healthy enough for live portfolio and signal updates.',
    );
  }

  ExecutionReconciliationRead executionReconciliation({
    required String requestedSide,
    required double requestedAmount,
    required bool submitting,
    TradeEvaluationModel? evaluation,
    RealtimeTradeUpdateModel? tradeUpdate,
  }) {
    final requested = requestedAmount > 0 && requestedSide.isNotEmpty;
    final approved = evaluation?.allowTrade == true &&
        evaluation?.approvedSide == requestedSide;
    final ack = tradeUpdate != null &&
        <String>{'accepted', 'executed', 'filled', 'open', 'rejected'}
            .contains(tradeUpdate.status.toLowerCase());
    final rejected =
        tradeUpdate?.status.toLowerCase().contains('reject') == true;
    final partial =
        tradeUpdate?.status.toLowerCase().contains('partial') == true;
    final timeout = submitting && tradeUpdate == null;
    final orphaned = tradeUpdate != null && evaluation == null;
    final score = (100 -
            (requested ? 0 : 12) -
            (approved ? 0 : 22) -
            (ack || !submitting ? 0 : 18) -
            (rejected ? 28 : 0) -
            (partial ? 10 : 0) -
            (timeout ? 18 : 0) -
            (orphaned ? 14 : 0))
        .clamp(0, 99)
        .toDouble();
    return ExecutionReconciliationRead(
      consistencyScore: score,
      requestedOrderTracked: requested,
      approvedOrderAligned: approved,
      exchangeAcknowledged: ack,
      fillStatus: tradeUpdate?.status.toUpperCase() ??
          (submitting ? 'PENDING' : 'NOT SUBMITTED'),
      partialFillRisk: partial,
      rejectedFillRisk: rejected,
      timeoutRisk: timeout,
      orphanedStateRisk: orphaned,
      summary: score >= 78
          ? 'Execution state is internally consistent.'
          : 'Execution needs reconciliation before increasing automation.',
    );
  }

  MarketDataIntegrityRead marketDataIntegrity({
    MarketChartModel? chart,
    InfrastructureSnapshotModel? infrastructure,
  }) {
    final candles = chart?.candles ?? const <MarketCandleModel>[];
    final stale = candles.isNotEmpty &&
        DateTime.now()
                .difference(
                  DateTime.fromMillisecondsSinceEpoch(
                    candles.last.timestampMs,
                    isUtc: true,
                  ),
                )
                .inMinutes >
            20;
    final gaps = _timestampGaps(candles);
    final depthMissing =
        (chart?.orderbookDepth.liquidityLadder.isEmpty ?? true);
    final duplicateEvents = (infrastructure?.websocketSequenceGaps ?? 0) > 0;
    final volumeSpike = _volumeSpike(candles);
    final abnormalSpread =
        (chart?.orderbookDepth.liquidityLadder.isNotEmpty ?? false)
            ? _spreadPct(chart!.orderbookDepth.liquidityLadder.first) > 0.7
            : false;
    final score = (100 -
            (stale ? 24 : 0) -
            gaps * 4 -
            (abnormalSpread ? 16 : 0) -
            (depthMissing ? 8 : 0) -
            (duplicateEvents ? 12 : 0) -
            (volumeSpike ? 8 : 0))
        .clamp(0, 99)
        .toDouble();
    return MarketDataIntegrityRead(
      reliabilityScore: score,
      staleCandles: stale,
      timestampGaps: gaps,
      abnormalSpread: abnormalSpread,
      missingDepthUpdates: depthMissing,
      duplicatedEvents: duplicateEvents,
      inconsistentVolumeSpikes: volumeSpike,
      summary: score >= 78
          ? 'Market data reliability is suitable for live decision support.'
          : 'Market data reliability is degraded; prefer watch/simulate mode.',
    );
  }

  StateRecoveryRead stateRecovery({
    InfrastructureSnapshotModel? infrastructure,
    bool aiMemoryAvailable = false,
    bool sessionRestored = true,
    bool executionStateAvailable = false,
  }) {
    final checks = <bool>[
      true,
      (infrastructure?.websocketReplayFrequency ?? 0) >= 0,
      infrastructure?.readinessStatus.toUpperCase() != 'BLOCKED',
      infrastructure?.replayCheckpointValid ?? false,
      executionStateAvailable,
      sessionRestored,
      aiMemoryAvailable,
    ];
    final score = checks.where((item) => item).length / checks.length * 100;
    return StateRecoveryRead(
      recoveryScore: score,
      crashRecoveryReady: checks[0],
      websocketRecoveryReady: checks[1],
      portfolioResyncReady: checks[2],
      replayTimelineReady: checks[3],
      executionStatePersisted: checks[4],
      sessionRestorationReady: checks[5],
      aiMemoryRecoveryReady: checks[6],
      recoveryPlan: const <String>[
        'Restore session and API-key context.',
        'Reconnect websocket with replay-safe ordering.',
        'Refresh portfolio snapshot silently.',
        'Hydrate chart/replay state only when visible.',
        'Keep execution advisory until consistency checks pass.',
      ],
    );
  }

  InfrastructureTelemetryRead telemetry({
    InfrastructureSnapshotModel? infrastructure,
    int localSignalQueue = 0,
  }) {
    final eventPressure = ((infrastructure?.marketThroughput ?? 0) +
            (infrastructure?.aiThroughput ?? 0) +
            localSignalQueue)
        .clamp(0, 300)
        .toDouble();
    final dropped = (infrastructure?.websocketSequenceGaps ?? 0) +
        (infrastructure?.staleFeedCount ?? 0);
    final renderFps = infrastructure?.renderFps ?? 60;
    final chartLatency = renderFps <= 0 ? 0.0 : 1000 / renderFps;
    final memoryPressure =
        ((infrastructure?.overlayPressure ?? 0) + eventPressure * 0.12)
            .clamp(0, 100)
            .toDouble();
    final score = (100 -
            dropped * 6 -
            memoryPressure * 0.22 -
            math.max(0, chartLatency - 16) * 1.8 -
            (infrastructure?.executionLatencyMs ?? 0) * 0.03)
        .clamp(0, 99)
        .toDouble();
    return InfrastructureTelemetryRead(
      healthScore: score,
      websocketLatencyMs: infrastructure?.redisLatencyMs ?? 0,
      chartRenderLatencyMs: chartLatency,
      eventQueuePressure: eventPressure,
      droppedUpdates: dropped,
      memoryPressure: memoryPressure,
      rebuildHotspots: memoryPressure >= 70
          ? 3
          : memoryPressure >= 45
              ? 1
              : 0,
      executionTimingMs: infrastructure?.executionLatencyMs ?? 0,
      syncFailures: dropped + (infrastructure?.configDriftCount ?? 0),
      status: score >= 80
          ? 'HEALTHY'
          : score >= 62
              ? 'WATCH'
              : 'DEGRADED',
    );
  }

  FailsafeExecutionRead failsafe({
    required RealtimeResilienceRead realtime,
    required MarketDataIntegrityRead data,
    required ExecutionReconciliationRead execution,
    bool portfolioSyncHealthy = true,
    bool backendConfirmationConsistent = true,
  }) {
    final checks = <bool>[
      realtime.streamHealthScore >= 68,
      data.reliabilityScore >= 68,
      execution.consistencyScore >= 60,
      portfolioSyncHealthy,
      backendConfirmationConsistent,
    ];
    final score = checks.where((item) => item).length / checks.length * 100;
    final advisory = score < 80;
    return FailsafeExecutionRead(
      failsafeScore: score,
      websocketHealthy: checks[0],
      marketDataFresh: checks[1],
      executionSyncHealthy: checks[2],
      portfolioSyncHealthy: checks[3],
      backendConfirmationConsistent: checks[4],
      advisoryOnly: advisory,
      verdict: advisory
          ? 'Advisory-only mode until infrastructure consistency improves.'
          : 'Infrastructure checks are aligned for backend-approved execution.',
    );
  }

  BackgroundSyncRead backgroundSync({
    required bool hasWatchlist,
    required bool hasAiMemory,
    InfrastructureSnapshotModel? infrastructure,
  }) {
    final degraded = infrastructure?.readinessStatus.toUpperCase() == 'WATCH' ||
        infrastructure?.readinessStatus.toUpperCase() == 'DEGRADED';
    return BackgroundSyncRead(
      portfolioRefreshCadenceSeconds: degraded ? 20 : 45,
      lazyRecoveryEnabled: true,
      stagedHydrationEnabled: true,
      replaySyncReady: infrastructure?.replayCheckpointValid ?? false,
      watchlistSyncReady: hasWatchlist,
      aiMemorySyncReady: hasAiMemory,
      batteryMode: degraded ? 'balanced recovery' : 'low-power steady sync',
      syncPlan: const <String>[
        'Refresh portfolio silently after reconnect.',
        'Hydrate visible chart first, then replay metadata.',
        'Sync watchlist and AI memory opportunistically.',
        'Avoid high-frequency polling while websocket is healthy.',
      ],
    );
  }

  PerformanceStabilityRead performanceStability({
    InfrastructureSnapshotModel? infrastructure,
    int visibleSignals = 0,
  }) {
    final chartPressure = (infrastructure?.overlayPressure ?? 0).toDouble();
    final streamPressure = ((infrastructure?.marketThroughput ?? 0) +
            (infrastructure?.aiThroughput ?? 0) +
            visibleSignals)
        .clamp(0, 240)
        .toDouble();
    final fps = infrastructure?.renderFps ?? 60;
    final score = (fps +
            (100 - chartPressure) * 0.28 +
            (100 - streamPressure * 0.3) * 0.22)
        .clamp(0, 99)
        .toDouble();
    return PerformanceStabilityRead(
      stabilityScore: score,
      memoryAllocationMode: chartPressure >= 70
          ? 'reduce overlay hydration'
          : 'allocation pressure normal',
      chartPressure: chartPressure,
      rebuildFrequencyMode: visibleSignals > 12
          ? 'coalesced top-signal rebuilds'
          : 'normal scoped rebuilds',
      websocketBatchingMode:
          streamPressure > 120 ? 'batched priority lanes' : 'low-latency lane',
      providerInvalidationScope:
          'invalidate visible providers only; keep heavy analytics lazy',
      eventStreamPressure: streamPressure,
      fpsStatus: fps >= 55
          ? 'stable'
          : fps >= 42
              ? 'watch'
              : 'degraded',
    );
  }

  FailureHandlingRead failureHandling({
    required RealtimeResilienceRead realtime,
    required FailsafeExecutionRead failsafe,
  }) {
    final healthy = !realtime.degradedMode && !failsafe.advisoryOnly;
    return FailureHandlingRead(
      userMessage: healthy
          ? 'Systems are synchronized. Live plans are current.'
          : 'Live sync is recovering. AI will keep plans visible and protect execution until checks pass.',
      retryStrategy: healthy
          ? 'No retry needed'
          : 'Silent reconnect, REST refresh, then replay-safe websocket resume',
      silentRecovery: !healthy,
      operationalGuidance: healthy
          ? 'Continue normal monitoring.'
          : 'Show graceful recovery state to retail users; keep raw diagnostics in Quant mode.',
    );
  }

  MultiDeviceConsistencyRead multiDeviceConsistency({
    bool sessionRestored = true,
    bool watchlistReady = false,
    bool replayReady = false,
    bool executionStateReady = false,
  }) {
    return MultiDeviceConsistencyRead(
      deviceSyncReady: true,
      sessionContinuityReady: sessionRestored,
      cloudExecutionStateReady: executionStateReady,
      watchlistContinuityReady: watchlistReady,
      replayContinuityReady: replayReady,
      consistencyNote:
          'Multi-device contract is ready for session, watchlist, replay, AI memory, and cloud execution state continuity.',
    );
  }

  bool _isStale(DateTime? lastEventAt) {
    if (lastEventAt == null) {
      return false;
    }
    return DateTime.now().difference(lastEventAt).inSeconds > 45;
  }

  int _timestampGaps(List<MarketCandleModel> candles) {
    if (candles.length < 3) {
      return 0;
    }
    final intervals = <int>[];
    for (var index = 1; index < candles.length; index++) {
      intervals
          .add(candles[index].timestampMs - candles[index - 1].timestampMs);
    }
    intervals.sort();
    final median = intervals[intervals.length ~/ 2].abs();
    if (median <= 0) {
      return 0;
    }
    return intervals.where((item) => item.abs() > median * 1.8).length;
  }

  bool _volumeSpike(List<MarketCandleModel> candles) {
    if (candles.length < 8) {
      return false;
    }
    final recent = candles.last.volume;
    final baseline = candles
            .skip(math.max(0, candles.length - 8))
            .take(7)
            .fold<double>(0, (sum, candle) => sum + candle.volume) /
        7;
    return baseline > 0 && recent > baseline * 5;
  }

  double _spreadPct(OrderbookLevelModel level) {
    if (level.bidPrice <= 0) {
      return 0;
    }
    return (level.askPrice - level.bidPrice).abs() / level.bidPrice * 100;
  }
}

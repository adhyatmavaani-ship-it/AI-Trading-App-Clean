class InfrastructureSnapshotModel {
  const InfrastructureSnapshotModel({
    required this.timestamp,
    required this.redisFallback,
    required this.redisLatencyMs,
    required this.websocketSequenceGaps,
    required this.websocketReplayFrequency,
    required this.staleFeedCount,
    required this.aiQueueDepth,
    required this.aiWorkerLatencyMs,
    required this.renderFps,
    required this.overlayPressure,
    required this.marketThroughput,
    required this.aiThroughput,
    required this.executionLatencyMs,
    required this.gpuQueueDepth,
    required this.gpuLatencyMs,
    required this.gpuRuntime,
    required this.haMode,
    required this.haActions,
    required this.sloMode,
    required this.sloScore,
    required this.sloActions,
    required this.replayCheckpointValid,
    required this.incidentSeverity,
    required this.incidentStatus,
    required this.retentionMode,
    required this.capacityScaleMode,
    required this.recommendedWebsocketInstances,
    required this.recommendedAiWorkers,
    required this.recommendedGpuWorkers,
    required this.runbookSteps,
    required this.releaseStatus,
    required this.releaseBlockerCount,
    required this.canaryMode,
    required this.canarySteps,
    required this.rollbackRecommended,
    required this.rollbackStrategy,
    required this.backupStatus,
    required this.auditManifestVersion,
    required this.configDriftState,
    required this.configDriftCount,
    required this.syntheticProbeMode,
    required this.syntheticProbeCount,
    required this.disasterRecoveryState,
    required this.disasterRecoveryDrillRequired,
    required this.complianceState,
    required this.complianceGapCount,
    required this.readinessStatus,
    required this.readinessScore,
    required this.readinessActions,
    required this.brokers,
  });

  final String timestamp;
  final bool redisFallback;
  final double redisLatencyMs;
  final int websocketSequenceGaps;
  final int websocketReplayFrequency;
  final int staleFeedCount;
  final int aiQueueDepth;
  final double aiWorkerLatencyMs;
  final double renderFps;
  final double overlayPressure;
  final int marketThroughput;
  final int aiThroughput;
  final double executionLatencyMs;
  final int gpuQueueDepth;
  final double gpuLatencyMs;
  final String gpuRuntime;
  final String haMode;
  final List<String> haActions;
  final String sloMode;
  final double sloScore;
  final List<String> sloActions;
  final bool replayCheckpointValid;
  final String incidentSeverity;
  final String incidentStatus;
  final String retentionMode;
  final String capacityScaleMode;
  final int recommendedWebsocketInstances;
  final int recommendedAiWorkers;
  final int recommendedGpuWorkers;
  final List<String> runbookSteps;
  final String releaseStatus;
  final int releaseBlockerCount;
  final String canaryMode;
  final List<int> canarySteps;
  final bool rollbackRecommended;
  final String rollbackStrategy;
  final String backupStatus;
  final String auditManifestVersion;
  final String configDriftState;
  final int configDriftCount;
  final String syntheticProbeMode;
  final int syntheticProbeCount;
  final String disasterRecoveryState;
  final bool disasterRecoveryDrillRequired;
  final String complianceState;
  final int complianceGapCount;
  final String readinessStatus;
  final double readinessScore;
  final List<String> readinessActions;
  final List<String> brokers;

  factory InfrastructureSnapshotModel.fromJson(Map<String, dynamic> json) {
    final redis = Map<String, dynamic>.from(
      json['redis'] as Map? ?? const <String, dynamic>{},
    );
    final websocket = Map<String, dynamic>.from(
      json['websocket'] as Map? ?? const <String, dynamic>{},
    );
    final aiWorkers = Map<String, dynamic>.from(
      json['ai_workers'] as Map? ?? const <String, dynamic>{},
    );
    final rendering = Map<String, dynamic>.from(
      json['rendering'] as Map? ?? const <String, dynamic>{},
    );
    final eventBus = Map<String, dynamic>.from(
      json['event_bus'] as Map? ?? const <String, dynamic>{},
    );
    final gpuInference = Map<String, dynamic>.from(
      json['gpu_inference'] as Map? ?? const <String, dynamic>{},
    );
    final highAvailability = Map<String, dynamic>.from(
      json['high_availability'] as Map? ?? const <String, dynamic>{},
    );
    final slo = Map<String, dynamic>.from(
      json['slo'] as Map? ?? const <String, dynamic>{},
    );
    final replayCheckpoint = Map<String, dynamic>.from(
      json['replay_checkpoint'] as Map? ?? const <String, dynamic>{},
    );
    final incident = Map<String, dynamic>.from(
      json['incident'] as Map? ?? const <String, dynamic>{},
    );
    final retention = Map<String, dynamic>.from(
      json['retention'] as Map? ?? const <String, dynamic>{},
    );
    final capacity = Map<String, dynamic>.from(
      json['capacity'] as Map? ?? const <String, dynamic>{},
    );
    final runbook = Map<String, dynamic>.from(
      json['runbook'] as Map? ?? const <String, dynamic>{},
    );
    final release = Map<String, dynamic>.from(
      json['release'] as Map? ?? const <String, dynamic>{},
    );
    final canary = Map<String, dynamic>.from(
      json['canary'] as Map? ?? const <String, dynamic>{},
    );
    final rollback = Map<String, dynamic>.from(
      json['rollback'] as Map? ?? const <String, dynamic>{},
    );
    final backup = Map<String, dynamic>.from(
      json['backup'] as Map? ?? const <String, dynamic>{},
    );
    final auditExport = Map<String, dynamic>.from(
      json['audit_export'] as Map? ?? const <String, dynamic>{},
    );
    final configDrift = Map<String, dynamic>.from(
      json['config_drift'] as Map? ?? const <String, dynamic>{},
    );
    final syntheticProbes = Map<String, dynamic>.from(
      json['synthetic_probes'] as Map? ?? const <String, dynamic>{},
    );
    final disasterRecovery = Map<String, dynamic>.from(
      json['disaster_recovery'] as Map? ?? const <String, dynamic>{},
    );
    final compliance = Map<String, dynamic>.from(
      json['compliance'] as Map? ?? const <String, dynamic>{},
    );
    final readiness = Map<String, dynamic>.from(
      json['readiness'] as Map? ?? const <String, dynamic>{},
    );
    final brokers = (json['brokers'] as List<dynamic>? ?? const <dynamic>[])
        .whereType<Map>()
        .map((item) => (item['broker'] ?? '').toString())
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
    return InfrastructureSnapshotModel(
      timestamp: json['timestamp'] as String? ?? '',
      redisFallback: redis['fallback'] == true,
      redisLatencyMs: (redis['latency_ms'] as num?)?.toDouble() ?? 0,
      websocketSequenceGaps:
          (websocket['sequence_gaps'] as num?)?.toInt() ?? 0,
      websocketReplayFrequency:
          (websocket['replay_frequency'] as num?)?.toInt() ?? 0,
      staleFeedCount: (websocket['stale_feed_count'] as num?)?.toInt() ?? 0,
      aiQueueDepth: (aiWorkers['queue_depth'] as num?)?.toInt() ?? 0,
      aiWorkerLatencyMs: (aiWorkers['latency_ms'] as num?)?.toDouble() ?? 0,
      renderFps: (rendering['fps'] as num?)?.toDouble() ?? 0,
      overlayPressure: (rendering['overlay_pressure'] as num?)?.toDouble() ?? 0,
      marketThroughput: (eventBus['market_throughput'] as num?)?.toInt() ?? 0,
      aiThroughput: (eventBus['ai_throughput'] as num?)?.toInt() ?? 0,
      executionLatencyMs: (json['execution_latency_ms'] as num?)?.toDouble() ?? 0,
      gpuQueueDepth: (gpuInference['queue_depth'] as num?)?.toInt() ?? 0,
      gpuLatencyMs: (gpuInference['latency_ms'] as num?)?.toDouble() ?? 0,
      gpuRuntime: gpuInference['runtime'] as String? ?? 'onnx_ready',
      haMode: highAvailability['mode'] as String? ?? 'UNKNOWN',
      haActions:
          (highAvailability['actions'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .toList(growable: false),
      sloMode: slo['mode'] as String? ?? 'UNKNOWN',
      sloScore: (slo['score'] as num?)?.toDouble() ?? 0,
      sloActions: (slo['actions'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(growable: false),
      replayCheckpointValid: replayCheckpoint['valid'] == true,
      incidentSeverity: incident['severity'] as String? ?? 'UNKNOWN',
      incidentStatus: incident['status'] as String? ?? 'UNKNOWN',
      retentionMode: retention['mode'] as String? ?? 'UNKNOWN',
      capacityScaleMode: capacity['scale_mode'] as String? ?? 'UNKNOWN',
      recommendedWebsocketInstances:
          (capacity['websocket_instances'] as num?)?.toInt() ?? 0,
      recommendedAiWorkers: (capacity['ai_workers'] as num?)?.toInt() ?? 0,
      recommendedGpuWorkers: (capacity['gpu_workers'] as num?)?.toInt() ?? 0,
      runbookSteps: (runbook['steps'] as List<dynamic>? ?? const <dynamic>[])
          .map((item) => item.toString())
          .toList(growable: false),
      releaseStatus: release['status'] as String? ?? 'UNKNOWN',
      releaseBlockerCount:
          (release['blockers'] as List<dynamic>? ?? const <dynamic>[]).length,
      canaryMode: canary['mode'] as String? ?? 'UNKNOWN',
      canarySteps: (canary['traffic_steps'] as List<dynamic>? ??
              const <dynamic>[])
          .whereType<num>()
          .map((item) => item.toInt())
          .toList(growable: false),
      rollbackRecommended: rollback['recommended'] == true,
      rollbackStrategy: rollback['strategy'] as String? ?? 'UNKNOWN',
      backupStatus: backup['status'] as String? ?? 'UNKNOWN',
      auditManifestVersion:
          auditExport['manifest_version'] as String? ?? 'unknown',
      configDriftState: configDrift['state'] as String? ?? 'UNKNOWN',
      configDriftCount: (configDrift['drift_count'] as num?)?.toInt() ?? 0,
      syntheticProbeMode: syntheticProbes['mode'] as String? ?? 'UNKNOWN',
      syntheticProbeCount:
          (syntheticProbes['probes'] as List<dynamic>? ?? const <dynamic>[])
              .length,
      disasterRecoveryState:
          disasterRecovery['state'] as String? ?? 'UNKNOWN',
      disasterRecoveryDrillRequired:
          disasterRecovery['drill_required'] == true,
      complianceState: compliance['state'] as String? ?? 'UNKNOWN',
      complianceGapCount:
          (compliance['gaps'] as List<dynamic>? ?? const <dynamic>[]).length,
      readinessStatus: readiness['status'] as String? ?? 'UNKNOWN',
      readinessScore: (readiness['score'] as num?)?.toDouble() ?? 0,
      readinessActions:
          (readiness['actions'] as List<dynamic>? ?? const <dynamic>[])
              .map((item) => item.toString())
              .toList(growable: false),
      brokers: brokers,
    );
  }
}

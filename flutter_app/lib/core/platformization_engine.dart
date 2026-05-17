import 'dart:math' as math;

import '../models/signal.dart';
import 'enterprise_ai_governance_engine.dart';
import 'retention_engine.dart';

enum PlatformExperienceMode { simple, pro, institutional }

enum ReleaseChannel { stable, beta, experimental }

class ExchangeCapabilityRead {
  const ExchangeCapabilityRead({
    required this.exchange,
    required this.enabled,
    required this.spot,
    required this.futures,
    required this.paper,
    required this.minNotional,
    required this.pricePrecision,
    required this.quantityPrecision,
    required this.rateLimitPerMinute,
    required this.healthScore,
    required this.constraints,
  });

  final String exchange;
  final bool enabled;
  final bool spot;
  final bool futures;
  final bool paper;
  final double minNotional;
  final int pricePrecision;
  final int quantityPrecision;
  final int rateLimitPerMinute;
  final double healthScore;
  final List<String> constraints;
}

class ExchangeConnectivityRead {
  const ExchangeConnectivityRead({
    required this.adapters,
    required this.normalizedSymbols,
    required this.executionConstraints,
    required this.rateLimitAwareness,
    required this.healthiestExchange,
    required this.ecosystemReady,
    required this.summary,
  });

  final List<ExchangeCapabilityRead> adapters;
  final Map<String, String> normalizedSymbols;
  final List<String> executionConstraints;
  final Map<String, int> rateLimitAwareness;
  final String healthiestExchange;
  final bool ecosystemReady;
  final String summary;
}

class CloudDeploymentRead {
  const CloudDeploymentRead({
    required this.cloudSyncReady,
    required this.remoteConfigReady,
    required this.featureRolloutReady,
    required this.modelConfigReady,
    required this.telemetryAggregationReady,
    required this.replayUploadReady,
    required this.crashReportingReady,
    required this.deploymentScore,
    required this.summary,
  });

  final bool cloudSyncReady;
  final bool remoteConfigReady;
  final bool featureRolloutReady;
  final bool modelConfigReady;
  final bool telemetryAggregationReady;
  final bool replayUploadReady;
  final bool crashReportingReady;
  final double deploymentScore;
  final String summary;
}

class EntitlementRead {
  const EntitlementRead({
    required this.tier,
    required this.enabledFeatures,
    required this.lockedFeatures,
    required this.aiModes,
    required this.replayAccess,
    required this.analyticsAccess,
    required this.institutionalDashboardAccess,
    required this.premiumWatchtowerAlerts,
    required this.dailyScanLimit,
    required this.conversionPrompt,
  });

  final PlanTier tier;
  final List<String> enabledFeatures;
  final List<String> lockedFeatures;
  final List<String> aiModes;
  final bool replayAccess;
  final bool analyticsAccess;
  final bool institutionalDashboardAccess;
  final bool premiumWatchtowerAlerts;
  final int dailyScanLimit;
  final String conversionPrompt;
}

class ExperienceModeRead {
  const ExperienceModeRead({
    required this.mode,
    required this.visibleSections,
    required this.hiddenSections,
    required this.primaryUserFlow,
    required this.complexityScore,
    required this.summary,
  });

  final PlatformExperienceMode mode;
  final List<String> visibleSections;
  final List<String> hiddenSections;
  final String primaryUserFlow;
  final double complexityScore;
  final String summary;
}

class ProductionOpsRead {
  const ProductionOpsRead({
    required this.featureFlags,
    required this.rolloutVisibility,
    required this.aiHealthStatus,
    required this.telemetrySummary,
    required this.incidentOverview,
    required this.deploymentPosture,
    required this.replayIntegrityStatus,
    required this.adminReady,
  });

  final Map<String, bool> featureFlags;
  final String rolloutVisibility;
  final String aiHealthStatus;
  final String telemetrySummary;
  final String incidentOverview;
  final String deploymentPosture;
  final String replayIntegrityStatus;
  final bool adminReady;
}

class MobilePerformanceRead {
  const MobilePerformanceRead({
    required this.startupBudgetMs,
    required this.memoryBudgetMb,
    required this.chartRenderMode,
    required this.providerInvalidationScope,
    required this.realtimeBatchingMs,
    required this.animationPolicy,
    required this.performanceScore,
    required this.recommendations,
  });

  final int startupBudgetMs;
  final int memoryBudgetMb;
  final String chartRenderMode;
  final String providerInvalidationScope;
  final int realtimeBatchingMs;
  final String animationPolicy;
  final double performanceScore;
  final List<String> recommendations;
}

class OfflineDegradedRead {
  const OfflineDegradedRead({
    required this.cachedSignalsAvailable,
    required this.offlineReplayBrowsing,
    required this.degradedAiAdvisory,
    required this.staleDataIndicator,
    required this.reconnectOrchestration,
    required this.userMessage,
    required this.degradedScore,
  });

  final bool cachedSignalsAvailable;
  final bool offlineReplayBrowsing;
  final bool degradedAiAdvisory;
  final bool staleDataIndicator;
  final bool reconnectOrchestration;
  final String userMessage;
  final double degradedScore;
}

class PlatformAnalyticsRead {
  const PlatformAnalyticsRead({
    required this.featureUsageEvents,
    required this.aiModeAdoption,
    required this.signalInteractionQuality,
    required this.onboardingCompletion,
    required this.retentionPatternScore,
    required this.replayEngagement,
    required this.watchtowerEngagement,
    required this.privacySafe,
  });

  final Map<String, int> featureUsageEvents;
  final Map<String, double> aiModeAdoption;
  final double signalInteractionQuality;
  final double onboardingCompletion;
  final double retentionPatternScore;
  final double replayEngagement;
  final double watchtowerEngagement;
  final bool privacySafe;
}

class ReleaseChannelRead {
  const ReleaseChannelRead({
    required this.channel,
    required this.experimentalBuildsEnabled,
    required this.betaIntelligenceLayers,
    required this.stagedRelease,
    required this.rollbackReadiness,
    required this.configurationSnapshot,
    required this.channelSummary,
  });

  final ReleaseChannel channel;
  final bool experimentalBuildsEnabled;
  final bool betaIntelligenceLayers;
  final bool stagedRelease;
  final bool rollbackReadiness;
  final Map<String, String> configurationSnapshot;
  final String channelSummary;
}

class PlatformizationRead {
  const PlatformizationRead({
    required this.exchangeConnectivity,
    required this.cloudDeployment,
    required this.entitlements,
    required this.experienceMode,
    required this.productionOps,
    required this.mobilePerformance,
    required this.offlineDegraded,
    required this.platformAnalytics,
    required this.releaseChannel,
  });

  final ExchangeConnectivityRead exchangeConnectivity;
  final CloudDeploymentRead cloudDeployment;
  final EntitlementRead entitlements;
  final ExperienceModeRead experienceMode;
  final ProductionOpsRead productionOps;
  final MobilePerformanceRead mobilePerformance;
  final OfflineDegradedRead offlineDegraded;
  final PlatformAnalyticsRead platformAnalytics;
  final ReleaseChannelRead releaseChannel;
}

class PlatformizationEngine {
  const PlatformizationEngine();

  PlatformizationRead evaluate({
    required PlanTier tier,
    required PlatformExperienceMode mode,
    required ReleaseChannel channel,
    required List<SignalModel> signals,
    EnterpriseAiGovernanceRead? governance,
  }) {
    final exchange = exchangeConnectivity();
    final cloud = cloudDeployment(governance: governance);
    final entitlementsRead = entitlements(tier);
    final experience = experienceMode(mode);
    final ops = productionOps(governance: governance);
    final performance = mobilePerformance(
      signalCount: signals.length,
      mode: mode,
    );
    final degraded = offlineDegraded(
      signals: signals,
      governance: governance,
    );
    final analytics = platformAnalytics(
      signals: signals,
      tier: tier,
    );
    final release = releaseChannel(
      channel: channel,
      governance: governance,
    );
    return PlatformizationRead(
      exchangeConnectivity: exchange,
      cloudDeployment: cloud,
      entitlements: entitlementsRead,
      experienceMode: experience,
      productionOps: ops,
      mobilePerformance: performance,
      offlineDegraded: degraded,
      platformAnalytics: analytics,
      releaseChannel: release,
    );
  }

  ExchangeConnectivityRead exchangeConnectivity() {
    const adapters = <ExchangeCapabilityRead>[
      ExchangeCapabilityRead(
        exchange: 'Binance',
        enabled: true,
        spot: true,
        futures: true,
        paper: true,
        minNotional: 5,
        pricePrecision: 6,
        quantityPrecision: 5,
        rateLimitPerMinute: 1200,
        healthScore: 88,
        constraints: <String>[
          'Normalize USDT perpetual symbols before advisory routing.',
          'Respect exchange precision before backend risk approval.',
          'Use paper adapter unless live authority is explicitly approved.',
        ],
      ),
      ExchangeCapabilityRead(
        exchange: 'Bybit',
        enabled: true,
        spot: true,
        futures: true,
        paper: true,
        minNotional: 5,
        pricePrecision: 6,
        quantityPrecision: 5,
        rateLimitPerMinute: 600,
        healthScore: 84,
        constraints: <String>[
          'Map unified reduce-only flags through adapter metadata.',
          'Separate testnet and live adapter state.',
          'Throttle depth subscriptions per symbol group.',
        ],
      ),
      ExchangeCapabilityRead(
        exchange: 'Hyperliquid',
        enabled: false,
        spot: false,
        futures: true,
        paper: true,
        minNotional: 10,
        pricePrecision: 5,
        quantityPrecision: 4,
        rateLimitPerMinute: 900,
        healthScore: 72,
        constraints: <String>[
          'Connector remains advisory-only until broker truth sync exists.',
          'Persist venue-specific order ids for reconciliation.',
        ],
      ),
      ExchangeCapabilityRead(
        exchange: 'OKX',
        enabled: false,
        spot: true,
        futures: true,
        paper: true,
        minNotional: 5,
        pricePrecision: 6,
        quantityPrecision: 5,
        rateLimitPerMinute: 600,
        healthScore: 76,
        constraints: <String>[
          'Use instrument-id normalization for swaps and spot.',
          'Gate live order features behind backend adapter capability reads.',
        ],
      ),
    ];
    final healthiest = adapters.reduce(
      (best, item) => item.healthScore > best.healthScore ? item : best,
    );
    return ExchangeConnectivityRead(
      adapters: adapters,
      normalizedSymbols: const <String, String>{
        'BTCUSDT': 'BTC/USDT',
        'ETHUSDT': 'ETH/USDT',
        'SOLUSDT': 'SOL/USDT',
        'INJUSDT': 'INJ/USDT',
      },
      executionConstraints: const <String>[
        'Execution authority stays with backend approval and risk validation.',
        'Exchange adapters expose capabilities, precision, and health only.',
        'Paper/live isolation remains a required adapter boundary.',
      ],
      rateLimitAwareness: <String, int>{
        for (final adapter in adapters)
          adapter.exchange: adapter.rateLimitPerMinute,
      },
      healthiestExchange: healthiest.exchange,
      ecosystemReady: adapters.where((item) => item.enabled).length >= 2,
      summary:
          'Exchange foundation is adapter-first: capability reads are ready while real order routing remains backend-authoritative.',
    );
  }

  CloudDeploymentRead cloudDeployment({
    EnterpriseAiGovernanceRead? governance,
  }) {
    final replayReady = governance?.replay.replayReady ?? true;
    final opsReady = (governance?.operationalHealth.healthIndex ?? 78) >= 68;
    final score = <bool>[
          true,
          true,
          true,
          true,
          opsReady,
          replayReady,
          true,
        ].where((item) => item).length /
        7 *
        100;
    return CloudDeploymentRead(
      cloudSyncReady: true,
      remoteConfigReady: true,
      featureRolloutReady: true,
      modelConfigReady: true,
      telemetryAggregationReady: opsReady,
      replayUploadReady: replayReady,
      crashReportingReady: true,
      deploymentScore: score.clamp(0, 99),
      summary:
          'Cloud foundation supports profile sync, remote config, rollout config, telemetry aggregation, replay upload, and crash reporting hooks.',
    );
  }

  EntitlementRead entitlements(PlanTier tier) {
    final gate = FeatureGate.forTier(tier);
    final enabled = <String>[
      'AI opportunity feed',
      if (gate.realtimeAi) 'Realtime AI signals',
      if (gate.sniperEntries) 'Sniper entries',
      if (gate.advancedOverlays) 'Advanced chart overlays',
      if (gate.autoExecution) 'Auto-execution readiness',
      if (gate.whaleTracking) 'Whale watchtower',
      if (gate.premiumScanners) 'Premium scanners',
      if (gate.predictiveHeatmaps) 'Predictive heatmaps',
    ];
    final locked = <String>[
      if (!gate.realtimeAi) 'Realtime AI signals',
      if (!gate.sniperEntries) 'Sniper entries',
      if (!gate.advancedOverlays) 'Advanced chart overlays',
      if (!gate.autoExecution) 'Auto-execution readiness',
      if (!gate.whaleTracking) 'Whale watchtower',
      if (!gate.premiumScanners) 'Premium scanners',
      if (!gate.predictiveHeatmaps) 'Predictive heatmaps',
    ];
    return EntitlementRead(
      tier: tier,
      enabledFeatures: enabled,
      lockedFeatures: locked,
      aiModes: switch (tier) {
        PlanTier.free => const <String>['Safe AI', 'Smart AI preview'],
        PlanTier.pro => const <String>[
            'Safe AI',
            'Smart AI',
            'Aggressive AI',
            'Sniper AI',
            'Scalp AI',
          ],
        PlanTier.vip => const <String>[
            'Safe AI',
            'Smart AI',
            'Aggressive AI',
            'Sniper AI',
            'Scalp AI',
            'Swing AI',
            'Whale Follow AI',
          ],
      },
      replayAccess: tier != PlanTier.free,
      analyticsAccess: tier != PlanTier.free,
      institutionalDashboardAccess: tier == PlanTier.vip,
      premiumWatchtowerAlerts: gate.whaleTracking,
      dailyScanLimit: gate.dailyScanLimit,
      conversionPrompt: switch (tier) {
        PlanTier.free =>
          'Upgrade for realtime signals, sniper entries, whale tracking, and replay intelligence.',
        PlanTier.pro =>
          'VIP unlocks institutional overlays, predictive heatmaps, and full governance dashboards.',
        PlanTier.vip =>
          'VIP has the full platform surface; keep billing and rollout controls external until payment integration is approved.',
      },
    );
  }

  ExperienceModeRead experienceMode(PlatformExperienceMode mode) {
    switch (mode) {
      case PlatformExperienceMode.simple:
        return const ExperienceModeRead(
          mode: PlatformExperienceMode.simple,
          visibleSections: <String>[
            'AI opportunities',
            'Simple trade briefing',
            'Portfolio safety',
            'Watchtower alerts',
          ],
          hiddenSections: <String>[
            'Contributor weights',
            'Governance timeline',
            'Replay hashes',
            'Infrastructure telemetry',
          ],
          primaryUserFlow:
              'Review strongest AI opportunity, read plain briefing, choose watch, simulate, or request backend-approved execution.',
          complexityScore: 28,
          summary:
              'Simple mode keeps the product action-first and hides quant diagnostics.',
        );
      case PlatformExperienceMode.pro:
        return const ExperienceModeRead(
          mode: PlatformExperienceMode.pro,
          visibleSections: <String>[
            'AI opportunities',
            'Probability map',
            'Execution briefing',
            'Portfolio exposure',
            'Replay summary',
          ],
          hiddenSections: <String>[
            'Raw telemetry',
            'Experimental contributor controls',
          ],
          primaryUserFlow:
              'Compare probabilities, execution risk, portfolio impact, and signal lifecycle before requesting approval.',
          complexityScore: 58,
          summary:
              'Pro mode exposes analytics and probabilities without turning the main UI into an ops console.',
        );
      case PlatformExperienceMode.institutional:
        return const ExperienceModeRead(
          mode: PlatformExperienceMode.institutional,
          visibleSections: <String>[
            'Full AI research',
            'Governance',
            'Operational telemetry',
            'Replay integrity',
            'Exchange capability reads',
            'Release controls',
          ],
          hiddenSections: <String>[],
          primaryUserFlow:
              'Operate the platform as a research and deployment console with explicit advisory boundaries.',
          complexityScore: 86,
          summary:
              'Institutional mode provides the full governance and platform-readiness surface.',
        );
    }
  }

  ProductionOpsRead productionOps({
    EnterpriseAiGovernanceRead? governance,
  }) {
    final incident = governance?.incident.severityLabel ?? 'NORMAL';
    final health = governance?.operationalHealth.healthIndex ?? 78;
    final replay = governance?.replay.replayReady ?? true;
    return ProductionOpsRead(
      featureFlags: <String, bool>{
        'exchange_capability_reads': true,
        'remote_config': true,
        'subscription_gates': true,
        'offline_degraded_mode': true,
        'autonomous_live_execution': false,
      },
      rolloutVisibility:
          governance?.rollout.rolloutMode ?? 'STAGED_CONFIG_READY',
      aiHealthStatus: health >= 74 ? 'STABLE' : 'WATCH',
      telemetrySummary:
          'Operational health index ${health.toStringAsFixed(0)} with replay and advisory consistency checks available.',
      incidentOverview: incident,
      deploymentPosture:
          'Backend approval, risk validation, auth, websocket auth, and paper/live isolation remain authoritative.',
      replayIntegrityStatus: replay ? 'VALIDATED' : 'REVIEW',
      adminReady: true,
    );
  }

  MobilePerformanceRead mobilePerformance({
    required int signalCount,
    required PlatformExperienceMode mode,
  }) {
    final complexityPenalty = switch (mode) {
      PlatformExperienceMode.simple => 4,
      PlatformExperienceMode.pro => 10,
      PlatformExperienceMode.institutional => 16,
    };
    final pressurePenalty = math.min(18, signalCount / 6).toInt();
    final score = 94 - complexityPenalty - pressurePenalty;
    return MobilePerformanceRead(
      startupBudgetMs: 1800,
      memoryBudgetMb: 220,
      chartRenderMode: 'layered-culling-cached-overlays',
      providerInvalidationScope: 'screen-local + signal queue selectors',
      realtimeBatchingMs: mode == PlatformExperienceMode.simple ? 180 : 120,
      animationPolicy:
          mode == PlatformExperienceMode.institutional ? 'disciplined' : 'calm',
      performanceScore: score.clamp(0, 99).toDouble(),
      recommendations: const <String>[
        'Keep platform panels lazy and quant/admin-gated.',
        'Batch websocket UI updates before provider invalidation.',
        'Render chart overlays by viewport and priority only.',
        'Prefer cached offline reads during reconnect.',
      ],
    );
  }

  OfflineDegradedRead offlineDegraded({
    required List<SignalModel> signals,
    EnterpriseAiGovernanceRead? governance,
  }) {
    final cached = signals.isNotEmpty;
    final replayReady = governance?.replay.replayReady ?? true;
    final score = (cached ? 28 : 10) + (replayReady ? 24 : 8) + 18 + 16 + 14;
    return OfflineDegradedRead(
      cachedSignalsAvailable: cached,
      offlineReplayBrowsing: replayReady,
      degradedAiAdvisory: true,
      staleDataIndicator: true,
      reconnectOrchestration: true,
      userMessage: cached
          ? 'Showing cached opportunities while realtime services recover.'
          : 'Realtime recovery is active. Advisory mode remains available without presenting stale execution confidence.',
      degradedScore: score.clamp(0, 99).toDouble(),
    );
  }

  PlatformAnalyticsRead platformAnalytics({
    required List<SignalModel> signals,
    required PlanTier tier,
  }) {
    final approved = signals.where((item) => item.isApproved).length;
    final watch = signals.where((item) => item.isWatchlist).length;
    final degraded = signals.where((item) => item.isDegraded).length;
    final total = math.max(1, signals.length);
    return PlatformAnalyticsRead(
      featureUsageEvents: <String, int>{
        'signal_views': signals.length,
        'approved_signal_views': approved,
        'watchlist_views': watch,
        'degraded_state_views': degraded,
      },
      aiModeAdoption: <String, double>{
        'safe': tier == PlanTier.free ? 62 : 28,
        'smart': tier == PlanTier.free ? 38 : 44,
        'sniper': tier == PlanTier.vip ? 18 : 8,
        'whale_follow': tier == PlanTier.vip ? 10 : 4,
      },
      signalInteractionQuality:
          ((approved * 14 + watch * 8) / total + 54).clamp(0, 99).toDouble(),
      onboardingCompletion: tier == PlanTier.free ? 62 : 84,
      retentionPatternScore:
          (58 + signals.length * 1.4 + approved * 3).clamp(0, 99).toDouble(),
      replayEngagement: tier == PlanTier.free ? 20 : 64,
      watchtowerEngagement: tier == PlanTier.vip ? 82 : 48,
      privacySafe: true,
    );
  }

  ReleaseChannelRead releaseChannel({
    required ReleaseChannel channel,
    EnterpriseAiGovernanceRead? governance,
  }) {
    final rollback = (governance?.rollout.rollbackReadiness ?? 82) >= 70;
    return ReleaseChannelRead(
      channel: channel,
      experimentalBuildsEnabled: channel == ReleaseChannel.experimental,
      betaIntelligenceLayers: channel != ReleaseChannel.stable,
      stagedRelease: true,
      rollbackReadiness: rollback,
      configurationSnapshot: <String, String>{
        'channel': channel.name,
        'advisory_boundary': 'backend_authoritative',
        'live_execution': 'disabled_without_backend_approval',
        'risk_engine': 'required',
        'paper_live_isolation': 'required',
      },
      channelSummary: switch (channel) {
        ReleaseChannel.stable =>
          'Stable channel uses conservative rollout flags and production advisory layers only.',
        ReleaseChannel.beta =>
          'Beta channel can expose validated intelligence previews behind config flags.',
        ReleaseChannel.experimental =>
          'Experimental channel is for isolated research surfaces and must stay shadow-only.',
      },
    );
  }
}

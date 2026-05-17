import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/ai_opportunity_engine.dart';
import '../core/ai_personality_engine.dart';
import '../core/adaptive_ai_intelligence_engine.dart';
import '../core/adaptive_decision_core.dart';
import '../core/edge_validation_engine.dart';
import '../core/enterprise_ai_governance_engine.dart';
import '../core/evolving_ai_intelligence_engine.dart';
import '../core/error_mapper.dart';
import '../core/error_presenter.dart';
import '../core/institutional_intelligence_engine.dart';
import '../core/proprietary_ai_engine.dart';
import '../core/trading_operating_system_engine.dart';
import '../core/trading_palette.dart';
import '../features/activity/providers/activity_providers.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/retention/providers/retention_providers.dart';
import '../features/realtime/providers/realtime_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../models/activity.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/realtime_event.dart';
import '../models/signal.dart';
import '../models/user_pnl.dart';
import '../providers/app_bootstrap_provider.dart';
import '../widgets/ai_explanation_panel.dart';
import '../widgets/ai_signal_card.dart';
import '../widgets/adaptive_ai_widgets.dart';
import '../widgets/adaptive_decision_widgets.dart';
import '../widgets/edge_validation_widgets.dart';
import '../widgets/enterprise_governance_widgets.dart';
import '../widgets/evolving_ai_widgets.dart';
import '../widgets/glass_panel.dart';
import '../widgets/gradient_action_button.dart';
import '../widgets/institutional_trust_widgets.dart';
import '../widgets/live_energy_widgets.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pulse_wrapper.dart';
import '../widgets/proprietary_ai_widgets.dart';
import '../widgets/retention_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';
import '../widgets/trading_os_widgets.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({
    super.key,
    required this.onOpenTrade,
    required this.onOpenTradeSignal,
    required this.onOpenSignals,
  });

  final ValueChanged<String> onOpenTrade;
  final ValueChanged<SignalModel> onOpenTradeSignal;
  final VoidCallback onOpenSignals;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userId = ref.watch(activeUserIdProvider);
    final settings = ref.watch(appSettingsProvider);
    final settingsController = ref.read(appSettingsProvider.notifier);
    final pnlAsync = ref.watch(userPnLProvider(userId));
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final marketSummaryAsync = ref.watch(marketSummaryProvider);
    final marketUniverseAsync = ref.watch(marketUniverseProvider);
    final signalFeed = ref.watch(signalFeedProvider);
    final initialSignalsAsync = ref.watch(initialSignalsProvider);
    final activityFeed = ref.watch(activityFeedProvider);
    final initialActivityAsync = ref.watch(initialActivityHistoryProvider);
    final latestDashboardSummary =
        ref.watch(latestDashboardSummaryProvider(userId));
    final latestTradeUpdate = ref.watch(latestTradeUpdateProvider(userId));
    final aiMode = aiTradingModeFromRiskLevel(settings.riskLevel);
    final retention = ref.watch(retentionSnapshotProvider);
    final localMemory = ref.watch(localAiMemoryProvider);
    const MarketChartModel? chart = null;
    const institutionalEngine = InstitutionalIntelligenceEngine();
    const adaptiveEngine = AdaptiveAiIntelligenceEngine();
    const edgeEngine = EdgeValidationEngine();
    const operatingSystem = TradingOperatingSystemEngine();
    const proprietaryEngine = ProprietaryAiEngine();
    const decisionCore = AdaptiveDecisionCore();
    const evolvingEngine = EvolvingAiIntelligenceEngine();
    const governanceEngine = EnterpriseAiGovernanceEngine();
    final outcomeReports = edgeEngine.signalOutcomes(
      signalFeed.items,
      mode: aiMode,
    );
    final pnl = pnlAsync.valueOrNull;
    final activeTrades =
        activeTradesAsync.valueOrNull ?? const <ActiveTradeModel>[];
    final marketSummary = marketSummaryAsync.valueOrNull;
    final marketUniverse = marketUniverseAsync.valueOrNull;
    final portfolioRead = operatingSystem.portfolioIntelligence(
      pnl: pnl,
      trades: activeTrades,
      market: marketSummary,
    );
    final orchestrationRead = operatingSystem.multiAssetOrchestration(
      signals: signalFeed.items,
      trades: activeTrades,
      universe: marketUniverse,
    );
    final driftRead = edgeEngine.modelDrift(outcomeReports);
    final copilotRead = operatingSystem.copilot(
      portfolio: portfolioRead,
      orchestration: orchestrationRead,
      drift: driftRead,
      market: marketSummary,
    );
    final realtimeRead = operatingSystem.realtimeOrchestration(
      signalCount: signalFeed.items.length,
      activeTrades: activeTrades.length,
      chartActive: false,
    );
    final cloudSyncRead = operatingSystem.cloudProfileSync(
      onboardingComplete: retention.level > 0,
      watchlistItems: signalFeed.items.length,
      replayItems: outcomeReports.length,
      aiMemoryAvailable: localMemory.preferredAssets.isNotEmpty ||
          localMemory.preferredModes.isNotEmpty,
    );
    final journalRead = operatingSystem.professionalJournal(
      trades: activeTrades,
      decisions: signalFeed.items
          .take(4)
          .map((signal) =>
              edgeEngine.decisionJournal(signal, null, mode: aiMode))
          .toList(growable: false),
      market: marketSummary,
      tradeUpdate: latestTradeUpdate,
    );
    final watchtowerRead = operatingSystem.watchtower(
      portfolio: portfolioRead,
      drift: driftRead,
      market: marketSummary,
      tradeUpdate: latestTradeUpdate,
    );
    final scalabilityRead = operatingSystem.scalability(
      signalCount: signalFeed.items.length,
      chartActive: false,
    );

    final activeSignal = signalFeed.items.isNotEmpty
        ? signalFeed.items.first
        : initialSignalsAsync.valueOrNull?.firstOrNull;
    final proprietaryReads = activeSignal == null
        ? null
        : _DashboardProprietaryReads.from(
            engine: proprietaryEngine,
            signal: activeSignal,
            signals: signalFeed.items,
            outcomes: outcomeReports,
            drift: driftRead,
            market: marketSummary,
            chart: chart,
          );
    final adaptiveDecisionRead =
        activeSignal == null || proprietaryReads == null
            ? null
            : decisionCore.evaluate(
                signal: activeSignal,
                signals: signalFeed.items,
                outcomes: outcomeReports,
                market: marketSummary,
                chart: chart,
                dna: proprietaryReads.dna,
                pressure: proprietaryReads.pressure,
                edgeConfidence: proprietaryReads.edgeConfidence,
                regime: proprietaryReads.regime,
                drift: driftRead,
              );
    final evolvingRead =
        adaptiveDecisionRead == null || proprietaryReads == null
            ? null
            : evolvingEngine.evaluate(
                decision: adaptiveDecisionRead,
                signals: signalFeed.items,
                outcomes: outcomeReports,
                market: marketSummary,
                chart: chart,
                regime: proprietaryReads.regime,
              );
    final governanceRead = activeSignal == null ||
            adaptiveDecisionRead == null ||
            evolvingRead == null ||
            proprietaryReads == null
        ? null
        : governanceEngine.evaluate(
            signal: activeSignal,
            decision: adaptiveDecisionRead,
            evolving: evolvingRead,
            outcomes: outcomeReports,
            market: marketSummary,
            chart: chart,
            regime: proprietaryReads.regime,
          );
    final newsItems = activityFeed.items.isNotEmpty
        ? activityFeed.items
        : (initialActivityAsync.valueOrNull ?? const <ActivityItemModel>[]);

    return RefreshIndicator(
      onRefresh: () async => _refresh(ref, userId),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1200;
          final tablet = constraints.maxWidth >= 760;
          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
            children: <Widget>[
              _ActionHeroOpportunity(
                signal: activeSignal,
                mode: aiMode,
                autoModeEnabled: settings.engineEnabled,
                onOpenTradeSignal: onOpenTradeSignal,
                onOpenSignals: onOpenSignals,
                onToggleAutoMode: () => settingsController.saveEngineState(
                  userId,
                  enabled: !settings.engineEnabled,
                ),
              ),
              const SizedBox(height: 18),
              _SessionAlphaBoard(signals: signalFeed.items, mode: aiMode),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final professional = ProfessionalPerformancePanel(
                    performance: institutionalEngine.performanceFromSignals(
                      signalFeed.items,
                    ),
                  );
                  final memory = AiMemoryPanel(
                    memory: institutionalEngine
                        .memoryFromSignals(
                          signalFeed.items,
                          mode: aiMode,
                        )
                        .withLocalMemory(localMemory),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: professional),
                        const SizedBox(width: 18),
                        Expanded(child: memory),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      professional,
                      const SizedBox(height: 18),
                      memory,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              _LiveAiEventPanel(signals: signalFeed.items, mode: aiMode),
              const SizedBox(height: 18),
              if (proprietaryReads != null) ...<Widget>[
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final dna = MarketDnaPanel(
                      profile: proprietaryReads.dna,
                    );
                    final signature = AiEdgeSignaturePanel(
                      signature: proprietaryReads.signature,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: dna),
                          const SizedBox(width: 18),
                          Expanded(child: signature),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        dna,
                        const SizedBox(height: 18),
                        signature,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final pressure = PredictivePressurePanel(
                      pressure: proprietaryReads.pressure,
                    );
                    final confidence = EdgeConfidencePanel(
                      confidence: proprietaryReads.edgeConfidence,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: pressure),
                          const SizedBox(width: 18),
                          Expanded(child: confidence),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        pressure,
                        const SizedBox(height: 18),
                        confidence,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                AiMarketNarrativePanel(
                  narrative: proprietaryReads.narrative,
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final regime = MarketRegimeMapPanel(
                      regime: proprietaryReads.regime,
                    );
                    final watchtower = ProprietaryWatchtowerPanel(
                      watchtower: proprietaryReads.watchtower,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: regime),
                          const SizedBox(width: 18),
                          Expanded(child: watchtower),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        regime,
                        const SizedBox(height: 18),
                        watchtower,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final memory = MarketBehaviorMemoryPanel(
                      memory: proprietaryReads.memory,
                    );
                    final research = AiResearchPanel(
                      research: proprietaryReads.research,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: memory),
                          const SizedBox(width: 18),
                          Expanded(child: research),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        memory,
                        const SizedBox(height: 18),
                        research,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
              ],
              if (adaptiveDecisionRead != null) ...<Widget>[
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final consensus = AiConsensusEnginePanel(
                      read: adaptiveDecisionRead.consensus,
                    );
                    final scenarios = ScenarioProbabilityMapPanel(
                      read: adaptiveDecisionRead.scenarios,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: consensus),
                          const SizedBox(width: 18),
                          Expanded(child: scenarios),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        consensus,
                        const SizedBox(height: 18),
                        scenarios,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final contributors = AiContributorPanel(
                      contributors: adaptiveDecisionRead.consensus.contributors,
                    );
                    final weights = AdaptiveWeightsPanel(
                      read: adaptiveDecisionRead.weights,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: contributors),
                          const SizedBox(width: 18),
                          Expanded(child: weights),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        contributors,
                        const SizedBox(height: 18),
                        weights,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                MarketReasoningPanel(read: adaptiveDecisionRead.reasoning),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final calibration = ConfidenceCalibrationCorePanel(
                      read: adaptiveDecisionRead.calibration,
                    );
                    final stability = StabilityDriftControlPanel(
                      read: adaptiveDecisionRead.stability,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: calibration),
                          const SizedBox(width: 18),
                          Expanded(child: stability),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        calibration,
                        const SizedBox(height: 18),
                        stability,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final timeline = AiConsensusTimelinePanel(
                      read: adaptiveDecisionRead.timeline,
                    );
                    final research = AdaptiveDecisionResearchPanel(
                      read: adaptiveDecisionRead.research,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: timeline),
                          const SizedBox(width: 18),
                          Expanded(child: research),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        timeline,
                        const SizedBox(height: 18),
                        research,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
              ],
              if (evolvingRead != null) ...<Widget>[
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final evolution = ContributorEvolutionPanel(
                      read: evolvingRead.contributorEvolution,
                    );
                    final meta = MetaIntelligencePanel(
                      read: evolvingRead.metaIntelligence,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: evolution),
                          const SizedBox(width: 18),
                          Expanded(child: meta),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        evolution,
                        const SizedBox(height: 18),
                        meta,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final memory = LongHorizonEdgeMemoryPanel(
                      read: evolvingRead.edgeMemory,
                    );
                    final strategy = StrategyEvolutionPanel(
                      read: evolvingRead.strategyEvolution,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: memory),
                          const SizedBox(width: 18),
                          Expanded(child: strategy),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        memory,
                        const SizedBox(height: 18),
                        strategy,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final reasoning = ReasoningMemoryPanel(
                      read: evolvingRead.reasoningMemory,
                    );
                    final optimization = SelfOptimizationPanel(
                      read: evolvingRead.selfOptimization,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: reasoning),
                          const SizedBox(width: 18),
                          Expanded(child: optimization),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        reasoning,
                        const SizedBox(height: 18),
                        optimization,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final regime = RegimeEvolutionMapPanel(
                      read: evolvingRead.regimeEvolution,
                    );
                    final ml = FutureMlFoundationPanel(
                      read: evolvingRead.mlFoundation,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: regime),
                          const SizedBox(width: 18),
                          Expanded(child: ml),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        regime,
                        const SizedBox(height: 18),
                        ml,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
              ],
              if (governanceRead != null) ...<Widget>[
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final timeline = AiGovernanceTimelinePanel(
                      read: governanceRead.timeline,
                    );
                    final snapshot = DeterministicDecisionSnapshotPanel(
                      snapshot: governanceRead.snapshot,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: timeline),
                          const SizedBox(width: 18),
                          Expanded(child: snapshot),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        timeline,
                        const SizedBox(height: 18),
                        snapshot,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final replay = DeterministicReplayPanel(
                      read: governanceRead.replay,
                    );
                    final incident = AiIncidentResponsePanel(
                      read: governanceRead.incident,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: replay),
                          const SizedBox(width: 18),
                          Expanded(child: incident),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        replay,
                        const SizedBox(height: 18),
                        incident,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final rollout = RolloutControlPanel(
                      read: governanceRead.rollout,
                    );
                    final explainability = ExplainabilityPersistencePanel(
                      read: governanceRead.explainability,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: rollout),
                          const SizedBox(width: 18),
                          Expanded(child: explainability),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        rollout,
                        const SizedBox(height: 18),
                        explainability,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final wide = constraints.maxWidth >= 820;
                    final compliance = ComplianceSafetyPosturePanel(
                      read: governanceRead.compliance,
                    );
                    final health = OperationalHealthIndexPanel(
                      read: governanceRead.operationalHealth,
                    );
                    if (wide) {
                      return Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Expanded(child: compliance),
                          const SizedBox(width: 18),
                          Expanded(child: health),
                        ],
                      );
                    }
                    return Column(
                      children: <Widget>[
                        compliance,
                        const SizedBox(height: 18),
                        health,
                      ],
                    );
                  },
                ),
                const SizedBox(height: 18),
                ResearchExperimentationPanel(read: governanceRead.research),
                const SizedBox(height: 18),
              ],
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final portfolio = PortfolioIntelligencePanel(
                    read: portfolioRead,
                  );
                  final copilot = AiCopilotPanel(read: copilotRead);
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: portfolio),
                        const SizedBox(width: 18),
                        Expanded(child: copilot),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      portfolio,
                      const SizedBox(height: 18),
                      copilot,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final orchestration = MultiAssetOrchestrationPanel(
                    read: orchestrationRead,
                  );
                  final watchtower = WatchtowerPanel(read: watchtowerRead);
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: orchestration),
                        const SizedBox(width: 18),
                        Expanded(child: watchtower),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      orchestration,
                      const SizedBox(height: 18),
                      watchtower,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final realtime = RealtimeOrchestrationPanel(
                    read: realtimeRead,
                  );
                  final scalability = ScalabilityPosturePanel(
                    read: scalabilityRead,
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: realtime),
                        const SizedBox(width: 18),
                        Expanded(child: scalability),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      realtime,
                      const SizedBox(height: 18),
                      scalability,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final cloud = CloudProfileSyncPanel(read: cloudSyncRead);
                  final journal = ProfessionalJournalPanel(read: journalRead);
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: cloud),
                        const SizedBox(width: 18),
                        Expanded(child: journal),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      cloud,
                      const SizedBox(height: 18),
                      journal,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final reliability = AiSelfEvaluationPanel(
                    evaluation: adaptiveEngine.selfEvaluation(
                      signalFeed.items,
                      chart: chart,
                    ),
                  );
                  final regime = RegimeAdaptationPanel(
                    regime: adaptiveEngine.regimeAdaptation(chart),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: reliability),
                        const SizedBox(width: 18),
                        Expanded(child: regime),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      reliability,
                      const SizedBox(height: 18),
                      regime,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final edge = EdgeValidationPanel(
                    read: edgeEngine.edgeValidation(outcomeReports),
                  );
                  final drift = ModelDriftPanel(
                    read: edgeEngine.modelDrift(outcomeReports),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: edge),
                        const SizedBox(width: 18),
                        Expanded(child: drift),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      edge,
                      const SizedBox(height: 18),
                      drift,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final correction = SelfCorrectionPanel(
                    read: edgeEngine.selfCorrection(outcomeReports),
                  );
                  final quant = QuantPerformancePanel(
                    read: edgeEngine.quantPerformance(outcomeReports),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: correction),
                        const SizedBox(width: 18),
                        Expanded(child: quant),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      correction,
                      const SizedBox(height: 18),
                      quant,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              StrategyLeaderboardPanel(
                read: edgeEngine.strategyLeaderboard(outcomeReports),
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final review = AiPerformanceReviewPanel(
                    review: adaptiveEngine.performanceReview(
                      signalFeed.items,
                      chart: chart,
                    ),
                  );
                  final analytics = HedgeFundAnalyticsPanel(
                    analytics: adaptiveEngine.hedgeFundAnalytics(
                      signalFeed.items,
                      chart: chart,
                    ),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: review),
                        const SizedBox(width: 18),
                        Expanded(child: analytics),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      review,
                      const SizedBox(height: 18),
                      analytics,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  final marketIntel = AdvancedMarketIntelPanel(
                    intel: adaptiveEngine.advancedMarketIntel(chart),
                  );
                  final replay = ReplayFoundationPanel(
                    replay: adaptiveEngine.replayFoundation(chart),
                  );
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: marketIntel),
                        const SizedBox(width: 18),
                        Expanded(child: replay),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      marketIntel,
                      const SizedBox(height: 18),
                      replay,
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(child: TraderLevelPanel(snapshot: retention)),
                        const SizedBox(width: 18),
                        Expanded(
                          child: ShadowPortfolioPanel(
                            trades: retention.shadowTrades,
                          ),
                        ),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      TraderLevelPanel(snapshot: retention),
                      const SizedBox(height: 18),
                      ShadowPortfolioPanel(trades: retention.shadowTrades),
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              LayoutBuilder(
                builder: (context, constraints) {
                  final wide = constraints.maxWidth >= 820;
                  if (wide) {
                    return Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: DailyMissionsPanel(
                            missions: retention.missions,
                          ),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                          child: SocialCompetitionPanel(snapshot: retention),
                        ),
                      ],
                    );
                  }
                  return Column(
                    children: <Widget>[
                      DailyMissionsPanel(missions: retention.missions),
                      const SizedBox(height: 18),
                      SocialCompetitionPanel(snapshot: retention),
                    ],
                  );
                },
              ),
              const SizedBox(height: 18),
              if (signalFeed.lastError != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: _InlineWarningBanner(
                    message:
                        ErrorMapper.isRecoverableBackend(signalFeed.lastError)
                            ? 'Offline mode. Showing last known signals.'
                            : userMessageForError(signalFeed.lastError),
                  ),
                ),
              if (latestDashboardSummary != null || latestTradeUpdate != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: _RealtimeDeskStrip(
                    summary: latestDashboardSummary,
                    tradeUpdate: latestTradeUpdate,
                    onOpenTrade: onOpenTrade,
                  ),
                ),
              if (desktop)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(
                      flex: 7,
                      child: _buildBalanceColumn(
                        context,
                        pnlAsync,
                        activeTradesAsync,
                        signalFeed.items.length,
                        latestDashboardSummary,
                      ),
                    ),
                    const SizedBox(width: 18),
                    Expanded(
                      flex: 5,
                      child: _buildSignalColumn(
                        context,
                        activeSignal,
                        onOpenTradeSignal,
                        onOpenSignals,
                        settings.engineEnabled,
                        aiMode,
                        () => settingsController.saveEngineState(
                          userId,
                          enabled: !settings.engineEnabled,
                        ),
                      ),
                    ),
                  ],
                )
              else ...<Widget>[
                _buildBalanceColumn(
                  context,
                  pnlAsync,
                  activeTradesAsync,
                  signalFeed.items.length,
                  latestDashboardSummary,
                ),
                const SizedBox(height: 18),
                _buildSignalColumn(
                  context,
                  activeSignal,
                  onOpenTradeSignal,
                  onOpenSignals,
                  settings.engineEnabled,
                  aiMode,
                  () => settingsController.saveEngineState(
                    userId,
                    enabled: !settings.engineEnabled,
                  ),
                ),
              ],
              const SizedBox(height: 18),
              tablet
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: _buildSentimentPanel(marketSummaryAsync),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                          child: _buildTopMoversPanel(
                            marketUniverseAsync,
                            onOpenTrade,
                          ),
                        ),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        _buildSentimentPanel(marketSummaryAsync),
                        const SizedBox(height: 18),
                        _buildTopMoversPanel(marketUniverseAsync, onOpenTrade),
                      ],
                    ),
              const SizedBox(height: 18),
              tablet
                  ? Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Expanded(
                          child: _buildActiveTradesPanel(
                            activeTradesAsync,
                            onOpenTrade,
                          ),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                            child: _buildNewsPanel(newsItems, onOpenTrade)),
                      ],
                    )
                  : Column(
                      children: <Widget>[
                        _buildActiveTradesPanel(activeTradesAsync, onOpenTrade),
                        const SizedBox(height: 18),
                        _buildNewsPanel(newsItems, onOpenTrade),
                      ],
                    ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _refresh(WidgetRef ref, String userId) async {
    ref.read(appBootstrapProvider.notifier).refresh();
    ref.invalidate(userPnLProvider(userId));
    ref.invalidate(activeTradesProvider(userId));
    ref.invalidate(marketSummaryProvider);
    ref.invalidate(marketUniverseProvider);
    ref.invalidate(initialSignalsProvider);
    ref.invalidate(initialActivityHistoryProvider);
  }

  Widget _buildBalanceColumn(
    BuildContext context,
    AsyncValue<UserPnLModel> pnlAsync,
    AsyncValue<List<ActiveTradeModel>> activeTradesAsync,
    int signalCount,
    DashboardRealtimeSummaryModel? realtimeSummary,
  ) {
    return Column(
      children: <Widget>[
        pnlAsync.when(
          data: (pnl) => _BalanceHeroCard(
            pnl: pnl,
            realtimeSummary: realtimeSummary,
          ),
          loading: () => const SectionCard(
            title: 'Balance Overview',
            subtitle: 'Loading live balance, today PnL, and equity graph.',
            child: LoadingState(label: 'Loading balance'),
          ),
          error: (error, _) => ErrorState(message: userMessageForError(error)),
        ),
        const SizedBox(height: 18),
        activeTradesAsync.when(
          data: (trades) => _QuickStatsRow(
            totalTrades: trades.length,
            signalCount: signalCount,
            riskExposure: trades.fold<double>(
              0,
              (sum, item) => sum + item.riskFraction,
            ),
          ),
          loading: () => const SizedBox(height: 110, child: LoadingState()),
          error: (error, _) => ErrorState(message: userMessageForError(error)),
        ),
      ],
    );
  }

  Widget _buildSignalColumn(
    BuildContext context,
    SignalModel? signal,
    ValueChanged<SignalModel> onOpenTradeSignal,
    VoidCallback onOpenSignals,
    bool autoModeEnabled,
    AiTradingMode mode,
    VoidCallback onToggleAutoMode,
  ) {
    return SectionCard(
      title: 'AI Opportunity Deck',
      subtitle: '${mode.label} is ranking live setups and entry progression.',
      trailing: const LivePulseIndicator(),
      glowColor: TradingPalette.violet,
      child: signal == null
          ? _NoIdleScannerState(
              mode: mode,
              onOpenSignals: onOpenSignals,
            )
          : Column(
              children: <Widget>[
                Row(
                  children: <Widget>[
                    Expanded(
                      child: GradientActionButton(
                        label: autoModeEnabled
                            ? '${mode.label} Running'
                            : 'Start ${mode.label}',
                        icon: autoModeEnabled
                            ? Icons.pause_circle_outline_rounded
                            : Icons.play_circle_fill_rounded,
                        onPressed: onToggleAutoMode,
                        expanded: true,
                      ),
                    ),
                    const SizedBox(width: 12),
                    TextButton(
                      onPressed: onOpenSignals,
                      child: const Text('Open feed'),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 360),
                  transitionBuilder: (child, animation) {
                    return FadeTransition(
                      opacity: animation,
                      child: SlideTransition(
                        position: Tween<Offset>(
                          begin: const Offset(0.08, 0),
                          end: Offset.zero,
                        ).animate(animation),
                        child: child,
                      ),
                    );
                  },
                  child: KeyedSubtree(
                    key: ValueKey<String>(signal.signalId),
                    child: PulseWrapper(
                      child: AiSignalCard(
                        signal: signal,
                        mode: mode,
                        onExecute: () => onOpenTradeSignal(signal),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 14),
                AiExplanationPanel(signal: signal),
              ],
            ),
    );
  }

  Widget _buildSentimentPanel(
      AsyncValue<MarketSummaryModel> marketSummaryAsync) {
    return SectionCard(
      title: 'Market Sentiment',
      subtitle: 'Breadth, confidence, scanner pulse, and AI mood.',
      trailing: const StatusBadge(label: 'SCANNER'),
      glowColor: TradingPalette.electricBlue,
      child: marketSummaryAsync.when(
        data: (summary) => _MarketSentimentContent(summary: summary),
        loading: () => const LoadingState(label: 'Loading market summary'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildTopMoversPanel(
    AsyncValue<MarketUniverseModel> marketUniverseAsync,
    ValueChanged<String> onOpenTrade,
  ) {
    return SectionCard(
      title: 'Top Gainers',
      subtitle: 'Highest momentum symbols from the live market universe.',
      trailing: const StatusBadge(label: 'MOMENTUM'),
      glowColor: TradingPalette.neonGreen,
      child: marketUniverseAsync.when(
        data: (universe) {
          final movers = universe.topGainers.isNotEmpty
              ? universe.topGainers
              : universe.items.take(6).toList();
          if (movers.isEmpty) {
            return const EmptyState(
              title: 'No movers yet',
              subtitle:
                  'The market scanner has not published ranked gainers yet.',
            );
          }
          return Column(
            children: movers
                .take(6)
                .map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: InkWell(
                      onTap: () => onOpenTrade(item.symbol),
                      borderRadius: BorderRadius.circular(16),
                      child: Ink(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: TradingPalette.overlay,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: TradingPalette.panelBorder),
                        ),
                        child: Row(
                          children: <Widget>[
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    item.symbol,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Vol ${item.volumeRatio.toStringAsFixed(2)}x | ${item.category}',
                                    style: const TextStyle(
                                      color: TradingPalette.textFaint,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 12),
                            Text(
                              '${item.changePct >= 0 ? '+' : ''}${item.changePct.toStringAsFixed(2)}%',
                              style: TextStyle(
                                color: item.changePct >= 0
                                    ? TradingPalette.neonGreen
                                    : TradingPalette.neonRed,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                )
                .toList(),
          );
        },
        loading: () => const LoadingState(label: 'Loading movers'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildActiveTradesPanel(
    AsyncValue<List<ActiveTradeModel>> activeTradesAsync,
    ValueChanged<String> onOpenTrade,
  ) {
    return SectionCard(
      title: 'Active Trades',
      subtitle: 'Open positions with risk, target, and execution state.',
      glowColor: TradingPalette.violet,
      child: activeTradesAsync.when(
        data: (trades) {
          if (trades.isEmpty) {
            return const EmptyState(
              title: 'No active trades',
              subtitle:
                  'When the AI desk opens new trades, they will appear here with SL, TP, and risk allocation.',
            );
          }
          return Column(
            children: trades
                .map(
                  (trade) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: InkWell(
                      onTap: () => onOpenTrade(trade.symbol),
                      borderRadius: BorderRadius.circular(18),
                      child: Ink(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: TradingPalette.overlay,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: TradingPalette.panelBorder),
                        ),
                        child: Row(
                          children: <Widget>[
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: trade.side.toUpperCase() == 'BUY'
                                    ? TradingPalette.neonGreen.withOpacity(0.14)
                                    : TradingPalette.neonRed.withOpacity(0.14),
                              ),
                              child: Icon(
                                trade.side.toUpperCase() == 'BUY'
                                    ? Icons.arrow_upward_rounded
                                    : Icons.arrow_downward_rounded,
                                color: trade.side.toUpperCase() == 'BUY'
                                    ? TradingPalette.neonGreen
                                    : TradingPalette.neonRed,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    '${trade.symbol} | ${trade.side}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    'Entry ${trade.entry.toStringAsFixed(4)} | TP ${trade.takeProfit.toStringAsFixed(4)} | SL ${trade.stopLoss.toStringAsFixed(4)}',
                                    style: const TextStyle(
                                      color: TradingPalette.textFaint,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 12),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: <Widget>[
                                Text(
                                  '${(trade.riskFraction * 100).toStringAsFixed(1)}%',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  trade.status,
                                  style: const TextStyle(
                                    color: TradingPalette.textFaint,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                )
                .toList(),
          );
        },
        loading: () => const LoadingState(label: 'Loading active trades'),
        error: (error, _) => ErrorState(message: userMessageForError(error)),
      ),
    );
  }

  Widget _buildNewsPanel(
    List<ActivityItemModel> newsItems,
    ValueChanged<String> onOpenTrade,
  ) {
    return SectionCard(
      title: 'Execution Feed',
      subtitle: 'Risk, signal, and execution events from the live backend.',
      glowColor: TradingPalette.electricBlue,
      child: newsItems.isEmpty
          ? const EmptyState(
              title: 'No live feed yet',
              subtitle:
                  'Scanner activity, risk events, and AI reasoning updates will stream here once the backend publishes events.',
            )
          : Column(
              children: newsItems
                  .take(6)
                  .map(
                    (item) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: InkWell(
                        onTap: item.symbol == null || item.symbol!.isEmpty
                            ? null
                            : () => onOpenTrade(item.symbol!),
                        borderRadius: BorderRadius.circular(18),
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: TradingPalette.overlay,
                            borderRadius: BorderRadius.circular(18),
                            border:
                                Border.all(color: TradingPalette.panelBorder),
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Container(
                                width: 10,
                                height: 10,
                                margin: const EdgeInsets.only(top: 4),
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: _activityColor(item),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: <Widget>[
                                    Text(
                                      item.symbol == null ||
                                              item.symbol!.isEmpty
                                          ? item.botState
                                          : '${item.symbol} | ${item.botState}',
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 6),
                                    Text(
                                      item.message,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        color: TradingPalette.textMuted,
                                      ),
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      _timeAgo(item.timestamp),
                                      style: const TextStyle(
                                        color: TradingPalette.textFaint,
                                        fontSize: 12,
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
    );
  }
}

class _BalanceHeroCard extends StatelessWidget {
  const _BalanceHeroCard({
    required this.pnl,
    this.realtimeSummary,
  });

  final UserPnLModel pnl;
  final DashboardRealtimeSummaryModel? realtimeSummary;

  @override
  Widget build(BuildContext context) {
    final positive = pnl.absolutePnl >= 0;
    final accent = positive ? TradingPalette.neonGreen : TradingPalette.neonRed;
    final chartValues = pnl.sparkline;
    final spots = chartValues
        .asMap()
        .entries
        .map((entry) => FlSpot(entry.key.toDouble(), entry.value))
        .toList();
    final minY = chartValues.reduce((a, b) => a < b ? a : b);
    final maxY = chartValues.reduce((a, b) => a > b ? a : b);

    return GlassPanel(
      glowColor: accent,
      padding: const EdgeInsets.all(22),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Total Balance',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '\$${pnl.currentEquity.toStringAsFixed(2)}',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
              const Spacer(),
              StatusBadge(
                label: positive
                    ? '+${pnl.pnlPct.toStringAsFixed(2)}%'
                    : '${pnl.pnlPct.toStringAsFixed(2)}%',
                color: accent,
              ),
            ],
          ),
          const SizedBox(height: 18),
          SizedBox(
            height: 180,
            child: LineChart(
              LineChartData(
                minY: minY * 0.995,
                maxY: maxY * 1.005,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (_) => FlLine(
                    color: TradingPalette.glassHighlight.withOpacity(0.05),
                    strokeWidth: 1,
                  ),
                ),
                borderData: FlBorderData(show: false),
                titlesData: const FlTitlesData(
                  topTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  bottomTitles:
                      AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                lineBarsData: <LineChartBarData>[
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    color: accent,
                    barWidth: 3,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: <Color>[
                          accent.withOpacity(0.24),
                          Colors.transparent,
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _InfoPill(
                label: 'Today PnL',
                value: '\$${pnl.absolutePnl.toStringAsFixed(2)}',
              ),
              _InfoPill(
                label: 'Peak Equity',
                value: '\$${pnl.peakEquity.toStringAsFixed(2)}',
              ),
              _InfoPill(
                label: 'Protection',
                value: pnl.protectionState,
              ),
              if (realtimeSummary != null)
                _InfoPill(
                  label: 'Exec Latency',
                  value:
                      '${realtimeSummary!.executionLatencyMs.toStringAsFixed(0)} ms',
                ),
              if (realtimeSummary != null)
                _InfoPill(
                  label: 'Slippage',
                  value:
                      '${realtimeSummary!.executionSlippageBps.toStringAsFixed(1)} bps',
                ),
              if (realtimeSummary != null && realtimeSummary!.degradedMode)
                const _InfoPill(
                  label: 'Realtime Mode',
                  value: 'DEGRADED',
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RealtimeDeskStrip extends StatelessWidget {
  const _RealtimeDeskStrip({
    required this.summary,
    required this.tradeUpdate,
    required this.onOpenTrade,
  });

  final DashboardRealtimeSummaryModel? summary;
  final RealtimeTradeUpdateModel? tradeUpdate;
  final ValueChanged<String> onOpenTrade;

  @override
  Widget build(BuildContext context) {
    final latestStatus = tradeUpdate == null
        ? 'Waiting for trade events'
        : '${tradeUpdate!.status.toUpperCase()} ${tradeUpdate!.symbol} ${tradeUpdate!.side.toUpperCase()}';
    final latestReason = tradeUpdate == null
        ? 'Dashboard is listening for backend execution, portfolio, and summary events.'
        : _tradeReasonLabel(tradeUpdate!);

    return GlassPanel(
      glowColor: summary?.degradedMode == true
          ? TradingPalette.amber
          : TradingPalette.electricBlue,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Realtime Desk State',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              StatusBadge(
                label: summary?.degradedMode == true ? 'DEGRADED' : 'LIVE',
                color: summary?.degradedMode == true
                    ? TradingPalette.amber
                    : TradingPalette.neonGreen,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              if (summary != null)
                _InfoPill(
                  label: 'Active Trades',
                  value: summary!.activeTrades.toString(),
                ),
              if (summary != null)
                _InfoPill(
                  label: 'Protection',
                  value: summary!.protectionState,
                ),
              if (summary != null)
                _InfoPill(
                  label: 'Latency',
                  value: '${summary!.executionLatencyMs.toStringAsFixed(0)} ms',
                ),
              if (summary != null)
                _InfoPill(
                  label: 'Slippage',
                  value:
                      '${summary!.executionSlippageBps.toStringAsFixed(1)} bps',
                ),
              if (tradeUpdate != null)
                _InfoPill(
                  label: 'Last Status',
                  value: tradeUpdate!.status.toUpperCase(),
                ),
            ],
          ),
          const SizedBox(height: 12),
          InkWell(
            onTap: tradeUpdate == null || tradeUpdate!.symbol.isEmpty
                ? null
                : () => onOpenTrade(tradeUpdate!.symbol),
            borderRadius: BorderRadius.circular(16),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: TradingPalette.overlay,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: TradingPalette.panelBorder),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    latestStatus,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    latestReason,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: TradingPalette.textMuted,
                        ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickStatsRow extends StatelessWidget {
  const _QuickStatsRow({
    required this.totalTrades,
    required this.riskExposure,
    required this.signalCount,
  });

  final int totalTrades;
  final double riskExposure;
  final int signalCount;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 760;
        final cards = <Widget>[
          _MiniMetricCard(
            label: 'Open Trades',
            value: totalTrades.toString(),
            icon: Icons.stacked_line_chart_rounded,
          ),
          _MiniMetricCard(
            label: 'Risk Exposure',
            value: '${(riskExposure * 100).toStringAsFixed(1)}%',
            icon: Icons.security_rounded,
          ),
          _MiniMetricCard(
            label: 'Signals Live',
            value: signalCount.toString(),
            icon: Icons.wifi_tethering_rounded,
          ),
        ];
        if (compact) {
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: cards
                .map(
                  (card) => SizedBox(
                    width: constraints.maxWidth > 0
                        ? (constraints.maxWidth - 12) / 2
                        : 180,
                    child: card,
                  ),
                )
                .toList(),
          );
        }
        return Row(
          children: cards
              .expand(
                (card) => <Widget>[
                  Expanded(child: card),
                  const SizedBox(width: 12),
                ],
              )
              .toList()
            ..removeLast(),
        );
      },
    );
  }
}

class _ActionHeroOpportunity extends StatelessWidget {
  const _ActionHeroOpportunity({
    required this.signal,
    required this.mode,
    required this.autoModeEnabled,
    required this.onOpenTradeSignal,
    required this.onOpenSignals,
    required this.onToggleAutoMode,
  });

  final SignalModel? signal;
  final AiTradingMode mode;
  final bool autoModeEnabled;
  final ValueChanged<SignalModel> onOpenTradeSignal;
  final VoidCallback onOpenSignals;
  final VoidCallback onToggleAutoMode;

  @override
  Widget build(BuildContext context) {
    final activeSignal = signal;
    if (activeSignal == null) {
      return GlassPanel(
        glowColor: TradingPalette.electricBlue,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                const StatusBadge(
                  label: 'AI SCANNER LIVE',
                  color: TradingPalette.electricBlue,
                ),
                const Spacer(),
                StatusBadge(label: mode.label, color: TradingPalette.violet),
              ],
            ),
            const SizedBox(height: 18),
            Text(
              'AI is hunting the next move',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 8),
            const Text(
              'No idle screen. Scanner is rotating breakout, whale, liquidity, and volatility candidates.',
              style: TextStyle(color: TradingPalette.textPrimary),
            ),
            const SizedBox(height: 18),
            const _LiveScannerPulse(),
            const SizedBox(height: 18),
            Row(
              children: <Widget>[
                Expanded(
                  child: GradientActionButton(
                    label: 'Open Hot Scanner',
                    icon: Icons.radar_rounded,
                    onPressed: onOpenSignals,
                    expanded: true,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: onToggleAutoMode,
                    icon: Icon(
                      autoModeEnabled
                          ? Icons.pause_circle_outline_rounded
                          : Icons.smart_toy_rounded,
                    ),
                    label: Text(autoModeEnabled ? 'AI Running' : 'Enable AI'),
                  ),
                ),
              ],
            ),
          ],
        ),
      );
    }

    final opportunity = SignalOpportunity.fromSignal(activeSignal, mode: mode);
    return PremiumSignalSurface(
      opportunity: opportunity,
      autoModeEnabled: autoModeEnabled,
      onPrimary: () => onOpenTradeSignal(activeSignal),
      onAuto: onToggleAutoMode,
      onChart: () => onOpenTradeSignal(activeSignal),
    );
  }
}

class _NoIdleScannerState extends StatelessWidget {
  const _NoIdleScannerState({
    required this.mode,
    required this.onOpenSignals,
  });

  final AiTradingMode mode;
  final VoidCallback onOpenSignals;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          '${mode.label} is preparing entries',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 12),
        const _LiveScannerPulse(),
        const SizedBox(height: 14),
        GradientActionButton(
          label: 'Open AI Scanner',
          icon: Icons.radar_rounded,
          onPressed: onOpenSignals,
          expanded: true,
        ),
      ],
    );
  }
}

class _SessionAlphaBoard extends StatelessWidget {
  const _SessionAlphaBoard({
    required this.signals,
    required this.mode,
  });

  final List<SignalModel> signals;
  final AiTradingMode mode;

  @override
  Widget build(BuildContext context) {
    final opportunities = signals
        .map((signal) => SignalOpportunity.fromSignal(signal, mode: mode))
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));
    final best = opportunities.isEmpty ? null : opportunities.first;
    final accuracy = opportunities.isEmpty
        ? 72.0
        : opportunities
                .map((item) => item.score)
                .reduce((value, element) => value + element) /
            opportunities.length;
    final streak = opportunities
        .take(6)
        .where((item) =>
            item.tier == OpportunityTier.strongSignal ||
            item.tier == OpportunityTier.highConviction)
        .length;
    final simulatedPnl = opportunities.take(6).fold<double>(
          0,
          (sum, item) =>
              sum +
              (item.expectedMovePct *
                  (item.bullish ? 1 : -0.35) *
                  item.mode.suggestedRiskMultiplier),
        );

    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'AI Session Edge',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: mode.label, color: TradingPalette.violet),
            ],
          ),
          const SizedBox(height: 12),
          LayoutBuilder(
            builder: (context, constraints) {
              final tight = constraints.maxWidth < 620;
              final children = <Widget>[
                _SessionMetric(
                  label: 'AI streak',
                  value: '${streak}x',
                  subtitle: 'strong setups',
                  color: TradingPalette.neonGreen,
                ),
                _SessionMetric(
                  label: 'Accuracy pulse',
                  value: '${accuracy.clamp(0, 99).toStringAsFixed(0)}%',
                  subtitle: 'session quality',
                  color: TradingPalette.electricBlue,
                ),
                _SessionMetric(
                  label: 'Best today',
                  value: best?.signal.symbol ?? 'SCANNING',
                  subtitle: best?.statusLabel ?? 'radar active',
                  color: TradingPalette.amber,
                ),
                _SessionMetric(
                  label: 'Sim replay',
                  value:
                      '${simulatedPnl >= 0 ? '+' : ''}${simulatedPnl.toStringAsFixed(1)}%',
                  subtitle: 'paper momentum',
                  color: simulatedPnl >= 0
                      ? TradingPalette.neonGreen
                      : TradingPalette.neonRed,
                ),
              ];
              if (tight) {
                return Column(
                  children: children
                      .map(
                        (child) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: child,
                        ),
                      )
                      .toList(),
                );
              }
              return Row(
                children: children
                    .map(
                      (child) => Expanded(
                        child: Padding(
                          padding: const EdgeInsets.only(right: 10),
                          child: child,
                        ),
                      ),
                    )
                    .toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _LiveAiEventPanel extends StatelessWidget {
  const _LiveAiEventPanel({
    required this.signals,
    required this.mode,
  });

  final List<SignalModel> signals;
  final AiTradingMode mode;

  @override
  Widget build(BuildContext context) {
    final events = const AiPersonalityEngine().liveEventNarratives(
      signals,
      mode,
    );
    return GlassPanel(
      glowColor: TradingPalette.neonGreen,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Live AI Events',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              const StatusBadge(
                label: 'PULSE',
                color: TradingPalette.neonGreen,
              ),
            ],
          ),
          const SizedBox(height: 12),
          const LiveEnergyBars(color: TradingPalette.neonGreen, height: 24),
          const SizedBox(height: 12),
          ...events.take(3).map(
                (event) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Container(
                        width: 9,
                        height: 9,
                        margin: const EdgeInsets.only(top: 6),
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: TradingPalette.neonGreen,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          event,
                          style: const TextStyle(
                            color: TradingPalette.textPrimary,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
        ],
      ),
    );
  }
}

class _SessionMetric extends StatelessWidget {
  const _SessionMetric({
    required this.label,
    required this.value,
    required this.subtitle,
    required this.color,
  });

  final String label;
  final String value;
  final String subtitle;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.09),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.22)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 6),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            subtitle,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: TradingPalette.textFaint),
          ),
        ],
      ),
    );
  }
}

class _LiveScannerPulse extends StatelessWidget {
  const _LiveScannerPulse();

  @override
  Widget build(BuildContext context) {
    const items = <({String label, double value, Color color})>[
      (
        label: 'Breakout radar',
        value: 0.68,
        color: TradingPalette.electricBlue,
      ),
      (
        label: 'Whale pulse',
        value: 0.54,
        color: TradingPalette.violet,
      ),
      (
        label: 'Volatility build',
        value: 0.73,
        color: TradingPalette.amber,
      ),
    ];
    return Column(
      children: items
          .map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                children: <Widget>[
                  SizedBox(
                    width: 118,
                    child: Text(
                      item.label,
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ),
                  Expanded(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(999),
                      child: LinearProgressIndicator(
                        minHeight: 8,
                        value: item.value,
                        backgroundColor: TradingPalette.overlay,
                        valueColor: AlwaysStoppedAnimation<Color>(item.color),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          )
          .toList(),
    );
  }
}

class _MiniMetricCard extends StatelessWidget {
  const _MiniMetricCard({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.violet,
      padding: const EdgeInsets.all(16),
      child: Row(
        children: <Widget>[
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: TradingPalette.violet.withOpacity(0.14),
            ),
            child: Icon(icon, color: TradingPalette.violet, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(label, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 4),
                Text(
                  value,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MarketSentimentContent extends StatelessWidget {
  const _MarketSentimentContent({required this.summary});

  final MarketSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    final progress = (summary.sentimentScore / 100).clamp(0.0, 1.0);
    final color = summary.sentimentScore >= 65
        ? TradingPalette.neonGreen
        : summary.sentimentScore <= 40
            ? TradingPalette.neonRed
            : TradingPalette.electricBlue;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                summary.sentimentLabel,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: color,
                      fontWeight: FontWeight.w800,
                    ),
              ),
            ),
            Text(
              '${summary.sentimentScore.toStringAsFixed(0)}/100',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: LinearProgressIndicator(
            value: progress,
            minHeight: 10,
            backgroundColor: TradingPalette.panelBorder,
            valueColor: AlwaysStoppedAnimation<Color>(color),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _InfoPill(
              label: 'Breadth',
              value: '${summary.marketBreadth.toStringAsFixed(1)}%',
            ),
            _InfoPill(
              label: 'Avg Change',
              value: '${summary.avgChangePct.toStringAsFixed(2)}%',
            ),
            _InfoPill(
              label: 'Confidence',
              value: '${summary.confidenceScore.toStringAsFixed(0)}%',
            ),
            _InfoPill(
              label: 'Scanner Avg',
              value: summary.scanner.averagePotentialScore.toStringAsFixed(0),
            ),
          ],
        ),
      ],
    );
  }
}

class _InfoPill extends StatelessWidget {
  const _InfoPill({
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
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _InlineWarningBanner extends StatelessWidget {
  const _InlineWarningBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.amber,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Icon(Icons.warning_amber_rounded, color: TradingPalette.amber),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

Color _activityColor(ActivityItemModel item) {
  final text = item.status.toLowerCase();
  if (text.contains('reject') || text.contains('error')) {
    return TradingPalette.neonRed;
  }
  if (text.contains('execute') || text.contains('ready')) {
    return TradingPalette.neonGreen;
  }
  return TradingPalette.electricBlue;
}

String _timeAgo(DateTime timestamp) {
  final diff = DateTime.now().difference(timestamp.toLocal());
  if (diff.inMinutes < 1) {
    return 'just now';
  }
  if (diff.inHours < 1) {
    return '${diff.inMinutes}m ago';
  }
  return '${diff.inHours}h ago';
}

String _tradeReasonLabel(RealtimeTradeUpdateModel tradeUpdate) {
  final reason = tradeUpdate.reason.trim();
  if (reason.isNotEmpty) {
    return reason;
  }
  final code = tradeUpdate.errorCode?.trim();
  if (code != null && code.isNotEmpty) {
    return code.replaceAll('_', ' ').toLowerCase();
  }
  return 'Backend published a ${tradeUpdate.status.toLowerCase()} update.';
}

class _DashboardProprietaryReads {
  const _DashboardProprietaryReads({
    required this.dna,
    required this.signature,
    required this.pressure,
    required this.memory,
    required this.narrative,
    required this.edgeConfidence,
    required this.regime,
    required this.watchtower,
    required this.research,
  });

  final MarketDnaProfile dna;
  final AiEdgeSignatureRead signature;
  final PredictivePressureRead pressure;
  final MarketBehaviorMemoryRead memory;
  final AiMarketNarrativeRead narrative;
  final EdgeConfidenceRead edgeConfidence;
  final MarketRegimeMapRead regime;
  final ProprietaryWatchtowerRead watchtower;
  final AiResearchRead research;

  factory _DashboardProprietaryReads.from({
    required ProprietaryAiEngine engine,
    required SignalModel signal,
    required List<SignalModel> signals,
    required List<SignalOutcomeReport> outcomes,
    required ModelDriftRead drift,
    MarketSummaryModel? market,
    MarketChartModel? chart,
  }) {
    final dna = engine.marketDna(
      signal: signal,
      market: market,
      chart: chart,
    );
    final signature = engine.edgeSignature(signal);
    final pressure = engine.predictivePressure(
      signal: signal,
      market: market,
      chart: chart,
    );
    final regime = engine.regimeMap(market: market, chart: chart);
    return _DashboardProprietaryReads(
      dna: dna,
      signature: signature,
      pressure: pressure,
      memory: engine.behaviorMemory(signals: signals, market: market),
      narrative: engine.marketNarrative(
        dna: dna,
        signature: signature,
        pressure: pressure,
        regime: regime,
      ),
      edgeConfidence: engine.edgeConfidence(
        dna: dna,
        signature: signature,
        outcomes: outcomes,
        drift: drift,
      ),
      regime: regime,
      watchtower: engine.proprietaryWatchtower(
        pressure: pressure,
        dna: dna,
        drift: drift,
      ),
      research: engine.researchLayer(signals: signals, outcomes: outcomes),
    );
  }
}

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}

extension on AiMemoryProfile {
  AiMemoryProfile withLocalMemory(LocalAiMemoryState local) {
    return AiMemoryProfile(
      preferredAssets: local.preferredAssets.isNotEmpty
          ? local.preferredAssets
          : preferredAssets,
      preferredMode: local.preferredModes.isNotEmpty
          ? local.preferredModes.first
          : preferredMode,
      successfulSetups: successfulSetups,
      avoidedSetups: avoidedSetups,
      favoriteStyle: local.favoriteStyle.trim().isNotEmpty
          ? local.favoriteStyle
          : favoriteStyle,
      personalizedNote: local.viewedSignals > 0
          ? 'AI has remembered ${local.viewedSignals} viewed opportunities and is prioritizing ${local.preferredAssets.take(3).join(', ')}.'
          : personalizedNote,
    );
  }
}

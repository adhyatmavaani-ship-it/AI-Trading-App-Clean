import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/adaptive_ai_intelligence_engine.dart';
import '../core/adaptive_decision_core.dart';
import '../core/ai_opportunity_engine.dart';
import '../core/edge_validation_engine.dart';
import '../core/enterprise_ai_governance_engine.dart';
import '../core/evolving_ai_intelligence_engine.dart';
import '../core/error_mapper.dart';
import '../core/error_presenter.dart';
import '../core/institutional_intelligence_engine.dart';
import '../core/proprietary_ai_engine.dart';
import '../core/trading_palette.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/settings/providers/settings_provider.dart';
import '../models/signal.dart';
import '../widgets/adaptive_ai_widgets.dart';
import '../widgets/adaptive_decision_widgets.dart';
import '../widgets/ai_signal_card.dart';
import '../widgets/edge_validation_widgets.dart';
import '../widgets/enterprise_governance_widgets.dart';
import '../widgets/evolving_ai_widgets.dart';
import '../widgets/glass_panel.dart';
import '../widgets/institutional_trust_widgets.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pulse_wrapper.dart';
import '../widgets/proprietary_ai_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/status_badge.dart';

class AiSignalScreen extends ConsumerWidget {
  const AiSignalScreen({
    super.key,
    required this.onExecuteSignal,
  });

  final ValueChanged<SignalModel> onExecuteSignal;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final signalFeed = ref.watch(signalFeedProvider);
    final initialSignalsAsync = ref.watch(initialSignalsProvider);
    final signals = signalFeed.items.isNotEmpty
        ? signalFeed.items
        : (initialSignalsAsync.valueOrNull ?? const <SignalModel>[]);
    final leadSignal = signals.isEmpty ? null : signals.first;
    final settings = ref.watch(appSettingsProvider);
    final userId = ref.watch(activeUserIdProvider);
    final mode = aiTradingModeFromRiskLevel(settings.riskLevel);
    final settingsController = ref.read(appSettingsProvider.notifier);
    const institutionalEngine = InstitutionalIntelligenceEngine();
    const adaptiveEngine = AdaptiveAiIntelligenceEngine();
    const edgeEngine = EdgeValidationEngine();
    const proprietaryEngine = ProprietaryAiEngine();
    const decisionCore = AdaptiveDecisionCore();
    const evolvingEngine = EvolvingAiIntelligenceEngine();
    const governanceEngine = EnterpriseAiGovernanceEngine();
    final outcomeReports = edgeEngine.signalOutcomes(signals, mode: mode);
    final leadOutcome = outcomeReports.isEmpty ? null : outcomeReports.first;
    final driftRead = edgeEngine.modelDrift(outcomeReports);
    final proprietaryReads = leadSignal == null
        ? null
        : _SignalProprietaryReads.from(
            engine: proprietaryEngine,
            signal: leadSignal,
            outcomes: outcomeReports,
            drift: driftRead,
          );
    final adaptiveDecisionRead = leadSignal == null || proprietaryReads == null
        ? null
        : decisionCore.evaluate(
            signal: leadSignal,
            signals: signals,
            outcomes: outcomeReports,
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
                signals: signals,
                outcomes: outcomeReports,
                regime: proprietaryReads.regime,
              );
    final governanceRead = leadSignal == null ||
            adaptiveDecisionRead == null ||
            evolvingRead == null ||
            proprietaryReads == null
        ? null
        : governanceEngine.evaluate(
            signal: leadSignal,
            decision: adaptiveDecisionRead,
            evolving: evolvingRead,
            outcomes: outcomeReports,
            regime: proprietaryReads.regime,
          );

    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(initialSignalsProvider),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
        children: <Widget>[
          if (signalFeed.lastError != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: GlassPanel(
                glowColor: TradingPalette.amber,
                child: Text(
                  ErrorMapper.isRecoverableBackend(signalFeed.lastError)
                      ? 'Offline mode. Showing last known signals.'
                      : userMessageForError(signalFeed.lastError),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.textPrimary,
                      ),
                ),
              ),
            ),
          _AiModeSelector(
            mode: mode,
            onChanged: (nextMode) => settingsController.saveRiskLevel(
              userId,
              nextMode == AiTradingMode.safe
                  ? 'low'
                  : nextMode == AiTradingMode.aggressive
                      ? 'high'
                      : 'medium',
            ),
          ),
          const SizedBox(height: 18),
          if (leadSignal != null && !leadSignal.executionAllowed)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: GlassPanel(
                glowColor: TradingPalette.electricBlue,
                child: Text(
                  SignalOpportunity.fromSignal(leadSignal, mode: mode)
                      .tradePlanLabel,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.textPrimary,
                      ),
                ),
              ),
            ),
          SectionCard(
              title: 'Best AI Opportunity',
              subtitle:
                  'The highest-priority setup is always promoted into an action plan.',
              trailing: const LivePulseIndicator(
                label: 'LIVE',
                color: TradingPalette.electricBlue,
              ),
              glowColor: TradingPalette.violet,
              child: signals.isEmpty
                  ? const _SignalRadarEmptyState()
                  : PulseWrapper(
                      child: AiSignalCard(
                        signal: signals.first,
                        mode: mode,
                        onExecute: () => onExecuteSignal(signals.first),
                      ),
                    )),
          if (leadSignal != null) ...<Widget>[
            const SizedBox(height: 18),
            SignalCalibrationPanel(
              calibration: adaptiveEngine.calibrateSignal(
                leadSignal,
                mode: mode,
              ),
            ),
            if (proprietaryReads != null) ...<Widget>[
              const SizedBox(height: 18),
              AiEdgeSignaturePanel(signature: proprietaryReads.signature),
              const SizedBox(height: 18),
              MarketDnaPanel(profile: proprietaryReads.dna),
              const SizedBox(height: 18),
              PredictivePressurePanel(pressure: proprietaryReads.pressure),
              const SizedBox(height: 18),
              EdgeConfidencePanel(confidence: proprietaryReads.edgeConfidence),
              const SizedBox(height: 18),
              AiMarketNarrativePanel(narrative: proprietaryReads.narrative),
              const SizedBox(height: 18),
              MarketRegimeMapPanel(regime: proprietaryReads.regime),
              const SizedBox(height: 18),
              ProprietaryWatchtowerPanel(
                watchtower: proprietaryReads.watchtower,
              ),
            ],
            if (adaptiveDecisionRead != null) ...<Widget>[
              const SizedBox(height: 18),
              AiConsensusEnginePanel(read: adaptiveDecisionRead.consensus),
              const SizedBox(height: 18),
              ScenarioProbabilityMapPanel(
                read: adaptiveDecisionRead.scenarios,
              ),
              const SizedBox(height: 18),
              MarketReasoningPanel(read: adaptiveDecisionRead.reasoning),
              const SizedBox(height: 18),
              AiConsensusTimelinePanel(read: adaptiveDecisionRead.timeline),
              const SizedBox(height: 18),
              StabilityDriftControlPanel(read: adaptiveDecisionRead.stability),
            ],
            if (evolvingRead != null) ...<Widget>[
              const SizedBox(height: 18),
              ContributorEvolutionPanel(
                read: evolvingRead.contributorEvolution,
              ),
              const SizedBox(height: 18),
              LongHorizonEdgeMemoryPanel(read: evolvingRead.edgeMemory),
              const SizedBox(height: 18),
              MetaIntelligencePanel(read: evolvingRead.metaIntelligence),
              const SizedBox(height: 18),
              StrategyEvolutionPanel(read: evolvingRead.strategyEvolution),
              const SizedBox(height: 18),
              ReasoningMemoryPanel(read: evolvingRead.reasoningMemory),
            ],
            if (governanceRead != null) ...<Widget>[
              const SizedBox(height: 18),
              AiGovernanceTimelinePanel(read: governanceRead.timeline),
              const SizedBox(height: 18),
              DeterministicDecisionSnapshotPanel(
                snapshot: governanceRead.snapshot,
              ),
              const SizedBox(height: 18),
              DeterministicReplayPanel(read: governanceRead.replay),
              const SizedBox(height: 18),
              AiIncidentResponsePanel(read: governanceRead.incident),
              const SizedBox(height: 18),
              ComplianceSafetyPosturePanel(read: governanceRead.compliance),
            ],
            const SizedBox(height: 18),
            if (leadOutcome != null) ...<Widget>[
              SignalOutcomeReportPanel(report: leadOutcome),
              const SizedBox(height: 18),
            ],
            AiDecisionJournalPanel(
              entry: edgeEngine.decisionJournal(
                leadSignal,
                leadOutcome,
                mode: mode,
              ),
            ),
            const SizedBox(height: 18),
            ConfidenceTransparencyPanel(
              transparency: institutionalEngine.transparencyForSignal(
                leadSignal,
                mode: mode,
              ),
            ),
            const SizedBox(height: 18),
            GlassPanel(
              glowColor: TradingPalette.neonGreen,
              child: SignalLifecycleRail(
                current: institutionalEngine.lifecycleForSignal(leadSignal),
              ),
            ),
          ],
          const SizedBox(height: 18),
          SectionCard(
            title: 'AI Opportunity Queue',
            subtitle:
                'Scalp watch, balanced entries, strong signals, and high-conviction trades.',
            trailing: StatusBadge(label: '${signals.length} live'),
            child: signals.isEmpty
                ? const _SignalRadarEmptyState()
                : Column(
                    children: signals
                        .map(
                          (signal) => Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: _SignalListTile(
                              signal: signal,
                              mode: mode,
                              onTap: () => onExecuteSignal(signal),
                            ),
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _SignalProprietaryReads {
  const _SignalProprietaryReads({
    required this.dna,
    required this.signature,
    required this.pressure,
    required this.narrative,
    required this.edgeConfidence,
    required this.regime,
    required this.watchtower,
  });

  final MarketDnaProfile dna;
  final AiEdgeSignatureRead signature;
  final PredictivePressureRead pressure;
  final AiMarketNarrativeRead narrative;
  final EdgeConfidenceRead edgeConfidence;
  final MarketRegimeMapRead regime;
  final ProprietaryWatchtowerRead watchtower;

  factory _SignalProprietaryReads.from({
    required ProprietaryAiEngine engine,
    required SignalModel signal,
    required List<SignalOutcomeReport> outcomes,
    required ModelDriftRead drift,
  }) {
    final dna = engine.marketDna(signal: signal);
    final signature = engine.edgeSignature(signal);
    final pressure = engine.predictivePressure(signal: signal);
    final regime = engine.regimeMap();
    return _SignalProprietaryReads(
      dna: dna,
      signature: signature,
      pressure: pressure,
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
    );
  }
}

class _AiModeSelector extends StatelessWidget {
  const _AiModeSelector({
    required this.mode,
    required this.onChanged,
  });

  final AiTradingMode mode;
  final ValueChanged<AiTradingMode> onChanged;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'AI Trading Mode',
      subtitle:
          'Choose how early the AI should surface opportunities. Backend risk checks remain final.',
      trailing: StatusBadge(label: mode.label, color: TradingPalette.violet),
      glowColor: TradingPalette.electricBlue,
      child: SegmentedButton<AiTradingMode>(
        segments: const <ButtonSegment<AiTradingMode>>[
          ButtonSegment<AiTradingMode>(
            value: AiTradingMode.safe,
            icon: Icon(Icons.shield_rounded),
            label: Text('Safe'),
          ),
          ButtonSegment<AiTradingMode>(
            value: AiTradingMode.balanced,
            icon: Icon(Icons.auto_awesome_rounded),
            label: Text('Smart'),
          ),
          ButtonSegment<AiTradingMode>(
            value: AiTradingMode.aggressive,
            icon: Icon(Icons.bolt_rounded),
            label: Text('Aggressive'),
          ),
        ],
        selected: <AiTradingMode>{mode},
        onSelectionChanged: (selection) => onChanged(selection.first),
      ),
    );
  }
}

class _SignalRadarEmptyState extends StatelessWidget {
  const _SignalRadarEmptyState();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const Text(
          'AI scanner is active',
          style: TextStyle(
            color: TradingPalette.textPrimary,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 12),
        for (final row in const <({String label, double value, Color color})>[
          (
            label: 'Hot breakout radar',
            value: 0.62,
            color: TradingPalette.electricBlue,
          ),
          (
            label: 'Liquidity sweep watch',
            value: 0.48,
            color: TradingPalette.amber,
          ),
          (
            label: 'Whale accumulation pulse',
            value: 0.57,
            color: TradingPalette.violet,
          ),
        ])
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: <Widget>[
                SizedBox(width: 156, child: Text(row.label)),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: row.value,
                      minHeight: 8,
                      backgroundColor: TradingPalette.overlay,
                      valueColor: AlwaysStoppedAnimation<Color>(row.color),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _SignalListTile extends StatelessWidget {
  const _SignalListTile({
    required this.signal,
    required this.mode,
    required this.onTap,
  });

  final SignalModel signal;
  final AiTradingMode mode;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final opportunity = SignalOpportunity.fromSignal(signal, mode: mode);
    final bullish = opportunity.bullish;
    final accent = opportunity.accent;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(18),
      child: Ink(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          color: TradingPalette.overlay,
          border: Border.all(color: TradingPalette.panelBorder),
        ),
        child: Row(
          children: <Widget>[
            Container(
              width: 50,
              height: 50,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: accent.withOpacity(0.16),
              ),
              child: Icon(
                bullish
                    ? Icons.arrow_upward_rounded
                    : Icons.arrow_downward_rounded,
                color: accent,
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Text(
                        signal.symbol,
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(width: 8),
                      StatusBadge(label: signal.action, color: accent),
                      const SizedBox(width: 8),
                      StatusBadge(
                        label: opportunity.statusLabel,
                        color: opportunity.canAttemptExecution
                            ? TradingPalette.neonGreen
                            : TradingPalette.electricBlue,
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    opportunity.insights.join(' | '),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: TradingPalette.textMuted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 14),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: <Widget>[
                Text(
                  opportunity.confidenceLabel,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 6),
                Text(
                  opportunity.expectedMoveLabel,
                  style: const TextStyle(color: TradingPalette.textFaint),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

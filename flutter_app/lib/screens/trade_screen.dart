import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/adaptive_ai_intelligence_engine.dart';
import '../core/ai_opportunity_engine.dart';
import '../core/edge_validation_engine.dart';
import '../core/error_presenter.dart';
import '../core/institutional_intelligence_engine.dart';
import '../core/production_infrastructure_engine.dart';
import '../core/trading_operating_system_engine.dart';
import '../core/trading_palette.dart';
import '../core/websocket_service.dart';
import '../features/auth/providers/auth_provider.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/signal.dart';
import '../models/trade_execution.dart';
import '../providers/app_providers.dart';
import '../widgets/adaptive_ai_widgets.dart';
import '../widgets/edge_validation_widgets.dart';
import '../widgets/glass_panel.dart';
import '../widgets/institutional_trust_widgets.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pro_trading_chart.dart';
import '../widgets/production_infrastructure_widgets.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';
import '../widgets/trading_os_widgets.dart';

class TradeScreen extends ConsumerStatefulWidget {
  const TradeScreen({super.key});

  @override
  ConsumerState<TradeScreen> createState() => _TradeScreenState();
}

class _TradeScreenState extends ConsumerState<TradeScreen> {
  late final TextEditingController _amountController;

  @override
  void initState() {
    super.initState();
    _amountController = TextEditingController(text: '100');
  }

  @override
  void dispose() {
    _amountController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(activeUserIdProvider);
    final authState = ref.watch(authControllerProvider);
    final selectedSymbol = ref.watch(selectedMarketSymbolProvider);
    final selectedInterval = ref.watch(selectedMarketIntervalProvider);
    final tradeIntent = ref.watch(resolvedTradeIntentProvider);
    final tradeEvaluationAsync = ref.watch(tradeEvaluationProvider);
    final executionState = ref.watch(tradeExecutionControllerProvider);
    final paperState = ref.watch(localPaperTradingProvider);
    final executionController =
        ref.read(tradeExecutionControllerProvider.notifier);
    final marketChartAsync = ref.watch(marketChartProvider);
    final socketState =
        ref.watch(webSocketServiceProvider).stateListenable.value;
    final marketUniverseAsync = ref.watch(marketUniverseProvider);
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final pnlAsync = ref.watch(userPnLProvider(userId));
    final signalFeed = ref.watch(signalFeedProvider);
    final signalItems = signalFeed.items;
    final symbolOptions = _buildSymbolOptions(
      selectedSymbol: selectedSymbol,
      signals: signalItems,
      universe: marketUniverseAsync.valueOrNull,
    );
    _syncPaperMarketPrices(
      chart: marketChartAsync.valueOrNull,
      universe: marketUniverseAsync.valueOrNull,
    );
    final executionBlocked = executionState.isSubmitting ||
        !_canExecuteTrade(
          state: executionState,
          evaluation: tradeEvaluationAsync.valueOrNull,
        );
    const operatingSystem = TradingOperatingSystemEngine();
    final portfolioRead = operatingSystem.portfolioIntelligence(
      pnl: pnlAsync.valueOrNull,
      trades: activeTradesAsync.valueOrNull ?? const <ActiveTradeModel>[],
    );

    _syncAmountField(executionState.amount);

    return RefreshIndicator(
      onRefresh: () => _refreshTradeSurface(userId),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 1100;
          final executionPanel = _TradeExecutionPanel(
            selectedSymbol: selectedSymbol,
            tradeIntent: tradeIntent,
            tradeEvaluationAsync: tradeEvaluationAsync,
            chart: marketChartAsync.valueOrNull,
            portfolioRead: portfolioRead,
            websocketState: socketState,
            executionState: executionState,
            paperState: paperState,
            authDegraded: authState.isDegraded,
            amountController: _amountController,
            onSideChanged: executionController.setSide,
            onAmountPresetSelected: (amount) {
              executionController.setAmount(amount);
              _amountController.text = amount.toStringAsFixed(0);
            },
            onAmountChanged: (value) {
              final parsed = double.tryParse(value);
              if (parsed != null) {
                executionController.setAmount(parsed);
              }
            },
            onExecute: executionBlocked
                ? null
                : () => _confirmAndExecute(
                      userId: userId,
                      symbol: selectedSymbol,
                      intent: tradeIntent,
                      evaluation: tradeEvaluationAsync.valueOrNull,
                    ),
            onPaperExecute: () => _executePaperTrade(
              symbol: selectedSymbol,
              intent: tradeIntent,
              evaluation: tradeEvaluationAsync.valueOrNull,
              chart: marketChartAsync.valueOrNull,
            ),
            onDismissFeedback: executionController.clearFeedback,
          );

          final chartPanel = SectionCard(
            title: 'Execution Chart',
            subtitle:
                'Live candles for $selectedSymbol with direct symbol and timeframe switching.',
            trailing: const LivePulseIndicator(
              label: 'MARKET',
              color: TradingPalette.electricBlue,
            ),
            glowColor: TradingPalette.electricBlue,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                _SymbolStrip(
                  symbols: symbolOptions,
                  selectedSymbol: selectedSymbol,
                  onSelect: (symbol) {
                    ref.read(selectedMarketSymbolProvider.notifier).state =
                        symbol;
                  },
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: <Widget>[
                    for (final interval in const <String>[
                      '1m',
                      '5m',
                      '15m',
                      '1h'
                    ])
                      ChoiceChip(
                        label: Text(interval),
                        selected: selectedInterval == interval,
                        onSelected: (_) => ref
                            .read(selectedMarketIntervalProvider.notifier)
                            .state = interval,
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                marketChartAsync.when(
                  data: (chart) => ProTradingChart(
                    chart: chart,
                    onAssistantModeChanged: (mode) async {
                      await ref
                          .read(tradingRepositoryProvider)
                          .setAssistantMode(mode);
                      ref.invalidate(assistantModeProvider);
                      ref.invalidate(marketChartProvider);
                    },
                  ),
                  loading: () => const SizedBox(
                    height: 360,
                    child: LoadingState(label: 'Loading live chart'),
                  ),
                  error: (error, _) =>
                      ErrorState(message: userMessageForError(error)),
                ),
              ],
            ),
          );

          final activeTradesPanel = _buildActiveTradesPanel(
            selectedSymbol: selectedSymbol,
            activeTradesAsync: activeTradesAsync,
          );

          return ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
            children: <Widget>[
              _TradeHeroCard(
                selectedSymbol: selectedSymbol,
                tradeIntent: tradeIntent,
                signal: _signalForSymbol(signalItems, selectedSymbol),
                evaluation: tradeEvaluationAsync.valueOrNull,
              ),
              const SizedBox(height: 18),
              if (isWide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(flex: 7, child: chartPanel),
                    const SizedBox(width: 18),
                    Expanded(flex: 5, child: executionPanel),
                  ],
                )
              else ...<Widget>[
                chartPanel,
                const SizedBox(height: 18),
                executionPanel,
              ],
              const SizedBox(height: 18),
              activeTradesPanel,
              const SizedBox(height: 18),
              _PaperPortfolioPanel(
                state: paperState,
                onClose: (tradeId) {
                  ref.read(localPaperTradingProvider.notifier).close(tradeId);
                },
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _refreshTradeSurface(String userId) async {
    ref.invalidate(marketChartProvider);
    ref.invalidate(marketUniverseProvider);
    ref.invalidate(initialSignalsProvider);
    ref.invalidate(tradeEvaluationProvider);
    ref.invalidate(activeTradesProvider(userId));
    ref.invalidate(userPnLProvider(userId));
  }

  Future<void> _confirmAndExecute({
    required String userId,
    required String symbol,
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
  }) async {
    final executionController =
        ref.read(tradeExecutionControllerProvider.notifier);
    final amount = double.tryParse(_amountController.text.trim());
    if (amount == null || amount <= 0) {
      executionController.setAmount(0);
      return;
    }
    executionController.setAmount(amount);

    final confirmed = await showModalBottomSheet<bool>(
          context: context,
          backgroundColor: TradingPalette.deepNavy,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          ),
          builder: (sheetContext) {
            return _TradeConfirmSheet(
              symbol: symbol,
              side: ref.read(tradeExecutionControllerProvider).side,
              amount: amount,
              signal: intent,
              evaluation: evaluation,
            );
          },
        ) ??
        false;
    if (!confirmed) {
      return;
    }

    final response = await executionController.execute(
      userId: userId,
      symbol: symbol,
      intent: intent,
      evaluation: evaluation,
    );
    if (!mounted || response == null) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Trade ${response.status.toLowerCase()} for ${response.symbol} at ${response.executedPrice.toStringAsFixed(4)}',
        ),
      ),
    );
  }

  void _executePaperTrade({
    required String symbol,
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
    required MarketChartModel? chart,
  }) {
    final executionState = ref.read(tradeExecutionControllerProvider);
    final amount =
        double.tryParse(_amountController.text.trim()) ?? executionState.amount;
    final price = _paperMarketPrice(
      chart: chart,
      intent: intent,
      evaluation: evaluation,
    );
    final reason = _traderFacingReason(
      evaluation?.reason.trim().isNotEmpty == true
          ? evaluation!.reason
          : intent?.reason?.trim().isNotEmpty == true
              ? intent!.reason!
              : null,
      fallback:
          'Local paper fill created while live execution remains backend-authoritative.',
    );
    final position = ref.read(localPaperTradingProvider.notifier).execute(
          symbol: symbol,
          side: executionState.side,
          notional: amount,
          price: price,
          reason: reason,
        );
    HapticFeedback.mediumImpact();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Paper ${position.side} opened on ${position.symbol} at ${position.entry.toStringAsFixed(4)}',
        ),
      ),
    );
  }

  void _syncPaperMarketPrices({
    required MarketChartModel? chart,
    required MarketUniverseModel? universe,
  }) {
    final prices = <String, double>{};
    final chartPrice = _latestChartPrice(chart);
    if (chart != null && chartPrice > 0) {
      prices[chart.symbol.toUpperCase()] = chartPrice;
    }
    for (final entry in universe?.items ?? const <MarketUniverseEntryModel>[]) {
      if (entry.price > 0) {
        prices[entry.symbol.toUpperCase()] = entry.price;
      }
    }
    for (final entry
        in universe?.topGainers ?? const <MarketUniverseEntryModel>[]) {
      if (entry.price > 0) {
        prices[entry.symbol.toUpperCase()] = entry.price;
      }
    }
    for (final entry
        in universe?.highVolatility ?? const <MarketUniverseEntryModel>[]) {
      if (entry.price > 0) {
        prices[entry.symbol.toUpperCase()] = entry.price;
      }
    }
    for (final entry
        in universe?.aiPicks ?? const <MarketUniverseEntryModel>[]) {
      if (entry.price > 0) {
        prices[entry.symbol.toUpperCase()] = entry.price;
      }
    }
    if (prices.isEmpty) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }
      ref
          .read(localPaperTradingProvider.notifier)
          .markMarketPrices(prices, source: 'live_market');
    });
  }

  void _syncAmountField(double amount) {
    final current = double.tryParse(_amountController.text.trim());
    if (current == amount) {
      return;
    }
    final formatted =
        amount % 1 == 0 ? amount.toStringAsFixed(0) : amount.toStringAsFixed(2);
    _amountController.value = TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: formatted.length),
    );
  }
}

class _TradeHeroCard extends StatelessWidget {
  const _TradeHeroCard({
    required this.selectedSymbol,
    required this.tradeIntent,
    required this.signal,
    required this.evaluation,
  });

  final String selectedSymbol;
  final TradeIntent? tradeIntent;
  final SignalModel? signal;
  final TradeEvaluationModel? evaluation;

  @override
  Widget build(BuildContext context) {
    final effectiveSignal = signal;
    final opportunity = effectiveSignal == null
        ? null
        : SignalOpportunity.fromSignal(effectiveSignal);
    final resolvedEvaluation = evaluation;
    final confidence = resolvedEvaluation?.confidenceScore ??
        tradeIntent?.confidence ??
        effectiveSignal?.confidence;
    final confidenceLabel = confidence == null
        ? 'AI plan building'
        : 'Confidence ${(confidence * 100).toStringAsFixed(0)}%';
    final approvalLabel = resolvedEvaluation == null
        ? 'Risk check running'
        : resolvedEvaluation.allowTrade
            ? 'TRADE READY ${resolvedEvaluation.approvedSide}'
            : opportunity?.secondaryLabel ?? 'PAPER PLAN';
    final approvalColor = resolvedEvaluation == null
        ? TradingPalette.electricBlue
        : resolvedEvaluation.allowTrade
            ? TradingPalette.neonGreen
            : TradingPalette.neonRed;

    return GlassPanel(
      glowColor: TradingPalette.violet,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  opportunity?.heroTitle ?? 'AI Trade Terminal',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  opportunity?.tradePlanLabel ??
                      'Pick a symbol, follow the AI plan, and let backend risk validation decide if capital can be deployed.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: <Widget>[
                    StatusBadge(
                      label: selectedSymbol,
                      color: TradingPalette.electricBlue,
                    ),
                    StatusBadge(
                      label: confidenceLabel,
                      color: (tradeIntent?.lowConfidence ?? false)
                          ? TradingPalette.amber
                          : TradingPalette.neonGreen,
                    ),
                    StatusBadge(
                      label: tradeIntent?.side ??
                          effectiveSignal?.action ??
                          'MANUAL',
                      color: _sideColor(
                        tradeIntent?.side ?? effectiveSignal?.action ?? 'BUY',
                      ),
                    ),
                    StatusBadge(
                      label: approvalLabel,
                      color: approvalColor,
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          const LivePulseIndicator(
            label: 'EXEC LIVE',
            color: TradingPalette.neonGreen,
          ),
        ],
      ),
    );
  }
}

class _TradeExecutionPanel extends StatelessWidget {
  const _TradeExecutionPanel({
    required this.selectedSymbol,
    required this.tradeIntent,
    required this.tradeEvaluationAsync,
    required this.chart,
    required this.portfolioRead,
    required this.websocketState,
    required this.executionState,
    required this.paperState,
    required this.authDegraded,
    required this.amountController,
    required this.onSideChanged,
    required this.onAmountPresetSelected,
    required this.onAmountChanged,
    required this.onExecute,
    required this.onPaperExecute,
    required this.onDismissFeedback,
  });

  final String selectedSymbol;
  final TradeIntent? tradeIntent;
  final AsyncValue<TradeEvaluationModel> tradeEvaluationAsync;
  final MarketChartModel? chart;
  final PortfolioIntelligenceRead portfolioRead;
  final WsState websocketState;
  final TradeExecutionState executionState;
  final LocalPaperPortfolioState paperState;
  final bool authDegraded;
  final TextEditingController amountController;
  final ValueChanged<String> onSideChanged;
  final ValueChanged<double> onAmountPresetSelected;
  final ValueChanged<String> onAmountChanged;
  final VoidCallback? onExecute;
  final VoidCallback onPaperExecute;
  final VoidCallback onDismissFeedback;

  @override
  Widget build(BuildContext context) {
    final evaluation = tradeEvaluationAsync.valueOrNull;
    const institutionalEngine = InstitutionalIntelligenceEngine();
    const adaptiveEngine = AdaptiveAiIntelligenceEngine();
    const edgeEngine = EdgeValidationEngine();
    final planSignal = _signalFromTradeIntent(
      tradeIntent: tradeIntent,
      fallbackSide: executionState.side,
      evaluation: evaluation,
    );
    final outcomeReports = edgeEngine.signalOutcomes(
      planSignal == null ? const <SignalModel>[] : <SignalModel>[planSignal],
      chart: chart,
    );
    final outcomeReport = outcomeReports.isEmpty ? null : outcomeReports.first;
    final briefing = institutionalEngine.executionBriefing(
      symbol: selectedSymbol,
      side: executionState.side,
      notional: executionState.amount,
      evaluation: evaluation,
      signal: planSignal,
      chart: chart,
    );
    final precision = adaptiveEngine.executionPrecision(
      signal: planSignal,
      evaluation: evaluation,
      chart: chart,
    );
    final autopilot = adaptiveEngine.autopilot(
      chart: chart,
      signal: planSignal,
      evaluation: evaluation,
    );
    final safety = adaptiveEngine.autopilotSafety(
      signal: planSignal,
      evaluation: evaluation,
      chart: chart,
    );
    final executionOutcome = edgeEngine.executionOutcome(
      outcomeReport,
      chart: chart,
    );
    final replayMetadata = edgeEngine.replayMetadata(
      outcomeReports,
      chart: chart,
    );
    const infrastructureEngine = ProductionInfrastructureEngine();
    final realtimeResilience = infrastructureEngine.realtimeResilience(
      websocketState: websocketState,
    );
    final dataIntegrity = infrastructureEngine.marketDataIntegrity(
      chart: chart,
    );
    final reconciliation = infrastructureEngine.executionReconciliation(
      requestedSide: executionState.side,
      requestedAmount: executionState.amount,
      submitting: executionState.isSubmitting,
      evaluation: evaluation,
    );
    final failsafe = infrastructureEngine.failsafe(
      realtime: realtimeResilience,
      data: dataIntegrity,
      execution: reconciliation,
    );
    final failureHandling = infrastructureEngine.failureHandling(
      realtime: realtimeResilience,
      failsafe: failsafe,
    );
    final workspace = const TradingOperatingSystemEngine().executionWorkspace(
      portfolio: portfolioRead,
      signal: planSignal,
      evaluation: evaluation,
    );
    final executionReady = _canExecuteTrade(
      state: executionState,
      evaluation: evaluation,
    );
    return SectionCard(
      title: 'Execution Flow',
      subtitle:
          'Plan the entry instantly. Capital only deploys after backend meta and risk validation.',
      trailing: StatusBadge(
        label: executionState.isSubmitting
            ? 'SUBMITTING'
            : executionReady
                ? 'TRADE READY'
                : 'PLAN MODE',
        color: executionState.isSubmitting
            ? TradingPalette.amber
            : executionReady
                ? TradingPalette.neonGreen
                : TradingPalette.neonRed,
      ),
      glowColor: TradingPalette.neonGreen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          if (tradeIntent != null) ...<Widget>[
            _LiveSignalContextCard(tradeIntent: tradeIntent!),
            const SizedBox(height: 16),
          ],
          _BackendApprovalCard(
            symbol: selectedSymbol,
            side: executionState.side,
            evaluationAsync: tradeEvaluationAsync,
            authDegraded: authDegraded,
          ),
          const SizedBox(height: 18),
          ExecutionBriefingPanel(briefing: briefing),
          const SizedBox(height: 18),
          ExecutionPrecisionPanel(precision: precision),
          const SizedBox(height: 18),
          AutopilotPanel(autopilot: autopilot, safety: safety),
          const SizedBox(height: 18),
          ExecutionWorkspacePanel(read: workspace),
          const SizedBox(height: 18),
          FailsafeExecutionPanel(read: failsafe),
          if (failsafe.advisoryOnly) ...<Widget>[
            const SizedBox(height: 18),
            FailureHandlingPanel(read: failureHandling),
          ],
          const SizedBox(height: 18),
          ExecutionReconciliationPanel(read: reconciliation),
          const SizedBox(height: 18),
          ExecutionOutcomePanel(read: executionOutcome),
          if (planSignal != null) ...<Widget>[
            const SizedBox(height: 18),
            AiDecisionJournalPanel(
              entry: edgeEngine.decisionJournal(planSignal, outcomeReport),
            ),
          ],
          const SizedBox(height: 18),
          ReplayMetadataPanel(read: replayMetadata),
          if (chart != null) ...<Widget>[
            const SizedBox(height: 18),
            MicrostructurePanel(
              read: institutionalEngine.microstructureForChart(chart!),
            ),
            const SizedBox(height: 18),
            MarketContextPanel(
              contextRead: institutionalEngine.marketContextForChart(chart),
            ),
          ],
          const SizedBox(height: 18),
          Text(
            'Side',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          SegmentedButton<String>(
            segments: const <ButtonSegment<String>>[
              ButtonSegment<String>(
                value: 'BUY',
                icon: Icon(Icons.arrow_upward_rounded),
                label: Text('BUY'),
              ),
              ButtonSegment<String>(
                value: 'SELL',
                icon: Icon(Icons.arrow_downward_rounded),
                label: Text('SELL'),
              ),
            ],
            selected: <String>{executionState.side},
            onSelectionChanged: (selection) => onSideChanged(selection.first),
          ),
          const SizedBox(height: 18),
          Text(
            'Trade Amount',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: amountController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            inputFormatters: <TextInputFormatter>[
              FilteringTextInputFormatter.allow(RegExp(r'^\d*\.?\d{0,2}$')),
            ],
            onChanged: onAmountChanged,
            decoration: InputDecoration(
              prefixText: '\$ ',
              hintText: 'Enter order notional',
              filled: true,
              fillColor: TradingPalette.overlay,
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(18),
                borderSide: const BorderSide(color: TradingPalette.panelBorder),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(18),
                borderSide: const BorderSide(color: TradingPalette.panelBorder),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              for (final amount in const <double>[50, 100, 250, 500, 1000])
                ActionChip(
                  label: Text('\$${amount.toStringAsFixed(0)}'),
                  onPressed: executionState.isSubmitting
                      ? null
                      : () => onAmountPresetSelected(amount),
                ),
            ],
          ),
          const SizedBox(height: 18),
          _ExecutionGuardrailCard(
            symbol: selectedSymbol,
            side: executionState.side,
            amount: executionState.amount,
            tradeIntent: tradeIntent,
            evaluation: evaluation,
          ),
          if (executionState.errorMessage != null) ...<Widget>[
            const SizedBox(height: 16),
            _FeedbackCard(
              color: TradingPalette.neonRed,
              title: 'Execution Failed',
              message: executionState.errorMessage!,
              onDismiss: onDismissFeedback,
            ),
          ],
          if (executionState.lastResponse != null) ...<Widget>[
            const SizedBox(height: 16),
            _ExecutionSuccessCard(
              response: executionState.lastResponse!,
              onDismiss: onDismissFeedback,
            ),
          ],
          const SizedBox(height: 18),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onExecute,
              icon: executionState.isSubmitting
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(
                      executionState.side == 'BUY'
                          ? Icons.rocket_launch_rounded
                          : Icons.swap_vert_circle_rounded,
                    ),
              label: Text(
                executionState.isSubmitting
                    ? 'Sending order...'
                    : executionReady
                        ? 'Confirm ${executionState.side} on $selectedSymbol'
                        : 'Open as paper / wait for risk check',
              ),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: executionState.isSubmitting ? null : onPaperExecute,
              icon: const Icon(Icons.account_balance_wallet_rounded),
              label: Text(
                'Paper trade now - Balance \$${paperState.cashBalance.toStringAsFixed(0)}',
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            authDegraded
                ? 'Production auth is reconnecting. Local paper fills stay active; live orders remain disabled until backend authority returns.'
                : 'Paper mode is always available for practice. Live execution still requires backend meta and risk approval.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textMuted,
                ),
          ),
        ],
      ),
    );
  }
}

// ignore: unused_element
class _TradeChartSurface extends StatelessWidget {
  const _TradeChartSurface({
    required this.chart,
    required this.signal,
  });

  final MarketChartModel chart;
  final SignalModel? signal;

  @override
  Widget build(BuildContext context) {
    if (chart.candles.isEmpty) {
      return const SizedBox(
        height: 340,
        child: EmptyState(
          title: 'No chart data',
          subtitle: 'The backend did not return candles for this symbol yet.',
        ),
      );
    }

    final latest = chart.candles.last;
    final minPrice = chart.candles.map((item) => item.low).reduce(math.min);
    final maxPrice = chart.candles.map((item) => item.high).reduce(math.max);
    final width = math.max(420.0, chart.candles.length * 12.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Container(
            height: 340,
            color: TradingPalette.overlay,
            child: InteractiveViewer(
              minScale: 1,
              maxScale: 2.5,
              boundaryMargin: const EdgeInsets.all(24),
              child: SizedBox(
                width: width,
                height: 340,
                child: CustomPaint(
                  painter: _TradeCandlestickPainter(
                    candles: chart.candles,
                    minPrice: minPrice,
                    maxPrice: maxPrice,
                    signal: signal,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _MetricPill(
              label: 'Latest',
              value: latest.close.toStringAsFixed(
                latest.close >= 100 ? 2 : 4,
              ),
              accent: chart.changePct >= 0
                  ? TradingPalette.neonGreen
                  : TradingPalette.neonRed,
            ),
            _MetricPill(
              label: 'Change',
              value:
                  '${chart.changePct >= 0 ? '+' : ''}${chart.changePct.toStringAsFixed(2)}%',
              accent: chart.changePct >= 0
                  ? TradingPalette.neonGreen
                  : TradingPalette.neonRed,
            ),
            _MetricPill(
              label: 'Range',
              value:
                  '${minPrice.toStringAsFixed(2)} - ${maxPrice.toStringAsFixed(2)}',
            ),
            _MetricPill(
              label: 'Volume',
              value: latest.volume.toStringAsFixed(0),
            ),
          ],
        ),
      ],
    );
  }
}

class _TradeCandlestickPainter extends CustomPainter {
  const _TradeCandlestickPainter({
    required this.candles,
    required this.minPrice,
    required this.maxPrice,
    required this.signal,
  });

  final List<MarketCandleModel> candles;
  final double minPrice;
  final double maxPrice;
  final SignalModel? signal;

  @override
  void paint(Canvas canvas, Size size) {
    final bodyWidth = math.max(4.0, size.width / (candles.length * 1.8));
    final gap = size.width / candles.length;
    final priceRange = math.max(maxPrice - minPrice, 0.0000001);
    final chartRect = Rect.fromLTWH(0, 0, size.width, size.height);

    canvas.drawRect(
      chartRect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: <Color>[Color(0xFF111A31), Color(0xFF0B1122)],
        ).createShader(chartRect),
    );

    final gridPaint = Paint()
      ..color = TradingPalette.panelBorder.withOpacity(0.35)
      ..strokeWidth = 1;
    for (var step = 1; step <= 4; step += 1) {
      final y = size.height * (step / 5);
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    for (var index = 0; index < candles.length; index += 1) {
      final candle = candles[index];
      final x = (index * gap) + (gap / 2);
      final highY = _mapY(candle.high, priceRange, size.height);
      final lowY = _mapY(candle.low, priceRange, size.height);
      final openY = _mapY(candle.open, priceRange, size.height);
      final closeY = _mapY(candle.close, priceRange, size.height);
      final bullish = candle.close >= candle.open;
      final color = bullish ? TradingPalette.neonGreen : TradingPalette.neonRed;
      final wickPaint = Paint()
        ..color = color.withOpacity(0.9)
        ..strokeWidth = 1.3;
      final bodyPaint = Paint()
        ..color = color
        ..style = PaintingStyle.fill;

      canvas.drawLine(Offset(x, highY), Offset(x, lowY), wickPaint);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTRB(
            x - (bodyWidth / 2),
            math.min(openY, closeY),
            x + (bodyWidth / 2),
            math.max(openY, closeY) + 1.2,
          ),
          const Radius.circular(4),
        ),
        bodyPaint,
      );
    }

    final latestPrice = candles.last.close;
    final latestY = _mapY(latestPrice, priceRange, size.height);
    canvas.drawLine(
      Offset(0, latestY),
      Offset(size.width, latestY),
      Paint()
        ..color = TradingPalette.electricBlue.withOpacity(0.45)
        ..strokeWidth = 1,
    );

    if (signal != null && signal!.price > 0) {
      final signalY = _mapY(signal!.price, priceRange, size.height);
      canvas.drawLine(
        Offset(0, signalY),
        Offset(size.width, signalY),
        Paint()
          ..color = _sideColor(signal!.action).withOpacity(0.55)
          ..strokeWidth = 1.1,
      );
    }
  }

  double _mapY(double price, double priceRange, double height) {
    final ratio = (price - minPrice) / priceRange;
    return height - (ratio * height);
  }

  @override
  bool shouldRepaint(covariant _TradeCandlestickPainter oldDelegate) {
    return oldDelegate.candles != candles ||
        oldDelegate.minPrice != minPrice ||
        oldDelegate.maxPrice != maxPrice ||
        oldDelegate.signal != signal;
  }
}

class _SymbolStrip extends StatelessWidget {
  const _SymbolStrip({
    required this.symbols,
    required this.selectedSymbol,
    required this.onSelect,
  });

  final List<String> symbols;
  final String selectedSymbol;
  final ValueChanged<String> onSelect;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        children: symbols
            .map(
              (symbol) => Padding(
                padding: const EdgeInsets.only(right: 10),
                child: ChoiceChip(
                  label: Text(symbol),
                  selected: symbol == selectedSymbol,
                  onSelected: (_) => onSelect(symbol),
                ),
              ),
            )
            .toList(),
      ),
    );
  }
}

class _LiveSignalContextCard extends StatelessWidget {
  const _LiveSignalContextCard({required this.tradeIntent});

  final TradeIntent tradeIntent;

  @override
  Widget build(BuildContext context) {
    final confidence = tradeIntent.confidence ?? 0;
    final side = tradeIntent.side ?? 'MANUAL';
    final accent = _sideColor(side);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: accent.withOpacity(0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: accent.withOpacity(0.32)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              StatusBadge(label: side, color: accent),
              const SizedBox(width: 10),
              StatusBadge(
                label: '${(confidence * 100).toStringAsFixed(0)}%',
                color: TradingPalette.electricBlue,
              ),
              if (tradeIntent.lowConfidence) ...<Widget>[
                const SizedBox(width: 10),
                const StatusBadge(
                  label: 'WATCHLIST',
                  color: TradingPalette.amber,
                ),
              ],
            ],
          ),
          const SizedBox(height: 10),
          Text(
            _traderFacingReason(
              tradeIntent.reason,
              fallback:
                  'Live signal matched for this symbol. Backend risk checks still run before execution.',
            ),
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                ),
          ),
          if ((tradeIntent.rejectionReason ?? '').isNotEmpty) ...<Widget>[
            const SizedBox(height: 10),
            Text(
              _traderFacingReason(
                tradeIntent.rejectionReason,
                fallback:
                    'Live capital is waiting for cleaner confirmation. Paper mode remains available.',
              ),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.amber,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ],
      ),
    );
  }
}

class _BackendApprovalCard extends StatelessWidget {
  const _BackendApprovalCard({
    required this.symbol,
    required this.side,
    required this.evaluationAsync,
    required this.authDegraded,
  });

  final String symbol;
  final String side;
  final AsyncValue<TradeEvaluationModel> evaluationAsync;
  final bool authDegraded;

  @override
  Widget build(BuildContext context) {
    return evaluationAsync.when(
      data: (evaluation) {
        final allowed = evaluation.allowTrade;
        final sideMatch = evaluation.approvedSide == side;
        final accent = allowed && sideMatch
            ? TradingPalette.neonGreen
            : allowed
                ? TradingPalette.amber
                : TradingPalette.neonRed;
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: accent.withOpacity(0.10),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: accent.withOpacity(0.34)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  StatusBadge(
                    label: allowed ? 'RISK APPROVED' : 'PAPER PLAN ONLY',
                    color: accent,
                  ),
                  StatusBadge(
                    label: evaluation.approvedSide,
                    color: _sideColor(evaluation.approvedSide),
                  ),
                  StatusBadge(
                    label: 'Score ${evaluation.alphaScore.toStringAsFixed(0)}',
                    color: TradingPalette.electricBlue,
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                '${_strategyLabel(evaluation.strategy)} on $symbol (${evaluation.timeframe})',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                _traderFacingReason(
                  evaluation.reason,
                  fallback:
                      'AI is building a controlled trade plan while backend risk checks stay authoritative.',
                ),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: TradingPalette.textPrimary,
                    ),
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: <Widget>[
                  _MetricPill(
                    label: 'Probability',
                    value:
                        '${(evaluation.inference.tradeProbability * 100).toStringAsFixed(0)}%',
                    accent: TradingPalette.electricBlue,
                  ),
                  _MetricPill(
                    label: 'Expected Return',
                    value:
                        '${(evaluation.alphaDecision.expectedReturn * 100).toStringAsFixed(2)}%',
                    accent: TradingPalette.neonGreen,
                  ),
                  _MetricPill(
                    label: 'Risk Score',
                    value:
                        '${(evaluation.alphaDecision.riskScore * 100).toStringAsFixed(2)}%',
                    accent: TradingPalette.amber,
                  ),
                ],
              ),
              if (allowed && !sideMatch) ...<Widget>[
                const SizedBox(height: 10),
                Text(
                  'Current side is $side, but backend approved ${evaluation.approvedSide}. Switch side to continue.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.amber,
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
            ],
          ),
        );
      },
      loading: () => const SizedBox(
        height: 140,
        child: LoadingState(label: 'Building AI trade plan'),
      ),
      error: (error, _) => _DegradedApprovalCard(
        symbol: symbol,
        authDegraded: authDegraded,
      ),
    );
  }
}

class _DegradedApprovalCard extends StatelessWidget {
  const _DegradedApprovalCard({
    required this.symbol,
    required this.authDegraded,
  });

  final String symbol;
  final bool authDegraded;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: TradingPalette.amber.withOpacity(0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: TradingPalette.amber.withOpacity(0.34)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              StatusBadge(label: 'PAPER READY', color: TradingPalette.amber),
              StatusBadge(label: 'LIVE LOCKED', color: TradingPalette.violet),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Paper execution is available for $symbol',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            authDegraded
                ? 'Realtime auth is reconnecting. The app stays open in advisory mode; use paper trade while live execution remains protected.'
                : 'Backend validation is still building. You can open a local paper position now without touching live execution.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                ),
          ),
        ],
      ),
    );
  }
}

class _ExecutionGuardrailCard extends StatelessWidget {
  const _ExecutionGuardrailCard({
    required this.symbol,
    required this.side,
    required this.amount,
    required this.tradeIntent,
    required this.evaluation,
  });

  final String symbol;
  final String side;
  final double amount;
  final TradeIntent? tradeIntent;
  final TradeEvaluationModel? evaluation;

  @override
  Widget build(BuildContext context) {
    final resolvedEvaluation = evaluation;
    final signalConfidence =
        resolvedEvaluation?.confidenceScore ?? tradeIntent?.confidence;
    final confidenceText = resolvedEvaluation == null
        ? 'AI is preparing the live plan. Execution unlocks only after risk validation.'
        : resolvedEvaluation.allowTrade
            ? 'Approved $side $symbol using ${resolvedEvaluation.strategy} at ${(signalConfidence! * 100).toStringAsFixed(0)}% confidence.'
            : 'Capital is protected for this setup. Use paper/shadow tracking or switch to the next stronger symbol.';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Trade plan summary',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          Text(
            '$side $symbol for \$${amount.toStringAsFixed(2)}',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: _sideColor(side),
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            confidenceText,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          Text(
            resolvedEvaluation == null
                ? 'The app stays active with chart, plan, and watch progression while risk validation finishes.'
                : resolvedEvaluation.allowTrade
                    ? 'Risk budget ${resolvedEvaluation.riskBudget.toStringAsFixed(4)} | rollout ${(resolvedEvaluation.rolloutCapitalFraction * 100).toStringAsFixed(0)}% | regime ${resolvedEvaluation.snapshot.regime}'
                    : 'Unsafe capital deployment is stopped before it reaches execution. Paper tracking remains available.',
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
        ],
      ),
    );
  }
}

class _ExecutionSuccessCard extends StatelessWidget {
  const _ExecutionSuccessCard({
    required this.response,
    required this.onDismiss,
  });

  final TradeExecutionResponseModel response;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    return _FeedbackCard(
      color: TradingPalette.neonGreen,
      title: 'Execution Confirmed',
      message:
          '${response.symbol} ${response.side} ${response.status.toLowerCase()} at ${response.executedPrice.toStringAsFixed(4)} for ${response.executedQuantity.toStringAsFixed(6)} units.\nSL ${response.stopLoss.toStringAsFixed(4)} | TP ${response.takeProfit.toStringAsFixed(4)}',
      footer: response.explanation.isEmpty ? null : response.explanation,
      onDismiss: onDismiss,
    );
  }
}

class _FeedbackCard extends StatelessWidget {
  const _FeedbackCard({
    required this.color,
    required this.title,
    required this.message,
    required this.onDismiss,
    this.footer,
  });

  final Color color;
  final String title;
  final String message;
  final String? footer;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.34)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: color,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ),
              IconButton(
                onPressed: onDismiss,
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          Text(
            message,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                ),
          ),
          if ((footer ?? '').isNotEmpty) ...<Widget>[
            const SizedBox(height: 10),
            Text(
              footer!,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }
}

class _TradeConfirmSheet extends StatelessWidget {
  const _TradeConfirmSheet({
    required this.symbol,
    required this.side,
    required this.amount,
    required this.signal,
    required this.evaluation,
  });

  final String symbol;
  final String side;
  final double amount;
  final TradeIntent? signal;
  final TradeEvaluationModel? evaluation;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Confirm Trade',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 12),
          Text(
            '$side $symbol for \$${amount.toStringAsFixed(2)}',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  color: _sideColor(side),
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 10),
          Text(
            _traderFacingReason(
              evaluation?.reason ?? signal?.reason,
              fallback:
                  'This request will be sent to the backend execution pipeline for final risk validation and order placement.',
            ),
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              if (signal?.strategy != null && signal!.strategy!.isNotEmpty)
                StatusBadge(
                  label: signal!.strategy!,
                  color: TradingPalette.electricBlue,
                ),
              if (signal?.confidence != null)
                StatusBadge(
                  label:
                      'Confidence ${((evaluation?.confidenceScore ?? signal!.confidence!) * 100).toStringAsFixed(0)}%',
                  color:
                      (evaluation?.allowTrade == false || signal!.lowConfidence)
                          ? TradingPalette.amber
                          : TradingPalette.neonGreen,
                ),
              StatusBadge(
                label: evaluation?.allowTrade == true
                    ? 'Backend validated'
                    : 'Risk checked',
                color: TradingPalette.violet,
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: <Widget>[
              Expanded(
                child: OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(false),
                  child: const Text('Cancel'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: () => Navigator.of(context).pop(true),
                  child: const Text('Execute'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({
    required this.label,
    required this.value,
    this.accent,
  });

  final String label;
  final String value;
  final Color? accent;

  @override
  Widget build(BuildContext context) {
    final resolvedAccent = accent ?? TradingPalette.textPrimary;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: resolvedAccent,
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

Widget _buildActiveTradesPanel({
  required String selectedSymbol,
  required AsyncValue<List<ActiveTradeModel>> activeTradesAsync,
}) {
  return SectionCard(
    title: 'Open Positions',
    subtitle:
        'Positions refresh after execution so the portfolio and trade tab stay in sync.',
    trailing: const StatusBadge(label: 'PORTFOLIO'),
    glowColor: TradingPalette.violet,
    child: activeTradesAsync.when(
      data: (trades) {
        if (trades.isEmpty) {
          return const EmptyState(
            title: 'No active positions',
            subtitle:
                'Executed trades will appear here once the backend opens them.',
          );
        }

        final filtered = trades
            .where((trade) => trade.symbol == selectedSymbol)
            .toList(growable: false);
        final visible =
            filtered.isNotEmpty ? filtered : trades.take(4).toList();

        return Column(
          children: visible
              .map(
                (trade) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Container(
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
                            color: _sideColor(trade.side).withOpacity(0.16),
                          ),
                          child: Icon(
                            trade.side.toUpperCase() == 'BUY'
                                ? Icons.arrow_upward_rounded
                                : Icons.arrow_downward_rounded,
                            color: _sideColor(trade.side),
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
                                'Qty ${trade.executedQuantity.toStringAsFixed(6)} | Entry ${trade.entry.toStringAsFixed(4)}',
                                style: const TextStyle(
                                  color: TradingPalette.textMuted,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'SL ${trade.stopLoss.toStringAsFixed(4)} | TP ${trade.takeProfit.toStringAsFixed(4)}',
                                style: const TextStyle(
                                  color: TradingPalette.textFaint,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 12),
                        StatusBadge(
                          label: trade.status,
                          color: TradingPalette.electricBlue,
                        ),
                      ],
                    ),
                  ),
                ),
              )
              .toList(),
        );
      },
      loading: () => const LoadingState(label: 'Loading open positions'),
      error: (error, _) => ErrorState(message: userMessageForError(error)),
    ),
  );
}

class _PaperPortfolioPanel extends StatelessWidget {
  const _PaperPortfolioPanel({
    required this.state,
    required this.onClose,
  });

  final LocalPaperPortfolioState state;
  final ValueChanged<String> onClose;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Paper Portfolio',
      subtitle:
          'Local simulated fills are marked to live market data with TP/SL and PnL. Live execution is separate.',
      trailing: StatusBadge(
        label: '${state.positions.length} PAPER',
        color: TradingPalette.amber,
      ),
      glowColor: TradingPalette.amber,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricPill(
                label: 'Cash',
                value: '\$${state.cashBalance.toStringAsFixed(0)}',
                accent: TradingPalette.electricBlue,
              ),
              _MetricPill(
                label: 'Equity',
                value: '\$${state.equity.toStringAsFixed(0)}',
                accent: TradingPalette.neonGreen,
              ),
              _MetricPill(
                label: 'Open Notional',
                value: '\$${state.openNotional.toStringAsFixed(0)}',
                accent: TradingPalette.amber,
              ),
              _MetricPill(
                label: 'PnL',
                value:
                    '${state.pnlPct >= 0 ? '+' : ''}${(state.pnlPct * 100).toStringAsFixed(2)}%',
                accent: state.pnlPct >= 0
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (state.positions.isEmpty)
            const EmptyState(
              title: 'No paper positions yet',
              subtitle:
                  'Press Paper trade now to open a simulated position instantly.',
            )
          else
            ...state.positions.map(
              (position) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: TradingPalette.overlay,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: TradingPalette.panelBorder),
                  ),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        position.side == 'SELL'
                            ? Icons.arrow_downward_rounded
                            : Icons.arrow_upward_rounded,
                        color: _sideColor(position.side),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              '${position.symbol} ${position.side}',
                              style:
                                  const TextStyle(fontWeight: FontWeight.w900),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Entry ${position.entry.toStringAsFixed(4)} | Qty ${position.quantity.toStringAsFixed(5)}',
                              style: const TextStyle(
                                color: TradingPalette.textMuted,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Mark ${position.currentPrice.toStringAsFixed(4)} | ${position.marketDataSource.replaceAll('_', ' ')}',
                              style: const TextStyle(
                                color: TradingPalette.electricBlue,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'SL ${position.stopLoss.toStringAsFixed(4)} | TP ${position.takeProfit.toStringAsFixed(4)}',
                              style: const TextStyle(
                                color: TradingPalette.textFaint,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: <Widget>[
                          Text(
                            '${position.simulatedPnl >= 0 ? '+' : ''}\$${position.simulatedPnl.toStringAsFixed(2)}',
                            style: TextStyle(
                              color: position.simulatedPnl >= 0
                                  ? TradingPalette.neonGreen
                                  : TradingPalette.neonRed,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                          Text(
                            '${position.pnlPct >= 0 ? '+' : ''}${(position.pnlPct * 100).toStringAsFixed(2)}%',
                            style: const TextStyle(
                              color: TradingPalette.textMuted,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          TextButton(
                            onPressed: () => onClose(position.tradeId),
                            child: const Text('Close'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

List<String> _buildSymbolOptions({
  required String selectedSymbol,
  required List<SignalModel> signals,
  required MarketUniverseModel? universe,
}) {
  final ordered = <String>[selectedSymbol];
  final seen = <String>{selectedSymbol};

  void add(String value) {
    final symbol = value.trim().toUpperCase();
    if (symbol.isEmpty || !seen.add(symbol)) {
      return;
    }
    ordered.add(symbol);
  }

  for (final signal in signals) {
    add(signal.symbol);
  }
  for (final entry in universe?.aiPicks ?? const <MarketUniverseEntryModel>[]) {
    add(entry.symbol);
  }
  for (final entry
      in universe?.topGainers ?? const <MarketUniverseEntryModel>[]) {
    add(entry.symbol);
  }
  return ordered.take(14).toList(growable: false);
}

SignalModel? _signalForSymbol(List<SignalModel> signals, String symbol) {
  for (final signal in signals) {
    if (signal.symbol == symbol) {
      return signal;
    }
  }
  return null;
}

SignalModel? _signalFromTradeIntent({
  required TradeIntent? tradeIntent,
  required String fallbackSide,
  required TradeEvaluationModel? evaluation,
}) {
  final intent = tradeIntent;
  if (intent == null) {
    return null;
  }
  final confidence = intent.confidence ?? evaluation?.confidenceScore ?? 0;
  final confidencePct = confidence <= 1 ? confidence * 100 : confidence;
  return SignalModel(
    signalId: intent.signalId ?? '',
    symbol: intent.symbol,
    action: intent.side ?? fallbackSide,
    strategy: _strategyLabel(intent.strategy ?? 'AI'),
    confidence: confidence,
    alphaScore: confidencePct,
    regime: evaluation?.snapshot.regime ?? 'UNKNOWN',
    price: intent.price ?? evaluation?.snapshot.price ?? 0,
    signalVersion: 0,
    publishedAt: DateTime.now(),
    decisionReason: _traderFacingReason(intent.reason),
    degradedMode: false,
    requiredTier: 'pro',
    minBalance: 0,
    rejectionReason: intent.rejectionReason == null
        ? null
        : _traderFacingReason(intent.rejectionReason),
    lowConfidence: intent.lowConfidence,
    quality: 'trade_plan',
    qualityScore: confidencePct,
    qualityReasons: const <String>[],
    executionAllowed: evaluation?.allowTrade ?? false,
    marketDataStale: false,
    marketDataSources: const <String, String>{},
  );
}

double _paperMarketPrice({
  required MarketChartModel? chart,
  required TradeIntent? intent,
  required TradeEvaluationModel? evaluation,
}) {
  final chartPrice = _latestChartPrice(chart);
  if (chartPrice > 0) {
    return chartPrice;
  }
  final evaluationPrice = evaluation?.snapshot.price ?? 0;
  if (evaluationPrice > 0) {
    return evaluationPrice;
  }
  final intentPrice = intent?.price ?? 0;
  if (intentPrice > 0) {
    return intentPrice;
  }
  return 0;
}

double _latestChartPrice(MarketChartModel? chart) {
  if (chart == null) {
    return 0;
  }
  if (chart.latestPrice > 0) {
    return chart.latestPrice;
  }
  if (chart.candles.isNotEmpty && chart.candles.last.close > 0) {
    return chart.candles.last.close;
  }
  return 0;
}

bool _canExecuteTrade({
  required TradeExecutionState state,
  required TradeEvaluationModel? evaluation,
}) {
  if (state.isSubmitting || state.amount <= 0 || evaluation == null) {
    return false;
  }
  if (!evaluation.allowTrade) {
    return false;
  }
  return evaluation.approvedSide == state.side;
}

String _strategyLabel(String? value) {
  final raw = (value ?? '').trim();
  if (raw.isEmpty) {
    return 'AI trade plan';
  }
  final normalized = raw
      .replaceAll(RegExp(r'[_\-]+'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  if (normalized.toLowerCase().contains('low confidence watchlist')) {
    return 'AI preparing entry';
  }
  if (normalized.toLowerCase().contains('fallback')) {
    return 'Conservative AI watch';
  }
  return normalized
      .split(' ')
      .where((part) => part.isNotEmpty)
      .map((part) => part.length <= 3
          ? part.toUpperCase()
          : '${part[0].toUpperCase()}${part.substring(1).toLowerCase()}')
      .join(' ');
}

String _traderFacingReason(String? value, {String? fallback}) {
  final raw = (value ?? '').trim();
  if (raw.isEmpty) {
    return fallback ??
        'AI is monitoring this setup while live execution remains protected by backend risk checks.';
  }
  final lower = raw.toLowerCase();
  final messages = <String>[];

  void add(String message) {
    if (!messages.contains(message)) {
      messages.add(message);
    }
  }

  if (lower.contains('confidence_below_floor') ||
      lower.contains('low_confidence') ||
      lower.contains('ai_low_confidence')) {
    add(
      'Confidence is still building, so live capital is waiting for stronger confirmation.',
    );
  }
  if (lower.contains('whale_conflict') ||
      lower.contains('conflicts with whale')) {
    add(
      'Whale flow is mixed; paper trading is available while live risk stays reduced.',
    );
  }
  if (lower.contains('alpha_engine_rejected')) {
    add('AI edge quality is not strong enough for live execution yet.');
  }
  if (lower.contains('latency threshold') ||
      lower.contains('latency_threshold') ||
      lower.contains('backend validation')) {
    add('Realtime validation is refreshing before live execution is allowed.');
  }
  if (lower.contains('fallback_watchlist') ||
      lower.contains('rule-based fallback')) {
    add(
      'AI is tracking this as a conservative watchlist setup while confirmation builds.',
    );
  }
  if (lower.contains('blocked:')) {
    add(
      'Live execution is paused for this setup, but paper mode can still simulate the plan.',
    );
  }
  if (messages.isNotEmpty) {
    return messages.join(' ');
  }

  final cleaned = raw
      .replaceAll(RegExp(r'\bstrict_gate:'), '')
      .replaceAll(RegExp(r'\bmeta:'), '')
      .replaceAll(RegExp(r'\blearning:'), '')
      .replaceAll(RegExp(r'[_|]+'), ' ')
      .replaceAll(RegExp(r'\s+'), ' ')
      .trim();
  if (cleaned.isEmpty) {
    return fallback ??
        'AI is monitoring this setup while live execution remains protected by backend risk checks.';
  }
  return cleaned;
}

Color _sideColor(String side) {
  return side.toUpperCase() == 'SELL'
      ? TradingPalette.neonRed
      : TradingPalette.neonGreen;
}

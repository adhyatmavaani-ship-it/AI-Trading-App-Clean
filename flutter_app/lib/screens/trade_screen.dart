import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/adaptive_ai_intelligence_engine.dart';
import '../core/ai_opportunity_engine.dart';
import '../core/error_presenter.dart';
import '../core/institutional_intelligence_engine.dart';
import '../core/technical_analysis_engine.dart';
import '../core/trading_palette.dart';
import '../core/websocket_service.dart';
import '../features/auth/providers/auth_provider.dart';
import '../features/market/providers/market_providers.dart';
import '../features/pnl/providers/pnl_providers.dart';
import '../features/retention/providers/retention_providers.dart';
import '../features/signals/providers/signal_providers.dart';
import '../features/trade/providers/trade_providers.dart';
import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/signal.dart';
import '../models/trade_execution.dart';
import '../providers/app_providers.dart';
import '../widgets/glass_panel.dart';
import '../widgets/institutional_trust_widgets.dart';
import '../widgets/live_pulse_indicator.dart';
import '../widgets/pro_trading_chart.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';
import '../widgets/status_badge.dart';

class TradeScreen extends ConsumerStatefulWidget {
  const TradeScreen({super.key});

  @override
  ConsumerState<TradeScreen> createState() => _TradeScreenState();
}

class _TradeScreenState extends ConsumerState<TradeScreen> {
  late final TextEditingController _amountController;
  late final ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _amountController = TextEditingController(text: '100');
    _scrollController = ScrollController(keepScrollOffset: false);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scrollController.hasClients) {
        return;
      }
      _scrollController.jumpTo(0);
    });
    ref.listenManual<String>(
      selectedMarketSymbolProvider,
      (_, __) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted || !_scrollController.hasClients) {
            return;
          }
          _scrollController.animateTo(
            0,
            duration: const Duration(milliseconds: 260),
            curve: Curves.easeOutCubic,
          );
        });
      },
    );
  }

  @override
  void dispose() {
    _amountController.dispose();
    _scrollController.dispose();
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
    final technicalReport = marketChartAsync.valueOrNull == null
        ? null
        : const TechnicalAnalysisEngine()
            .analyze(marketChartAsync.valueOrNull!);
    final socketState =
        ref.watch(webSocketServiceProvider).stateListenable.value;
    final marketUniverseAsync = ref.watch(marketUniverseProvider);
    final activeTradesAsync = ref.watch(activeTradesProvider(userId));
    final signalFeed = ref.watch(signalFeedProvider);
    final localMemory = ref.watch(localAiMemoryProvider);
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
    final riskShield = _riskShieldPreview(
      side: executionState.side,
      amount: executionState.amount,
      paperState: paperState,
      chart: marketChartAsync.valueOrNull,
      evaluation: tradeEvaluationAsync.valueOrNull,
      intent: tradeIntent,
    );
    final executionBlocked = executionState.isSubmitting ||
        !paperState.liveUnlocked ||
        !_canExecuteTrade(
          state: executionState,
          evaluation: tradeEvaluationAsync.valueOrNull,
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
            executionState: executionState,
            paperState: paperState,
            riskShield: riskShield,
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
              userId: userId,
              symbol: selectedSymbol,
              intent: tradeIntent,
              evaluation: tradeEvaluationAsync.valueOrNull,
              chart: marketChartAsync.valueOrNull,
              riskShield: riskShield,
            ),
            onDismissFeedback: executionController.clearFeedback,
          );
          Widget buildStickyExecutionBar() {
            return _StickyExecutionBar(
              disabled: executionState.isSubmitting,
              activeSide: executionState.side,
              websocketState: socketState,
              onBuy: () {
                executionController.setSide('BUY');
                if (!executionBlocked) {
                  _confirmAndExecute(
                    userId: userId,
                    symbol: selectedSymbol,
                    intent: tradeIntent,
                    evaluation: tradeEvaluationAsync.valueOrNull,
                  );
                }
              },
              onSell: () {
                executionController.setSide('SELL');
                if (!executionBlocked) {
                  _confirmAndExecute(
                    userId: userId,
                    symbol: selectedSymbol,
                    intent: tradeIntent,
                    evaluation: tradeEvaluationAsync.valueOrNull,
                  );
                }
              },
              onAskAi: () => _showAiReadout(
                context: context,
                symbol: selectedSymbol,
                chart: marketChartAsync.valueOrNull,
                signal: _signalForSymbol(signalItems, selectedSymbol),
              ),
              onAuto: () async {
                await ref
                    .read(tradingRepositoryProvider)
                    .setAssistantMode('FULL_AUTO');
                ref.invalidate(assistantModeProvider);
                ref.invalidate(marketChartProvider);
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Auto mode armed. Manual override remains active.',
                      ),
                    ),
                  );
                }
              },
            );
          }

          final chartPanel = SectionCard(
            title: 'TradingView-style Live Chart',
            subtitle:
                'Full candle view for $selectedSymbol with timeframe, symbol, and fullscreen controls.',
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
                    activeTrades: activeTradesAsync.valueOrNull ??
                        const <ActiveTradeModel>[],
                    fullscreenActionBar: buildStickyExecutionBar(),
                    height: isWide
                        ? 520
                        : math.max(
                            520, MediaQuery.sizeOf(context).height * 0.56),
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
          final stickyExecutionBar = buildStickyExecutionBar();

          return Stack(
            children: <Widget>[
              ListView(
                controller: _scrollController,
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 6, 20, 112),
                children: <Widget>[
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
                    _BeginnerAiCoachPanel(report: technicalReport),
                    const SizedBox(height: 18),
                    _TechnicalAiReportPanel(
                      report: technicalReport,
                      localMemory: localMemory,
                    ),
                    const SizedBox(height: 18),
                    executionPanel,
                  ],
                  if (isWide) ...<Widget>[
                    const SizedBox(height: 18),
                    _BeginnerAiCoachPanel(report: technicalReport),
                    const SizedBox(height: 18),
                    _TechnicalAiReportPanel(
                      report: technicalReport,
                      localMemory: localMemory,
                    ),
                  ],
                  const SizedBox(height: 18),
                  _TradeHeroCard(
                    selectedSymbol: selectedSymbol,
                    tradeIntent: tradeIntent,
                    signal: _signalForSymbol(signalItems, selectedSymbol),
                    evaluation: tradeEvaluationAsync.valueOrNull,
                  ),
                  const SizedBox(height: 14),
                  _AiReasoningPanel(
                    symbol: selectedSymbol,
                    chart: marketChartAsync.valueOrNull,
                    signal: _signalForSymbol(signalItems, selectedSymbol),
                    evaluation: tradeEvaluationAsync.valueOrNull,
                    executionState: executionState,
                    activeTrades: activeTradesAsync.valueOrNull ??
                        const <ActiveTradeModel>[],
                  ),
                  const SizedBox(height: 18),
                  activeTradesPanel,
                  const SizedBox(height: 18),
                  _PaperPortfolioPanel(
                    state: paperState,
                    onClose: (tradeId) {
                      ref
                          .read(localPaperTradingProvider.notifier)
                          .close(tradeId);
                    },
                    onAcknowledgeLesson: ({
                      required tradeId,
                      required lesson,
                      required acknowledged,
                    }) {
                      ref
                          .read(localPaperTradingProvider.notifier)
                          .acknowledgeLesson(
                            tradeId: tradeId,
                            lesson: lesson,
                            acknowledged: acknowledged,
                          );
                    },
                  ),
                ],
              ),
              Positioned(
                left: 16,
                right: 16,
                bottom: 14,
                child: stickyExecutionBar,
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

  Future<void> _executePaperTrade({
    required String userId,
    required String symbol,
    required TradeIntent? intent,
    required TradeEvaluationModel? evaluation,
    required MarketChartModel? chart,
    required RiskShieldPreview riskShield,
  }) async {
    final executionController =
        ref.read(tradeExecutionControllerProvider.notifier);
    final executionState = ref.read(tradeExecutionControllerProvider);
    final amount =
        double.tryParse(_amountController.text.trim()) ?? executionState.amount;
    if (amount <= 0) {
      executionController.setAmount(0);
      return;
    }
    executionController.setAmount(amount);
    final price = _paperMarketPrice(
      chart: chart,
      intent: intent,
      evaluation: evaluation,
    );
    final response = await executionController.executePaperSandbox(
      userId: userId,
      symbol: symbol,
      intent: intent,
      evaluation: evaluation,
      paperState: ref.read(localPaperTradingProvider),
      riskShield: riskShield,
      selectedPrice: price,
    );
    if (!mounted || response == null) {
      return;
    }
    ref.read(localPaperTradingProvider.notifier).mirrorBackendFill(
          response: response,
          reason: response.explanation.isNotEmpty
              ? response.explanation
              : 'Backend paper sandbox fill',
        );
    HapticFeedback.mediumImpact();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Paper ${response.side} submitted on ${response.symbol} at ${response.executedPrice.toStringAsFixed(4)}',
        ),
      ),
    );
  }

  void _showAiReadout({
    required BuildContext context,
    required String symbol,
    required MarketChartModel? chart,
    required SignalModel? signal,
  }) {
    final guide = chart?.executionGuide;
    final reasons = <String>[
      if (signal?.decisionReason.trim().isNotEmpty == true)
        signal!.decisionReason,
      if ((chart?.marketRegime.state ?? '').trim().isNotEmpty)
        'Regime: ${chart!.marketRegime.state}. Confidence ${chart.marketRegime.confidence.toStringAsFixed(0)}%.',
      if (guide != null && guide.riskReward > 0)
        'Execution plan: ${guide.side} with R:R ${guide.riskReward.toStringAsFixed(2)}.',
      if (chart == null || chart.candles.isEmpty)
        'Live candles are not verified yet. AI should wait instead of forcing a setup.',
    ];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: TradingPalette.deepNavy,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(22, 18, 22, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'AI Readout: $symbol',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
              const SizedBox(height: 14),
              for (final reason in reasons)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Text(reason),
                ),
            ],
          ),
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

class _AiReasoningPanel extends StatelessWidget {
  const _AiReasoningPanel({
    required this.symbol,
    required this.chart,
    required this.signal,
    required this.evaluation,
    required this.executionState,
    required this.activeTrades,
  });

  final String symbol;
  final MarketChartModel? chart;
  final SignalModel? signal;
  final TradeEvaluationModel? evaluation;
  final TradeExecutionState executionState;
  final List<ActiveTradeModel> activeTrades;

  @override
  Widget build(BuildContext context) {
    final activeTrade = activeTrades
        .where((trade) => trade.symbol.toUpperCase() == symbol.toUpperCase())
        .firstOrNull;
    final guide = chart?.executionGuide;
    final allowTrade = evaluation?.allowTrade == true;
    final side = (evaluation?.approvedSide.isNotEmpty == true
            ? evaluation!.approvedSide
            : signal?.action ?? guide?.side ?? 'WAIT')
        .toUpperCase();
    final title = allowTrade
        ? '$symbol $side validated'
        : activeTrade != null
            ? '$symbol active trade under AI watch'
            : '$symbol setup waiting';
    final reasons = _reasoningLines(
      symbol: symbol,
      chart: chart,
      signal: signal,
      evaluation: evaluation,
      activeTrade: activeTrade,
    );
    final color = allowTrade
        ? TradingPalette.neonGreen
        : activeTrade != null
            ? TradingPalette.electricBlue
            : TradingPalette.amber;
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                activeTrade != null
                    ? Icons.auto_graph_rounded
                    : allowTrade
                        ? Icons.verified_rounded
                        : Icons.psychology_alt_rounded,
                color: color,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label: chart?.activeAssistantMode ?? 'ASSISTED',
                color: color,
              ),
            ],
          ),
          const SizedBox(height: 12),
          _AiStateRibbon(
            stage: _aiStage(
              chart: chart,
              signal: signal,
              evaluation: evaluation,
              executionState: executionState,
              activeTrade: activeTrade,
            ),
          ),
          const SizedBox(height: 12),
          if (chart != null) ...<Widget>[
            _LiveConfidenceDelta(chart: chart!, evaluation: evaluation),
            const SizedBox(height: 12),
          ],
          for (final reason in reasons.take(4))
            Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Padding(
                    padding: const EdgeInsets.only(top: 7),
                    child: Icon(Icons.circle, size: 6, color: color),
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      reason,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: TradingPalette.textMuted,
                            height: 1.25,
                          ),
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

class _AiStateRibbon extends StatelessWidget {
  const _AiStateRibbon({required this.stage});

  final String stage;

  @override
  Widget build(BuildContext context) {
    const stages = <String>[
      'Scanning Market',
      'Ranking Opportunities',
      'Validating Risk',
      'Confirming Liquidity',
      'Executing Position',
      'Monitoring Trade',
      'Trailing Stop Active',
      'Evaluating Exit',
    ];
    final activeIndex = stages.indexOf(stage);
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: stages.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final active = index == activeIndex;
          final complete = activeIndex >= 0 && index < activeIndex;
          final color = active
              ? TradingPalette.electricBlue
              : complete
                  ? TradingPalette.neonGreen
                  : TradingPalette.panelBorder;
          return AnimatedContainer(
            duration: const Duration(milliseconds: 220),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: color.withOpacity(active ? 0.16 : 0.08),
              borderRadius: BorderRadius.circular(999),
              border:
                  Border.all(color: color.withOpacity(active ? 0.42 : 0.22)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  complete
                      ? Icons.check_rounded
                      : active
                          ? Icons.sync_rounded
                          : Icons.circle_outlined,
                  size: 14,
                  color: color,
                ),
                const SizedBox(width: 6),
                Text(
                  stages[index],
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: active || complete
                            ? TradingPalette.textPrimary
                            : TradingPalette.textMuted,
                        fontWeight: FontWeight.w800,
                      ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _LiveConfidenceDelta extends StatelessWidget {
  const _LiveConfidenceDelta({required this.chart, required this.evaluation});

  final MarketChartModel chart;
  final TradeEvaluationModel? evaluation;

  @override
  Widget build(BuildContext context) {
    final current = _normalizedConfidence(
      evaluation?.confidenceScore ?? chart.opportunity.confidence,
    );
    final previous = _previousConfidence(chart) ?? current;
    final delta = current - previous;
    final color = delta >= 0
        ? TradingPalette.neonGreen
        : delta <= -1
            ? TradingPalette.neonRed
            : TradingPalette.amber;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.26)),
      ),
      child: Row(
        children: <Widget>[
          Icon(
            delta >= 0 ? Icons.north_east_rounded : Icons.south_east_rounded,
            color: color,
            size: 18,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'AI confidence ${previous.toStringAsFixed(0)}% -> ${current.toStringAsFixed(0)}%',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
                const SizedBox(height: 3),
                Text(
                  _confidenceReason(chart: chart, delta: delta),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: TradingPalette.textMuted,
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

class _TechnicalAiReportPanel extends StatelessWidget {
  const _TechnicalAiReportPanel({
    required this.report,
    required this.localMemory,
  });

  final TechnicalAnalysisReport? report;
  final LocalAiMemoryState localMemory;

  @override
  Widget build(BuildContext context) {
    final report = this.report;
    if (report == null) {
      return const SectionCard(
        title: 'AI Technical Report',
        subtitle: 'Reading live candles, RSI, MACD, pivots, SMA, and EMA.',
        trailing: StatusBadge(label: 'LOADING'),
        glowColor: TradingPalette.electricBlue,
        child: LoadingState(label: 'AI is reading candles...'),
      );
    }

    final color = report.side == 'BUY'
        ? TradingPalette.neonGreen
        : report.side == 'SELL'
            ? TradingPalette.neonRed
            : TradingPalette.amber;
    return SectionCard(
      title: 'AI Trend View',
      subtitle:
          '${report.regime} | ${report.confidence.toStringAsFixed(0)}% confidence',
      trailing: StatusBadge(label: report.side, color: color),
      glowColor: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  shape: BoxShape.circle,
                  border: Border.all(color: color.withOpacity(0.35)),
                ),
                child: Icon(
                  report.side == 'SELL'
                      ? Icons.trending_down_rounded
                      : report.side == 'BUY'
                          ? Icons.trending_up_rounded
                          : Icons.pause_circle_filled_rounded,
                  color: color,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      '${report.symbol} ${report.side == 'BUY' ? 'BULLISH' : report.side == 'SELL' ? 'BEARISH' : 'WAIT'}',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      report.summary,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: TradingPalette.textMuted,
                            height: 1.25,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _AiWhyCard(
            report: report,
            color: color,
            personalizedNote: _personalizedNote(localMemory, report),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _TechnicalMetricTile(
                label: 'Confidence',
                value: '${report.confidence.toStringAsFixed(0)}%',
                color: color,
              ),
              _TechnicalMetricTile(
                label: 'RSI 14',
                value: report.rsi14.toStringAsFixed(1),
                color: _rsiColor(report.rsi14),
              ),
              _TechnicalMetricTile(
                label: 'MACD Hist',
                value: report.macdHistogram.toStringAsFixed(4),
                color: report.macdHistogram >= 0
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
              _TechnicalMetricTile(
                label: 'ADX 14',
                value: report.adx14.toStringAsFixed(1),
                color: TradingPalette.electricBlue,
              ),
              _TechnicalMetricTile(
                label: 'Volume',
                value: '${report.volumeRatio.toStringAsFixed(2)}x',
                color: report.volumeRatio >= 2
                    ? TradingPalette.neonGreen
                    : TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 14),
          _TechnicalPlanRow(
            label: 'Entry zone',
            value:
                '${_formatPrice(report.entryLow)} - ${_formatPrice(report.entryHigh)}',
            color: color,
          ),
          _TechnicalPlanRow(
            label: 'Stop loss',
            value: report.stopLoss <= 0
                ? 'No trade until setup confirms'
                : _formatPrice(report.stopLoss),
            color: TradingPalette.neonRed,
          ),
          _TechnicalPlanRow(
            label: 'Targets',
            value: report.takeProfit1 <= 0
                ? 'Pending'
                : '${_formatPrice(report.takeProfit1)} / ${_formatPrice(report.takeProfit2)}',
            color: TradingPalette.neonGreen,
          ),
          _TechnicalPlanRow(
            label: 'Pivot map',
            value:
                'P ${_formatPrice(report.pivot)} | S1 ${_formatPrice(report.support1)} | R1 ${_formatPrice(report.resistance1)}',
            color: TradingPalette.amber,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _TechnicalMetricTile(
                label: 'Scalp score',
                value: '${report.scalpScore.toStringAsFixed(0)}%',
                color: TradingPalette.neonGreen,
              ),
              _TechnicalMetricTile(
                label: 'Swing score',
                value: '${report.swingScore.toStringAsFixed(0)}%',
                color: TradingPalette.electricBlue,
              ),
              _TechnicalMetricTile(
                label: 'SMA 20',
                value: _formatPrice(report.sma20),
                color: TradingPalette.electricBlue,
              ),
              _TechnicalMetricTile(
                label: 'SMA 50',
                value: _formatPrice(report.sma50),
                color: TradingPalette.violet,
              ),
              _TechnicalMetricTile(
                label: 'EMA 9',
                value: _formatPrice(report.ema9),
                color: TradingPalette.neonGreen,
              ),
              _TechnicalMetricTile(
                label: 'EMA 21',
                value: _formatPrice(report.ema21),
                color: TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 14),
          for (final bullet in report.bullets)
            _AnalysisBullet(text: bullet, color: color),
          const SizedBox(height: 10),
          Text(
            'Live trade can still execute only after backend risk validation approves the side, size, and stop loss.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textFaint,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}

class _AiWhyCard extends StatelessWidget {
  const _AiWhyCard({
    required this.report,
    required this.color,
    required this.personalizedNote,
  });

  final TechnicalAnalysisReport report;
  final Color color;
  final String personalizedNote;

  @override
  Widget build(BuildContext context) {
    final warning = report.warning.trim();
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: (warning.isEmpty ? color : TradingPalette.neonRed)
            .withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: (warning.isEmpty ? color : TradingPalette.neonRed)
              .withOpacity(0.24),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                warning.isEmpty
                    ? Icons.psychology_alt_rounded
                    : Icons.warning_amber_rounded,
                color: warning.isEmpty ? color : TradingPalette.neonRed,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  warning.isEmpty ? report.whyTitle : warning,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                        color: TradingPalette.textPrimary,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          for (final bullet in report.bullets.take(2))
            _AnalysisBullet(text: bullet, color: color),
          const SizedBox(height: 10),
          Text(
            'Personalized for you',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            personalizedNote,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  height: 1.25,
                ),
          ),
        ],
      ),
    );
  }
}

class _BeginnerAiCoachPanel extends StatelessWidget {
  const _BeginnerAiCoachPanel({required this.report});

  final TechnicalAnalysisReport? report;

  @override
  Widget build(BuildContext context) {
    final report = this.report;
    if (report == null) {
      return const SectionCard(
        title: 'Beginner AI Guide',
        subtitle: 'Simple market read for safe decision making.',
        trailing: StatusBadge(label: 'READING'),
        glowColor: TradingPalette.electricBlue,
        child: LoadingState(label: 'AI is preparing beginner guidance...'),
      );
    }

    final color = report.side == 'BUY'
        ? TradingPalette.neonGreen
        : report.side == 'SELL'
            ? TradingPalette.neonRed
            : TradingPalette.amber;
    return SectionCard(
      title: 'Beginner AI Guide',
      subtitle:
          'Simple trade view: sentiment, action, entry, stop-loss, target.',
      trailing: StatusBadge(label: report.marketSentiment, color: color),
      glowColor: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.14),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: color.withOpacity(0.32)),
                ),
                child: Icon(
                  report.side == 'BUY'
                      ? Icons.arrow_upward_rounded
                      : report.side == 'SELL'
                          ? Icons.arrow_downward_rounded
                          : Icons.pause_rounded,
                  color: color,
                  size: 30,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      report.beginnerAction,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: TradingPalette.textPrimary,
                            fontWeight: FontWeight.w900,
                            height: 1.18,
                          ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      'Market sentiment: ${report.marketSentiment}. Risk: ${report.riskLabel}. AI confidence: ${report.confidence.toStringAsFixed(0)}%.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: TradingPalette.textMuted,
                            height: 1.25,
                          ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _BeginnerStepTile(
                icon: Icons.login_rounded,
                label: 'Entry',
                value:
                    '${_formatPrice(report.entryLow)} - ${_formatPrice(report.entryHigh)}',
                color: color,
              ),
              _BeginnerStepTile(
                icon: Icons.security_rounded,
                label: 'Stop-loss',
                value: report.stopLoss <= 0
                    ? 'No trade'
                    : _formatPrice(report.stopLoss),
                color: TradingPalette.neonRed,
              ),
              _BeginnerStepTile(
                icon: Icons.flag_rounded,
                label: 'Target',
                value: report.takeProfit1 <= 0
                    ? 'Wait'
                    : _formatPrice(report.takeProfit1),
                color: TradingPalette.neonGreen,
              ),
              _BeginnerStepTile(
                icon: Icons.balance_rounded,
                label: 'R:R',
                value: report.riskReward <= 0
                    ? 'Pending'
                    : report.riskReward.toStringAsFixed(2),
                color: TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 14),
          const _BeginnerPlainLine(
            icon: Icons.candlestick_chart_rounded,
            text:
                'AI reads every candle update and refreshes this view with RSI, MACD, pivot, SMA, EMA, and volatility context.',
          ),
          const _BeginnerPlainLine(
            icon: Icons.verified_user_rounded,
            text:
                'For beginners, no live order should be placed until price reaches the entry zone and backend risk approval is green.',
          ),
        ],
      ),
    );
  }
}

class _BeginnerStepTile extends StatelessWidget {
  const _BeginnerStepTile({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 148, maxWidth: 220),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: color.withOpacity(0.09),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.24)),
      ),
      child: Row(
        children: <Widget>[
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: TradingPalette.textMuted,
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 3),
                Text(
                  value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: TradingPalette.textPrimary,
                        fontWeight: FontWeight.w900,
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

class _BeginnerPlainLine extends StatelessWidget {
  const _BeginnerPlainLine({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, color: TradingPalette.electricBlue, size: 18),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                    height: 1.25,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TechnicalMetricTile extends StatelessWidget {
  const _TechnicalMetricTile({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 96, maxWidth: 150),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w900,
                ),
          ),
        ],
      ),
    );
  }
}

class _TechnicalPlanRow extends StatelessWidget {
  const _TechnicalPlanRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 92,
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: TradingPalette.textMuted,
                    fontWeight: FontWeight.w800,
                  ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: color.withOpacity(0.08),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: color.withOpacity(0.22)),
              ),
              child: Text(
                value,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AnalysisBullet extends StatelessWidget {
  const _AnalysisBullet({required this.text, required this.color});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.only(top: 7),
            child: Icon(Icons.circle, size: 6, color: color),
          ),
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                    height: 1.25,
                  ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StickyExecutionBar extends StatelessWidget {
  const _StickyExecutionBar({
    required this.disabled,
    required this.activeSide,
    required this.websocketState,
    required this.onBuy,
    required this.onSell,
    required this.onAskAi,
    required this.onAuto,
  });

  final bool disabled;
  final String activeSide;
  final WsState websocketState;
  final VoidCallback onBuy;
  final VoidCallback onSell;
  final VoidCallback onAskAi;
  final VoidCallback onAuto;

  @override
  Widget build(BuildContext context) {
    final connected = websocketState == WsState.connected;
    return GlassPanel(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      radius: 18,
      glowColor: connected ? TradingPalette.electricBlue : TradingPalette.amber,
      child: Row(
        children: <Widget>[
          _StickyAction(
            label: 'BUY',
            icon: Icons.trending_up_rounded,
            color: TradingPalette.neonGreen,
            selected: activeSide == 'BUY',
            onTap: disabled ? null : onBuy,
          ),
          const SizedBox(width: 8),
          _StickyAction(
            label: 'SELL',
            icon: Icons.trending_down_rounded,
            color: TradingPalette.neonRed,
            selected: activeSide == 'SELL',
            onTap: disabled ? null : onSell,
          ),
          const SizedBox(width: 8),
          _StickyAction(
            label: 'ASK AI',
            icon: Icons.psychology_alt_rounded,
            color: TradingPalette.electricBlue,
            selected: false,
            onTap: onAskAi,
          ),
          const SizedBox(width: 8),
          _StickyAction(
            label: 'AUTO',
            icon: Icons.auto_mode_rounded,
            color: TradingPalette.amber,
            selected: false,
            onTap: onAuto,
          ),
        ],
      ),
    );
  }
}

class _StickyAction extends StatelessWidget {
  const _StickyAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 11),
          decoration: BoxDecoration(
            color: selected
                ? color.withOpacity(0.18)
                : Colors.white.withOpacity(0.045),
            borderRadius: BorderRadius.circular(14),
            border:
                Border.all(color: color.withOpacity(selected ? 0.48 : 0.22)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon,
                  size: 17,
                  color: onTap == null ? TradingPalette.textFaint : color),
              const SizedBox(width: 6),
              Flexible(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: onTap == null
                            ? TradingPalette.textFaint
                            : TradingPalette.textPrimary,
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ExecutionLiveStateCard extends StatelessWidget {
  const _ExecutionLiveStateCard({
    required this.state,
    required this.evaluation,
    required this.chart,
  });

  final TradeExecutionState state;
  final TradeEvaluationModel? evaluation;
  final MarketChartModel? chart;

  @override
  Widget build(BuildContext context) {
    final response = state.lastResponse;
    final accepted = response != null;
    final color = accepted ? TradingPalette.neonGreen : TradingPalette.amber;
    final liquidity = chart?.orderbookDepth.pressureScore;
    final riskApproved = evaluation?.allowTrade == true;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 260),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.30)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                accepted
                    ? Icons.task_alt_rounded
                    : Icons.motion_photos_on_rounded,
                color: color,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 220),
                  child: Text(
                    accepted ? 'Position activating' : 'Execution mode',
                    key: ValueKey<bool>(accepted),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
              ),
              StatusBadge(
                label: accepted ? response.status.toUpperCase() : 'VALIDATING',
                color: color,
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (!accepted)
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: const LinearProgressIndicator(minHeight: 5),
            )
          else
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 240),
              child: Text(
                '${response.symbol} ${response.side} at ${response.executedPrice.toStringAsFixed(response.executedPrice >= 100 ? 2 : 4)} | SL ${response.stopLoss.toStringAsFixed(response.stopLoss >= 100 ? 2 : 4)} | TP ${response.takeProfit.toStringAsFixed(response.takeProfit >= 100 ? 2 : 4)}',
                key: ValueKey<String>(response.tradeId),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: TradingPalette.textMuted,
                    ),
              ),
            ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _ExecutionStepPill(
                label: 'AI validation',
                complete: riskApproved,
              ),
              _ExecutionStepPill(
                label: liquidity == null
                    ? 'Liquidity checking'
                    : 'Liquidity ${liquidity.toStringAsFixed(0)}',
                complete: accepted || (liquidity ?? 0) >= 45,
              ),
              _ExecutionStepPill(
                label: accepted ? 'Accepted' : 'Awaiting broker',
                complete: accepted,
              ),
              _ExecutionStepPill(
                label: accepted ? 'Portfolio updating' : 'Risk recap ready',
                complete: accepted,
              ),
            ],
          ),
          if (evaluation != null) ...<Widget>[
            const SizedBox(height: 12),
            _CompactRiskRecap(evaluation: evaluation!),
          ],
        ],
      ),
    );
  }
}

class _ExecutionStepPill extends StatelessWidget {
  const _ExecutionStepPill({
    required this.label,
    required this.complete,
  });

  final String label;
  final bool complete;

  @override
  Widget build(BuildContext context) {
    final color = complete ? TradingPalette.neonGreen : TradingPalette.amber;
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(
            complete
                ? Icons.check_circle_rounded
                : Icons.radio_button_checked_rounded,
            size: 14,
            color: color,
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _CompactRiskRecap extends StatelessWidget {
  const _CompactRiskRecap({required this.evaluation});

  final TradeEvaluationModel evaluation;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: TradingPalette.panelSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: _RiskRecapMetric(
              label: 'Alpha',
              value: evaluation.alphaScore.toStringAsFixed(0),
            ),
          ),
          Expanded(
            child: _RiskRecapMetric(
              label: 'Daily Risk',
              value: evaluation.riskBudget.toStringAsFixed(3),
            ),
          ),
          Expanded(
            child: _RiskRecapMetric(
              label: 'Rollout',
              value:
                  '${(evaluation.rolloutCapitalFraction * 100).toStringAsFixed(0)}%',
            ),
          ),
        ],
      ),
    );
  }
}

class _RiskRecapMetric extends StatelessWidget {
  const _RiskRecapMetric({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(label, style: Theme.of(context).textTheme.labelSmall),
        const SizedBox(height: 3),
        Text(
          value,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
      ],
    );
  }
}

class _AutoModeDashboard extends StatelessWidget {
  const _AutoModeDashboard({
    required this.autopilot,
    required this.safety,
    required this.chart,
    required this.evaluation,
  });

  final AutopilotIntelligenceRead autopilot;
  final AutopilotSafetyRead safety;
  final MarketChartModel? chart;
  final TradeEvaluationModel? evaluation;

  @override
  Widget build(BuildContext context) {
    final protectionColor = safety.safetyScore >= 80
        ? TradingPalette.neonGreen
        : safety.safetyScore >= 60
            ? TradingPalette.amber
            : TradingPalette.neonRed;
    final strategy = _strategyLabel(
      evaluation?.strategy ?? chart?.strategyState.activeStrategy,
    );
    final trailingStop = chart?.trailingStop.currentStop ?? 0;
    final projectedStop = chart?.trailingStop.projectedStop ?? 0;
    final volatility = chart?.opportunity.volatilityScore ?? 0;
    final liquidity = chart?.orderbookDepth.pressureScore ??
        chart?.liquidityHeatmap.pressureScore ??
        0;
    final confidence = _normalizedConfidence(
      evaluation?.confidenceScore ?? chart?.opportunity.confidence ?? 0,
    );
    final feed = chart?.aiFeed
            .where((item) => item.detail.trim().isNotEmpty)
            .take(3)
            .map((item) => item.detail.trim())
            .toList(growable: false) ??
        const <String>[];
    final reasoning = feed.isNotEmpty
        ? feed
        : <String>[
            autopilot.reason,
            safety.confidenceStable
                ? 'Confidence stable; AI is monitoring invalidation quality.'
                : 'Confidence unstable; AI keeps exposure defensive.',
          ];
    return GlassPanel(
      glowColor: protectionColor,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'AI Auto Mode',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: safety.verdict, color: protectionColor),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricPill(
                label: 'Strategy',
                value: strategy,
                accent: TradingPalette.electricBlue,
              ),
              _MetricPill(
                label: 'Confidence',
                value: '${confidence.toStringAsFixed(0)}%',
                accent: protectionColor,
              ),
              _MetricPill(
                label: 'Trailing SL',
                value: trailingStop > 0 ? _formatPrice(trailingStop) : 'Armed',
                accent: TradingPalette.amber,
              ),
              _MetricPill(
                label: 'Projected',
                value:
                    projectedStop > 0 ? _formatPrice(projectedStop) : 'Watch',
                accent: TradingPalette.violet,
              ),
            ],
          ),
          const SizedBox(height: 14),
          _AutoStateLine(
            label: 'Volatility adaptation',
            value: volatility >= 70
                ? 'Defensive exits'
                : volatility >= 45
                    ? 'Normal exits'
                    : 'Patient entries',
            active: safety.volatilityAcceptable,
          ),
          _AutoStateLine(
            label: 'Liquidity adaptation',
            value: liquidity >= 60
                ? 'Supportive'
                : liquidity >= 40
                    ? 'Selective'
                    : 'Weak',
            active: safety.liquidityAcceptable,
          ),
          _AutoStateLine(
            label: 'Position protection',
            value:
                trailingStop > 0 ? 'Trailing stop active' : 'Risk gates armed',
            active: safety.safetyScore >= 60,
          ),
          const SizedBox(height: 10),
          ...reasoning.map(
            (line) => _AutoReasoningLine(text: _traderFacingReason(line)),
          ),
        ],
      ),
    );
  }
}

class _AutoStateLine extends StatelessWidget {
  const _AutoStateLine({
    required this.label,
    required this.value,
    required this.active,
  });

  final String label;
  final String value;
  final bool active;

  @override
  Widget build(BuildContext context) {
    final color = active ? TradingPalette.neonGreen : TradingPalette.amber;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: <Widget>[
          Icon(Icons.shield_rounded, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                  ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            value,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
          ),
        ],
      ),
    );
  }
}

class _AutoReasoningLine extends StatelessWidget {
  const _AutoReasoningLine({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 6),
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
          const SizedBox(width: 9),
          Expanded(
            child: Text(
              text,
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

class _TradeExecutionPanel extends StatelessWidget {
  const _TradeExecutionPanel({
    required this.selectedSymbol,
    required this.tradeIntent,
    required this.tradeEvaluationAsync,
    required this.chart,
    required this.executionState,
    required this.paperState,
    required this.riskShield,
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
  final TradeExecutionState executionState;
  final LocalPaperPortfolioState paperState;
  final RiskShieldPreview riskShield;
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
    final planSignal = _signalFromTradeIntent(
      tradeIntent: tradeIntent,
      fallbackSide: executionState.side,
      evaluation: evaluation,
    );
    final briefing = institutionalEngine.executionBriefing(
      symbol: selectedSymbol,
      side: executionState.side,
      notional: executionState.amount,
      evaluation: evaluation,
      signal: planSignal,
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
    final executionReady = _canExecuteTrade(
          state: executionState,
          evaluation: evaluation,
        ) &&
        paperState.liveUnlocked;
    final paperReady = !executionState.isSubmitting && riskShield.approved;
    return SectionCard(
      title: 'Order Execution',
      subtitle:
          'Paper mode is active. Live mode stays locked until the rookie challenge is cleared.',
      trailing: StatusBadge(
        label: paperState.licenseStatus.toUpperCase(),
        color: executionState.isSubmitting
            ? TradingPalette.amber
            : paperState.liveUnlocked
                ? TradingPalette.neonGreen
                : TradingPalette.amber,
      ),
      glowColor: TradingPalette.neonGreen,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _ModeLockStrip(paperState: paperState),
          const SizedBox(height: 14),
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
          if (executionState.isSubmitting ||
              executionState.lastResponse != null) ...<Widget>[
            const SizedBox(height: 18),
            _ExecutionLiveStateCard(
              state: executionState,
              evaluation: evaluation,
              chart: chart,
            ),
          ],
          const SizedBox(height: 18),
          ExecutionBriefingPanel(briefing: briefing),
          const SizedBox(height: 18),
          _AutoModeDashboard(
            autopilot: autopilot,
            safety: safety,
            chart: chart,
            evaluation: evaluation,
          ),
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
            paperState: paperState,
            riskShield: riskShield,
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
              onPressed: paperReady ? onPaperExecute : null,
              icon: const Icon(Icons.account_balance_wallet_rounded),
              label: Text(
                riskShield.approved
                    ? 'Place paper trade - Qty ${riskShield.autoQuantity.toStringAsFixed(5)}'
                    : 'Paper trade locked by risk shield',
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            authDegraded
                ? 'Production auth is reconnecting. Paper submission will wait for backend authority before the ledger changes.'
                : 'Paper mode submits to the backend sandbox ledger. Live execution still requires meta and risk approval.',
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
                ? 'Realtime auth is reconnecting. The app stays open in advisory mode; paper submit remains backend-authoritative.'
                : 'Backend validation is still building. You can submit a paper sandbox request without touching live execution.',
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
    required this.paperState,
    required this.riskShield,
  });

  final String symbol;
  final String side;
  final double amount;
  final TradeIntent? tradeIntent;
  final TradeEvaluationModel? evaluation;
  final LocalPaperPortfolioState paperState;
  final RiskShieldPreview riskShield;

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

    final shieldColor =
        riskShield.approved ? TradingPalette.neonGreen : TradingPalette.neonRed;
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
            'Risk engine status',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          Row(
            children: <Widget>[
              Icon(
                riskShield.approved
                    ? Icons.verified_user_rounded
                    : Icons.block_rounded,
                color: shieldColor,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  riskShield.approved ? 'APPROVED' : 'BLOCKED',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: shieldColor,
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            riskShield.approved
                ? 'Your daily loss is currently \$${riskShield.dailyLoss.abs().toStringAsFixed(0)}. Safe to execute inside the auto-size cap.'
                : riskShield.reason,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _MetricPill(
                label: 'Auto-Qty',
                value: riskShield.autoQuantity <= 0
                    ? 'Pending'
                    : riskShield.autoQuantity.toStringAsFixed(5),
                accent: TradingPalette.neonGreen,
              ),
              _MetricPill(
                label: 'Max size',
                value: '\$${riskShield.maxNotional.toStringAsFixed(0)}',
                accent: TradingPalette.electricBlue,
              ),
              _MetricPill(
                label: 'Stop-Loss',
                value: _formatPrice(riskShield.stopLoss),
                accent: TradingPalette.neonRed,
              ),
              _MetricPill(
                label: 'Target',
                value: _formatPrice(riskShield.takeProfit),
                accent: TradingPalette.neonGreen,
              ),
              _MetricPill(
                label: 'R:R',
                value: '1:${riskShield.riskReward.toStringAsFixed(2)}',
                accent: TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '$side $symbol request \$${amount.toStringAsFixed(2)}. $confidenceText',
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
          const SizedBox(height: 8),
          Text(
            'Challenge: ${paperState.closedTradeCount}/10 trades | Win rate ${(paperState.winRate * 100).toStringAsFixed(0)}% | Avg R:R ${paperState.averageRiskReward.toStringAsFixed(2)}',
            style: const TextStyle(color: TradingPalette.textFaint),
          ),
        ],
      ),
    );
  }
}

class _ModeLockStrip extends StatelessWidget {
  const _ModeLockStrip({required this.paperState});

  final LocalPaperPortfolioState paperState;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 10,
      runSpacing: 10,
      children: <Widget>[
        const StatusBadge(
          label: 'Paper Mode',
          color: TradingPalette.neonGreen,
        ),
        StatusBadge(
          label:
              paperState.liveUnlocked ? 'Live Mode Ready' : 'Live Mode Locked',
          color: paperState.liveUnlocked
              ? TradingPalette.neonGreen
              : TradingPalette.neonRed,
        ),
      ],
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
    final confidence = evaluation?.confidenceScore ?? signal?.confidence;
    final confidencePct =
        confidence == null ? null : _normalizedConfidence(confidence);
    final validated = evaluation?.allowTrade == true;
    final sideAligned = evaluation == null || evaluation!.approvedSide == side;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Execution Review',
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                ),
                StatusBadge(
                  label: validated ? 'RISK APPROVED' : 'CHECKING RISK',
                  color: validated
                      ? TradingPalette.neonGreen
                      : TradingPalette.amber,
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              '$side $symbol',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    color: _sideColor(side),
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              'Notional \$${amount.toStringAsFixed(2)}',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                  ),
            ),
            const SizedBox(height: 14),
            Text(
              _traderFacingReason(
                evaluation?.reason ?? signal?.reason,
                fallback:
                    'Order will pass through meta approval, risk validation, and backend execution before capital is deployed.',
              ),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textPrimary,
                  ),
            ),
            const SizedBox(height: 16),
            _ConfirmationCheckRow(
              label: 'Meta strategy',
              value: _strategyLabel(evaluation?.strategy ?? signal?.strategy),
              approved: evaluation != null || signal != null,
            ),
            _ConfirmationCheckRow(
              label: 'Risk validation',
              value: validated ? 'Approved' : 'Awaiting backend approval',
              approved: validated,
            ),
            _ConfirmationCheckRow(
              label: 'Direction alignment',
              value: sideAligned
                  ? side
                  : 'Backend wants ${evaluation?.approvedSide ?? 'HOLD'}',
              approved: sideAligned && evaluation != null,
            ),
            _ConfirmationCheckRow(
              label: 'AI confidence',
              value: confidencePct == null
                  ? 'Pending'
                  : '${confidencePct.toStringAsFixed(0)}%',
              approved: confidencePct != null && confidencePct >= 60,
            ),
            if (evaluation != null) ...<Widget>[
              const SizedBox(height: 8),
              _CompactRiskRecap(evaluation: evaluation!),
            ],
            const SizedBox(height: 18),
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
                  child: FilledButton.icon(
                    onPressed: () => Navigator.of(context).pop(true),
                    icon: const Icon(Icons.verified_rounded),
                    label: const Text('Execute'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ConfirmationCheckRow extends StatelessWidget {
  const _ConfirmationCheckRow({
    required this.label,
    required this.value,
    required this.approved,
  });

  final String label;
  final String value;
  final bool approved;

  @override
  Widget build(BuildContext context) {
    final color = approved ? TradingPalette.neonGreen : TradingPalette.amber;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: <Widget>[
          Icon(
            approved ? Icons.check_circle_rounded : Icons.pending_rounded,
            size: 18,
            color: color,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textMuted,
                  ),
            ),
          ),
          const SizedBox(width: 12),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.right,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: TradingPalette.textPrimary,
                    fontWeight: FontWeight.w800,
                  ),
            ),
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
      constraints: const BoxConstraints(minWidth: 96, maxWidth: 180),
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
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
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
    subtitle: 'Live positions with protected exits and active risk state.',
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

        return AnimatedSize(
          duration: const Duration(milliseconds: 240),
          curve: Curves.easeOutCubic,
          child: Column(
            children: visible
                .map(
                  (trade) => _ActivePositionTile(
                    key: ValueKey<String>(trade.tradeId),
                    trade: trade,
                  ),
                )
                .toList(),
          ),
        );
      },
      loading: () => const LoadingState(label: 'Loading open positions'),
      error: (error, _) => ErrorState(message: userMessageForError(error)),
    ),
  );
}

class _ActivePositionTile extends StatelessWidget {
  const _ActivePositionTile({
    super.key,
    required this.trade,
  });

  final ActiveTradeModel trade;

  @override
  Widget build(BuildContext context) {
    final sideColor = _sideColor(trade.side);
    final riskPct = (trade.riskFraction * 100).clamp(0, 100).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: TradingPalette.overlay,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: sideColor.withOpacity(0.26)),
        ),
        child: Row(
          children: <Widget>[
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: sideColor.withOpacity(0.16),
              ),
              child: Icon(
                trade.side.toUpperCase() == 'BUY'
                    ? Icons.arrow_upward_rounded
                    : Icons.arrow_downward_rounded,
                color: sideColor,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Row(
                    children: <Widget>[
                      Expanded(
                        child: Text(
                          '${trade.symbol} | ${trade.side}',
                          style: const TextStyle(fontWeight: FontWeight.w900),
                        ),
                      ),
                      StatusBadge(
                        label: trade.status,
                        color: TradingPalette.electricBlue,
                      ),
                    ],
                  ),
                  const SizedBox(height: 5),
                  Text(
                    'Entry ${_formatPrice(trade.entry)} | Qty ${trade.executedQuantity.toStringAsFixed(6)}',
                    style: const TextStyle(color: TradingPalette.textMuted),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Protected by SL ${_formatPrice(trade.stopLoss)} | TP ${_formatPrice(trade.takeProfit)}',
                    style: const TextStyle(color: TradingPalette.textFaint),
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(999),
                    child: LinearProgressIndicator(
                      value: (riskPct / 100).clamp(0.0, 1.0),
                      minHeight: 5,
                      backgroundColor: TradingPalette.panelSoft,
                      valueColor: AlwaysStoppedAnimation<Color>(sideColor),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PaperPortfolioPanel extends StatelessWidget {
  const _PaperPortfolioPanel({
    required this.state,
    required this.onClose,
    required this.onAcknowledgeLesson,
  });

  final LocalPaperPortfolioState state;
  final ValueChanged<String> onClose;
  final LessonAcknowledgementChanged onAcknowledgeLesson;

  @override
  Widget build(BuildContext context) {
    return SectionCard(
      title: 'Paper Portfolio',
      subtitle:
          'Backend sandbox fills are mirrored here when available; live execution is separate.',
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
              _MetricPill(
                label: 'License',
                value: state.licenseStatus,
                accent: state.liveUnlocked
                    ? TradingPalette.neonGreen
                    : TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 12),
          LinearProgressIndicator(
            value: (state.closedTradeCount / 10).clamp(0.0, 1.0),
            minHeight: 6,
            backgroundColor: TradingPalette.panelSoft,
            valueColor: AlwaysStoppedAnimation<Color>(
              state.liveUnlocked
                  ? TradingPalette.neonGreen
                  : TradingPalette.amber,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Rookie Challenge: ${state.closedTradeCount}/10 paper trades, win rate ${(state.winRate * 100).toStringAsFixed(0)}%, avg R:R ${state.averageRiskReward.toStringAsFixed(2)}.',
            style: const TextStyle(color: TradingPalette.textMuted),
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
          if (state.closedTrades.isNotEmpty) ...<Widget>[
            const SizedBox(height: 16),
            Text(
              'Trade post-mortem report',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w900,
                  ),
            ),
            const SizedBox(height: 10),
            _PostMortemCard(
              trade: state.closedTrades.first,
              onAcknowledgeLesson: onAcknowledgeLesson,
            ),
          ],
        ],
      ),
    );
  }
}

typedef LessonAcknowledgementChanged = void Function({
  required String tradeId,
  required String lesson,
  required bool acknowledged,
});

class _PostMortemCard extends StatelessWidget {
  const _PostMortemCard({
    required this.trade,
    required this.onAcknowledgeLesson,
  });

  final LocalPaperClosedTrade trade;
  final LessonAcknowledgementChanged onAcknowledgeLesson;

  @override
  Widget build(BuildContext context) {
    final color = trade.realizedPnl >= 0
        ? TradingPalette.neonGreen
        : TradingPalette.neonRed;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(
                trade.realizedPnl >= 0
                    ? Icons.check_circle_rounded
                    : Icons.error_rounded,
                color: color,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  '${trade.symbol} ${trade.side} Trade',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: trade.result, color: color),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Result: ${trade.result} (${trade.realizedPnl >= 0 ? '+' : ''}\$${trade.realizedPnl.toStringAsFixed(2)} Virtual)',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: TradingPalette.textPrimary,
                  fontWeight: FontWeight.w800,
                ),
          ),
          const SizedBox(height: 10),
          Text(
            'AI analysis',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            trade.aiAnalysis,
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Lesson learned tagged',
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: TradingPalette.textMuted,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 6),
          for (final lesson in trade.lessonTags)
            CheckboxListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: trade.acknowledgedLessons.contains(lesson),
              onChanged: (value) => onAcknowledgeLesson(
                tradeId: trade.tradeId,
                lesson: lesson,
                acknowledged: value ?? false,
              ),
              title: Text(lesson),
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

RiskShieldPreview _riskShieldPreview({
  required String side,
  required double amount,
  required LocalPaperPortfolioState paperState,
  required MarketChartModel? chart,
  required TradeEvaluationModel? evaluation,
  required TradeIntent? intent,
}) {
  final normalizedSide = side.toUpperCase() == 'SELL' ? 'SELL' : 'BUY';
  final entry = _paperMarketPrice(
    chart: chart,
    intent: intent,
    evaluation: evaluation,
  );
  final guide = chart?.executionGuide;
  var stopLoss = guide?.stopLoss ?? 0.0;
  var takeProfit = guide?.tp2 ?? guide?.tp1 ?? 0.0;
  if (entry > 0 && (stopLoss <= 0 || takeProfit <= 0)) {
    stopLoss = normalizedSide == 'SELL' ? entry * 1.015 : entry * 0.985;
    takeProfit = normalizedSide == 'SELL' ? entry * 0.97 : entry * 1.03;
  }
  final riskPerUnit =
      normalizedSide == 'SELL' ? stopLoss - entry : entry - stopLoss;
  final rewardPerUnit =
      normalizedSide == 'SELL' ? entry - takeProfit : takeProfit - entry;
  final riskReward = riskPerUnit <= 0 ? 0.0 : rewardPerUnit / riskPerUnit;
  final riskAmount = paperState.equity * 0.01;
  final autoQuantity = riskPerUnit <= 0 ? 0.0 : riskAmount / riskPerUnit;
  final maxNotional = autoQuantity * entry;
  final dailyLoss = paperState.realizedPnl < 0 ? paperState.realizedPnl : 0.0;
  if (entry <= 0 || stopLoss <= 0 || takeProfit <= 0) {
    return RiskShieldPreview(
      approved: false,
      reason: 'Entry, stop-loss, and target are mandatory before execution.',
      reasonCode: 'MANDATORY_BRACKET_MISSING',
      autoQuantity: 0,
      maxNotional: 0,
      riskAmount: riskAmount,
      riskReward: 0,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  if (riskPerUnit <= 0 || rewardPerUnit <= 0) {
    return RiskShieldPreview(
      approved: false,
      reason: 'Stop-loss and target must be on the protective side of entry.',
      reasonCode: 'INVALID_BRACKET_DIRECTION',
      autoQuantity: 0,
      maxNotional: 0,
      riskAmount: riskAmount,
      riskReward: riskReward,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  if (dailyLoss <= -(paperState.startingBalance * 0.03)) {
    return RiskShieldPreview(
      approved: false,
      reason: 'Daily loss protection is active until midnight.',
      reasonCode: 'DAILY_LOSS_LIMIT_REACHED',
      autoQuantity: autoQuantity,
      maxNotional: maxNotional,
      riskAmount: riskAmount,
      riskReward: riskReward,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  if (paperState.consecutiveLosses >= 3) {
    return RiskShieldPreview(
      approved: false,
      reason: 'Three consecutive losses triggered the 2-hour cooldown.',
      reasonCode: 'CONSECUTIVE_LOSS_LOCK',
      autoQuantity: autoQuantity,
      maxNotional: maxNotional,
      riskAmount: riskAmount,
      riskReward: riskReward,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  if (riskReward < 1.5) {
    return RiskShieldPreview(
      approved: false,
      reason: 'Risk-reward must be at least 1:1.5.',
      reasonCode: 'RISK_REWARD_TOO_LOW',
      autoQuantity: autoQuantity,
      maxNotional: maxNotional,
      riskAmount: riskAmount,
      riskReward: riskReward,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  if (amount > maxNotional * 1.000001) {
    return RiskShieldPreview(
      approved: false,
      reason:
          'Requested amount is above AI auto-sizing. User override cannot increase risk.',
      reasonCode: 'POSITION_SIZE_EXCEEDS_RISK_LIMIT',
      autoQuantity: autoQuantity,
      maxNotional: maxNotional,
      riskAmount: riskAmount,
      riskReward: riskReward,
      entry: entry,
      stopLoss: stopLoss,
      takeProfit: takeProfit,
      dailyLoss: dailyLoss,
    );
  }
  return RiskShieldPreview(
    approved: true,
    reason: 'Risk shield approved.',
    reasonCode: 'APPROVED',
    autoQuantity: autoQuantity,
    maxNotional: maxNotional,
    riskAmount: riskAmount,
    riskReward: riskReward,
    entry: entry,
    stopLoss: stopLoss,
    takeProfit: takeProfit,
    dailyLoss: dailyLoss,
  );
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

List<String> _reasoningLines({
  required String symbol,
  required MarketChartModel? chart,
  required SignalModel? signal,
  required TradeEvaluationModel? evaluation,
  required ActiveTradeModel? activeTrade,
}) {
  if (chart == null || chart.candles.isEmpty) {
    return <String>[
      'Loading verified live candles for $symbol. AI is waiting instead of inventing a trade.',
      'Execution stays paused until the backend returns a complete market snapshot and risk check.',
    ];
  }
  final guide = chart.executionGuide;
  final rr = guide.riskReward;
  final lines = <String>[];
  if (activeTrade != null) {
    lines.add(
      'Position is open. AI is monitoring candle structure, volatility, and profit protection around SL ${_formatPrice(activeTrade.stopLoss)} and TP ${_formatPrice(activeTrade.takeProfit)}.',
    );
    if (chart.trailingStop.path.isNotEmpty) {
      lines.add(
        'Trailing stop path is active with ${chart.trailingStop.path.length} recalculation points.',
      );
    }
  } else if (evaluation?.allowTrade == true) {
    lines.add(
      '${evaluation!.approvedSide} passed meta and risk validation with alpha ${evaluation.alphaScore.toStringAsFixed(0)} and confidence ${(evaluation.confidenceScore * 100).toStringAsFixed(0)}%.',
    );
  } else {
    lines.add(
      '${signal?.action ?? guide.side} is not a live order yet. AI is waiting for risk/reward, trend, and liquidity alignment.',
    );
    lines.add(
        _waitingReason(chart: chart, signal: signal, evaluation: evaluation));
  }
  lines.add(
    'Market regime is ${chart.marketRegime.state}; AI confidence ${chart.marketRegime.confidence.toStringAsFixed(0)}%, trend strength ${chart.opportunity.trendStrength.toStringAsFixed(0)}%.',
  );
  lines.add(
    rr > 0
        ? 'Execution map: entry ${_formatPrice(guide.entryLow)}-${_formatPrice(guide.entryHigh)}, stop ${_formatPrice(guide.stopLoss)}, TP2 ${_formatPrice(guide.tp2)}, R:R ${rr.toStringAsFixed(2)}.'
        : 'No complete RR map yet. Waiting is preferred until entry, stop, and target are all valid.',
  );
  final reason = evaluation?.reason.trim().isNotEmpty == true
      ? evaluation!.reason
      : signal?.reasons.firstOrNull;
  if (reason != null && reason.trim().isNotEmpty) {
    lines.add(reason.trim());
  } else if (chart.opportunity.volatilityScore >= 72) {
    lines.add(
      'Volatility is elevated; AI will reduce chase behavior and prioritize invalidation quality.',
    );
  } else {
    lines.add(
        'No forced setup. AI will only act when the validation stack improves.');
  }
  return lines;
}

String _aiStage({
  required MarketChartModel? chart,
  required SignalModel? signal,
  required TradeEvaluationModel? evaluation,
  required TradeExecutionState executionState,
  required ActiveTradeModel? activeTrade,
}) {
  if (executionState.isSubmitting) {
    return 'Executing Position';
  }
  if (activeTrade != null && (chart?.trailingStop.path.isNotEmpty ?? false)) {
    return 'Trailing Stop Active';
  }
  if (activeTrade != null) {
    return 'Monitoring Trade';
  }
  if (chart == null || chart.candles.isEmpty) {
    return 'Scanning Market';
  }
  if (signal == null) {
    return 'Ranking Opportunities';
  }
  if (evaluation == null) {
    return 'Validating Risk';
  }
  if (evaluation.allowTrade) {
    return 'Confirming Liquidity';
  }
  return 'Evaluating Exit';
}

String _waitingReason({
  required MarketChartModel chart,
  required SignalModel? signal,
  required TradeEvaluationModel? evaluation,
}) {
  final reason = evaluation?.reason.trim().isNotEmpty == true
      ? evaluation!.reason
      : signal?.rejectionReason ?? signal?.qualityReasons.firstOrNull;
  if (reason != null && reason.trim().isNotEmpty) {
    return 'Why waiting: ${_traderFacingReason(reason)}';
  }
  if (chart.executionGuide.riskReward > 0 &&
      chart.executionGuide.riskReward < 1.5) {
    return 'Why waiting: RR below threshold.';
  }
  if (chart.orderbookDepth.pressureScore < 40) {
    return 'Why waiting: liquidity weak.';
  }
  if (chart.opportunity.volatilityScore >= 72) {
    return 'Why waiting: volatility unstable.';
  }
  if (chart.opportunity.trendStrength < 45) {
    return 'Why waiting: higher-timeframe trend conflict.';
  }
  if (chart.opportunity.confidence < 60) {
    return 'Why waiting: AI confidence too low.';
  }
  return 'Why waiting: setup is incomplete, so capital stays protected.';
}

double _normalizedConfidence(double value) {
  if (value <= 1) {
    return (value * 100).clamp(0, 100);
  }
  return value.clamp(0, 100);
}

double? _previousConfidence(MarketChartModel chart) {
  if (chart.confidenceHistory.length >= 2) {
    return _normalizedConfidence(
        chart.confidenceHistory[chart.confidenceHistory.length - 2].score);
  }
  if (chart.confidenceHistory.length == 1) {
    return _normalizedConfidence(chart.confidenceHistory.first.score);
  }
  if (chart.candles.length < 8) {
    return null;
  }
  final latest = chart.opportunity.confidence;
  final recent =
      chart.candles.last.close - chart.candles[chart.candles.length - 4].close;
  final prior = chart.candles[chart.candles.length - 4].close -
      chart.candles[chart.candles.length - 8].close;
  final weakening = recent.abs() < prior.abs();
  final adjusted = latest + (weakening ? 6 : -4);
  return _normalizedConfidence(adjusted);
}

String _confidenceReason({
  required MarketChartModel chart,
  required double delta,
}) {
  if (delta <= -1) {
    if (chart.opportunity.momentumScore < 55) {
      return 'Momentum weakening near resistance.';
    }
    if (chart.opportunity.volatilityScore >= 72) {
      return 'Volatility expanding; false-breakout risk is higher.';
    }
    if (chart.orderbookDepth.pressureScore < 45) {
      return 'Liquidity support is weakening.';
    }
    return 'Structure quality declined on the latest candle.';
  }
  if (delta >= 1) {
    if (chart.executionGuide.riskReward >= 2) {
      return 'RR improved while validation remains aligned.';
    }
    return 'Momentum and market structure are improving.';
  }
  return 'Confidence is stable; AI is monitoring for invalidation.';
}

String _formatPrice(double value) {
  if (value <= 0) {
    return 'pending';
  }
  return value >= 100 ? value.toStringAsFixed(2) : value.toStringAsFixed(4);
}

Color _rsiColor(double value) {
  if (value >= 70) {
    return TradingPalette.neonRed;
  }
  if (value <= 30) {
    return TradingPalette.amber;
  }
  if (value >= 52) {
    return TradingPalette.neonGreen;
  }
  if (value <= 48) {
    return TradingPalette.neonRed;
  }
  return TradingPalette.electricBlue;
}

String _personalizedNote(
  LocalAiMemoryState memory,
  TechnicalAnalysisReport report,
) {
  final style = memory.favoriteStyle.toLowerCase();
  final preferredAsset = memory.preferredAssets.isEmpty
      ? report.symbol
      : memory.preferredAssets.first;
  final isScalper = style.contains('scalp') ||
      style.contains('short') ||
      memory.preferredModes.any((mode) => mode.toLowerCase().contains('scalp'));
  final isSwing = style.contains('swing') ||
      style.contains('conservative') ||
      memory.preferredModes.any((mode) => mode.toLowerCase().contains('swing'));
  if (isScalper) {
    return 'Since you prefer short-term scalping around $preferredAsset, this setup is ranked by scalp score ${report.scalpScore.toStringAsFixed(0)}% and quick ${report.riskReward.toStringAsFixed(1)} R:R fit.';
  }
  if (isSwing) {
    return 'Since you behave like a swing trader, AI prioritizes EMA 20/50 trend quality and swing score ${report.swingScore.toStringAsFixed(0)}% before suggesting a hold.';
  }
  if (memory.viewedSignals > 0) {
    return 'Your recent watch history favors $preferredAsset, so AI compares this setup against your saved asset affinity before surfacing it.';
  }
  return 'No strong preference is saved yet; AI is using balanced risk-first scoring until your paper-trade behavior builds a profile.';
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

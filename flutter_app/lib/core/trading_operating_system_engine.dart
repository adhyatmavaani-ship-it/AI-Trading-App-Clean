import 'dart:math' as math;

import '../models/active_trade.dart';
import '../models/market_chart.dart';
import '../models/market_summary.dart';
import '../models/realtime_event.dart';
import '../models/signal.dart';
import '../models/trade_execution.dart';
import '../models/user_pnl.dart';
import 'edge_validation_engine.dart';

class PortfolioIntelligenceRead {
  const PortfolioIntelligenceRead({
    required this.grossExposurePct,
    required this.leverageExposure,
    required this.volatilityExposure,
    required this.correlationExposure,
    required this.concentrationRisk,
    required this.aiPortfolioHeat,
    required this.sectorExposure,
    required this.sideExposure,
    required this.regimeAdaptation,
    required this.warnings,
  });

  final double grossExposurePct;
  final double leverageExposure;
  final double volatilityExposure;
  final double correlationExposure;
  final double concentrationRisk;
  final double aiPortfolioHeat;
  final Map<String, double> sectorExposure;
  final Map<String, double> sideExposure;
  final String regimeAdaptation;
  final List<String> warnings;
}

class AssetOrchestrationRow {
  const AssetOrchestrationRow({
    required this.symbol,
    required this.rankScore,
    required this.assetGroup,
    required this.action,
    required this.correlationSuppressed,
    required this.reason,
  });

  final String symbol;
  final double rankScore;
  final String assetGroup;
  final String action;
  final bool correlationSuppressed;
  final String reason;
}

class MultiAssetOrchestrationRead {
  const MultiAssetOrchestrationRead({
    required this.globalRank,
    required this.primaryOpportunity,
    required this.suppressedSymbols,
    required this.exposureDirective,
  });

  final List<AssetOrchestrationRow> globalRank;
  final String primaryOpportunity;
  final List<String> suppressedSymbols;
  final String exposureDirective;
}

class AiCopilotRead {
  const AiCopilotRead({
    required this.posture,
    required this.primaryGuidance,
    required this.messages,
  });

  final String posture;
  final String primaryGuidance;
  final List<String> messages;
}

class CloudProfileSyncRead {
  const CloudProfileSyncRead({
    required this.preferencesReady,
    required this.aiMemoryReady,
    required this.onboardingReady,
    required this.watchlistsReady,
    required this.replayHistoryReady,
    required this.aiModesReady,
    required this.pendingSyncItems,
    required this.syncNote,
  });

  final bool preferencesReady;
  final bool aiMemoryReady;
  final bool onboardingReady;
  final bool watchlistsReady;
  final bool replayHistoryReady;
  final bool aiModesReady;
  final int pendingSyncItems;
  final String syncNote;
}

class RealtimeOrchestrationRead {
  const RealtimeOrchestrationRead({
    required this.batchWindowMs,
    required this.priorityLanes,
    required this.updateThrottleMs,
    required this.chartRefreshCadenceMs,
    required this.animationBudgetMs,
    required this.signalQueueMode,
    required this.loadState,
  });

  final int batchWindowMs;
  final List<String> priorityLanes;
  final int updateThrottleMs;
  final int chartRefreshCadenceMs;
  final int animationBudgetMs;
  final String signalQueueMode;
  final String loadState;
}

class ExecutionWorkspaceRead {
  const ExecutionWorkspaceRead({
    required this.readinessScore,
    required this.correlatedTradeWarning,
    required this.executionSequencing,
    required this.exposureAfterTradePct,
    required this.exposureBalancingAction,
    required this.positionManagement,
  });

  final double readinessScore;
  final String correlatedTradeWarning;
  final String executionSequencing;
  final double exposureAfterTradePct;
  final String exposureBalancingAction;
  final String positionManagement;
}

class WatchtowerAlert {
  const WatchtowerAlert({
    required this.title,
    required this.detail,
    required this.severity,
  });

  final String title;
  final String detail;
  final WatchtowerSeverity severity;
}

enum WatchtowerSeverity { info, warning, critical }

class WatchtowerRead {
  const WatchtowerRead({
    required this.alerts,
    required this.status,
    required this.riskPulse,
  });

  final List<WatchtowerAlert> alerts;
  final String status;
  final double riskPulse;
}

class JournalTimelineEntry {
  const JournalTimelineEntry({
    required this.category,
    required this.title,
    required this.detail,
    required this.timestamp,
  });

  final String category;
  final String title;
  final String detail;
  final DateTime timestamp;
}

class ProfessionalJournalRead {
  const ProfessionalJournalRead({
    required this.timeline,
    required this.sessionSummary,
    required this.disciplineScore,
  });

  final List<JournalTimelineEntry> timeline;
  final String sessionSummary;
  final double disciplineScore;
}

class ScalabilityRead {
  const ScalabilityRead({
    required this.lazyRenderingActive,
    required this.providerScopeMode,
    required this.eventBusMode,
    required this.chartUpdateCadence,
    required this.rebuildScope,
    required this.memoryPosture,
  });

  final bool lazyRenderingActive;
  final String providerScopeMode;
  final String eventBusMode;
  final String chartUpdateCadence;
  final String rebuildScope;
  final String memoryPosture;
}

class TradingOperatingSystemEngine {
  const TradingOperatingSystemEngine();

  PortfolioIntelligenceRead portfolioIntelligence({
    required UserPnLModel? pnl,
    required List<ActiveTradeModel> trades,
    MarketSummaryModel? market,
  }) {
    final equity = math.max(pnl?.currentEquity ?? 0, 1);
    final totalNotional = trades.fold<double>(
      0,
      (sum, trade) => sum + trade.entry * trade.executedQuantity,
    );
    final grossExposure = pnl?.grossExposure != 0
        ? (pnl?.grossExposure ?? totalNotional)
        : totalNotional;
    final grossPct = (grossExposure / equity * 100).clamp(0, 300).toDouble();
    final sector = _sectorExposure(trades, totalNotional);
    final side = _sideExposure(trades, totalNotional);
    final concentration =
        sector.values.isEmpty ? 0.0 : sector.values.reduce(math.max);
    final volatility = ((market?.avgVolatilityPct ?? 0) * 7 +
            trades.fold<double>(0, (sum, item) => sum + item.riskFraction) *
                220)
        .clamp(0, 100)
        .toDouble();
    final correlation = _correlationExposure(trades);
    final heat = (grossPct * 0.28 +
            volatility * 0.28 +
            correlation * 0.24 +
            concentration * 0.20)
        .clamp(0, 100)
        .toDouble();
    final warnings = <String>[
      if (correlation >= 70) 'Correlated exposure is elevated.',
      if (concentration >= 55) 'Portfolio concentration needs review.',
      if (grossPct >= 120) 'Gross exposure is above disciplined range.',
      if ((pnl?.rollingDrawdown ?? 0) >= 0.05) 'Drawdown pressure is active.',
    ];
    return PortfolioIntelligenceRead(
      grossExposurePct: grossPct,
      leverageExposure: (grossPct / 100).clamp(0, 5).toDouble(),
      volatilityExposure: volatility,
      correlationExposure: correlation,
      concentrationRisk: concentration,
      aiPortfolioHeat: heat,
      sectorExposure: sector,
      sideExposure: side,
      regimeAdaptation: heat >= 72
          ? 'Reduce new exposure and prioritize hedged/scalp setups.'
          : heat >= 48
              ? 'Allow only the strongest uncorrelated opportunities.'
              : 'Portfolio has room for selective high-edge entries.',
      warnings: warnings.isEmpty
          ? const <String>['Portfolio risk is inside normal operating range.']
          : warnings,
    );
  }

  MultiAssetOrchestrationRead multiAssetOrchestration({
    required List<SignalModel> signals,
    required List<ActiveTradeModel> trades,
    MarketUniverseModel? universe,
  }) {
    final openGroups = trades.map((trade) => _assetGroup(trade.symbol)).toSet();
    final universeMap = <String, MarketUniverseEntryModel>{
      for (final item in universe?.items ?? const <MarketUniverseEntryModel>[])
        item.symbol: item,
      for (final item
          in universe?.aiPicks ?? const <MarketUniverseEntryModel>[])
        item.symbol: item,
    };
    final rows = signals.map((signal) {
      final item = universeMap[signal.symbol];
      final group = _assetGroup(signal.symbol, category: item?.category);
      final correlated = openGroups.contains(group) && trades.isNotEmpty;
      final score = (math.max(signal.alphaScore, signal.qualityScore) +
              (item?.trendPct ?? 0) * 0.18 +
              (item?.volumeRatio ?? 0) * 1.4 -
              (correlated ? 14 : 0))
          .clamp(0, 100)
          .toDouble();
      return AssetOrchestrationRow(
        symbol: signal.symbol,
        rankScore: score,
        assetGroup: group,
        action: correlated ? 'Wait / reduce duplicate risk' : 'Eligible',
        correlationSuppressed: correlated,
        reason: correlated
            ? '$group exposure is already active.'
            : 'Uncorrelated opportunity with ${score.toStringAsFixed(0)} score.',
      );
    }).toList()
      ..sort((a, b) => b.rankScore.compareTo(a.rankScore));
    return MultiAssetOrchestrationRead(
      globalRank: rows.take(8).toList(growable: false),
      primaryOpportunity:
          rows.isEmpty ? 'No ranked setup yet' : rows.first.symbol,
      suppressedSymbols: rows
          .where((row) => row.correlationSuppressed)
          .map((row) => row.symbol)
          .toList(growable: false),
      exposureDirective: rows.any((row) => row.correlationSuppressed)
          ? 'Suppress duplicate correlated risk and prioritize clean groups.'
          : 'Global queue is clean enough for strongest-edge prioritization.',
    );
  }

  AiCopilotRead copilot({
    required PortfolioIntelligenceRead portfolio,
    required MultiAssetOrchestrationRead orchestration,
    ModelDriftRead? drift,
    MarketSummaryModel? market,
  }) {
    final messages = <String>[
      portfolio.regimeAdaptation,
      if (orchestration.primaryOpportunity != 'No ranked setup yet')
        '${orchestration.primaryOpportunity} is currently the strongest global setup.',
      if ((market?.avgVolatilityPct ?? 0) >= 4)
        'Current volatility favors shorter execution windows.',
      if ((market?.sentimentScore ?? 50) < 42)
        'Market sentiment is defensive; reduce alt continuation assumptions.',
      if (drift?.driftDetected == true)
        'AI stability is deteriorating; tighten confirmation before new risk.',
    ];
    final heat = portfolio.aiPortfolioHeat;
    return AiCopilotRead(
      posture: heat >= 72
          ? 'Defensive desk'
          : heat >= 48
              ? 'Selective desk'
              : 'Opportunity desk',
      primaryGuidance: messages.first,
      messages: messages.take(5).toList(growable: false),
    );
  }

  CloudProfileSyncRead cloudProfileSync({
    required bool onboardingComplete,
    required int watchlistItems,
    required int replayItems,
    required bool aiMemoryAvailable,
  }) {
    final checks = <bool>[
      true,
      aiMemoryAvailable,
      onboardingComplete,
      watchlistItems > 0,
      replayItems > 0,
      true,
    ];
    return CloudProfileSyncRead(
      preferencesReady: checks[0],
      aiMemoryReady: checks[1],
      onboardingReady: checks[2],
      watchlistsReady: checks[3],
      replayHistoryReady: checks[4],
      aiModesReady: checks[5],
      pendingSyncItems: checks.where((item) => !item).length,
      syncNote:
          'Cloud sync contract is prepared for preferences, AI memory, onboarding, watchlists, replay history, and AI modes.',
    );
  }

  RealtimeOrchestrationRead realtimeOrchestration({
    required int signalCount,
    required int activeTrades,
    required bool chartActive,
  }) {
    final heavy = signalCount > 12 || activeTrades > 4;
    return RealtimeOrchestrationRead(
      batchWindowMs: heavy ? 180 : 90,
      priorityLanes: const <String>[
        'execution',
        'portfolio',
        'market',
        'ai',
        'analytics',
      ],
      updateThrottleMs: heavy ? 240 : 120,
      chartRefreshCadenceMs: chartActive ? (heavy ? 500 : 250) : 900,
      animationBudgetMs: heavy ? 8 : 12,
      signalQueueMode: heavy ? 'prioritized top-edge queue' : 'normal queue',
      loadState: heavy
          ? 'Heavy realtime load: batching and throttling active.'
          : 'Realtime load normal: low-latency updates active.',
    );
  }

  ExecutionWorkspaceRead executionWorkspace({
    required PortfolioIntelligenceRead portfolio,
    required SignalModel? signal,
    TradeEvaluationModel? evaluation,
  }) {
    final confidence = evaluation?.confidenceScore ??
        (signal == null
            ? 0.0
            : signal.confidence <= 1
                ? signal.confidence * 100
                : signal.confidence);
    final correlated = signal != null &&
        portfolio.sectorExposure.containsKey(_assetGroup(signal.symbol));
    final exposureAfter =
        (portfolio.grossExposurePct + (evaluation?.riskBudget ?? 0.01) * 100)
            .clamp(0, 300)
            .toDouble();
    final readiness = (confidence * 0.46 +
            (100 - portfolio.aiPortfolioHeat) * 0.34 +
            (evaluation?.allowTrade == true ? 20 : 0) -
            (correlated ? 12 : 0))
        .clamp(0, 100)
        .toDouble();
    return ExecutionWorkspaceRead(
      readinessScore: readiness,
      correlatedTradeWarning: correlated
          ? 'New trade overlaps current ${_assetGroup(signal.symbol)} exposure.'
          : 'No direct portfolio correlation conflict detected.',
      executionSequencing: readiness >= 75
          ? 'Sequence as primary execution candidate after backend approval.'
          : 'Keep as watch/simulate candidate until portfolio heat improves.',
      exposureAfterTradePct: exposureAfter,
      exposureBalancingAction: exposureAfter >= 120
          ? 'Trim or avoid additional notional before entry.'
          : 'Exposure remains inside planned operating range.',
      positionManagement:
          'Manage open positions first, then route only the highest scoring approved strategy.',
    );
  }

  WatchtowerRead watchtower({
    required PortfolioIntelligenceRead portfolio,
    ModelDriftRead? drift,
    MarketSummaryModel? market,
    RealtimeTradeUpdateModel? tradeUpdate,
  }) {
    final alerts = <WatchtowerAlert>[
      if (portfolio.aiPortfolioHeat >= 70)
        const WatchtowerAlert(
          title: 'Portfolio heat elevated',
          detail: 'Reduce correlated entries and check concentration.',
          severity: WatchtowerSeverity.warning,
        ),
      if ((market?.avgVolatilityPct ?? 0) >= 5)
        const WatchtowerAlert(
          title: 'Volatility expansion',
          detail: 'Scalp windows are favored over late swing entries.',
          severity: WatchtowerSeverity.warning,
        ),
      if (drift?.driftDetected == true)
        const WatchtowerAlert(
          title: 'Edge deterioration',
          detail: 'AI drift monitor recommends stricter confirmation.',
          severity: WatchtowerSeverity.critical,
        ),
      if (tradeUpdate != null)
        WatchtowerAlert(
          title: 'Execution event',
          detail:
              '${tradeUpdate.status.toUpperCase()} ${tradeUpdate.symbol} ${tradeUpdate.side}',
          severity: WatchtowerSeverity.info,
        ),
    ];
    final resolved = alerts.isEmpty
        ? const <WatchtowerAlert>[
            WatchtowerAlert(
              title: 'Desk normal',
              detail:
                  'No portfolio, market, or execution instability detected.',
              severity: WatchtowerSeverity.info,
            ),
          ]
        : alerts;
    return WatchtowerRead(
      alerts: resolved,
      status: resolved
              .any((item) => item.severity == WatchtowerSeverity.critical)
          ? 'ATTENTION'
          : resolved.any((item) => item.severity == WatchtowerSeverity.warning)
              ? 'WATCH'
              : 'NORMAL',
      riskPulse: portfolio.aiPortfolioHeat,
    );
  }

  ProfessionalJournalRead professionalJournal({
    required List<ActiveTradeModel> trades,
    required List<AiDecisionJournalEntry> decisions,
    MarketSummaryModel? market,
    RealtimeTradeUpdateModel? tradeUpdate,
  }) {
    final now = DateTime.now();
    final timeline = <JournalTimelineEntry>[
      JournalTimelineEntry(
        category: 'Portfolio',
        title: '${trades.length} active positions',
        detail: trades.isEmpty
            ? 'No open exposure currently.'
            : 'Portfolio timeline is tracking open exposure and risk fraction.',
        timestamp: now,
      ),
      if (market != null)
        JournalTimelineEntry(
          category: 'Regime',
          title: market.sentimentLabel,
          detail:
              'Breadth ${market.marketBreadth.toStringAsFixed(0)} | Vol ${market.avgVolatilityPct.toStringAsFixed(2)}',
          timestamp: now,
        ),
      if (tradeUpdate != null)
        JournalTimelineEntry(
          category: 'Execution',
          title: tradeUpdate.status.toUpperCase(),
          detail: '${tradeUpdate.symbol} ${tradeUpdate.side}',
          timestamp: tradeUpdate.timestamp,
        ),
      ...decisions.take(3).map(
            (decision) => JournalTimelineEntry(
              category: 'AI',
              title: decision.symbol,
              detail: decision.learned,
              timestamp: now,
            ),
          ),
    ];
    final discipline = (100 -
            trades.fold<double>(0, (sum, trade) => sum + trade.riskFraction) *
                180)
        .clamp(0, 99)
        .toDouble();
    return ProfessionalJournalRead(
      timeline: timeline.take(8).toList(growable: false),
      sessionSummary: discipline >= 72
          ? 'Session discipline is controlled; continue prioritizing edge quality.'
          : 'Session needs tighter risk discipline before adding exposure.',
      disciplineScore: discipline,
    );
  }

  ScalabilityRead scalability({
    required int signalCount,
    required bool chartActive,
  }) {
    final heavy = signalCount > 12;
    return ScalabilityRead(
      lazyRenderingActive: true,
      providerScopeMode: 'Riverpod scoped providers with visible-surface reads',
      eventBusMode: 'Prioritized websocket lanes with REST fallback',
      chartUpdateCadence: chartActive
          ? (heavy ? 'coalesced chart refresh' : 'realtime chart refresh')
          : 'background chart cadence',
      rebuildScope: heavy
          ? 'Reduced rebuild scope: top-edge surfaces only'
          : 'Normal rebuild scope',
      memoryPosture:
          'Advisory reads are derived from existing models and avoid persistent timers.',
    );
  }

  Map<String, double> _sectorExposure(
    List<ActiveTradeModel> trades,
    double totalNotional,
  ) {
    if (trades.isEmpty || totalNotional <= 0) {
      return const <String, double>{};
    }
    final grouped = <String, double>{};
    for (final trade in trades) {
      final group = _assetGroup(trade.symbol);
      grouped[group] = (grouped[group] ?? 0) +
          trade.entry * trade.executedQuantity / totalNotional * 100;
    }
    return grouped;
  }

  Map<String, double> _sideExposure(
    List<ActiveTradeModel> trades,
    double totalNotional,
  ) {
    if (trades.isEmpty || totalNotional <= 0) {
      return const <String, double>{};
    }
    final grouped = <String, double>{};
    for (final trade in trades) {
      final side = trade.side.toUpperCase();
      grouped[side] = (grouped[side] ?? 0) +
          trade.entry * trade.executedQuantity / totalNotional * 100;
    }
    return grouped;
  }

  double _correlationExposure(List<ActiveTradeModel> trades) {
    if (trades.length <= 1) {
      return trades.isEmpty ? 0 : 28;
    }
    final groups = trades.map((trade) => _assetGroup(trade.symbol)).toList();
    final largest = groups
        .map((group) => groups.where((item) => item == group).length)
        .reduce(math.max);
    return (largest / trades.length * 100).clamp(0, 100).toDouble();
  }

  String _assetGroup(String symbol, {String? category}) {
    final normalized = symbol.toUpperCase();
    if (normalized.contains('BTC')) {
      return 'BTC';
    }
    if (normalized.contains('ETH')) {
      return 'ETH';
    }
    if (category != null && category.toLowerCase().contains('meme')) {
      return 'Meme volatility';
    }
    if (RegExp('SOL|BNB|XRP|ADA|AVAX|LINK|DOGE|DOT|MATIC')
        .hasMatch(normalized)) {
      return 'Majors';
    }
    if (RegExp('PEPE|SHIB|BONK|WIF|FLOKI').hasMatch(normalized)) {
      return 'Meme volatility';
    }
    return 'Altcoins';
  }
}

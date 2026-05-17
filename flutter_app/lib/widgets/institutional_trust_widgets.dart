import 'package:flutter/material.dart';

import '../core/institutional_intelligence_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class ConfidenceTransparencyPanel extends StatelessWidget {
  const ConfidenceTransparencyPanel({
    super.key,
    required this.transparency,
  });

  final SignalTransparency transparency;

  @override
  Widget build(BuildContext context) {
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
                  'AI Confidence Transparency',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label:
                    '${transparency.confirmationCount}/${transparency.contributors.length} confirmed',
                color: TradingPalette.electricBlue,
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...transparency.contributors.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Icon(
                    item.confirmed
                        ? Icons.check_circle_rounded
                        : Icons.cancel_rounded,
                    color: item.confirmed
                        ? TradingPalette.neonGreen
                        : TradingPalette.textFaint,
                    size: 18,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          item.label,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          item.detail,
                          style: const TextStyle(
                            color: TradingPalette.textMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    item.score.toStringAsFixed(0),
                    style: TextStyle(
                      color: item.confirmed
                          ? TradingPalette.neonGreen
                          : TradingPalette.textMuted,
                      fontWeight: FontWeight.w900,
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

class ExecutionBriefingPanel extends StatelessWidget {
  const ExecutionBriefingPanel({
    super.key,
    required this.briefing,
  });

  final ExecutionBriefing briefing;

  @override
  Widget build(BuildContext context) {
    final sideColor = briefing.side.toUpperCase() == 'SELL'
        ? TradingPalette.neonRed
        : TradingPalette.neonGreen;
    return GlassPanel(
      glowColor: sideColor,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'AI Trade Briefing',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: briefing.side, color: sideColor),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${briefing.symbol} ${briefing.side} | ${briefing.confidence.toStringAsFixed(0)}% confidence | Risk ${briefing.riskGrade}',
            style: const TextStyle(
              color: TradingPalette.textPrimary,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _BriefingMetric(
                label: 'Leverage',
                value: '${briefing.suggestedLeverage.toStringAsFixed(1)}x',
              ),
              _BriefingMetric(
                label: 'Size',
                value: briefing.positionSizeLabel,
              ),
              _BriefingMetric(label: 'Entry', value: briefing.entryLabel),
              _BriefingMetric(
                label: 'Invalidation',
                value: briefing.invalidation,
              ),
              _BriefingMetric(
                label: 'Hold',
                value: briefing.expectedHoldDuration,
              ),
              _BriefingMetric(
                label: 'Decay',
                value: briefing.confidenceDecay,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            'TP ladder: ${briefing.takeProfitZones.map((price) => price.toStringAsFixed(price >= 100 ? 2 : 4)).join(' / ')}',
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
          const SizedBox(height: 6),
          Text(
            '${briefing.volatilityAdjustedRisk}. Liquidation risk: ${briefing.liquidationRisk}. Regime: ${briefing.marketRegime}.',
            style: const TextStyle(color: TradingPalette.textMuted),
          ),
        ],
      ),
    );
  }
}

class _BriefingMetric extends StatelessWidget {
  const _BriefingMetric({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 94),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 3),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class MicrostructurePanel extends StatelessWidget {
  const MicrostructurePanel({
    super.key,
    required this.read,
  });

  final MarketMicrostructureRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Market Microstructure',
      badge: '${read.trapProbability.toStringAsFixed(0)}% trap',
      color: TradingPalette.violet,
      rows: <String>[
        read.liquiditySweep,
        read.orderAbsorption,
        read.imbalanceZones,
        'Fakeout risk ${read.fakeoutRisk.toStringAsFixed(0)}%, exhaustion ${read.exhaustionRisk.toStringAsFixed(0)}%',
        read.smartMoneyBias,
      ],
    );
  }
}

class MarketContextPanel extends StatelessWidget {
  const MarketContextPanel({
    super.key,
    required this.contextRead,
  });

  final MarketContextRead contextRead;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Market Context',
      badge: contextRead.volatilityRegime,
      color: TradingPalette.amber,
      rows: <String>[
        contextRead.btcDominanceInfluence,
        contextRead.fearGreedState,
        contextRead.sectorMomentum,
        'Trend regime: ${contextRead.marketTrendRegime}',
        contextRead.correlationRisk,
        'Sentiment bias: ${contextRead.sentimentBias}',
      ],
    );
  }
}

class ProfessionalPerformancePanel extends StatelessWidget {
  const ProfessionalPerformancePanel({
    super.key,
    required this.performance,
  });

  final ProfessionalPerformanceRead performance;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.neonGreen,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Professional Metrics',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: <Widget>[
              _BriefingMetric(
                label: 'Win rate',
                value: '${performance.winRate.toStringAsFixed(0)}%',
              ),
              _BriefingMetric(
                label: 'Avg RR',
                value: '1:${performance.averageRiskReward.toStringAsFixed(2)}',
              ),
              _BriefingMetric(
                label: 'Profit factor',
                value: performance.profitFactor.toStringAsFixed(2),
              ),
              _BriefingMetric(
                label: 'Max DD',
                value: '${performance.maxDrawdown.toStringAsFixed(1)}%',
              ),
              _BriefingMetric(
                label: 'AI align',
                value: '${performance.aiAlignmentScore.toStringAsFixed(0)}%',
              ),
              _BriefingMetric(
                label: 'Discipline',
                value: '${performance.disciplineScore.toStringAsFixed(0)}%',
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class AiMemoryPanel extends StatelessWidget {
  const AiMemoryPanel({
    super.key,
    required this.memory,
  });

  final AiMemoryProfile memory;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Adaptive AI Memory',
      badge: memory.preferredMode,
      color: TradingPalette.electricBlue,
      rows: <String>[
        'Preferred assets: ${memory.preferredAssets.take(4).join(', ')}',
        'Favorite style: ${memory.favoriteStyle}',
        'Successful setups: ${memory.successfulSetups.take(3).join(', ')}',
        'Avoided setups: ${memory.avoidedSetups.take(2).join(', ')}',
        memory.personalizedNote,
      ],
    );
  }
}

class SignalLifecycleRail extends StatelessWidget {
  const SignalLifecycleRail({
    super.key,
    required this.current,
  });

  final String current;

  static const List<String> stages = <String>[
    'SCANNING',
    'BUILDING',
    'CONFIRMING',
    'ENTRY ACTIVE',
    'IN PROFIT',
    'TAKE PROFIT HIT',
    'EXIT COMPLETE',
  ];

  @override
  Widget build(BuildContext context) {
    final invalidated =
        current == 'INVALIDATED' || current == 'FAILED STRUCTURE';
    final activeIndex =
        invalidated ? 2 : stages.indexOf(current).clamp(0, stages.length - 1);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: Text(
                'Signal lifecycle',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ),
            StatusBadge(
              label: current,
              color: invalidated
                  ? TradingPalette.neonRed
                  : TradingPalette.neonGreen,
            ),
          ],
        ),
        const SizedBox(height: 10),
        Row(
          children: <Widget>[
            for (var index = 0; index < stages.length; index += 1)
              Expanded(
                child: Container(
                  height: index == activeIndex ? 9 : 6,
                  margin: EdgeInsets.only(
                      right: index == stages.length - 1 ? 0 : 5),
                  decoration: BoxDecoration(
                    color: invalidated && index >= activeIndex
                        ? TradingPalette.neonRed
                        : index <= activeIndex
                            ? TradingPalette.neonGreen
                            : TradingPalette.panelBorder,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _DeskPanel extends StatelessWidget {
  const _DeskPanel({
    required this.title,
    required this.badge,
    required this.color,
    required this.rows,
  });

  final String title;
  final String badge;
  final Color color;
  final List<String> rows;

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
          ...rows.map(
            (row) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.only(top: 6),
                    decoration:
                        BoxDecoration(shape: BoxShape.circle, color: color),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      row,
                      style: const TextStyle(color: TradingPalette.textPrimary),
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

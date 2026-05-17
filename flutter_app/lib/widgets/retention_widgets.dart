import 'package:flutter/material.dart';

import '../core/retention_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'live_energy_widgets.dart';
import 'status_badge.dart';

class TraderLevelPanel extends StatelessWidget {
  const TraderLevelPanel({
    super.key,
    required this.snapshot,
  });

  final RetentionSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final progress = (snapshot.xp / snapshot.nextLevelXp).clamp(0.0, 1.0);
    return GlassPanel(
      glowColor: TradingPalette.violet,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              ConfidencePulseRing(
                value: snapshot.reputation / 100,
                color: TradingPalette.violet,
                label: 'REP',
                size: 92,
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'AI Trader Level ${snapshot.level}',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                            fontWeight: FontWeight.w900,
                          ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${snapshot.streakDays}-day AI streak | ${snapshot.dailyAccuracy.toStringAsFixed(0)}% daily accuracy pulse',
                      style: const TextStyle(color: TradingPalette.textMuted),
                    ),
                    const SizedBox(height: 12),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(999),
                      child: LinearProgressIndicator(
                        value: progress,
                        minHeight: 9,
                        backgroundColor: TradingPalette.overlay,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                          TradingPalette.violet,
                        ),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${snapshot.xp} XP / ${snapshot.nextLevelXp} XP',
                      style: Theme.of(context).textTheme.labelSmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class DailyMissionsPanel extends StatelessWidget {
  const DailyMissionsPanel({
    super.key,
    required this.missions,
  });

  final List<RetentionMission> missions;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Daily AI Missions',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 12),
          ...missions.take(4).map(
                (mission) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _MissionTile(mission: mission),
                ),
              ),
        ],
      ),
    );
  }
}

class _MissionTile extends StatelessWidget {
  const _MissionTile({required this.mission});

  final RetentionMission mission;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 46,
            height: 46,
            child: CircularProgressIndicator(
              value: mission.progress,
              backgroundColor: TradingPalette.panelBorder,
              valueColor: const AlwaysStoppedAnimation<Color>(
                TradingPalette.electricBlue,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  mission.title,
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 3),
                Text(
                  mission.subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(color: TradingPalette.textMuted),
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          StatusBadge(
            label: '+${mission.rewardXp} XP',
            color: TradingPalette.amber,
          ),
        ],
      ),
    );
  }
}

class ShadowPortfolioPanel extends StatelessWidget {
  const ShadowPortfolioPanel({
    super.key,
    required this.trades,
  });

  final List<ShadowTrade> trades;

  @override
  Widget build(BuildContext context) {
    final total = trades.fold<double>(
      0,
      (sum, trade) => sum + trade.simulatedPnlPct,
    );
    return GlassPanel(
      glowColor: total >= 0 ? TradingPalette.neonGreen : TradingPalette.neonRed,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Shadow Portfolio',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label: '${total >= 0 ? '+' : ''}${total.toStringAsFixed(1)}%',
                color: total >= 0
                    ? TradingPalette.neonGreen
                    : TradingPalette.neonRed,
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (trades.isEmpty)
            const Text(
              'AI is preparing simulated entries from the next opportunity wave.',
              style: TextStyle(color: TradingPalette.textMuted),
            )
          else
            ...trades.take(3).map(
                  (trade) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      children: <Widget>[
                        Expanded(
                          child: Text(
                            '${trade.symbol} ${trade.side}',
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        Text(
                          '${trade.simulatedPnlPct >= 0 ? '+' : ''}${trade.simulatedPnlPct.toStringAsFixed(1)}%',
                          style: TextStyle(
                            color: trade.simulatedPnlPct >= 0
                                ? TradingPalette.neonGreen
                                : TradingPalette.neonRed,
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

class SocialCompetitionPanel extends StatelessWidget {
  const SocialCompetitionPanel({
    super.key,
    required this.snapshot,
  });

  final RetentionSnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: TradingPalette.amber,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'AI Battle Board',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(
                label:
                    '${snapshot.communityConviction.toStringAsFixed(0)}% conviction',
                color: TradingPalette.amber,
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...snapshot.leaderboard.take(4).map(
                (rank) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Row(
                    children: <Widget>[
                      SizedBox(
                        width: 32,
                        child: Text(
                          '#${rank.rank}',
                          style: const TextStyle(
                            color: TradingPalette.textMuted,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                      Expanded(
                        child: Text(
                          rank.name,
                          style: const TextStyle(fontWeight: FontWeight.w900),
                        ),
                      ),
                      Text(
                        rank.badge,
                        style: const TextStyle(color: TradingPalette.textFaint),
                      ),
                      const SizedBox(width: 10),
                      Text(
                        rank.score.toStringAsFixed(0),
                        style: const TextStyle(
                          color: TradingPalette.amber,
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

class FeatureGatePanel extends StatelessWidget {
  const FeatureGatePanel({
    super.key,
    required this.gate,
  });

  final FeatureGate gate;

  @override
  Widget build(BuildContext context) {
    final tier = gate.tier.name.toUpperCase();
    return GlassPanel(
      glowColor: gate.tier == PlanTier.vip
          ? TradingPalette.amber
          : gate.tier == PlanTier.pro
              ? TradingPalette.violet
              : TradingPalette.electricBlue,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  '$tier AI Access',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: '${gate.dailyScanLimit} scans'),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: <Widget>[
              _GateChip(label: 'Realtime AI', enabled: gate.realtimeAi),
              _GateChip(label: 'Sniper entries', enabled: gate.sniperEntries),
              _GateChip(label: 'Auto execution', enabled: gate.autoExecution),
              _GateChip(label: 'Whale tracking', enabled: gate.whaleTracking),
              _GateChip(
                label: 'Predictive heatmaps',
                enabled: gate.predictiveHeatmaps,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _GateChip extends StatelessWidget {
  const _GateChip({
    required this.label,
    required this.enabled,
  });

  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(label),
      avatar: Icon(
        enabled ? Icons.check_circle_rounded : Icons.lock_rounded,
        size: 16,
        color: enabled ? TradingPalette.neonGreen : TradingPalette.textFaint,
      ),
      backgroundColor: TradingPalette.overlay,
      side: BorderSide(
        color: enabled
            ? TradingPalette.neonGreen.withOpacity(0.24)
            : TradingPalette.panelBorder,
      ),
    );
  }
}

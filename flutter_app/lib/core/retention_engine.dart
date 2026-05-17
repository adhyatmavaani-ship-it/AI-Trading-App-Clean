import 'dart:math' as math;

import '../models/signal.dart';
import 'ai_opportunity_engine.dart';

enum PlanTier { free, pro, vip }

enum AdvancedAiMode {
  safe,
  smart,
  aggressive,
  sniper,
  scalp,
  swing,
  whaleFollow,
}

class FeatureGate {
  const FeatureGate({
    required this.tier,
    required this.realtimeAi,
    required this.sniperEntries,
    required this.advancedOverlays,
    required this.autoExecution,
    required this.whaleTracking,
    required this.premiumScanners,
    required this.predictiveHeatmaps,
    required this.dailyScanLimit,
  });

  final PlanTier tier;
  final bool realtimeAi;
  final bool sniperEntries;
  final bool advancedOverlays;
  final bool autoExecution;
  final bool whaleTracking;
  final bool premiumScanners;
  final bool predictiveHeatmaps;
  final int dailyScanLimit;

  static FeatureGate forTier(PlanTier tier) {
    switch (tier) {
      case PlanTier.free:
        return const FeatureGate(
          tier: PlanTier.free,
          realtimeAi: false,
          sniperEntries: false,
          advancedOverlays: false,
          autoExecution: false,
          whaleTracking: false,
          premiumScanners: false,
          predictiveHeatmaps: false,
          dailyScanLimit: 12,
        );
      case PlanTier.pro:
        return const FeatureGate(
          tier: PlanTier.pro,
          realtimeAi: true,
          sniperEntries: true,
          advancedOverlays: true,
          autoExecution: true,
          whaleTracking: true,
          premiumScanners: true,
          predictiveHeatmaps: false,
          dailyScanLimit: 120,
        );
      case PlanTier.vip:
        return const FeatureGate(
          tier: PlanTier.vip,
          realtimeAi: true,
          sniperEntries: true,
          advancedOverlays: true,
          autoExecution: true,
          whaleTracking: true,
          premiumScanners: true,
          predictiveHeatmaps: true,
          dailyScanLimit: 999,
        );
    }
  }
}

class RetentionMission {
  const RetentionMission({
    required this.title,
    required this.subtitle,
    required this.progress,
    required this.rewardXp,
    required this.badge,
  });

  final String title;
  final String subtitle;
  final double progress;
  final int rewardXp;
  final String badge;
}

class TraderAchievement {
  const TraderAchievement({
    required this.title,
    required this.subtitle,
    required this.level,
    required this.unlocked,
  });

  final String title;
  final String subtitle;
  final int level;
  final bool unlocked;
}

class ShadowTrade {
  const ShadowTrade({
    required this.symbol,
    required this.side,
    required this.entry,
    required this.simulatedPnlPct,
    required this.reason,
    required this.opportunity,
  });

  final String symbol;
  final String side;
  final double entry;
  final double simulatedPnlPct;
  final String reason;
  final SignalOpportunity opportunity;
}

class SocialTraderRank {
  const SocialTraderRank({
    required this.name,
    required this.rank,
    required this.score,
    required this.badge,
  });

  final String name;
  final int rank;
  final double score;
  final String badge;
}

class RetentionSnapshot {
  const RetentionSnapshot({
    required this.level,
    required this.xp,
    required this.nextLevelXp,
    required this.reputation,
    required this.streakDays,
    required this.dailyAccuracy,
    required this.missions,
    required this.achievements,
    required this.shadowTrades,
    required this.leaderboard,
    required this.communityConviction,
    required this.featureGate,
  });

  final int level;
  final int xp;
  final int nextLevelXp;
  final double reputation;
  final int streakDays;
  final double dailyAccuracy;
  final List<RetentionMission> missions;
  final List<TraderAchievement> achievements;
  final List<ShadowTrade> shadowTrades;
  final List<SocialTraderRank> leaderboard;
  final double communityConviction;
  final FeatureGate featureGate;
}

class RetentionEngine {
  const RetentionEngine();

  RetentionSnapshot build({
    required List<SignalModel> signals,
    required AiTradingMode mode,
    PlanTier tier = PlanTier.pro,
  }) {
    final opportunities = signals
        .map((signal) => SignalOpportunity.fromSignal(signal, mode: mode))
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));
    final scoreSum = opportunities.fold<double>(
      0,
      (sum, item) => sum + item.score,
    );
    final averageScore =
        opportunities.isEmpty ? 68.0 : scoreSum / opportunities.length;
    final highQuality = opportunities
        .where((item) =>
            item.tier == OpportunityTier.strongSignal ||
            item.tier == OpportunityTier.highConviction)
        .length;
    final xp = 420 + (opportunities.length * 22) + (highQuality * 65);
    final level = math.max(1, (xp / 350).floor());
    final nextLevelXp = (level + 1) * 350;
    final streak = math.max(1, highQuality + 3);
    final shadowTrades = _shadowTrades(opportunities);

    return RetentionSnapshot(
      level: level,
      xp: xp,
      nextLevelXp: nextLevelXp,
      reputation: (averageScore + highQuality * 3).clamp(0, 99),
      streakDays: streak,
      dailyAccuracy: (62 + averageScore * 0.32).clamp(55, 94),
      missions: _missions(opportunities, highQuality),
      achievements: _achievements(level, highQuality, opportunities),
      shadowTrades: shadowTrades,
      leaderboard: _leaderboard(averageScore),
      communityConviction:
          (averageScore + opportunities.length * 2).clamp(20, 96),
      featureGate: FeatureGate.forTier(tier),
    );
  }

  List<RetentionMission> _missions(
    List<SignalOpportunity> opportunities,
    int highQuality,
  ) {
    final whaleCount =
        opportunities.where((item) => item.whalePressure >= 65).length;
    final scalpCount = opportunities
        .where((item) => item.tier == OpportunityTier.scalpWatch)
        .length;
    return <RetentionMission>[
      RetentionMission(
        title: 'Complete 3 AI scans',
        subtitle: 'Open scanner opportunities and review AI logic.',
        progress: (opportunities.length / 3).clamp(0, 1),
        rewardXp: 80,
        badge: 'Scanner Pulse',
      ),
      RetentionMission(
        title: 'Find a momentum ignition',
        subtitle: 'Catch one strong or high-conviction setup today.',
        progress: (highQuality / 1).clamp(0, 1),
        rewardXp: 120,
        badge: 'Momentum Hunter',
      ),
      RetentionMission(
        title: 'Track whale pressure',
        subtitle: 'Monitor two whale-activity opportunities.',
        progress: (whaleCount / 2).clamp(0, 1),
        rewardXp: 100,
        badge: 'Whale Tracker',
      ),
      RetentionMission(
        title: 'Shadow trade discipline',
        subtitle: 'Review scalp-watch setups without forcing execution.',
        progress: (scalpCount / 2).clamp(0, 1),
        rewardXp: 90,
        badge: 'Patient Sniper',
      ),
    ];
  }

  List<TraderAchievement> _achievements(
    int level,
    int highQuality,
    List<SignalOpportunity> opportunities,
  ) {
    final whaleElite = opportunities.any((item) => item.whalePressure >= 78);
    return <TraderAchievement>[
      TraderAchievement(
        title: 'Momentum Hunter',
        subtitle: 'Captured repeated momentum expansion setups.',
        level: math.max(1, level),
        unlocked: highQuality >= 1,
      ),
      TraderAchievement(
        title: 'Breakout Sniper',
        subtitle: 'Detected high breakout probability before the crowd.',
        level: math.max(1, level - 1),
        unlocked: opportunities.any((item) => item.breakoutProbability >= 78),
      ),
      TraderAchievement(
        title: 'Whale Tracker Elite',
        subtitle: 'Tracked smart money participation.',
        level: math.max(1, level - 2),
        unlocked: whaleElite,
      ),
    ];
  }

  List<ShadowTrade> _shadowTrades(List<SignalOpportunity> opportunities) {
    return opportunities.take(5).map((item) {
      final pnl = item.expectedMovePct *
          item.mode.suggestedRiskMultiplier *
          (item.bullish ? 0.72 : 0.58);
      return ShadowTrade(
        symbol: item.signal.symbol,
        side: item.sideLabel,
        entry: item.signal.price,
        simulatedPnlPct: pnl,
        reason:
            'If ${item.mode.label} tracked this setup, paper replay estimates ${pnl >= 0 ? '+' : ''}${pnl.toStringAsFixed(1)}%.',
        opportunity: item,
      );
    }).toList(growable: false);
  }

  List<SocialTraderRank> _leaderboard(double averageScore) {
    return <SocialTraderRank>[
      SocialTraderRank(
        name: 'You',
        rank: 7,
        score: averageScore.clamp(0, 99),
        badge: 'AI Operator',
      ),
      const SocialTraderRank(
        name: 'NeonScalper',
        rank: 1,
        score: 94,
        badge: 'Sniper Elite',
      ),
      const SocialTraderRank(
        name: 'WhalePilot',
        rank: 2,
        score: 91,
        badge: 'Whale Tracker',
      ),
      const SocialTraderRank(
        name: 'BreakoutX',
        rank: 3,
        score: 88,
        badge: 'Momentum Hunter',
      ),
    ];
  }
}

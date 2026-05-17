import '../models/signal.dart';
import 'ai_opportunity_engine.dart';

class AiPersonalityEngine {
  const AiPersonalityEngine();

  String narrativeForOpportunity(SignalOpportunity opportunity) {
    if (opportunity.whalePressure >= 72) {
      return 'Whale participation rising on ${opportunity.signal.symbol}. Smart money pressure is building.';
    }
    if (opportunity.breakoutProbability >= 78) {
      return 'AI detecting breakout compression on ${opportunity.signal.symbol}. Pressure is nearing ignition.';
    }
    if (opportunity.liquiditySweepProbability >= 68) {
      return 'Liquidity sweep probability is elevated. AI is waiting for reclaim confirmation.';
    }
    if (opportunity.tier == OpportunityTier.scalpWatch) {
      return 'Momentum is forming. AI is tracking a micro-entry window before full confirmation.';
    }
    if (opportunity.tier == OpportunityTier.highConviction) {
      return 'High conviction flow detected. Trend acceleration and structure alignment are active.';
    }
    return 'AI scanning structure, volume, whales, and volatility for the next high-quality trigger.';
  }

  String notificationForOpportunity(SignalOpportunity opportunity) {
    final side = opportunity.bullish ? 'long' : 'short';
    if (opportunity.tier == OpportunityTier.highConviction) {
      return 'AI Sniper detected a high-conviction $side setup on ${opportunity.signal.symbol}';
    }
    if (opportunity.whalePressure >= 72) {
      return 'Whale activity increasing on ${opportunity.signal.symbol}';
    }
    if (opportunity.tier == OpportunityTier.strongSignal) {
      return 'Momentum ignition triggered on ${opportunity.signal.symbol}';
    }
    return 'AI is preparing an entry on ${opportunity.signal.symbol}';
  }

  List<String> liveEventNarratives(
      List<SignalModel> signals, AiTradingMode mode) {
    final opportunities = signals
        .map((signal) => SignalOpportunity.fromSignal(signal, mode: mode))
        .toList()
      ..sort((a, b) => b.score.compareTo(a.score));
    if (opportunities.isEmpty) {
      return const <String>[
        'AI scanner rotating breakout, liquidity, and whale activity.',
        'Volatility radar active. Waiting for the next clean impulse.',
        'Smart money filter is watching compression zones.',
      ];
    }
    return opportunities.take(5).map(narrativeForOpportunity).toList();
  }
}

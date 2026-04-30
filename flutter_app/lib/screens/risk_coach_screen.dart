import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../features/risk_coach/providers/risk_coach_providers.dart';
import '../features/risk_coach/widgets/risk_coach_terminal.dart';


class RiskCoachScreen extends ConsumerWidget {
  const RiskCoachScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(riskCoachTerminalProvider);
    final executionState = ref.watch(riskCoachExecutionControllerProvider);
    final terminal = ref.read(riskCoachTerminalProvider.notifier);
    final execution = ref.read(riskCoachExecutionControllerProvider.notifier);

    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 6, 20, 32),
      children: <Widget>[
        Container(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: <Color>[
                Color(0xFF153042),
                TradingPalette.panelSoft,
              ],
            ),
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: TradingPalette.panelBorder),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                'AI Trading Risk Coach',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                'Risk-first execution, structured post-mortems, and educational review. No guaranteed profits and no financial advice.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        RiskCoachTerminal(
          state: state,
          executionState: executionState,
          onCreateTrade: terminal.createPracticeTrade,
          onCloseTrade: terminal.closeTrade,
          onPanicClose: terminal.panicClose,
          onTradeLevelChanged: ({
            double? entry,
            double? stopLoss,
            double? takeProfit,
          }) async {
            final trade = executionState.trade ?? state.trade;
            if (trade == null) {
              return;
            }
            await execution.updateLevels(
              tradeId: trade.tradeId,
              entry: entry,
              stopLoss: stopLoss,
              takeProfit: takeProfit,
            );
          },
        ),
      ],
    );
  }
}

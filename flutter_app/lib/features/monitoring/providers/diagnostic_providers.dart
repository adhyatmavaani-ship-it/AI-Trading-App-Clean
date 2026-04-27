import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../models/system_diagnostics.dart';
import '../../../providers/app_providers.dart';

final exchangeDiagnosticsProvider =
    StreamProvider<SystemDiagnosticsModel>((ref) {
  return ref
      .watch(tradingRepositoryProvider)
      .watchExchangeDiagnostics(sampleSymbol: 'BTCUSDT');
});

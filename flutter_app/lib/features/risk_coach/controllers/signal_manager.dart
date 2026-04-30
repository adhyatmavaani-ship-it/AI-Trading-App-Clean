import '../models/risk_coach_models.dart';

class SignalManager {
  SignalManager({
    List<RiskSignalMarker> markers = const <RiskSignalMarker>[],
  }) {
    replace(markers);
  }

  final Map<int, List<RiskSignalMarker>> _markersByTimestamp = <int, List<RiskSignalMarker>>{};
  final Map<String, RiskSignalMarker> _markersByTradeId = <String, RiskSignalMarker>{};

  void replace(List<RiskSignalMarker> markers) {
    _markersByTimestamp.clear();
    _markersByTradeId.clear();
    for (final marker in markers) {
      _markersByTimestamp.putIfAbsent(marker.timestampMs, () => <RiskSignalMarker>[]).add(marker);
      _markersByTradeId[marker.tradeId] = marker;
    }
  }

  List<RiskSignalMarker> markersForTimestamp(int timestampMs) {
    return _markersByTimestamp[timestampMs] ?? const <RiskSignalMarker>[];
  }

  RiskSignalMarker? markerForTrade(String tradeId) {
    return _markersByTradeId[tradeId];
  }
}

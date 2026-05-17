import '../models/market_chart.dart';

class ChartViewportIndex {
  const ChartViewportIndex({
    required this.visibleStartTs,
    required this.visibleEndTs,
  });

  final int visibleStartTs;
  final int visibleEndTs;

  List<MarketOverlayModel> overlays(
    List<MarketOverlayModel> source, {
    int limit = 32,
    DateTime? now,
  }) {
    final reference = now ?? DateTime.now().toUtc();
    if (visibleStartTs <= 0 || visibleEndTs <= 0) {
      return _sortedActive(source, reference).take(limit).toList(growable: false);
    }
    return _sortedActive(source, reference)
        .where((overlay) =>
            overlay.endTs >= visibleStartTs && overlay.startTs <= visibleEndTs)
        .take(limit)
        .toList(growable: false);
  }

  List<TradeMarkerModel> markers(
    List<TradeMarkerModel> source, {
    int limit = 48,
  }) {
    if (visibleStartTs <= 0 || visibleEndTs <= 0) {
      return source.take(limit).toList(growable: false);
    }
    return source
        .where((marker) {
          final markerTs = marker.timestamp.millisecondsSinceEpoch;
          return markerTs >= visibleStartTs && markerTs <= visibleEndTs;
        })
        .take(limit)
        .toList(growable: false);
  }

  List<MarketOverlayModel> _sortedActive(
    List<MarketOverlayModel> source,
    DateTime reference,
  ) {
    final active = source
        .where((overlay) =>
            overlay.expiresAt == null || overlay.expiresAt!.isAfter(reference))
        .toList();
    active.sort((left, right) => right.priority.compareTo(left.priority));
    return active;
  }
}

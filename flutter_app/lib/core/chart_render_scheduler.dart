class ChartRenderScheduler {
  ChartRenderScheduler({
    Duration targetFrame = const Duration(milliseconds: 16),
    Duration degradedFrame = const Duration(milliseconds: 33),
  })  : _targetFrame = targetFrame,
        _degradedFrame = degradedFrame;

  final Duration _targetFrame;
  final Duration _degradedFrame;
  DateTime? _lastFrameAt;
  bool _degraded = false;

  void setDegraded(bool value) {
    _degraded = value;
  }

  bool shouldRender({DateTime? now}) {
    final current = now ?? DateTime.now();
    final last = _lastFrameAt;
    final frame = _degraded ? _degradedFrame : _targetFrame;
    if (last != null && current.difference(last) < frame) {
      return false;
    }
    _lastFrameAt = current;
    return true;
  }
}

class RealtimeIntegrityDecision {
  const RealtimeIntegrityDecision({
    required this.accepted,
    required this.reason,
    required this.payload,
    this.latencyMs,
    this.stream,
    this.missingFrom,
    this.missingTo,
  });

  final bool accepted;
  final String reason;
  final Map<String, dynamic> payload;
  final int? latencyMs;
  final String? stream;
  final int? missingFrom;
  final int? missingTo;
}

class RealtimeIntegrityGate {
  RealtimeIntegrityGate({
    this.maxRecentEventIds = 256,
  });

  final int maxRecentEventIds;
  final Set<String> _recentEventIds = <String>{};
  final List<String> _recentEventOrder = <String>[];
  final Map<String, int> _lastSequenceByStream = <String, int>{};
  DateTime? _lastAcceptedAt;

  DateTime? get lastAcceptedAt => _lastAcceptedAt;

  bool isStale(Duration staleAfter, {DateTime? now}) {
    final last = _lastAcceptedAt;
    if (last == null) {
      return false;
    }
    return (now ?? DateTime.now().toUtc()).difference(last) > staleAfter;
  }

  RealtimeIntegrityDecision evaluate(Map<String, dynamic> payload) {
    final normalized = Map<String, dynamic>.from(payload);
    final realtime = Map<String, dynamic>.from(
      normalized['realtime'] as Map? ?? const <String, dynamic>{},
    );
    final stream = (realtime['stream'] ?? normalized['type'] ?? 'event')
        .toString()
        .trim();
    final eventId = (normalized['event_id'] ?? realtime['event_id'])
        ?.toString()
        .trim();
    if (eventId != null && eventId.isNotEmpty) {
      if (_recentEventIds.contains(eventId)) {
        return RealtimeIntegrityDecision(
          accepted: false,
          reason: 'duplicate_event',
          payload: normalized,
          latencyMs: _latencyMs(normalized, realtime),
          stream: stream,
        );
      }
    }

    final sequence = _sequenceId(normalized, realtime);
    if (sequence != null) {
      final lastSequence = _lastSequenceByStream[stream];
      if (lastSequence != null && sequence <= lastSequence) {
        return RealtimeIntegrityDecision(
          accepted: false,
          reason: 'old_sequence',
          payload: normalized,
          latencyMs: _latencyMs(normalized, realtime),
          stream: stream,
        );
      }
      if (lastSequence != null && sequence > lastSequence + 1) {
        return RealtimeIntegrityDecision(
          accepted: false,
          reason: 'sequence_gap',
          payload: normalized,
          latencyMs: _latencyMs(normalized, realtime),
          stream: stream,
          missingFrom: lastSequence + 1,
          missingTo: sequence,
        );
      }
      _lastSequenceByStream[stream] = sequence;
    }

    if (eventId != null && eventId.isNotEmpty) {
      _remember(eventId);
    }
    _lastAcceptedAt = DateTime.now().toUtc();
    return RealtimeIntegrityDecision(
      accepted: true,
      reason: 'accepted',
      payload: normalized,
      latencyMs: _latencyMs(normalized, realtime),
      stream: stream,
    );
  }

  void _remember(String eventId) {
    _recentEventIds.add(eventId);
    _recentEventOrder.add(eventId);
    while (_recentEventOrder.length > maxRecentEventIds) {
      final removed = _recentEventOrder.removeAt(0);
      _recentEventIds.remove(removed);
    }
  }

  int? _sequenceId(Map<String, dynamic> payload, Map<String, dynamic> realtime) {
    final raw = payload['sequence_id'] ?? realtime['sequence_id'];
    if (raw is num) {
      return raw.toInt();
    }
    return int.tryParse(raw?.toString() ?? '');
  }

  int? _latencyMs(Map<String, dynamic> payload, Map<String, dynamic> realtime) {
    final raw = payload['server_sent_at'] ?? realtime['server_sent_at'];
    if (raw == null) {
      return null;
    }
    final sentAt = DateTime.tryParse(raw.toString());
    if (sentAt == null) {
      return null;
    }
    return DateTime.now().toUtc().difference(sentAt.toUtc()).inMilliseconds;
  }
}

import 'package:ai_trading_app/core/realtime_integrity.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('drops duplicate realtime event ids', () {
    final gate = RealtimeIntegrityGate();

    final first = gate.evaluate(<String, dynamic>{
      'type': 'signal',
      'event_id': 'event-1',
      'sequence_id': 1,
    });
    final duplicate = gate.evaluate(<String, dynamic>{
      'type': 'signal',
      'event_id': 'event-1',
      'sequence_id': 2,
    });

    expect(first.accepted, isTrue);
    expect(duplicate.accepted, isFalse);
    expect(duplicate.reason, 'duplicate_event');
  });

  test('drops old sequence for the same stream', () {
    final gate = RealtimeIntegrityGate();

    expect(
      gate
          .evaluate(<String, dynamic>{
            'type': 'chart_snapshot',
            'event_id': 'event-1',
            'sequence_id': 10,
          })
          .accepted,
      isTrue,
    );
    final stale = gate.evaluate(<String, dynamic>{
      'type': 'chart_snapshot',
      'event_id': 'event-2',
      'sequence_id': 9,
    });

    expect(stale.accepted, isFalse);
    expect(stale.reason, 'old_sequence');
  });

  test('detects missing sequence range and delays acceptance', () {
    final gate = RealtimeIntegrityGate();
    expect(
      gate
          .evaluate(<String, dynamic>{
            'type': 'chart_snapshot',
            'event_id': 'event-10',
            'sequence_id': 10,
          })
          .accepted,
      isTrue,
    );

    final gap = gate.evaluate(<String, dynamic>{
      'type': 'chart_snapshot',
      'event_id': 'event-13',
      'sequence_id': 13,
    });

    expect(gap.accepted, isFalse);
    expect(gap.reason, 'sequence_gap');
    expect(gap.stream, 'chart_snapshot');
    expect(gap.missingFrom, 11);
    expect(gap.missingTo, 13);

    expect(
      gate
          .evaluate(<String, dynamic>{
            'type': 'chart_snapshot',
            'event_id': 'event-11',
            'sequence_id': 11,
          })
          .accepted,
      isTrue,
    );
  });

  test('detects stale feed after accepted event', () {
    final gate = RealtimeIntegrityGate();
    gate.evaluate(<String, dynamic>{
      'type': 'signal',
      'event_id': 'event-1',
      'sequence_id': 1,
    });

    expect(
      gate.isStale(
        const Duration(milliseconds: 1),
        now: DateTime.now().toUtc().add(const Duration(seconds: 1)),
      ),
      isTrue,
    );
  });
}

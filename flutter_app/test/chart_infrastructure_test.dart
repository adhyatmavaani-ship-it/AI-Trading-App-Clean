import 'package:ai_trading_app/core/chart_render_scheduler.dart';
import 'package:ai_trading_app/core/chart_spatial_index.dart';
import 'package:ai_trading_app/models/infrastructure_snapshot.dart';
import 'package:ai_trading_app/models/market_chart.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('chart render scheduler throttles redundant frames', () {
    final scheduler = ChartRenderScheduler();
    final now = DateTime.utc(2026, 1, 1);

    expect(scheduler.shouldRender(now: now), isTrue);
    expect(
      scheduler.shouldRender(now: now.add(const Duration(milliseconds: 5))),
      isFalse,
    );
    expect(
      scheduler.shouldRender(now: now.add(const Duration(milliseconds: 17))),
      isTrue,
    );
  });

  test('spatial index removes expired overlays and prioritizes visible zones', () {
    const index = ChartViewportIndex(
      visibleStartTs: 1000,
      visibleEndTs: 2000,
    );
    final overlays = <MarketOverlayModel>[
      MarketOverlayModel(
        zoneType: 'old',
        label: 'Old',
        startTs: 1100,
        endTs: 1200,
        low: 99,
        high: 100,
        confidence: 60,
        side: 'BUY',
        style: 'neutral',
        priority: 99,
        expiresAt: DateTime.utc(2025, 1, 1),
      ),
      const MarketOverlayModel(
        zoneType: 'liquidity_heatmap',
        label: 'Heatmap',
        startTs: 1300,
        endTs: 1500,
        low: 100,
        high: 101,
        confidence: 80,
        side: 'BUY',
        style: 'bullish',
        priority: 80,
      ),
      const MarketOverlayModel(
        zoneType: 'offscreen',
        label: 'Offscreen',
        startTs: 3000,
        endTs: 3200,
        low: 102,
        high: 103,
        confidence: 50,
        side: 'SELL',
        style: 'bearish',
        priority: 10,
      ),
    ];

    final visible = index.overlays(
      overlays,
      now: DateTime.utc(2026, 1, 1),
    );

    expect(visible.length, 1);
    expect(visible.single.zoneType, 'liquidity_heatmap');
  });

  test('market chart parses liquidity heatmap zones', () {
    final chart = MarketChartModel.fromJson(
      <String, dynamic>{
        'symbol': 'BTCUSDT',
        'interval': '5m',
        'candles': const <dynamic>[],
        'markers': const <dynamic>[],
        'confidence_intervals': const <dynamic>[],
        'confidence_history': const <dynamic>[],
        'liquidity_heatmap': <String, dynamic>{
          'pressure_score': 82.0,
          'nearest_wall': 'bid_liquidity',
          'heatmap_zones': <Map<String, dynamic>>[
            <String, dynamic>{
              'side': 'BUY',
              'label': 'Bid Liquidity',
              'start_ts': 1000,
              'end_ts': 2000,
              'low': 99.0,
              'high': 100.0,
              'intensity': 82.0,
              'opacity': 0.24,
            },
          ],
        },
      },
    );

    expect(chart.liquidityHeatmap.pressureScore, 82.0);
    expect(chart.liquidityHeatmap.heatmapZones.single.side, 'BUY');
  });

  test('market chart parses orderbook DOM and assistant payloads', () {
    final chart = MarketChartModel.fromJson(
      <String, dynamic>{
        'symbol': 'BTCUSDT',
        'interval': '5m',
        'candles': const <dynamic>[],
        'markers': const <dynamic>[],
        'confidence_intervals': const <dynamic>[],
        'confidence_history': const <dynamic>[],
        'orderbook_depth': <String, dynamic>{
          'sequence_id': 10,
          'pressure_score': 62.0,
          'liquidity_ladder': <Map<String, dynamic>>[
            <String, dynamic>{
              'level': 1,
              'bid_price': 100.0,
              'bid_size': 10.0,
              'ask_price': 100.1,
              'ask_size': 8.0,
              'imbalance': 11.1,
              'intensity': 100.0,
            },
          ],
        },
        'autonomous_assistant': <String, dynamic>{
          'summary': 'BTCUSDT trending',
          'voice_alert': 'Breakout conditions improving.',
          'recommendations': <String>['Wait for confirmation'],
          'replay_safe': true,
        },
        'render_hints': <String, dynamic>{
          'render_profile': <String, dynamic>{
            'mode': 'LOW_POWER',
            'target_fps': 30,
            'pressure': 88.0,
            'max_overlays': 18,
            'max_dom_levels': 8,
            'shader_quality': 'reduced',
            'thermal_safe': true,
          },
        },
      },
    );

    expect(chart.orderbookDepth.sequenceId, 10);
    expect(chart.orderbookDepth.liquidityLadder.single.bidPrice, 100.0);
    expect(chart.autonomousAssistant.voiceAlert, contains('Breakout'));
    expect(chart.renderProfile.mode, 'LOW_POWER');
    expect(chart.renderProfile.maxDomLevels, 8);
  });

  test('infrastructure snapshot parses incident readiness fields', () {
    final snapshot = InfrastructureSnapshotModel.fromJson(
      <String, dynamic>{
        'redis': <String, dynamic>{'fallback': false, 'latency_ms': 4},
        'websocket': <String, dynamic>{
          'sequence_gaps': 1,
          'replay_frequency': 2,
          'stale_feed_count': 0,
        },
        'ai_workers': <String, dynamic>{'queue_depth': 4, 'latency_ms': 22},
        'rendering': <String, dynamic>{'fps': 58, 'overlay_pressure': 12},
        'event_bus': <String, dynamic>{
          'market_throughput': 100,
          'ai_throughput': 20,
        },
        'gpu_inference': <String, dynamic>{
          'queue_depth': 2,
          'latency_ms': 18,
          'runtime': 'onnx_ready',
        },
        'high_availability': <String, dynamic>{'mode': 'NORMAL'},
        'slo': <String, dynamic>{'mode': 'NORMAL', 'score': 99.0},
        'replay_checkpoint': <String, dynamic>{'valid': true},
        'incident': <String, dynamic>{
          'severity': 'P3',
          'status': 'WATCH',
        },
        'retention': <String, dynamic>{'mode': 'STANDARD'},
        'capacity': <String, dynamic>{
          'scale_mode': 'HOLD',
          'websocket_instances': 1,
          'ai_workers': 1,
          'gpu_workers': 0,
        },
        'runbook': <String, dynamic>{
          'steps': <String>['continue normal operations'],
        },
        'release': <String, dynamic>{
          'status': 'READY',
          'blockers': const <dynamic>[],
        },
        'canary': <String, dynamic>{
          'mode': 'STANDARD',
          'traffic_steps': <int>[1, 5, 15, 30],
        },
        'rollback': <String, dynamic>{
          'recommended': false,
          'strategy': 'hold_and_monitor',
        },
        'backup': <String, dynamic>{'status': 'READY'},
        'audit_export': <String, dynamic>{
          'manifest_version': 'ops-audit-v1',
        },
        'config_drift': <String, dynamic>{
          'state': 'IN_POLICY',
          'drift_count': 0,
        },
        'synthetic_probes': <String, dynamic>{
          'mode': 'STANDARD',
          'probes': const <dynamic>[1, 2, 3, 4],
        },
        'disaster_recovery': <String, dynamic>{
          'state': 'READY',
          'drill_required': false,
        },
        'compliance': <String, dynamic>{
          'state': 'COMPLIANT',
          'gaps': const <dynamic>[],
        },
        'readiness': <String, dynamic>{
          'status': 'READY',
          'score': 98.0,
          'actions': <String>['continue normal operations'],
        },
      },
    );

    expect(snapshot.incidentSeverity, 'P3');
    expect(snapshot.retentionMode, 'STANDARD');
    expect(snapshot.recommendedWebsocketInstances, 1);
    expect(snapshot.runbookSteps.single, contains('normal'));
    expect(snapshot.releaseStatus, 'READY');
    expect(snapshot.canarySteps, <int>[1, 5, 15, 30]);
    expect(snapshot.rollbackRecommended, isFalse);
    expect(snapshot.backupStatus, 'READY');
    expect(snapshot.configDriftState, 'IN_POLICY');
    expect(snapshot.syntheticProbeCount, 4);
    expect(snapshot.disasterRecoveryState, 'READY');
    expect(snapshot.complianceState, 'COMPLIANT');
    expect(snapshot.readinessStatus, 'READY');
    expect(snapshot.readinessScore, 98.0);
  });
}

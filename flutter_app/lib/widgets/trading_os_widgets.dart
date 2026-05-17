import 'package:flutter/material.dart';

import '../core/trading_operating_system_engine.dart';
import '../core/trading_palette.dart';
import 'glass_panel.dart';
import 'status_badge.dart';

class PortfolioIntelligencePanel extends StatelessWidget {
  const PortfolioIntelligencePanel({
    super.key,
    required this.read,
  });

  final PortfolioIntelligenceRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Portfolio Intelligence',
      badge: '${read.aiPortfolioHeat.toStringAsFixed(0)} heat',
      color: _riskColor(read.aiPortfolioHeat),
      children: <Widget>[
        _MetricLine(
          label: 'Gross exposure',
          value: read.grossExposurePct,
          color: TradingPalette.electricBlue,
        ),
        _MetricLine(
          label: 'Correlation',
          value: read.correlationExposure,
          color: TradingPalette.amber,
        ),
        _MetricLine(
          label: 'Concentration',
          value: read.concentrationRisk,
          color: TradingPalette.neonRed,
        ),
        const SizedBox(height: 8),
        _Bullet(read.regimeAdaptation),
        _MapRows(title: 'Sector exposure', values: read.sectorExposure),
        _MapRows(title: 'Side exposure', values: read.sideExposure),
      ],
    );
  }
}

class MultiAssetOrchestrationPanel extends StatelessWidget {
  const MultiAssetOrchestrationPanel({
    super.key,
    required this.read,
  });

  final MultiAssetOrchestrationRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Multi-Asset Orchestration',
      badge: read.primaryOpportunity,
      color: TradingPalette.neonGreen,
      children: <Widget>[
        _Bullet(read.exposureDirective),
        const SizedBox(height: 8),
        if (read.globalRank.isEmpty)
          const _Bullet('Global opportunity queue is building.')
        else
          ...read.globalRank.take(5).map(
                (row) => _RankRow(row: row),
              ),
      ],
    );
  }
}

class AiCopilotPanel extends StatelessWidget {
  const AiCopilotPanel({
    super.key,
    required this.read,
  });

  final AiCopilotRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'AI Co-Pilot',
      badge: read.posture,
      color: TradingPalette.electricBlue,
      children: <Widget>[
        Text(
          read.primaryGuidance,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        ...read.messages.skip(1).map(_Bullet.new),
      ],
    );
  }
}

class CloudProfileSyncPanel extends StatelessWidget {
  const CloudProfileSyncPanel({
    super.key,
    required this.read,
  });

  final CloudProfileSyncRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Cloud Profile Sync',
      badge: read.pendingSyncItems == 0
          ? 'READY'
          : '${read.pendingSyncItems} pending',
      color: read.pendingSyncItems == 0
          ? TradingPalette.neonGreen
          : TradingPalette.amber,
      children: <Widget>[
        _CheckRow(label: 'Preferences', ok: read.preferencesReady),
        _CheckRow(label: 'AI memory', ok: read.aiMemoryReady),
        _CheckRow(label: 'Onboarding', ok: read.onboardingReady),
        _CheckRow(label: 'Watchlists', ok: read.watchlistsReady),
        _CheckRow(label: 'Replay history', ok: read.replayHistoryReady),
        _CheckRow(label: 'AI modes', ok: read.aiModesReady),
        const SizedBox(height: 8),
        _Bullet(read.syncNote),
      ],
    );
  }
}

class RealtimeOrchestrationPanel extends StatelessWidget {
  const RealtimeOrchestrationPanel({
    super.key,
    required this.read,
  });

  final RealtimeOrchestrationRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Realtime Orchestration',
      badge: read.signalQueueMode,
      color: TradingPalette.violet,
      children: <Widget>[
        _Bullet(read.loadState),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            _MetricPill(label: 'Batch', value: '${read.batchWindowMs}ms'),
            _MetricPill(label: 'Throttle', value: '${read.updateThrottleMs}ms'),
            _MetricPill(
              label: 'Chart',
              value: '${read.chartRefreshCadenceMs}ms',
            ),
            _MetricPill(
              label: 'Animation',
              value: '${read.animationBudgetMs}ms',
            ),
          ],
        ),
        const SizedBox(height: 10),
        _Bullet('Priority lanes: ${read.priorityLanes.join(' > ')}'),
      ],
    );
  }
}

class ExecutionWorkspacePanel extends StatelessWidget {
  const ExecutionWorkspacePanel({
    super.key,
    required this.read,
  });

  final ExecutionWorkspaceRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Execution Workspace',
      badge: '${read.readinessScore.toStringAsFixed(0)} ready',
      color: _riskColor(100 - read.readinessScore),
      children: <Widget>[
        _MetricLine(
          label: 'Readiness',
          value: read.readinessScore,
          color: _riskColor(100 - read.readinessScore),
        ),
        _Bullet(read.correlatedTradeWarning),
        _Bullet(read.executionSequencing),
        _Bullet(
          'Exposure after trade: ${read.exposureAfterTradePct.toStringAsFixed(1)}%',
        ),
        _Bullet(read.exposureBalancingAction),
        _Bullet(read.positionManagement),
      ],
    );
  }
}

class WatchtowerPanel extends StatelessWidget {
  const WatchtowerPanel({
    super.key,
    required this.read,
  });

  final WatchtowerRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'AI Watchtower',
      badge: read.status,
      color: _riskColor(read.riskPulse),
      children: <Widget>[
        _MetricLine(
          label: 'Risk pulse',
          value: read.riskPulse,
          color: _riskColor(read.riskPulse),
        ),
        const SizedBox(height: 8),
        ...read.alerts.map((alert) => _AlertRow(alert: alert)),
      ],
    );
  }
}

class ProfessionalJournalPanel extends StatelessWidget {
  const ProfessionalJournalPanel({
    super.key,
    required this.read,
  });

  final ProfessionalJournalRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Professional Journal',
      badge: '${read.disciplineScore.toStringAsFixed(0)} discipline',
      color: _riskColor(100 - read.disciplineScore),
      children: <Widget>[
        _Bullet(read.sessionSummary),
        const SizedBox(height: 8),
        ...read.timeline.take(6).map(
              (entry) => _TimelineRow(entry: entry),
            ),
      ],
    );
  }
}

class ScalabilityPosturePanel extends StatelessWidget {
  const ScalabilityPosturePanel({
    super.key,
    required this.read,
  });

  final ScalabilityRead read;

  @override
  Widget build(BuildContext context) {
    return _DeskPanel(
      title: 'Scalability Posture',
      badge: read.lazyRenderingActive ? 'LAZY RENDER' : 'STANDARD',
      color: TradingPalette.electricBlue,
      children: <Widget>[
        _Bullet(read.providerScopeMode),
        _Bullet(read.eventBusMode),
        _Bullet('Chart cadence: ${read.chartUpdateCadence}'),
        _Bullet(read.rebuildScope),
        _Bullet(read.memoryPosture),
      ],
    );
  }
}

class _DeskPanel extends StatelessWidget {
  const _DeskPanel({
    required this.title,
    required this.badge,
    required this.color,
    required this.children,
  });

  final String title;
  final String badge;
  final Color color;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      glowColor: color,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              StatusBadge(label: badge, color: color),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }
}

class _RankRow extends StatelessWidget {
  const _RankRow({required this.row});

  final AssetOrchestrationRow row;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(row.symbol,
                    style: const TextStyle(fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text(
                  '${row.assetGroup} | ${row.reason}',
                  style: const TextStyle(color: TradingPalette.textMuted),
                ),
              ],
            ),
          ),
          StatusBadge(
            label: row.rankScore.toStringAsFixed(0),
            color: row.correlationSuppressed
                ? TradingPalette.amber
                : TradingPalette.neonGreen,
          ),
        ],
      ),
    );
  }
}

class _AlertRow extends StatelessWidget {
  const _AlertRow({required this.alert});

  final WatchtowerAlert alert;

  @override
  Widget build(BuildContext context) {
    final color = switch (alert.severity) {
      WatchtowerSeverity.critical => TradingPalette.neonRed,
      WatchtowerSeverity.warning => TradingPalette.amber,
      WatchtowerSeverity.info => TradingPalette.electricBlue,
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(Icons.radar_rounded, color: color, size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(alert.title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(
                  alert.detail,
                  style: const TextStyle(color: TradingPalette.textMuted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  const _TimelineRow({required this.entry});

  final JournalTimelineEntry entry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          StatusBadge(label: entry.category, color: TradingPalette.violet),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(entry.title,
                    style: const TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(
                  entry.detail,
                  style: const TextStyle(color: TradingPalette.textMuted),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricLine extends StatelessWidget {
  const _MetricLine({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: <Widget>[
          SizedBox(width: 128, child: Text(label)),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: (value / 100).clamp(0.0, 1.0),
                minHeight: 7,
                backgroundColor: TradingPalette.overlay,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
          ),
          const SizedBox(width: 10),
          SizedBox(
            width: 42,
            child: Text(
              value.toStringAsFixed(0),
              textAlign: TextAlign.right,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 86),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: TradingPalette.overlay,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: TradingPalette.panelBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 3),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w900)),
        ],
      ),
    );
  }
}

class _CheckRow extends StatelessWidget {
  const _CheckRow({required this.label, required this.ok});

  final String label;
  final bool ok;

  @override
  Widget build(BuildContext context) {
    return _Bullet('${ok ? 'Ready' : 'Pending'}: $label');
  }
}

class _MapRows extends StatelessWidget {
  const _MapRows({required this.title, required this.values});

  final String title;
  final Map<String, double> values;

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) {
      return _Bullet('$title: no active exposure');
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 6),
          ...values.entries.take(4).map(
                (entry) =>
                    _Bullet('${entry.key}: ${entry.value.toStringAsFixed(1)}%'),
              ),
        ],
      ),
    );
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.text);

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 6,
            height: 6,
            margin: const EdgeInsets.only(top: 7),
            decoration: const BoxDecoration(
              color: TradingPalette.electricBlue,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: TradingPalette.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

Color _riskColor(double value) {
  if (value >= 72) {
    return TradingPalette.neonRed;
  }
  if (value >= 48) {
    return TradingPalette.amber;
  }
  return TradingPalette.neonGreen;
}

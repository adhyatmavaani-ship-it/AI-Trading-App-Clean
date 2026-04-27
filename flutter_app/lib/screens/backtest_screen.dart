import 'dart:async';
import 'dart:io';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/pnl/providers/pnl_providers.dart';
import '../models/backtest_job.dart';
import '../providers/app_providers.dart';
import '../widgets/metric_card.dart';
import '../widgets/section_card.dart';
import '../widgets/state_widgets.dart';

class BacktestScreen extends ConsumerStatefulWidget {
  const BacktestScreen({super.key});

  @override
  ConsumerState<BacktestScreen> createState() => _BacktestScreenState();
}

class _BacktestScreenState extends ConsumerState<BacktestScreen> {
  String _symbol = 'BTCUSDT';
  int _days = 7;
  String _strategy = 'ensemble';
  bool _compareMode = false;
  String? _jobId;
  BacktestJobStatusModel? _status;
  bool _submitting = false;
  bool _exporting = false;
  Timer? _pollTimer;

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final userId = ref.watch(activeUserIdProvider);
    return ListView(
      padding: const EdgeInsets.all(20),
      children: <Widget>[
        SectionCard(
          title: 'Backtest Setup',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              DropdownButtonFormField<String>(
                value: _symbol,
                decoration: const InputDecoration(labelText: 'Symbol'),
                items: const <DropdownMenuItem<String>>[
                  DropdownMenuItem<String>(
                    value: 'BTCUSDT',
                    child: Text('BTCUSDT'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'ETHUSDT',
                    child: Text('ETHUSDT'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'SOLUSDT',
                    child: Text('SOLUSDT'),
                  ),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _symbol = value;
                  });
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: _strategy,
                decoration: const InputDecoration(labelText: 'Strategy'),
                items: const <DropdownMenuItem<String>>[
                  DropdownMenuItem<String>(
                    value: 'ensemble',
                    child: Text('Ensemble'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'hybrid_crypto',
                    child: Text('Hybrid Crypto'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'ema_crossover',
                    child: Text('EMA Crossover'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'rsi',
                    child: Text('RSI'),
                  ),
                  DropdownMenuItem<String>(
                    value: 'breakout',
                    child: Text('Breakout'),
                  ),
                ],
                onChanged: (value) {
                  if (value == null) {
                    return;
                  }
                  setState(() {
                    _strategy = value;
                  });
                },
              ),
              const SizedBox(height: 16),
              Text('Lookback: $_days day(s)'),
              Slider(
                value: _days.toDouble(),
                min: 7,
                max: 30,
                divisions: 23,
                label: '$_days d',
                onChanged: (value) {
                  setState(() {
                    _days = value.round();
                  });
                },
              ),
              const SizedBox(height: 12),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Compare Low vs High Risk'),
                subtitle: const Text(
                  'Runs both profiles sequentially on the same historical data and overlays both equity curves.',
                ),
                value: _compareMode,
                onChanged: (value) {
                  setState(() {
                    _compareMode = value;
                  });
                },
              ),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: _submitting
                    ? null
                    : () => _startBacktest(userId),
                icon: const Icon(Icons.science_outlined),
                label: Text(_submitting ? 'Starting...' : 'Run Backtest'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        if (_status == null)
          const SectionCard(
            title: 'Backtest Status',
            child: EmptyState(
              title: 'No active backtest',
              subtitle:
                  'Run a historical replay to see progress, live logs, and the final equity curve.',
            ),
          )
        else ...<Widget>[
          SectionCard(
            title: 'Backtest Status',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: <Widget>[
                    MetricCard(
                      label: 'Progress',
                      value: '${_status!.progressPct.toStringAsFixed(0)}%',
                      icon: Icons.sync,
                    ),
                    MetricCard(
                      label: 'Trades',
                      value: _status!.tradesFound.toString(),
                      icon: Icons.swap_horiz,
                    ),
                    MetricCard(
                      label: 'Net PnL',
                      value: _status!.netProfit.toStringAsFixed(2),
                      icon: Icons.account_balance_wallet_outlined,
                    ),
                    if (_status!.comparisonProfiles.isNotEmpty)
                      MetricCard(
                        label: 'Profiles',
                        value: _status!.comparisonProfiles.length.toString(),
                        icon: Icons.compare_arrows_rounded,
                      ),
                  ],
                ),
                const SizedBox(height: 16),
                ClipRRect(
                  borderRadius: BorderRadius.circular(999),
                  child: LinearProgressIndicator(
                    value: (_status!.progressPct / 100).clamp(0, 1),
                    minHeight: 12,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Stage: ${_status!.currentStage.replaceAll('_', ' ')}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                if ((_status!.error ?? '').isNotEmpty) ...<Widget>[
                  const SizedBox(height: 8),
                  Text(
                    _status!.error!,
                    style: const TextStyle(color: Color(0xFFFF8E72)),
                  ),
                ],
                if (_status!.isTerminal) ...<Widget>[
                  const SizedBox(height: 16),
                  OutlinedButton.icon(
                    onPressed: _exporting ? null : _exportCsv,
                    icon: const Icon(Icons.download_rounded),
                    label: Text(_exporting ? 'Saving CSV...' : 'Download CSV'),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 20),
          SectionCard(
            title: 'Live Logs',
            child: SizedBox(
              height: 220,
              child: ListView.separated(
                itemCount: _status!.logs.length,
                separatorBuilder: (_, __) => const Divider(height: 16),
                itemBuilder: (context, index) {
                  final log = _status!.logs[_status!.logs.length - 1 - index];
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        log.message,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        log.timestamp.toLocal().toString(),
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    ],
                  );
                },
              ),
            ),
          ),
          const SizedBox(height: 20),
          if (_status!.comparisonProfiles.isNotEmpty)
            _ComparisonBacktestReport(
              profiles: _status!.comparisonProfiles,
            )
          else if (_status!.result != null)
            _CompletedBacktestReport(result: _status!.result!),
        ],
      ],
    );
  }

  Future<void> _startBacktest(String userId) async {
    setState(() {
      _submitting = true;
    });
    try {
      final repository = ref.read(tradingRepositoryProvider);
      final response = _compareMode
          ? await repository.compareBacktest(
              BacktestCompareRequestModel(
                symbol: _symbol,
                days: _days,
                strategy: _strategy,
                profiles: const <String>['low', 'high'],
              ),
            )
          : await repository.runBacktest(
              BacktestRunRequestModel(
                symbol: _symbol,
                days: _days,
                strategy: _strategy,
              ),
            );
      _pollTimer?.cancel();
      setState(() {
        _jobId = response.jobId;
        _status = response;
      });
      _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
        _pollStatus();
      });
      await _pollStatus();
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Backtest start failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _submitting = false;
        });
      }
    }
  }

  Future<void> _pollStatus() async {
    final jobId = _jobId;
    if (jobId == null || jobId.trim().isEmpty) {
      return;
    }
    try {
      final repository = ref.read(tradingRepositoryProvider);
      final nextStatus = await repository.fetchBacktestStatus(jobId);
      if (!mounted) {
        return;
      }
      setState(() {
        _status = nextStatus;
      });
      if (nextStatus.isTerminal) {
        _pollTimer?.cancel();
      }
    } catch (_) {
      _pollTimer?.cancel();
    }
  }

  Future<void> _exportCsv() async {
    final jobId = _jobId;
    if (jobId == null || jobId.trim().isEmpty) {
      return;
    }
    setState(() {
      _exporting = true;
    });
    try {
      final repository = ref.read(tradingRepositoryProvider);
      final csv = await repository.exportBacktestCsv(jobId);
      final file = await _writeExportFile(jobId, csv);
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('CSV saved to ${file.path}')),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('CSV export failed: $error')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _exporting = false;
        });
      }
    }
  }

  Future<File> _writeExportFile(String jobId, String csv) async {
    final userProfile = Platform.environment['USERPROFILE'];
    Directory outputDir;
    if (userProfile != null && userProfile.trim().isNotEmpty) {
      outputDir = Directory('$userProfile\\Downloads');
      if (!outputDir.existsSync()) {
        outputDir = Directory.systemTemp;
      }
    } else {
      outputDir = Directory.systemTemp;
    }
    final file = File('${outputDir.path}\\backtest_$jobId.csv');
    await file.writeAsString(csv, flush: true);
    return file;
  }
}

class _CompletedBacktestReport extends StatelessWidget {
  const _CompletedBacktestReport({required this.result});

  final BacktestJobResultModel result;

  @override
  Widget build(BuildContext context) {
    final summary = result.summary;
    final spots = result.equityCurve
        .map((point) => FlSpot(point.step.toDouble(), point.equity))
        .toList();
    final positive = summary.totalProfit >= 0;
    final curveColor =
        positive ? const Color(0xFF66E0B4) : const Color(0xFFFF8E72);
    return SectionCard(
      title: 'Final Report',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              MetricCard(
                label: 'ROI',
                value: '${summary.roiPct.toStringAsFixed(2)}%',
                icon: Icons.show_chart,
              ),
              MetricCard(
                label: 'Win Rate',
                value: '${(summary.winRate * 100).toStringAsFixed(1)}%',
                icon: Icons.verified_outlined,
              ),
              MetricCard(
                label: 'Max DD',
                value: '${(summary.maxDrawdown * 100).toStringAsFixed(2)}%',
                icon: Icons.shield_outlined,
              ),
              MetricCard(
                label: 'Trades',
                value: summary.totalTrades.toString(),
                icon: Icons.receipt_long_outlined,
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 260,
            child: LineChart(
              LineChartData(
                gridData: const FlGridData(show: false),
                titlesData: const FlTitlesData(show: false),
                borderData: FlBorderData(show: false),
                lineBarsData: <LineChartBarData>[
                  LineChartBarData(
                    isCurved: true,
                    barWidth: 3,
                    color: curveColor,
                    dotData: const FlDotData(show: false),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        colors: <Color>[
                          // ignore: deprecated_member_use
                          curveColor.withOpacity(0.25),
                          Colors.transparent,
                        ],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                    spots: spots,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Final equity ${summary.finalEquity.toStringAsFixed(2)} | Profit factor ${summary.profitFactor.toStringAsFixed(2)}',
          ),
        ],
      ),
    );
  }
}

class _ComparisonBacktestReport extends StatelessWidget {
  const _ComparisonBacktestReport({required this.profiles});

  final List<BacktestComparisonProfileResultModel> profiles;

  @override
  Widget build(BuildContext context) {
    final low = profiles.cast<BacktestComparisonProfileResultModel?>().firstWhere(
          (profile) => profile?.riskProfile == 'low',
          orElse: () => null,
        );
    final high = profiles.cast<BacktestComparisonProfileResultModel?>().firstWhere(
          (profile) => profile?.riskProfile == 'high',
          orElse: () => null,
        );
    final chartBars = <LineChartBarData>[];
    final allSpots = <FlSpot>[];
    if (low != null) {
      final spots = low.equityCurve
          .map((point) => FlSpot(point.step.toDouble(), point.equity))
          .toList();
      allSpots.addAll(spots);
      chartBars.add(
        LineChartBarData(
          isCurved: true,
          barWidth: 3,
          color: const Color(0xFF5AA9FF),
          dotData: const FlDotData(show: false),
          spots: spots,
        ),
      );
    }
    if (high != null) {
      final spots = high.equityCurve
          .map((point) => FlSpot(point.step.toDouble(), point.equity))
          .toList();
      allSpots.addAll(spots);
      chartBars.add(
        LineChartBarData(
          isCurved: true,
          barWidth: 3,
          color: const Color(0xFFFFA94D),
          dotData: const FlDotData(show: false),
          spots: spots,
        ),
      );
    }
    final minY = allSpots.isEmpty
        ? 0.0
        : allSpots.map((spot) => spot.y).reduce((a, b) => a < b ? a : b);
    final maxY = allSpots.isEmpty
        ? 1.0
        : allSpots.map((spot) => spot.y).reduce((a, b) => a > b ? a : b);
    return SectionCard(
      title: 'Comparison Report',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: <Widget>[
              _ProfileComparisonCard(
                label: 'Low Risk',
                color: const Color(0xFF5AA9FF),
                profile: low,
              ),
              _ProfileComparisonCard(
                label: 'High Risk',
                color: const Color(0xFFFFA94D),
                profile: high,
              ),
            ],
          ),
          const SizedBox(height: 20),
          SizedBox(
            height: 280,
            child: LineChart(
              LineChartData(
                minY: minY == maxY ? minY - 1 : minY * 0.999,
                maxY: minY == maxY ? maxY + 1 : maxY * 1.001,
                gridData: const FlGridData(show: false),
                titlesData: const FlTitlesData(show: false),
                borderData: FlBorderData(show: false),
                lineBarsData: chartBars,
              ),
            ),
          ),
          const SizedBox(height: 16),
          _ComparisonTable(low: low, high: high),
        ],
      ),
    );
  }
}

class _ProfileComparisonCard extends StatelessWidget {
  const _ProfileComparisonCard({
    required this.label,
    required this.color,
    required this.profile,
  });

  final String label;
  final Color color;
  final BacktestComparisonProfileResultModel? profile;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 220,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF10242C),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: color.withOpacity(0.6)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Icon(Icons.show_chart, color: color, size: 18),
              const SizedBox(width: 8),
              Text(label, style: Theme.of(context).textTheme.titleSmall),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            profile == null
                ? 'No result'
                : 'ROI ${profile!.summary.roiPct.toStringAsFixed(2)}% | Win ${(profile!.summary.winRate * 100).toStringAsFixed(1)}%',
          ),
          const SizedBox(height: 4),
          Text(
            profile == null
                ? ''
                : 'Drawdown ${(profile!.summary.maxDrawdown * 100).toStringAsFixed(2)}% | Trades ${profile!.summary.totalTrades}',
          ),
        ],
      ),
    );
  }
}

class _ComparisonTable extends StatelessWidget {
  const _ComparisonTable({
    required this.low,
    required this.high,
  });

  final BacktestComparisonProfileResultModel? low;
  final BacktestComparisonProfileResultModel? high;

  @override
  Widget build(BuildContext context) {
    return Table(
      columnWidths: const <int, TableColumnWidth>{
        0: FlexColumnWidth(1.4),
        1: FlexColumnWidth(1),
        2: FlexColumnWidth(1),
      },
      children: <TableRow>[
        _row(context, 'Metric', 'Low', 'High', header: true),
        _row(
          context,
          'ROI',
          low == null ? '-' : '${low!.summary.roiPct.toStringAsFixed(2)}%',
          high == null ? '-' : '${high!.summary.roiPct.toStringAsFixed(2)}%',
        ),
        _row(
          context,
          'Win Rate',
          low == null ? '-' : '${(low!.summary.winRate * 100).toStringAsFixed(1)}%',
          high == null ? '-' : '${(high!.summary.winRate * 100).toStringAsFixed(1)}%',
        ),
        _row(
          context,
          'Drawdown',
          low == null ? '-' : '${(low!.summary.maxDrawdown * 100).toStringAsFixed(2)}%',
          high == null ? '-' : '${(high!.summary.maxDrawdown * 100).toStringAsFixed(2)}%',
        ),
        _row(
          context,
          'Trades',
          low == null ? '-' : '${low!.summary.totalTrades}',
          high == null ? '-' : '${high!.summary.totalTrades}',
        ),
      ],
    );
  }

  TableRow _row(
    BuildContext context,
    String metric,
    String lowValue,
    String highValue, {
    bool header = false,
  }) {
    final style = header
        ? Theme.of(context)
            .textTheme
            .titleSmall
        : Theme.of(context).textTheme.bodyMedium;
    return TableRow(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Text(metric, style: style),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Text(lowValue, style: style),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Text(highValue, style: style),
        ),
      ],
    );
  }
}

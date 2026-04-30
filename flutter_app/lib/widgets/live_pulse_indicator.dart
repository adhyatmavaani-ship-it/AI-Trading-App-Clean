import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/trading_palette.dart';
import '../core/websocket_service.dart';
import '../providers/app_providers.dart';

class LivePulseIndicator extends ConsumerStatefulWidget {
  const LivePulseIndicator({
    super.key,
    this.label = 'LIVE',
    this.color = TradingPalette.neonGreen,
    this.allowRetry = true,
  });

  final String label;
  final Color color;
  final bool allowRetry;

  @override
  ConsumerState<LivePulseIndicator> createState() =>
      _LivePulseIndicatorState();
}

class _LivePulseIndicatorState extends ConsumerState<LivePulseIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1300),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final socketService = ref.read(webSocketServiceProvider);
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return ValueListenableBuilder<WsState>(
          valueListenable: socketService.stateListenable,
          builder: (context, wsState, _) {
            final indicator = _resolveState(wsState);
            final glow = indicator.animate
                ? 0.18 + (math.sin(_controller.value * math.pi) * 0.18)
                : 0.08;
            return InkWell(
              borderRadius: BorderRadius.circular(999),
              onTap: widget.allowRetry &&
                      (wsState == WsState.degraded ||
                          wsState == WsState.disconnected)
                  ? socketService.reconnectNow
                  : null,
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: indicator.color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: indicator.color.withOpacity(0.28)),
                  boxShadow: <BoxShadow>[
                    BoxShadow(
                      color: indicator.color.withOpacity(glow),
                      blurRadius: 16,
                      spreadRadius: -8,
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: indicator.color,
                        shape: BoxShape.circle,
                        boxShadow: <BoxShadow>[
                          BoxShadow(
                            color: indicator.color.withOpacity(0.45),
                            blurRadius: 10,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      indicator.label,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: indicator.color,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.4,
                          ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  _WsIndicatorState _resolveState(WsState state) {
    switch (state) {
      case WsState.connecting:
        return const _WsIndicatorState(
          label: 'CONNECTING',
          color: TradingPalette.amber,
          animate: true,
        );
      case WsState.connected:
        return _WsIndicatorState(
          label: widget.label,
          color: widget.color,
          animate: true,
        );
      case WsState.degraded:
        return const _WsIndicatorState(
          label: 'RECONNECTING',
          color: TradingPalette.amber,
          animate: true,
        );
      case WsState.disconnected:
        return const _WsIndicatorState(
          label: 'DISCONNECTED',
          color: TradingPalette.neonRed,
          animate: false,
        );
    }
  }
}

class _WsIndicatorState {
  const _WsIndicatorState({
    required this.label,
    required this.color,
    required this.animate,
  });

  final String label;
  final Color color;
  final bool animate;
}

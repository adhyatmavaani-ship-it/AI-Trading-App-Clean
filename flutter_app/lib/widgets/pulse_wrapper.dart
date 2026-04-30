import 'package:flutter/material.dart';

class PulseWrapper extends StatefulWidget {
  final Widget child;
  const PulseWrapper({super.key, required this.child});

  @override
  State<PulseWrapper> createState() => _PulseWrapperState();
}

class _PulseWrapperState extends State<PulseWrapper>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: Tween<double>(begin: 0.7, end: 1.0).animate(_controller),
      child: widget.child,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}

import 'package:flutter/foundation.dart';

enum BackendWarmupState {
  idle,
  connecting,
  waking,
  retrying,
  slow,
  ready,
}

final ValueNotifier<BackendWarmupState> backendWarmupState =
    ValueNotifier<BackendWarmupState>(BackendWarmupState.idle);

void markBackendWaking() {
  backendWarmupState.value = BackendWarmupState.waking;
}

void markBackendConnecting() {
  backendWarmupState.value = BackendWarmupState.connecting;
}

void markBackendSlow() {
  backendWarmupState.value = BackendWarmupState.slow;
}

void markBackendRetrying() {
  backendWarmupState.value = BackendWarmupState.retrying;
}

void markBackendReady() {
  backendWarmupState.value = BackendWarmupState.ready;
}

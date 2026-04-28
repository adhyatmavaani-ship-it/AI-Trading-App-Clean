import 'package:flutter/foundation.dart';

enum BackendWarmupState {
  idle,
  waking,
  ready,
}

final ValueNotifier<BackendWarmupState> backendWarmupState =
    ValueNotifier<BackendWarmupState>(BackendWarmupState.idle);

void markBackendWaking() {
  backendWarmupState.value = BackendWarmupState.waking;
}

void markBackendReady() {
  backendWarmupState.value = BackendWarmupState.ready;
}

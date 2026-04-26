#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

echo "[beta-preflight] backend compile"
cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m compileall app tests scripts

echo "[beta-preflight] backend tests"
"$PYTHON_BIN" -m unittest discover -s tests -v

echo "[beta-preflight] app boot smoke"
"$PYTHON_BIN" -m unittest tests.test_app_boot -v

echo "[beta-preflight] process + websocket smoke"
"$PYTHON_BIN" scripts/process_smoke_check.py --token "${BETA_SMOKE_TOKEN:-beta-preflight-token}"

echo "[beta-preflight] flutter analyze"
cd "$ROOT_DIR/flutter_app"
flutter analyze

echo "[beta-preflight] cloud functions tests"
cd "$ROOT_DIR/cloud_functions"
npm test

echo "[beta-preflight] complete"

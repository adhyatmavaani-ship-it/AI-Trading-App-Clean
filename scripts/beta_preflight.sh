#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

echo "[beta-preflight] backend compile"
cd "$ROOT_DIR"
"$PYTHON_BIN" -m compileall backend/app backend/tests backend/scripts

echo "[beta-preflight] backend tests"
"$PYTHON_BIN" -m unittest discover -s backend/tests -v

echo "[beta-preflight] app boot smoke"
"$PYTHON_BIN" -m unittest discover -s backend/tests -p test_app_boot.py -v

echo "[beta-preflight] process + websocket smoke"
"$PYTHON_BIN" backend/scripts/process_smoke_check.py --token "${BETA_SMOKE_TOKEN:-beta-preflight-token}"

echo "[beta-preflight] flutter analyze"
cd "$ROOT_DIR/flutter_app"
flutter analyze

echo "[beta-preflight] cloud functions tests"
cd "$ROOT_DIR/cloud_functions"
npm test

echo "[beta-preflight] complete"

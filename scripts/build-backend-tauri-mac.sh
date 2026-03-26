#!/usr/bin/env bash
set -euo pipefail

# Build the PyInstaller backend executable for the current host and copy it into
# the Tauri sidecar binaries directory using Tauri's `externalBin` naming rules:
#   src-tauri/binaries/backend-$TARGET_TRIPLE
#
# Note: We intentionally do not commit binaries; they are generated artifacts.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT_DIR"

echo "[1/3] Build backend via existing Electron script..."
bash electron/build-backend.sh

echo "[2/3] Copy backend into Tauri binaries..."
TRIPLE="$(rustc --print host-tuple)"
mkdir -p src-tauri/binaries
cp -f electron/backend/backend "src-tauri/binaries/backend-$TRIPLE"

echo "[3/3] Done"
echo "Sidecar: src-tauri/binaries/backend-$TRIPLE"


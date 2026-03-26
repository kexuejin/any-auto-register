param(
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

# Build the PyInstaller backend executable on Windows and copy it into the
# Tauri sidecar binaries directory using Tauri's `externalBin` naming rules:
#   src-tauri/binaries/backend-$TARGET_TRIPLE.exe
#
# This is designed to run on a Windows runner (CI) where Rust is installed.

Write-Host "[1/3] Build backend (PyInstaller)..."

# Reuse the repo's requirements / backend.spec generation from electron script logic,
# but on Windows we run it directly instead of bash.
& $Python -m venv "electron\.backend-build-venv"
& "electron\.backend-build-venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& "electron\.backend-build-venv\Scripts\python.exe" -m pip install -r requirements.txt
& "electron\.backend-build-venv\Scripts\python.exe" -m pip install pyinstaller

& "electron\.backend-build-venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --name backend `
  --hidden-import=cbor2 `
  --hidden-import=_cbor2 `
  --add-data "platforms;platforms" `
  --add-data "core;core" `
  --add-data "api;api" `
  --add-data "services;services" `
  --add-data "static;static" `
  main.py

Write-Host "[2/3] Copy backend into Tauri binaries..."
$triple = (& rustc --print host-tuple).Trim()
New-Item -ItemType Directory -Force -Path "src-tauri\binaries" | Out-Null
Copy-Item -Force "dist\backend.exe" "src-tauri\binaries\backend-$triple.exe"

Write-Host "[3/3] Done"
Write-Host "Sidecar: src-tauri\binaries\backend-$triple.exe"


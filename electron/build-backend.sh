#!/bin/bash
# 将 Python 后端打包为单文件可执行程序，输出到 electron/backend/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../"

PYTHON_BIN="${PYTHON_BIN:-python3}"
BACKEND_BUILD_VENV="${BACKEND_BUILD_VENV:-$SCRIPT_DIR/.backend-build-venv}"

cd "$BACKEND_DIR"

echo "[1/5] 准备打包虚拟环境: $BACKEND_BUILD_VENV"
"$PYTHON_BIN" -m venv "$BACKEND_BUILD_VENV"
source "$BACKEND_BUILD_VENV/bin/activate"
python -m pip install --quiet --upgrade pip setuptools wheel

echo "[2/5] 安装后端依赖 (requirements.txt)..."
python -m pip install --quiet -r requirements.txt

echo "[3/5] 安装 PyInstaller..."
python -m pip install --quiet pyinstaller

echo "[4/5] 打包后端..."
pyinstaller --noconfirm --clean --onefile --name backend \
  --hidden-import=cbor2 \
  --hidden-import=_cbor2 \
  --add-data "platforms:platforms" \
  --add-data "core:core" \
  --add-data "api:api" \
  --add-data "services:services" \
  --add-data "static:static" \
  main.py

echo "[5/5] 复制产物到 electron/backend/"
mkdir -p "$SCRIPT_DIR/backend"
cp dist/backend* "$SCRIPT_DIR/backend/"

echo "完成! 可执行文件: $SCRIPT_DIR/backend/backend"

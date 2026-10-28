#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
APP_ROOT="$PWD"
ACTION="${1:-update}"
if [ "$#" -gt 0 ]; then shift; fi
case "$ACTION" in setup|update|recalculate|excel-button|excel-update|excel-recalculate) ;; *) echo "Unknown action"; exit 2;; esac
if [ "$ACTION" != setup ]; then
  if [ ! -x "$APP_ROOT/.venv/bin/python" ]; then
    echo "Run 1_Setup once before using this workbook. No automatic installation was attempted."
    exit 1
  fi
  exec "$APP_ROOT/.venv/bin/python" "$APP_ROOT/local_runner.py" "$ACTION" "$@"
fi
export UV_CACHE_DIR="$APP_ROOT/.runtime/cache"
export UV_PYTHON_INSTALL_DIR="$APP_ROOT/.runtime/python"
export UV_PYTHON_BIN_DIR="$APP_ROOT/.runtime/bin"
export UV_PROJECT_ENVIRONMENT="$APP_ROOT/.venv"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
UV_APP="$APP_ROOT/.tools/uv"
if [ ! -x "$UV_APP" ]; then
  mkdir -p "$APP_ROOT/.tools"
  echo "Preparing the local Python installer (internet required)..."
  curl --fail --location --silent --show-error --retry 2 \
    https://astral.sh/uv/0.13.6/install.sh -o "$APP_ROOT/.tools/install-uv.sh"
  UV_UNMANAGED_INSTALL="$APP_ROOT/.tools" sh "$APP_ROOT/.tools/install-uv.sh"
fi
if [ "$ACTION" = setup ] || [ ! -x "$APP_ROOT/.venv/bin/python" ]; then
  echo "Preparing Python and dependencies in this folder..."
  "$UV_APP" sync --frozen --no-dev --no-install-project --python 3.12 --managed-python
fi
"$APP_ROOT/.venv/bin/python" "$APP_ROOT/local_runner.py" "$ACTION" "$@"

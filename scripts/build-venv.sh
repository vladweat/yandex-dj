#!/usr/bin/env bash
# Production venv на хосте (Python 3.12 = базовый образ Docker).
# Результат: backend/.venv → site-packages копируется в образ.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/../backend"

PYTHON="${PYTHON:-python3.12}"

if ! command -v "$PYTHON" &>/dev/null; then
  echo "ERROR: $PYTHON not found. Install Python 3.12 (must match Docker base image)."
  exit 1
fi

PY_MINOR=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PY_MINOR" != "3.12" ]; then
  echo "ERROR: need Python 3.12, got $PY_MINOR"
  echo "Set PYTHON=python3.12 if installed under another name."
  exit 1
fi

if [ -n "${VIRTUAL_ENV:-}" ]; then
  echo "Note: ignoring active VIRTUAL_ENV=$VIRTUAL_ENV"
  unset VIRTUAL_ENV
fi

EXTRAS="${EXTRAS:-ml}"

echo "==> Creating venv with $PYTHON ..."
rm -rf .venv
"$PYTHON" -m venv .venv

VENV_PY="$(pwd)/.venv/bin/python"
"$VENV_PY" -m pip install -U pip "setuptools>=77.0.3"

if [[ -n "${EXTRAS}" && "${EXTRAS}" == *"ml"* ]]; then
  echo "==> Installing torch (CPU-only, no CUDA) ..."
  "$VENV_PY" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
fi

echo "==> Installing project ..."
if [[ -n "${EXTRAS}" ]]; then
  "$VENV_PY" -m pip install ".[${EXTRAS}]"
else
  "$VENV_PY" -m pip install .
fi

mkdir -p .libs .models
if [ ! -f .libs/libgomp.so.1 ]; then
  for src in /lib/x86_64-linux-gnu/libgomp.so.1 /usr/lib/x86_64-linux-gnu/libgomp.so.1; do
    if [ -e "${src}" ]; then
      cp -L "${src}" .libs/libgomp.so.1
      echo "Copied libgomp.so.1 into .libs"
      break
    fi
  done
  if [ ! -f .libs/libgomp.so.1 ]; then
    echo "WARN: libgomp.so.1 not found on host; torch may fail in Docker slim"
  fi
fi

echo "==> Embedding model ..."
"$VENV_PY" scripts/prepare_embeddings.py

rm -rf build prompt_dj.egg-info .cache

"${SCRIPT_DIR}/verify-venv.sh"

echo ""
echo "Done. Next: make build && make up"

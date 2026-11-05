#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"
PYTHON="${PYTHON:-python3.12}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON not found. Install Python 3.12." >&2
  exit 1
fi

PYTHON_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PYTHON_VERSION" != "3.12" ]; then
  echo "ERROR: backend tests use Python 3.12; got $PYTHON_VERSION from $PYTHON" >&2
  exit 1
fi

VENV_DIR="${BACKEND_DIR}/.venv-test"
if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo "==> Creating test environment in backend/.venv-test"
  "$PYTHON" -m venv "$VENV_DIR"
fi

cd "$BACKEND_DIR"
"${VENV_DIR}/bin/python" -m pip install -e '.[dev]'

# Unit tests use local dummy endpoints and never require live service credentials.
export TOKEN_ENCRYPTION_KEY=$("${VENV_DIR}/bin/python" -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
export DATABASE_URL="postgresql+asyncpg://prompt_dj:prompt_dj@localhost:5432/prompt_dj_test"
export REDIS_URL="redis://localhost:6379/15"
unset OPENAI_API_KEY TG_BOT_TOKEN METRICS_TOKEN

"${VENV_DIR}/bin/ruff" check app tests
"${VENV_DIR}/bin/python" -m pytest tests/ -q

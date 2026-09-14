#!/usr/bin/env bash
# Упаковка артефактов для переноса на offline-машину.
#
#   make venv
#   make pack
#
# Результат: dist/prompt-dj-offline-YYYYMMDD.tar.gz
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
OUT_DIR="${ROOT_DIR}/dist"
STAMP="$(date +%Y%m%d)"
ARCHIVE="${OUT_DIR}/prompt-dj-offline-${STAMP}.tar.gz"

if [[ ! -d "${BACKEND_DIR}/.venv/lib" ]]; then
  echo "error: сначала запустите make venv" >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

echo "==> Упаковка в ${ARCHIVE}"

tar -czf "${ARCHIVE}" \
  -C "${ROOT_DIR}" \
  backend/.venv/lib \
  backend/.libs \
  backend/.models \
  backend/app \
  backend/alembic \
  backend/alembic.ini \
  backend/Dockerfile \
  backend/.dockerignore \
  backend/pyproject.toml \
  backend/scripts/prepare_embeddings.py \
  docker-compose.yml \
  Makefile \
  scripts/build-venv.sh \
  scripts/pack-offline-bundle.sh

echo "==> Готово: ${ARCHIVE}"
du -sh "${ARCHIVE}"

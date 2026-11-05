#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js 20+."
  exit 1
fi

# Offline Docker (node:20-alpine): node_modules копируется с хоста, сеть в образе отключена.
#
# Проблема: npm 10 на glibc-хосте отклоняет musl-пакеты, если они указаны как
# обязательные зависимости.
#
# Решение:
#   1. gnu — dependencies (хост glibc: dev, typecheck, tsc)
#   2. musl — optionalDependencies (plain npm install на glibc не падает, musl пропускается)
#   3. musl — force-install ниже (попадают в node_modules для offline-сборки в Alpine)
#
# Не запускайте голый npm install для Docker — только make deps-frontend.
echo "Installing frontend dependencies (glibc)..."
npm install --omit=optional --no-audit --no-fund --verbose

MUSL_PKGS=(
  "@next/swc-linux-x64-musl@15.5.25"
  "@rollup/rollup-linux-x64-musl@4.63.1"
  "@tailwindcss/oxide-linux-x64-musl@4.3.3"
  "lightningcss-linux-x64-musl@1.32.0"
  "@esbuild/linux-x64-musl@0.28.2"
)
echo "Installing musl binaries for Alpine Docker (force, no-save)..."
for pkg in "${MUSL_PKGS[@]}"; do
  npm install --no-save --force --no-audit --no-fund "$pkg"
done

mkdir -p public

echo ""
echo "OK: frontend/node_modules ready"
echo "Next (offline): make up-frontend"

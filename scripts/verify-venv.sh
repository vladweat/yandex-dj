#!/usr/bin/env bash
# Проверка venv после установки — падает при любой проблеме.
set -euo pipefail

cd "$(dirname "$0")/../backend"

VENV_PY="$(pwd)/.venv/bin/python"
MODEL_DIR=".models/intfloat--multilingual-e5-base"

if [[ ! -x "${VENV_PY}" ]]; then
  echo "ERROR: ${VENV_PY} not found" >&2
  exit 1
fi

echo "==> Verifying packages ..."
"${VENV_PY}" <<'PY'
import setuptools
import sympy
import torch

st_ver = tuple(int(x) for x in setuptools.__version__.split(".")[:3])
assert st_ver >= (77, 0, 3), setuptools.__version__
assert "+cpu" in torch.__version__ or not torch.cuda.is_available(), torch.__version__

from sentence_transformers import SentenceTransformer
from yandex_music import ClientAsync
import aiohttp
import fastapi
import asyncpg
import openai
import instructor

print(f"  torch {torch.__version__}")
print(f"  setuptools {setuptools.__version__}")
print("  imports OK")
PY

if [[ ! -d "${MODEL_DIR}" ]]; then
  echo "ERROR: model not found: ${MODEL_DIR}" >&2
  exit 1
fi

echo "==> Verifying embedding model ..."
"${VENV_PY}" <<PY
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("${MODEL_DIR}")
vec = model.encode("test", show_progress_bar=False)
assert len(vec) > 0, "empty embedding"
print(f"  model OK, dim={len(vec)}")
PY

SP_SIZE=$(du -sh .venv/lib/python3.12/site-packages | cut -f1)
MODEL_SIZE=$(du -sh .models | cut -f1)
echo "==> OK: site-packages ${SP_SIZE}, models ${MODEL_SIZE}"

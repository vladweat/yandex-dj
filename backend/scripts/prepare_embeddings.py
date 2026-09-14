"""Скачать embedding-модель в .models для offline Docker-сборки."""

import os
from pathlib import Path

from sentence_transformers import SentenceTransformer

MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / ".models"
DEST = MODELS_DIR / MODEL.replace("/", "--")

MODELS_DIR.mkdir(parents=True, exist_ok=True)

if DEST.exists() and any(DEST.iterdir()):
    print(f"Model already present: {DEST}")
else:
    print(f"Downloading {MODEL} -> {DEST}")
    SentenceTransformer(MODEL).save(str(DEST))
    print("OK")

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

import asyncio

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.embedding import warmup_embedding_model
from app.db.session import engine

# uvicorn по умолчанию не поднимает INFO у app.* — без этого нет диагностики retrieval
logging.getLogger("app").setLevel(logging.INFO)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, warmup_embedding_model)
    yield
    await engine.dispose()


app = FastAPI(
    title="Prompt DJ",
    description="Генерация плейлистов Яндекс Музыки из текстового промпта",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

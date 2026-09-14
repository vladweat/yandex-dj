from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app import __version__
from app.api.v1.router import api_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Prompt DJ",
    description="Генерация плейлистов Яндекс Музыки из текстового промпта",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, llm, playlists, retrieval, yandex

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(yandex.router)
api_router.include_router(llm.router)
api_router.include_router(retrieval.router)
api_router.include_router(playlists.router)

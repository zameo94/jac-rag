import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import (
    api_keys,
    auth,
    chat,
    conversations,
    documents,
    invitations,
    llm,
    members,
    workspaces,
    widget,
)
from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.cors import CorsDispatcher
from app.core.errors import register_exception_handlers
from app.services.rag import rerank

logger = logging.getLogger(__name__)

settings = get_settings()


def preload_reranker() -> None:
    if not get_settings().rerank_enabled:
        return
    if get_settings().rerank_mode != "warmup":
        return
    try:
        rerank.get_reranker()
        logger.info("reranker preloaded: %s", get_settings().rerank_model)
    except Exception as exc:  # pragma: no cover - defensive at startup
        logger.warning("reranker preload failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    preload_reranker()
    yield


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    lifespan=lifespan,
    openapi_url="/openapi.json" if settings.is_development else None,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

app.add_middleware(
    CorsDispatcher,
    cms_origins=settings.cors_origin_list,
    cms_allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(workspaces.router, prefix="/api/v1/workspaces", tags=["Workspaces"])
app.include_router(members.router, prefix="/api/v1/workspaces", tags=["Members"])
app.include_router(invitations.router, prefix="/api/v1", tags=["Invitations"])
app.include_router(documents.router, prefix="/api/v1/workspaces", tags=["Documents"])
app.include_router(api_keys.router, prefix="/api/v1/workspaces", tags=["API keys"])
app.include_router(chat.router, prefix="/api/v1/workspaces", tags=["Chat"])
app.include_router(
    conversations.router, prefix="/api/v1/workspaces", tags=["Conversations"]
)
app.include_router(llm.router, prefix="/api/v1/workspaces", tags=["LLM"])
app.include_router(widget.router, prefix="/api/v1/widget", tags=["Widget"])


@app.get("/health", status_code=200, tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

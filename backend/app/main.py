from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, chat, documents, invitations, members, tenants
from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.errors import register_exception_handlers

settings = get_settings()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    openapi_url="/openapi.json" if settings.is_development else None,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["Tenants"])
app.include_router(members.router, prefix="/api/v1/tenants", tags=["Members"])
app.include_router(invitations.router, prefix="/api/v1", tags=["Invitations"])
app.include_router(documents.router, prefix="/api/v1/tenants", tags=["Documents"])
app.include_router(chat.router, prefix="/api/v1/tenants", tags=["Chat"])


@app.get("/health", status_code=200, tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

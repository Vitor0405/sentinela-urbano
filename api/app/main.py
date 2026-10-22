import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings, production_problems
from app.deps import DbSession
from app.routers import (
    account,
    admin_settings,
    auth,
    catalog,
    occurrences,
    queue,
    sectors,
    team,
    tracking,
)

logging.basicConfig(level=logging.INFO)

settings = get_settings()

# Refuse to run for real with development secrets or test addresses.
if settings.app_env == "production" and (problems := production_problems(settings)):
    raise RuntimeError(
        "Configuração insegura para produção: " + "; ".join(problems) + ". Veja docs/PUBLICACAO.md."
    )

is_production = settings.app_env == "production"
app = FastAPI(
    title="Sentinela Urbano API",
    description="Vigilância comunitária de risco de arbovirose.",
    version="0.5.0",
    docs_url=None if is_production else "/api/docs",
    openapi_url=None if is_production else "/api/openapi.json",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    # Tracking links carry their token in the fragment, which is never sent; this also
    # keeps paths out of third-party Referer headers (e.g. the map tile server).
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (account, admin_settings, auth, catalog, occurrences, queue, sectors, team, tracking):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health", tags=["infra"])
def health(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

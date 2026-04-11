from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.analysis.router import router as analysis_router
from app.auth.router import router as auth_router
from app.errors.router import router as errors_router
from app.history.router import router as history_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter
from app.database import engine

settings = get_settings()
configure_logging(debug=settings.DEBUG)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed exclusively by Alembic (the migrate service runs
    # `alembic upgrade head` before this process starts).
    # create_all is intentionally absent — running it alongside Alembic
    # causes duplicate-type errors in pg_type when tables already exist.
    logger.info("startup_complete", app=settings.APP_NAME)

    yield

    await engine.dispose()
    logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        lifespan=lifespan,
        # Disable interactive docs in production — exposes full API schema
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,  # explicit list, never "*" with credentials
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],   # only methods this API actually uses
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SlowAPIMiddleware)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    register_exception_handlers(app)

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(errors_router, prefix="/errors", tags=["errors"])
    # Analysis routes nest under /errors (POST /errors/{id}/analyze, GET /errors/{id}/analysis)
    app.include_router(analysis_router, prefix="/errors", tags=["analysis"])
    app.include_router(history_router, prefix="/history", tags=["history"])

    @app.get("/health", tags=["system"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

"""Pabrik aplikasi FastAPI untuk HC Store AI."""

from fastapi import FastAPI

import app as app_package
from app.api import health
from app.config import Settings
from app.errors import register_exception_handlers
from app.request_id import RequestIDMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Membuat dan mengonfigurasi instance aplikasi FastAPI."""
    if settings is None:
        settings = Settings()

    docs_url = "/docs" if settings.docs_enabled else None
    openapi_url = "/openapi.json" if settings.docs_enabled else None

    app = FastAPI(
        title="HC Store AI",
        version=app_package.__version__,
        docs_url=docs_url,
        openapi_url=openapi_url,
        redoc_url=None,
    )

    app.state.settings = settings
    app.state.model_loaded = False

    register_exception_handlers(app)
    app.add_middleware(RequestIDMiddleware)
    app.include_router(health.router)

    return app

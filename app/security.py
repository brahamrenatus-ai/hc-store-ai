"""Autentikasi API key untuk endpoint yang dilindungi."""

import secrets

from fastapi import Header, Request

from app.errors import AppError


async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> str:
    """Dependency untuk memverifikasi autentikasi header X-API-Key."""
    expected_key = request.app.state.settings.service_api_key.get_secret_value()
    # Dibandingkan sebagai bytes: compare_digest menolak str non-ASCII (TypeError → 500).
    if not x_api_key or not secrets.compare_digest(
        x_api_key.encode("utf-8"), expected_key.encode("utf-8")
    ):
        raise AppError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid or missing API key.",
        )

    return x_api_key

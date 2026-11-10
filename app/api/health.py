"""Endpoint pemeriksaan kesehatan layanan E1."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request

import app as app_package

router = APIRouter(prefix="/api/v1")


@router.get(
    "/health",
    summary="Pemeriksaan status kesehatan layanan",
    description="Memeriksa status operasional layanan AI dan kesiapan modul-modul pendukungnya.",
)
async def health(request: Request) -> dict:
    """Mengembalikan status kesiapan layanan dan status modul ringkasan serta prediksi."""
    settings = request.app.state.settings
    provider_configured = settings.provider_configured
    model_loaded = getattr(request.app.state, "model_loaded", False)

    summaries = "ok" if provider_configured else "degraded"
    predictions = "ok" if model_loaded else "unavailable"

    status = "ok" if (summaries == "ok" and predictions == "ok") else "degraded"

    tz = ZoneInfo(settings.app_timezone)
    timestamp = datetime.now(tz).isoformat(timespec="seconds")

    request_id = getattr(request.state, "request_id", "")

    return {
        "request_id": request_id,
        "data": {
            "status": status,
            "version": app_package.__version__,
            "modules": {
                "summaries": summaries,
                "predictions": predictions,
            },
            "model_loaded": model_loaded,
            "provider_configured": provider_configured,
            "timestamp": timestamp,
        },
        "meta": {},
    }

"""Endpoint ringkasan penjualan harian (E2) dan mingguan (E3)."""

from fastapi import APIRouter, Depends, Request

from app.agent_workflow.executor import Executor
from app.agent_workflow.head import Head
from app.security import require_api_key
from app.summaries import (
    DailySummaryRequest,
    WeeklySummaryRequest,
    today_in,
    validate_summary_request,
)

router = APIRouter(prefix="/api/v1/summaries", dependencies=[Depends(require_api_key)])


def _get_head(request: Request) -> Head:
    """Membangun instance Head dari state aplikasi."""
    settings = request.app.state.settings
    executor = Executor(
        api_key=settings.gemini_api_key,
        model=getattr(settings, "gemini_model", "gemini-2.0-flash"),
    )
    return Head(executor=executor, timezone=settings.app_timezone)


@router.post(
    "/daily",
    summary="Ringkasan penjualan harian (E2)",
    description="Menghasilkan ringkasan penjualan satu hari dari data agregat yang dikirim.",
)
async def daily_summary(body: DailySummaryRequest, request: Request) -> dict:
    """Endpoint ringkasan harian — kontrak API §5 E2."""
    today = today_in(body.timezone)
    data_notes = validate_summary_request(body, today)

    head = _get_head(request)
    request_id = getattr(request.state, "request_id", "")

    result = await head.generate_daily_summary(
        request=body,
        request_id=request_id,
        data_notes=data_notes,
    )

    return result.response.model_dump(mode="json")


@router.post(
    "/weekly",
    summary="Ringkasan penjualan mingguan (E3)",
    description="Menghasilkan ringkasan penjualan satu minggu dari data agregat yang dikirim.",
)
async def weekly_summary(body: WeeklySummaryRequest, request: Request) -> dict:
    """Endpoint ringkasan mingguan — kontrak API §5 E3."""
    today = today_in(body.timezone)
    data_notes = validate_summary_request(body, today)

    head = _get_head(request)
    request_id = getattr(request.state, "request_id", "")

    result = await head.generate_weekly_summary(
        request=body,
        request_id=request_id,
        data_notes=data_notes,
    )

    return result.response.model_dump(mode="json")

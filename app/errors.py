"""Skema dan penanganan galat standar untuk layanan HC Store AI."""

import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

USER_MESSAGES: dict[str, str] = {
    "MALFORMED_JSON": "Format data yang dikirim tidak bisa dibaca.",
    "UNAUTHORIZED": "Akses ke layanan AI ditolak.",
    "NOT_FOUND": "Alamat layanan AI tidak ditemukan.",
    "METHOD_NOT_ALLOWED": "Cara pemanggilan layanan AI tidak didukung.",
    "PAYLOAD_TOO_LARGE": "Data yang dikirim terlalu besar.",
    "UNSUPPORTED_MEDIA_TYPE": "Format data yang dikirim harus JSON.",
    "VALIDATION_ERROR": "Data yang dikirim belum lengkap atau tidak valid.",
    "INCONSISTENT_DATA": "Data penjualan yang dikirim tidak konsisten.",
    "RATE_LIMITED": "Terlalu banyak permintaan. Coba lagi sebentar lagi.",
    "INTERNAL_ERROR": "Terjadi kesalahan pada layanan AI. Coba lagi nanti.",
    "PREDICTION_FAILED": "Prediksi penjualan belum bisa dibuat.",
    "MODEL_UNAVAILABLE": "Model prediksi sedang tidak tersedia.",
}


class AppError(Exception):
    """Exception aplikasi terstruktur dengan kode dan detail galat."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details if details is not None else []
        self.retryable = retryable


def get_request_id(request: Request) -> str:
    """Mengambil atau membuat request ID dari request state."""
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        request_id = f"req_{uuid.uuid4().hex}"
        request.state.request_id = request_id
    return request_id


def create_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    retryable: bool = False,
) -> JSONResponse:
    """Membentuk JSONResponse galat beramplop standar dengan header X-Request-ID."""
    request_id = get_request_id(request)
    body = {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
            "user_message": USER_MESSAGES.get(code, ""),
            "retryable": retryable,
            "details": details if details is not None else [],
        },
    }
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={"X-Request-ID": request_id},
    )


def format_validation_loc(loc: tuple[Any, ...]) -> str:
    """Memformat tuple lokasi Pydantic menjadi string field sesuai kontrak."""
    parts = list(loc)
    if parts and parts[0] == "body":
        parts = parts[1:]
    if not parts:
        return "body"

    res = ""
    for part in parts:
        if isinstance(part, int):
            res += f"[{part}]"
        else:
            if res:
                res += f".{part}"
            else:
                res = str(part)
    return res


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Menangani kegagalan validasi masukan request body."""
    errors = exc.errors()
    if any(err.get("type") == "json_invalid" for err in errors):
        return create_error_response(
            request=request,
            status_code=400,
            code="MALFORMED_JSON",
            message="Malformed JSON in request body.",
            details=[],
            retryable=False,
        )

    details = []
    for err in errors:
        field_str = format_validation_loc(err.get("loc", ()))
        issue_str = str(err.get("msg", ""))
        details.append({"field": field_str, "issue": issue_str})

    return create_error_response(
        request=request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details=details,
        retryable=False,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Menangani Starlette / FastAPI HTTP exceptions seperti 404 dan 405."""
    if exc.status_code == 404:
        code = "NOT_FOUND"
        message = "The requested resource was not found."
    elif exc.status_code == 405:
        code = "METHOD_NOT_ALLOWED"
        message = "Method not allowed."
    else:
        code = "INTERNAL_ERROR" if exc.status_code >= 500 else "VALIDATION_ERROR"
        message = str(exc.detail) if exc.detail else "HTTP error."

    return create_error_response(
        request=request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=[],
        retryable=False,
    )


async def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    """Menangani instance AppError terstruktur."""
    return create_error_response(
        request=request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        retryable=exc.retryable,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Menangani unhandled exception dengan kode 500 tanpa membocorkan detail internal."""
    return create_error_response(
        request=request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="Internal server error.",
        details=[],
        retryable=True,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Mendaftarkan seluruh penangan galat ke aplikasi FastAPI."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

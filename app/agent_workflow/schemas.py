"""Skema respons ringkasan (E2, E3) sesuai kontrak API §5 dan PRD §12.5.

Semua field di ``data`` dan ``meta`` mengikuti bentuk yang disepakati
di ``docs/api-contract.md`` v0.3 sehingga FS bisa merender setiap
keadaan dari ``generation_mode`` saja (AE-FR-050).
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class GenerationMode(StrEnum):
    """Mode pembuatan ringkasan (kontrak API §5 E2)."""

    AI = "ai"
    TEMPLATE_FALLBACK = "template_fallback"
    NO_DATA = "no_data"


class FallbackReason(StrEnum):
    """Alasan ringkasan menggunakan teks cadangan (kontrak API §5 E2)."""

    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"


# ---------------------------------------------------------------------------
# Komponen respons
# ---------------------------------------------------------------------------


class PeriodOut(BaseModel):
    """Rentang periode di respons."""

    model_config = ConfigDict(extra="forbid")
    start: dt.date
    end: dt.date


class KeyFigure(BaseModel):
    """Satu angka kunci yang dihitung secara deterministik (AE-FR-021).

    Field ini dihasilkan kode, bukan LLM, sehingga FS bisa menampilkannya
    sebagai kartu angka yang selalu konsisten dengan teks.
    """

    model_config = ConfigDict(extra="forbid")
    key: str = Field(description="Kunci mesin, mis. 'total_revenue'")
    label: str = Field(description="Label tampilan bahasa Indonesia")
    value: int = Field(description="Nilai numerik mentah")
    unit: str = Field(description="Satuan, mis. 'IDR', 'transaksi', 'unit'")
    display: str = Field(description="Nilai terformat, mis. 'Rp 4.390.000'")
    source: str = Field(description="Asal data, mis. 'sales.total_revenue'")


class Observation(BaseModel):
    """Satu observasi bisnis dengan bukti (AE-FR-003)."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(description="ID observasi, mis. 'obs_top_product'")
    text: str = Field(description="Kalimat observasi dalam bahasa Indonesia")
    evidence: list[str] = Field(
        description="Referensi ke field sumber data, mis. ['sales.product_sales']"
    )


class DataNote(BaseModel):
    """Catatan kualitas data yang diteruskan ke FS."""

    model_config = ConfigDict(extra="forbid")
    code: str
    field: str


class ValidationInfo(BaseModel):
    """Info validasi keluaran LLM di metadata."""

    model_config = ConfigDict(extra="forbid")
    schema_ok: bool
    numeric_check: Literal["passed", "failed", "skipped"]


# ---------------------------------------------------------------------------
# Data dan meta respons
# ---------------------------------------------------------------------------


class SummaryData(BaseModel):
    """Blok ``data`` respons ringkasan (kontrak API §5 E2, §12.5)."""

    model_config = ConfigDict(extra="forbid")
    summary_type: Literal["daily", "weekly"]
    period: PeriodOut
    generation_mode: GenerationMode
    summary_text: str
    key_figures: list[KeyFigure] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    data_notes: list[DataNote] = Field(default_factory=list)


class SummaryMeta(BaseModel):
    """Blok ``meta`` respons ringkasan."""

    model_config = ConfigDict(extra="forbid")
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str
    latency_ms: int = 0
    validation: ValidationInfo
    fallback_reason: FallbackReason | None = None
    generated_at: str = Field(description="Timestamp ISO 8601 dengan offset")


class SummaryResponse(BaseModel):
    """Amplop respons ringkasan lengkap."""

    model_config = ConfigDict(extra="forbid")
    request_id: str
    data: SummaryData
    meta: SummaryMeta

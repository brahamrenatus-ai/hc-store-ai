"""Validasi request ringkasan penjualan harian dan mingguan lintas field dan konsistensi data."""

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.errors import AppError
from app.summaries.schemas import (
    DailySummaryRequest,
    PeriodSales,
    WeeklySummaryRequest,
)


@dataclass(frozen=True)
class DataNote:
    """Catatan kualitas data untuk request ringkasan yang lolos validasi."""

    code: str
    field: str


def today_in(timezone: str) -> dt.date:
    """Mengembalikan tanggal hari ini di zona waktu yang ditentukan."""
    return dt.datetime.now(ZoneInfo(timezone)).date()


def validate_summary_request(
    req: DailySummaryRequest | WeeklySummaryRequest,
    today: dt.date,
) -> list[DataNote]:
    """Memvalidasi request ringkasan penjualan (lapis 2 lintas field dan lapis 3 konsistensi).

    Mengembalikan daftar DataNote untuk request yang valid, atau melempar AppError.
    """
    layer2_errors: list[dict[str, str]] = []

    if isinstance(req, DailySummaryRequest):
        # 1. date > today
        if req.date > today:
            layer2_errors.append(
                {
                    "field": "date",
                    "issue": "Date is after today in the given timezone",
                }
            )

        # 2. sales.period.start atau .end != date
        if req.sales.period.start != req.date or req.sales.period.end != req.date:
            layer2_errors.append(
                {
                    "field": "sales.period",
                    "issue": "Period must start and end on date",
                }
            )

        # 3. previous_period ada dan periodenya bukan (date - 1, date - 1)
        if req.previous_period is not None:
            expected_prev = req.date - dt.timedelta(days=1)
            if (
                req.previous_period.period.start != expected_prev
                or req.previous_period.period.end != expected_prev
            ):
                layer2_errors.append(
                    {
                        "field": "previous_period.period",
                        "issue": "Previous period must be the day before date",
                    }
                )

    elif isinstance(req, WeeklySummaryRequest):
        # 1. end - start != 6 hari
        if (req.sales.period.end - req.sales.period.start).days != 6:
            layer2_errors.append(
                {
                    "field": "sales.period",
                    "issue": "Weekly period must span exactly 7 days",
                }
            )

        # 2. sales.period.end > today
        if req.sales.period.end > today:
            layer2_errors.append(
                {
                    "field": "sales.period",
                    "issue": "Weekly period must end on or before today",
                }
            )

        # 3. Untuk setiap baris daily_breakdown[i] sesuai urutan list:
        # tanggal di luar sales.period -> Date is outside sales.period
        # ... selain itu, tanggalnya sudah muncul di baris sebelumnya ->
        # Duplicate date in daily_breakdown
        seen_dates: set[dt.date] = set()
        for i, item in enumerate(req.sales.daily_breakdown):
            if item.date < req.sales.period.start or item.date > req.sales.period.end:
                layer2_errors.append(
                    {
                        "field": f"sales.daily_breakdown[{i}].date",
                        "issue": "Date is outside sales.period",
                    }
                )
            elif item.date in seen_dates:
                layer2_errors.append(
                    {
                        "field": f"sales.daily_breakdown[{i}].date",
                        "issue": "Duplicate date in daily_breakdown",
                    }
                )
            else:
                seen_dates.add(item.date)

        # 4. previous_period ada dan periodenya bukan (start - 7, start - 1)
        if req.previous_period is not None:
            expected_start = req.sales.period.start - dt.timedelta(days=7)
            expected_end = req.sales.period.start - dt.timedelta(days=1)
            if (
                req.previous_period.period.start != expected_start
                or req.previous_period.period.end != expected_end
            ):
                layer2_errors.append(
                    {
                        "field": "previous_period.period",
                        "issue": ("Previous period must be the 7 days before sales.period"),
                    }
                )

    if layer2_errors:
        raise AppError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details=layer2_errors,
            retryable=False,
        )

    # Lapis 3: Konsistensi data
    layer3_errors: list[dict[str, str]] = []

    def _check_block_consistency(blok_name: str, block: PeriodSales) -> None:
        if len(block.product_sales) > 0:
            if sum(p.units_sold for p in block.product_sales) != block.units_sold:
                layer3_errors.append(
                    {
                        "field": f"{blok_name}.product_sales",
                        "issue": ("Sum of product_sales.units_sold does not match units_sold"),
                    }
                )
            if sum(p.revenue for p in block.product_sales) != block.total_revenue:
                layer3_errors.append(
                    {
                        "field": f"{blok_name}.product_sales",
                        "issue": ("Sum of product_sales.revenue does not match total_revenue"),
                    }
                )
        if block.transaction_count == 0 and (block.units_sold > 0 or block.total_revenue > 0):
            layer3_errors.append(
                {
                    "field": f"{blok_name}.transaction_count",
                    "issue": ("Zero transactions but non-zero units_sold or total_revenue"),
                }
            )

    # 1. Blok sales
    _check_block_consistency("sales", req.sales)

    # 2. Khusus mingguan: rincian per hari
    if isinstance(req, WeeklySummaryRequest):
        breakdown = req.sales.daily_breakdown
        if sum(d.total_revenue for d in breakdown) != req.sales.total_revenue:
            layer3_errors.append(
                {
                    "field": "sales.daily_breakdown",
                    "issue": (
                        "Sum of daily_breakdown.total_revenue does not match sales.total_revenue"
                    ),
                }
            )
        if sum(d.transaction_count for d in breakdown) != req.sales.transaction_count:
            layer3_errors.append(
                {
                    "field": "sales.daily_breakdown",
                    "issue": (
                        "Sum of daily_breakdown.transaction_count does not"
                        " match sales.transaction_count"
                    ),
                }
            )
        if sum(d.units_sold for d in breakdown) != req.sales.units_sold:
            layer3_errors.append(
                {
                    "field": "sales.daily_breakdown",
                    "issue": ("Sum of daily_breakdown.units_sold does not match sales.units_sold"),
                }
            )

    # 3. Blok previous_period bila ada
    if req.previous_period is not None:
        _check_block_consistency("previous_period", req.previous_period)

    if layer3_errors:
        raise AppError(
            status_code=422,
            code="INCONSISTENT_DATA",
            message="Request data is inconsistent.",
            details=layer3_errors,
            retryable=False,
        )

    # Catatan kualitas data (hanya untuk request yang lolos lapis 2 dan 3)
    notes: list[DataNote] = []

    # 1. previous_period tidak ada atau null
    if req.previous_period is None:
        notes.append(DataNote(code="NO_PREVIOUS_PERIOD", field="previous_period"))

    # 2. inventory tidak ada atau null
    if req.inventory is None:
        notes.append(DataNote(code="NO_INVENTORY", field="inventory"))

    # 3. sales.product_sales kosong dan sales.units_sold > 0
    if len(req.sales.product_sales) == 0 and req.sales.units_sold > 0:
        notes.append(DataNote(code="NO_PRODUCT_BREAKDOWN", field="sales.product_sales"))

    # 4. previous_period ada, product_sales-nya kosong, dan units_sold-nya > 0
    if (
        req.previous_period is not None
        and len(req.previous_period.product_sales) == 0
        and req.previous_period.units_sold > 0
    ):
        notes.append(
            DataNote(
                code="NO_PRODUCT_BREAKDOWN",
                field="previous_period.product_sales",
            )
        )

    # 5. inventory ada dan minimal satu product_id di sales.product_sales
    # tidak ada di inventory.items
    if req.inventory is not None:
        inventory_ids = {item.product_id for item in req.inventory.items}
        if any(item.product_id not in inventory_ids for item in req.sales.product_sales):
            notes.append(
                DataNote(
                    code="PRODUCTS_MISSING_FROM_INVENTORY",
                    field="inventory.items",
                )
            )

    return notes

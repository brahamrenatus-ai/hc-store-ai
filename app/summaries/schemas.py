"""Skema Pydantic untuk request ringkasan penjualan harian dan mingguan."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StringConstraints,
    field_validator,
    model_validator,
)

MAX_PRODUCT_SALES = 500
MAX_INVENTORY_ITEMS = 2000
WEEK_DAYS = 7

NonNegativeInt = Annotated[int, Strict(), Field(ge=0)]
ProductId = Annotated[str, StringConstraints(min_length=1, max_length=64)]
ProductName = Annotated[str, StringConstraints(min_length=1, max_length=120)]

# Dicocokkan ke daftar zona, bukan lewat ZoneInfo(nama): ZoneInfo mencari nama itu sebagai
# path, dan string sangat panjang melempar OSError yang lolos dari Pydantic menjadi 500.
_IANA_TIMEZONES = frozenset(available_timezones())


def _check_timezone(value: str) -> str:
    if value not in _IANA_TIMEZONES:
        raise ValueError("Unknown IANA timezone")
    return value


IanaTimezone = Annotated[str, AfterValidator(_check_timezone)]


class SummaryBaseModel(BaseModel):
    """Model dasar dengan konfigurasi larangan field tambahan."""

    model_config = ConfigDict(extra="forbid")


class Period(SummaryBaseModel):
    """Rentang tanggal periode penjualan."""

    start: dt.date = Field(description="Tanggal awal periode penjualan")
    end: dt.date = Field(description="Tanggal akhir periode penjualan")

    @model_validator(mode="after")
    def validate_period_range(self) -> Period:
        if self.end < self.start:
            raise ValueError("End date must be on or after start date")
        return self


class ProductSale(SummaryBaseModel):
    """Rincian penjualan untuk satu produk."""

    product_id: ProductId = Field(description="Identifikator unik produk")
    name: ProductName = Field(description="Nama produk yang terjual")
    units_sold: NonNegativeInt = Field(description="Jumlah unit produk yang terjual")
    revenue: NonNegativeInt = Field(description="Total pendapatan dari penjualan produk")


class DailyTotals(SummaryBaseModel):
    """Agregat penjualan harian untuk rincian mingguan."""

    date: dt.date = Field(description="Tanggal penjualan harian dalam rincian mingguan")
    total_revenue: NonNegativeInt = Field(
        description="Total pendapatan kotor pada tanggal tersebut"
    )
    transaction_count: NonNegativeInt = Field(description="Jumlah transaksi pada tanggal tersebut")
    units_sold: NonNegativeInt = Field(
        description="Jumlah total unit terjual pada tanggal tersebut"
    )


class PeriodSales(SummaryBaseModel):
    """Agregat dan rincian penjualan untuk suatu periode."""

    period: Period = Field(description="Rentang tanggal periode penjualan")
    total_revenue: NonNegativeInt = Field(
        description="Total pendapatan kotor penjualan pada periode"
    )
    transaction_count: NonNegativeInt = Field(
        description="Jumlah total transaksi penjualan pada periode"
    )
    units_sold: NonNegativeInt = Field(description="Jumlah total unit terjual pada periode")
    product_sales: list[ProductSale] = Field(
        max_length=MAX_PRODUCT_SALES,
        description="Daftar rincian penjualan per produk",
    )

    @field_validator("product_sales")
    @classmethod
    def validate_unique_product_id(cls, items: list[ProductSale]) -> list[ProductSale]:
        seen: set[str] = set()
        for item in items:
            if item.product_id in seen:
                raise ValueError("Duplicate product_id in product_sales")
            seen.add(item.product_id)
        return items


class DailySales(PeriodSales):
    """Data penjualan untuk ringkasan harian."""

    daily_breakdown: None = Field(
        default=None,
        description="Rincian per hari (harus null atau tidak dikirim pada harian)",
    )


class WeeklySales(PeriodSales):
    """Data penjualan untuk ringkasan mingguan."""

    daily_breakdown: list[DailyTotals] = Field(
        max_length=WEEK_DAYS,
        description="Daftar rincian penjualan per hari dalam periode mingguan",
    )


class InventoryItem(SummaryBaseModel):
    """Status stok inventaris untuk satu produk."""

    product_id: ProductId = Field(description="Identifikator unik produk di inventaris")
    name: ProductName = Field(description="Nama produk di inventaris")
    current_stock: NonNegativeInt = Field(description="Jumlah stok fisik produk saat snapshot")
    reorder_level: NonNegativeInt | None = Field(
        default=None,
        description="Batas minimum stok untuk pemesanan kembali",
    )


class Inventory(SummaryBaseModel):
    """Data posisi stok inventaris toko."""

    snapshot_at: AwareDatetime = Field(description="Waktu pengambilan snapshot data inventaris")
    items: list[InventoryItem] = Field(
        max_length=MAX_INVENTORY_ITEMS,
        description="Daftar status stok barang inventaris",
    )

    @field_validator("items")
    @classmethod
    def validate_unique_product_id(cls, items: list[InventoryItem]) -> list[InventoryItem]:
        seen: set[str] = set()
        for item in items:
            if item.product_id in seen:
                raise ValueError("Duplicate product_id in inventory items")
            seen.add(item.product_id)
        return items


class Options(SummaryBaseModel):
    """Pilihan konfigurasi tambahan ringkasan."""

    language: Literal["id"] = Field(
        default="id",
        description="Bahasa yang digunakan untuk hasil ringkasan",
    )


class DailySummaryRequest(SummaryBaseModel):
    """Request ringkasan penjualan harian."""

    date: dt.date = Field(description="Tanggal penjualan yang diringkas")
    timezone: IanaTimezone = Field(description="Zona waktu IANA toko")
    sales: DailySales = Field(description="Data penjualan harian")
    previous_period: PeriodSales | None = Field(
        default=None,
        description="Data penjualan periode sebelumnya sebagai pembanding",
    )
    inventory: Inventory | None = Field(
        default=None,
        description="Data posisi stok barang toko",
    )
    options: Options = Field(
        default_factory=Options,
        description="Pilihan konfigurasi tambahan ringkasan",
    )


class WeeklySummaryRequest(SummaryBaseModel):
    """Request ringkasan penjualan mingguan."""

    timezone: IanaTimezone = Field(description="Zona waktu IANA toko")
    sales: WeeklySales = Field(description="Data penjualan mingguan")
    previous_period: PeriodSales | None = Field(
        default=None,
        description="Data penjualan periode sebelumnya sebagai pembanding",
    )
    inventory: Inventory | None = Field(
        default=None,
        description="Data posisi stok barang toko",
    )
    options: Options = Field(
        default_factory=Options,
        description="Pilihan konfigurasi tambahan ringkasan",
    )

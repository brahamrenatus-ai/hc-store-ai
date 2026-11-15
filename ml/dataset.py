"""Pemuat dan pemeriksa dataset latih untuk HC Store AI.

Modul ini memvalidasi skema berkas CSV dan aturan integritas D1–D7
sesuai kontrak data sebelum dataset digunakan untuk pelatihan model (AE-FR-034).
"""

import argparse
import csv
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# Konstanta nama kolom
COL_DATE = "date"
COL_PRODUCT_ID = "product_id"
COL_UNITS_SOLD = "units_sold"
COL_REVENUE = "revenue"
COL_STOCKOUT = "stockout"
COL_PROMO = "promo"
COL_UNIT_PRICE = "unit_price"

COL_NAME = "name"
COL_CATEGORY = "category"
COL_PRICE = "price"
COL_LISTED_FROM = "listed_from"
COL_LISTED_UNTIL = "listed_until"
COL_UNIT = "unit"

# Konstanta kolom wajib dan opsional
SALES_REQUIRED = (COL_DATE, COL_PRODUCT_ID, COL_UNITS_SOLD, COL_REVENUE)
SALES_OPTIONAL = (COL_STOCKOUT, COL_PROMO, COL_UNIT_PRICE)
PRODUCTS_REQUIRED = (
    COL_PRODUCT_ID,
    COL_NAME,
    COL_CATEGORY,
    COL_PRICE,
    COL_LISTED_FROM,
    COL_UNIT,
)
PRODUCTS_OPTIONAL = (COL_LISTED_UNTIL,)

DEFAULT_MIN_DAYS = 180
MAX_EXAMPLES = 5
CHECK_CODES = ("SCHEMA", "D1", "D2", "D3", "D4", "D5", "D6", "D7")


@dataclass(frozen=True, slots=True)
class SalesRow:
    """Baris data penjualan harian yang telah tervalidasi."""

    date: date
    product_id: str
    units_sold: int
    revenue: int
    stockout: int | None = None
    promo: int | None = None
    unit_price: int | None = None


@dataclass(frozen=True, slots=True)
class Product:
    """Informasi katalog produk yang telah tervalidasi."""

    product_id: str
    name: str
    category: str
    price: int
    listed_from: date
    listed_until: date | None
    unit: str


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Hasil pemeriksaan satu aturan validasi dataset."""

    code: str
    passed: bool
    count: int
    message: str
    examples: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DatasetReport:
    """Laporan hasil validasi dataset latih."""

    sales_path: str
    products_path: str
    sales_sha256: str
    products_sha256: str
    sales_rows: int
    product_count: int
    date_min: date | None
    date_max: date | None
    checks: tuple[CheckResult, ...]
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)


@dataclass(frozen=True, slots=True)
class TrainingData:
    """Data latih bertipe yang siap digunakan oleh tahapan selanjutnya."""

    sales: tuple[SalesRow, ...]
    products: dict[str, Product]
    report: DatasetReport


class DatasetError(Exception):
    """Pengecualian yang dilempar ketika dataset latih gagal validasi."""

    def __init__(self, report: DatasetReport) -> None:
        failed_codes = [c.code for c in report.checks if not c.passed]
        joined = ", ".join(failed_codes)
        super().__init__(f"Dataset latih tidak lolos pemeriksaan: {joined}")
        self.report = report


@dataclass(slots=True)
class _ParsedSalesRow:
    line_num: int
    date: date
    product_id: str
    units_sold: int
    revenue: int
    raw_stockout: str | None
    raw_promo: str | None
    unit_price: int | None


_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INT_REGEX = re.compile(r"^-?[0-9]+$")


def _parse_strict_date(value: str) -> date | None:
    if not _DATE_REGEX.match(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_strict_int(value: str) -> int | None:
    if not _INT_REGEX.match(value):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _fill_missing(row: dict) -> dict[str, str]:
    """Sel yang hilang di baris pendek (DictReader mengisinya None) dianggap kosong."""
    return {k: ("" if v is None else v) for k, v in row.items() if k is not None}


def validate_dataset(
    sales_path: Path | str,
    products_path: Path | str,
    *,
    today: date,
    min_days: int = DEFAULT_MIN_DAYS,
) -> DatasetReport:
    """Memvalidasi dataset latih dan mengembalikan laporan pemeriksaan."""
    if min_days < 1:
        raise ValueError("min_days harus minimal 1 hari")

    sales_p = Path(sales_path)
    products_p = Path(products_path)

    sales_sha256 = hashlib.sha256(sales_p.read_bytes()).hexdigest()
    products_sha256 = hashlib.sha256(products_p.read_bytes()).hexdigest()

    with sales_p.open(encoding="utf-8-sig", newline="") as f:
        sales_reader = csv.DictReader(f)
        sales_header = list(sales_reader.fieldnames or [])
        sales_raw_rows: list[tuple[int, dict[str, str]]] = []
        for row in sales_reader:
            sales_raw_rows.append((sales_reader.line_num, _fill_missing(row)))

    with products_p.open(encoding="utf-8-sig", newline="") as f:
        products_reader = csv.DictReader(f)
        products_header = list(products_reader.fieldnames or [])
        products_raw_rows: list[tuple[int, dict[str, str]]] = []
        for row in products_reader:
            products_raw_rows.append((products_reader.line_num, _fill_missing(row)))

    # Tahap A: Header kedua berkas
    schema_findings: list[str] = []
    warnings: list[str] = []

    # Kolom wajib yang hilang
    for col in SALES_REQUIRED:
        if col not in sales_header:
            schema_findings.append(f"{sales_p.name}: kolom wajib hilang: {col}")

    for col in PRODUCTS_REQUIRED:
        if col not in products_header:
            schema_findings.append(f"{products_p.name}: kolom wajib hilang: {col}")

    # Kolom tidak dikenal (peringatan)
    unknown_sales = [c for c in sales_header if c not in SALES_REQUIRED and c not in SALES_OPTIONAL]
    if unknown_sales:
        warnings.append(f"{sales_p.name}: kolom tidak dikenal: {', '.join(unknown_sales)}")

    unknown_products = [
        c for c in products_header if c not in PRODUCTS_REQUIRED and c not in PRODUCTS_OPTIONAL
    ]
    if unknown_products:
        warnings.append(f"{products_p.name}: kolom tidak dikenal: {', '.join(unknown_products)}")

    if schema_findings:
        schema_check = CheckResult(
            code="SCHEMA",
            passed=False,
            count=len(schema_findings),
            message="Skema berkas, kolom wajib, dan tipe data valid",
            examples=tuple(schema_findings[:MAX_EXAMPLES]),
        )
        return DatasetReport(
            sales_path=str(sales_path),
            products_path=str(products_path),
            sales_sha256=sales_sha256,
            products_sha256=products_sha256,
            sales_rows=0,
            product_count=0,
            date_min=None,
            date_max=None,
            checks=(schema_check,),
            warnings=tuple(warnings),
        )

    # Tahap B: Isi sel berkas products
    seen_pids: set[str] = set()
    for line_num, row in products_raw_rows:
        bad_cols: list[str] = []
        pid = row.get(COL_PRODUCT_ID, "")
        if not (1 <= len(pid) <= 64):
            bad_cols.append(COL_PRODUCT_ID)

        name = row.get(COL_NAME, "")
        if not (1 <= len(name) <= 120):
            bad_cols.append(COL_NAME)

        category = row.get(COL_CATEGORY, "")
        if not category:
            bad_cols.append(COL_CATEGORY)

        price_str = row.get(COL_PRICE, "")
        price_val = _parse_strict_int(price_str)
        if price_val is None or price_val <= 0:
            bad_cols.append(COL_PRICE)

        lf_str = row.get(COL_LISTED_FROM, "")
        lf_val = _parse_strict_date(lf_str)
        if lf_val is None:
            bad_cols.append(COL_LISTED_FROM)

        lu_str = row.get(COL_LISTED_UNTIL, "")
        if lu_str:
            lu_val = _parse_strict_date(lu_str)
            if lu_val is None:
                bad_cols.append(COL_LISTED_UNTIL)
            elif lf_val is not None and lu_val < lf_val:
                bad_cols.append(COL_LISTED_UNTIL)

        unit = row.get(COL_UNIT, "")
        if not unit:
            bad_cols.append(COL_UNIT)

        # Pemeriksaan duplikasi product_id
        is_dup_pid = False
        if pid:
            if pid in seen_pids:
                is_dup_pid = True
            elif 1 <= len(pid) <= 64:
                seen_pids.add(pid)

        if bad_cols:
            schema_findings.append(
                f"{products_p.name} baris {line_num} kolom {', '.join(bad_cols)}"
            )
        elif is_dup_pid:
            schema_findings.append(f"{products_p.name} baris {line_num} product_id ganda")

    # Tahap B: Isi sel berkas sales
    if not sales_raw_rows:
        schema_findings.append(f"{sales_p.name}: tidak ada baris data")
    else:
        has_unit_price = COL_UNIT_PRICE in sales_header
        for line_num, row in sales_raw_rows:
            bad_cols = []
            d_str = row.get(COL_DATE, "")
            if _parse_strict_date(d_str) is None:
                bad_cols.append(COL_DATE)

            pid = row.get(COL_PRODUCT_ID, "")
            if not (1 <= len(pid) <= 64):
                bad_cols.append(COL_PRODUCT_ID)

            u_str = row.get(COL_UNITS_SOLD, "")
            if _parse_strict_int(u_str) is None:
                bad_cols.append(COL_UNITS_SOLD)

            r_str = row.get(COL_REVENUE, "")
            if _parse_strict_int(r_str) is None:
                bad_cols.append(COL_REVENUE)

            if has_unit_price:
                up_str = row.get(COL_UNIT_PRICE, "")
                up_val = _parse_strict_int(up_str)
                if up_val is None or up_val <= 0:
                    bad_cols.append(COL_UNIT_PRICE)

            if bad_cols:
                schema_findings.append(
                    f"{sales_p.name} baris {line_num} kolom {', '.join(bad_cols)}"
                )

    if schema_findings:
        schema_check = CheckResult(
            code="SCHEMA",
            passed=False,
            count=len(schema_findings),
            message="Skema berkas, kolom wajib, dan tipe data valid",
            examples=tuple(schema_findings[:MAX_EXAMPLES]),
        )
        return DatasetReport(
            sales_path=str(sales_path),
            products_path=str(products_path),
            sales_sha256=sales_sha256,
            products_sha256=products_sha256,
            sales_rows=0,
            product_count=0,
            date_min=None,
            date_max=None,
            checks=(schema_check,),
            warnings=tuple(warnings),
        )

    # SCHEMA lolos
    schema_check = CheckResult(
        code="SCHEMA",
        passed=True,
        count=0,
        message="Skema berkas, kolom wajib, dan tipe data valid",
        examples=(),
    )

    # Bangun kamus produk
    products: dict[str, Product] = {}
    for _ln, row in products_raw_rows:
        pid = row[COL_PRODUCT_ID]
        lu_raw = row.get(COL_LISTED_UNTIL, "")
        products[pid] = Product(
            product_id=pid,
            name=row[COL_NAME],
            category=row[COL_CATEGORY],
            price=int(row[COL_PRICE]),
            listed_from=date.fromisoformat(row[COL_LISTED_FROM]),
            listed_until=date.fromisoformat(lu_raw) if lu_raw else None,
            unit=row[COL_UNIT],
        )

    # Bangun baris penjualan yang telah diurai
    has_unit_price = COL_UNIT_PRICE in sales_header
    has_stockout = COL_STOCKOUT in sales_header
    has_promo = COL_PROMO in sales_header

    parsed_sales: list[_ParsedSalesRow] = []
    for line_num, row in sales_raw_rows:
        parsed_sales.append(
            _ParsedSalesRow(
                line_num=line_num,
                date=date.fromisoformat(row[COL_DATE]),
                product_id=row[COL_PRODUCT_ID],
                units_sold=int(row[COL_UNITS_SOLD]),
                revenue=int(row[COL_REVENUE]),
                raw_stockout=row.get(COL_STOCKOUT) if has_stockout else None,
                raw_promo=row.get(COL_PROMO) if has_promo else None,
                unit_price=int(row[COL_UNIT_PRICE]) if has_unit_price else None,
            )
        )

    sales_rows = len(parsed_sales)
    product_count = len(products)
    all_dates = [r.date for r in parsed_sales]
    date_min = min(all_dates)
    date_max = max(all_dates)
    akhir_data = date_max

    # Pemeriksaan D1: Keunikan pasangan (date, product_id)
    seen_pairs: set[tuple[date, str]] = set()
    d1_findings: list[str] = []
    for r in parsed_sales:
        pair = (r.date, r.product_id)
        if pair in seen_pairs:
            d1_findings.append(f"baris {r.line_num}")
        else:
            seen_pairs.add(pair)
    d1_check = CheckResult(
        code="D1",
        passed=len(d1_findings) == 0,
        count=len(d1_findings),
        message="Setiap pasangan tanggal dan produk harus unik",
        examples=tuple(d1_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D2: Satu baris per hari tanpa celah
    d2_a_findings: list[str] = []
    for r in parsed_sales:
        if r.product_id in products:
            prod = products[r.product_id]
            batas_akhir = (
                min(akhir_data, prod.listed_until) if prod.listed_until is not None else akhir_data
            )
            if r.date < prod.listed_from or r.date > batas_akhir:
                d2_a_findings.append(f"baris {r.line_num}")

    present_dates: dict[str, set[date]] = {pid: set() for pid in products}
    for r in parsed_sales:
        if r.product_id in present_dates:
            present_dates[r.product_id].add(r.date)

    d2_b_findings: list[str] = []
    one_day = timedelta(days=1)
    for pid in sorted(products.keys()):
        prod = products[pid]
        if prod.listed_from > akhir_data:
            continue
        batas_akhir = (
            min(akhir_data, prod.listed_until) if prod.listed_until is not None else akhir_data
        )
        curr = prod.listed_from
        while curr <= batas_akhir:
            if curr not in present_dates[pid]:
                d2_b_findings.append(f"{pid} {curr.isoformat()}")
            curr += one_day

    d2_findings = d2_a_findings + d2_b_findings
    d2_check = CheckResult(
        code="D2",
        passed=len(d2_findings) == 0,
        count=len(d2_findings),
        message="Kelengkapan baris per hari untuk setiap produk tanpa celah",
        examples=tuple(d2_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D3: units_sold >= 0, revenue >= 0, units_sold == 0 => revenue == 0
    d3_findings: list[str] = []
    for r in parsed_sales:
        if r.units_sold < 0 or r.revenue < 0 or (r.units_sold == 0 and r.revenue != 0):
            d3_findings.append(f"baris {r.line_num}")
    d3_check = CheckResult(
        code="D3",
        passed=len(d3_findings) == 0,
        count=len(d3_findings),
        message="Unit terjual dan pendapatan harus valid dan konsisten",
        examples=tuple(d3_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D4: product_id dikenal di katalog products
    d4_findings: list[str] = []
    for r in parsed_sales:
        if r.product_id not in products:
            d4_findings.append(f"baris {r.line_num}")
    d4_check = CheckResult(
        code="D4",
        passed=len(d4_findings) == 0,
        count=len(d4_findings),
        message="ID produk harus terdaftar di katalog produk",
        examples=tuple(d4_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D5: revenue <= units_sold * harga
    d5_findings: list[str] = []
    for r in parsed_sales:
        if r.product_id in products:
            prod = products[r.product_id]
            harga = r.unit_price if r.unit_price is not None else prod.price
            if r.revenue > r.units_sold * harga:
                d5_findings.append(f"baris {r.line_num}")
    d5_check = CheckResult(
        code="D5",
        passed=len(d5_findings) == 0,
        count=len(d5_findings),
        message="Pendapatan tidak boleh melebihi unit terjual dikali harga",
        examples=tuple(d5_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D6: tidak ada tanggal di masa depan dan rentang memenuhi batas minimum
    d6_findings: list[str] = []
    for r in parsed_sales:
        if r.date > today:
            d6_findings.append(f"baris {r.line_num}")
    span_days = (date_max - date_min).days + 1
    if span_days < min_days:
        d6_findings.append(f"rentang {span_days} hari < {min_days}")
    d6_check = CheckResult(
        code="D6",
        passed=len(d6_findings) == 0,
        count=len(d6_findings),
        message="Data tidak boleh di masa depan dan rentang memenuhi batas minimum",
        examples=tuple(d6_findings[:MAX_EXAMPLES]),
    )

    # Pemeriksaan D7: flag stockout dan promo hanya '0' atau '1'
    d7_findings: list[str] = []
    if has_stockout or has_promo:
        for r in parsed_sales:
            is_bad = False
            if has_stockout and r.raw_stockout not in ("0", "1"):
                is_bad = True
            if has_promo and r.raw_promo not in ("0", "1"):
                is_bad = True
            if is_bad:
                d7_findings.append(f"baris {r.line_num}")
    d7_check = CheckResult(
        code="D7",
        passed=len(d7_findings) == 0,
        count=len(d7_findings),
        message="Flag stockout dan promo hanya boleh bernilai 0 atau 1",
        examples=tuple(d7_findings[:MAX_EXAMPLES]),
    )

    return DatasetReport(
        sales_path=str(sales_path),
        products_path=str(products_path),
        sales_sha256=sales_sha256,
        products_sha256=products_sha256,
        sales_rows=sales_rows,
        product_count=product_count,
        date_min=date_min,
        date_max=date_max,
        checks=(
            schema_check,
            d1_check,
            d2_check,
            d3_check,
            d4_check,
            d5_check,
            d6_check,
            d7_check,
        ),
        warnings=tuple(warnings),
    )


def load_dataset(
    sales_path: Path | str,
    products_path: Path | str,
    *,
    today: date,
    min_days: int = DEFAULT_MIN_DAYS,
) -> TrainingData:
    """Memvalidasi dan memuat dataset latih bertipe."""
    report = validate_dataset(sales_path, products_path, today=today, min_days=min_days)
    if not report.ok:
        raise DatasetError(report)

    sales_p = Path(sales_path)
    products_p = Path(products_path)

    with products_p.open(encoding="utf-8-sig", newline="") as f:
        products_reader = csv.DictReader(f)
        products: dict[str, Product] = {}
        for row in products_reader:
            pid = row[COL_PRODUCT_ID]
            lu_raw = row.get(COL_LISTED_UNTIL, "")
            products[pid] = Product(
                product_id=pid,
                name=row[COL_NAME],
                category=row[COL_CATEGORY],
                price=int(row[COL_PRICE]),
                listed_from=date.fromisoformat(row[COL_LISTED_FROM]),
                listed_until=date.fromisoformat(lu_raw) if lu_raw else None,
                unit=row[COL_UNIT],
            )

    with sales_p.open(encoding="utf-8-sig", newline="") as f:
        sales_reader = csv.DictReader(f)
        sales_header = list(sales_reader.fieldnames or [])
        has_stockout = COL_STOCKOUT in sales_header
        has_promo = COL_PROMO in sales_header
        has_unit_price = COL_UNIT_PRICE in sales_header

        sales_list: list[SalesRow] = []
        for row in sales_reader:
            sales_list.append(
                SalesRow(
                    date=date.fromisoformat(row[COL_DATE]),
                    product_id=row[COL_PRODUCT_ID],
                    units_sold=int(row[COL_UNITS_SOLD]),
                    revenue=int(row[COL_REVENUE]),
                    stockout=int(row[COL_STOCKOUT]) if has_stockout else None,
                    promo=int(row[COL_PROMO]) if has_promo else None,
                    unit_price=int(row[COL_UNIT_PRICE]) if has_unit_price else None,
                )
            )

    sales_list.sort(key=lambda r: (r.product_id, r.date))
    return TrainingData(
        sales=tuple(sales_list),
        products=products,
        report=report,
    )


def format_report(report: DatasetReport) -> str:
    """Memformat laporan dataset menjadi teks yang mudah dibaca tim DS."""
    summary_line = (
        f"baris penjualan: {report.sales_rows}, produk: {report.product_count}, "
        f"tanggal: {report.date_min} s.d. {report.date_max}"
    )
    lines: list[str] = [
        f"sales: {report.sales_path} sha256={report.sales_sha256}",
        f"products: {report.products_path} sha256={report.products_sha256}",
        summary_line,
    ]
    for check in report.checks:
        if check.passed:
            lines.append(f"{check.code} LOLOS: {check.message}")
        else:
            if check.examples:
                examples_str = "; ".join(check.examples)
                lines.append(
                    f"{check.code} GAGAL ({check.count}): {check.message}. Contoh: {examples_str}"
                )
            else:
                lines.append(f"{check.code} GAGAL ({check.count}): {check.message}")
    for warning in report.warnings:
        lines.append(f"PERINGATAN: {warning}")
    lines.append("HASIL: LOLOS" if report.ok else "HASIL: GAGAL")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Titik masuk antarmuka baris perintah (CLI)."""
    parser = argparse.ArgumentParser(
        description="Pemuat dan pemeriksa dataset latih untuk HC Store AI."
    )
    parser.add_argument(
        "--sales",
        required=True,
        help="Path berkas CSV penjualan harian (sales_daily.csv)",
    )
    parser.add_argument(
        "--products",
        required=True,
        help="Path berkas CSV katalog produk (products.csv)",
    )
    parser.add_argument(
        "--min-days",
        type=int,
        default=DEFAULT_MIN_DAYS,
        help=f"Rentang hari minimum riwayat penjualan (bawaan: {DEFAULT_MIN_DAYS})",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Tanggal hari ini dalam format YYYY-MM-DD (bawaan: hari ini)",
    )

    args = parser.parse_args(argv)

    if args.today:
        today_date = _parse_strict_date(args.today)
        if today_date is None:
            sys.stderr.write(
                f"Format --today tidak valid: {args.today}. Gunakan format YYYY-MM-DD.\n"
            )
            return 1
    else:
        today_date = date.today()

    try:
        report = validate_dataset(
            args.sales,
            args.products,
            today=today_date,
            min_days=args.min_days,
        )
    except ValueError as e:
        sys.stderr.write(f"Kesalahan konfigurasi: {e}\n")
        return 1

    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

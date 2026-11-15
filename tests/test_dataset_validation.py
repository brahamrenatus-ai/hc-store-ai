"""Test acceptance pemuat dan pemeriksaan dataset latih (AE-FR-034).

Aturan: `docs/data-contract.md` §2.1 (bentuk berkas) dan §3 (pemeriksaan D1-D7).
Fixture sintetis: `tests/fixtures/forecast/` (3 produk x 60 hari, 2026-09-01 s.d. 2026-10-30).
"""

import csv
import datetime as dt
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ml.dataset import (
    CHECK_CODES,
    DEFAULT_MIN_DAYS,
    MAX_EXAMPLES,
    PRODUCTS_OPTIONAL,
    PRODUCTS_REQUIRED,
    SALES_OPTIONAL,
    SALES_REQUIRED,
    DatasetError,
    DatasetReport,
    Product,
    SalesRow,
    TrainingData,
    format_report,
    load_dataset,
    validate_dataset,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "forecast"
SALES = FIXTURES / "sales_daily_sample.csv"
PRODUCTS = FIXTURES / "products_sample.csv"
TODAY = dt.date(2026, 11, 14)
SAMPLE_DAYS = 60
D_CODES = ("D1", "D2", "D3", "D4", "D5", "D6", "D7")


# ---------------------------------------------------------------------------
# Alat bantu: salin fixture ke tmp_path lalu ubah barisnya
# ---------------------------------------------------------------------------


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, header: list[str], rows: list[dict[str, str]], encoding="utf-8") -> Path:
    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _copy(tmp_path: Path, sales_edit=None, products_edit=None, encoding="utf-8"):
    """Salin fixture; `*_edit(header, rows)` boleh mengubah list di tempat."""
    sh, sr = _read(SALES)
    ph, pr = _read(PRODUCTS)
    if sales_edit:
        sales_edit(sh, sr)
    if products_edit:
        products_edit(ph, pr)
    s = _write(tmp_path / "sales_daily.csv", sh, sr, encoding)
    p = _write(tmp_path / "products.csv", ph, pr, encoding)
    return s, p


def _validate(s, p, **kw) -> DatasetReport:
    kw.setdefault("today", TODAY)
    kw.setdefault("min_days", SAMPLE_DAYS)
    return validate_dataset(s, p, **kw)


def _check(report: DatasetReport, code: str):
    found = [c for c in report.checks if c.code == code]
    assert len(found) == 1, f"{code} tidak ada atau ganda di report.checks"
    return found[0]


def _line_of(rows: list[dict[str, str]], date: str, pid: str) -> int:
    """Nomor baris fisik CSV (header = baris 1) untuk pasangan (date, product_id)."""
    for i, r in enumerate(rows):
        if r["date"] == date and r["product_id"] == pid:
            return i + 2
    raise AssertionError("baris tidak ditemukan di fixture")


# ---------------------------------------------------------------------------
# Konstanta dan bentuk publik
# ---------------------------------------------------------------------------


def test_column_constants_follow_contract():
    assert SALES_REQUIRED == ("date", "product_id", "units_sold", "revenue")
    assert SALES_OPTIONAL == ("stockout", "promo", "unit_price")
    assert PRODUCTS_REQUIRED == ("product_id", "name", "category", "price", "listed_from", "unit")
    assert PRODUCTS_OPTIONAL == ("listed_until",)
    assert DEFAULT_MIN_DAYS == 180
    assert MAX_EXAMPLES == 5
    assert CHECK_CODES == ("SCHEMA", *D_CODES)


def test_sample_fixture_passes_all_checks():
    report = _validate(SALES, PRODUCTS)
    assert report.ok is True
    assert [c.code for c in report.checks] == list(CHECK_CODES)
    for c in report.checks:
        assert c.passed is True, c.code
        assert c.count == 0, c.code
        assert c.examples == (), c.code
        assert isinstance(c.message, str) and c.message, c.code
    assert report.sales_rows == 156
    assert report.product_count == 3
    assert report.date_min == dt.date(2026, 9, 1)
    assert report.date_max == dt.date(2026, 10, 30)
    assert report.warnings == ()


def test_report_records_source_and_sha256():
    report = _validate(SALES, PRODUCTS)
    assert report.sales_sha256 == hashlib.sha256(SALES.read_bytes()).hexdigest()
    assert report.products_sha256 == hashlib.sha256(PRODUCTS.read_bytes()).hexdigest()
    assert report.sales_path == str(SALES)
    assert report.products_path == str(PRODUCTS)


def test_accepts_str_paths():
    assert _validate(str(SALES), str(PRODUCTS)).ok is True


def test_default_min_days_rejects_60_day_sample_only_in_d6():
    report = validate_dataset(SALES, PRODUCTS, today=TODAY)
    assert report.ok is False
    d6 = _check(report, "D6")
    assert d6.passed is False
    assert d6.count == 1
    assert d6.examples == ("rentang 60 hari < 180",)
    for code in ("SCHEMA", "D1", "D2", "D3", "D4", "D5", "D7"):
        assert _check(report, code).passed is True, code


def test_min_days_must_be_positive():
    with pytest.raises(ValueError):
        validate_dataset(SALES, PRODUCTS, today=TODAY, min_days=0)


# ---------------------------------------------------------------------------
# load_dataset
# ---------------------------------------------------------------------------


def test_load_dataset_returns_typed_sorted_rows():
    data = load_dataset(SALES, PRODUCTS, today=TODAY, min_days=SAMPLE_DAYS)
    assert isinstance(data, TrainingData)
    assert data.report.ok is True
    assert len(data.sales) == 156
    keys = [(r.product_id, r.date) for r in data.sales]
    assert keys == sorted(keys)
    first = data.sales[0]
    assert first == SalesRow(
        date=dt.date(2026, 9, 1),
        product_id="P001",
        units_sold=0,
        revenue=0,
        stockout=1,
        promo=0,
        unit_price=None,
    )
    assert set(data.products) == {"P001", "P002", "P003"}
    assert data.products["P003"] == Product(
        product_id="P003",
        name="Sepatu Formal Sintetis C",
        category="formal",
        price=150000,
        listed_from=dt.date(2026, 9, 1),
        listed_until=dt.date(2026, 10, 20),
        unit="pairs",
    )
    assert data.products["P001"].listed_until is None


def test_load_dataset_without_optional_columns_gives_none(tmp_path):
    def drop(h, rows):
        h.remove("stockout")
        h.remove("promo")
        for r in rows:
            del r["stockout"], r["promo"]

    s, p = _copy(tmp_path, sales_edit=drop)
    data = load_dataset(s, p, today=TODAY, min_days=SAMPLE_DAYS)
    assert all(r.stockout is None and r.promo is None for r in data.sales)
    assert _check(data.report, "D7").passed is True


def test_load_dataset_raises_with_report_when_invalid(tmp_path):
    def dup(h, rows):
        rows.append(dict(rows[0]))

    s, p = _copy(tmp_path, sales_edit=dup)
    with pytest.raises(DatasetError) as exc:
        load_dataset(s, p, today=TODAY, min_days=SAMPLE_DAYS)
    assert isinstance(exc.value.report, DatasetReport)
    assert exc.value.report.ok is False
    assert "D1" in str(exc.value)


# ---------------------------------------------------------------------------
# D1 unik
# ---------------------------------------------------------------------------


def test_d1_duplicate_pair(tmp_path):
    def dup(h, rows):
        rows.insert(3, dict(rows[0]))

    s, p = _copy(tmp_path, sales_edit=dup)
    report = _validate(s, p)
    d1 = _check(report, "D1")
    assert (d1.passed, d1.count, d1.examples) == (False, 1, ("baris 5",))
    assert _check(report, "D2").passed is True


def test_d1_examples_are_capped(tmp_path):
    def dup(h, rows):
        rows.extend(dict(r) for r in rows[:8])

    s, p = _copy(tmp_path, sales_edit=dup)
    d1 = _check(_validate(s, p), "D1")
    assert d1.count == 8
    assert len(d1.examples) == MAX_EXAMPLES


# ---------------------------------------------------------------------------
# D2 satu baris per hari tanpa celah
# ---------------------------------------------------------------------------


def test_d2_missing_day(tmp_path):
    def remove(h, rows):
        rows[:] = [r for r in rows if not (r["date"] == "2026-09-10" and r["product_id"] == "P001")]

    s, p = _copy(tmp_path, sales_edit=remove)
    d2 = _check(_validate(s, p), "D2")
    assert (d2.passed, d2.count, d2.examples) == (False, 1, ("P001 2026-09-10",))


def test_d2_row_before_listed_from(tmp_path):
    def add(h, rows):
        rows.append(
            {
                "date": "2026-09-10",
                "product_id": "P002",
                "units_sold": "1",
                "revenue": "400000",
                "stockout": "0",
                "promo": "0",
            }
        )

    s, p = _copy(tmp_path, sales_edit=add)
    d2 = _check(_validate(s, p), "D2")
    assert (d2.passed, d2.count, d2.examples) == (False, 1, ("baris 158",))


def test_d2_row_after_listed_until(tmp_path):
    def add(h, rows):
        rows.append(
            {
                "date": "2026-10-25",
                "product_id": "P003",
                "units_sold": "0",
                "revenue": "0",
                "stockout": "0",
                "promo": "0",
            }
        )

    s, p = _copy(tmp_path, sales_edit=add)
    d2 = _check(_validate(s, p), "D2")
    assert (d2.passed, d2.count, d2.examples) == (False, 1, ("baris 158",))


def test_d2_product_without_rows_counts_each_missing_day(tmp_path):
    def add(h, rows):
        rows.append(
            {
                "product_id": "P004",
                "name": "Sandal Sintetis D",
                "category": "sandal",
                "price": "100000",
                "listed_from": "2026-10-28",
                "listed_until": "",
                "unit": "pairs",
            }
        )

    s, p = _copy(tmp_path, products_edit=add)
    d2 = _check(_validate(s, p), "D2")
    assert d2.count == 3
    assert d2.examples == ("P004 2026-10-28", "P004 2026-10-29", "P004 2026-10-30")


def test_d2_product_listed_after_data_end_is_not_missing(tmp_path):
    def add(h, rows):
        rows.append(
            {
                "product_id": "P005",
                "name": "Sandal Sintetis E",
                "category": "sandal",
                "price": "100000",
                "listed_from": "2026-11-05",
                "listed_until": "",
                "unit": "pairs",
            }
        )

    s, p = _copy(tmp_path, products_edit=add)
    report = _validate(s, p)
    assert report.ok is True
    assert report.product_count == 4


# ---------------------------------------------------------------------------
# D3 bilangan bulat >= 0, unit 0 => pendapatan 0
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("units", "revenue"),
    [("-1", "0"), ("2", "-5"), ("0", "250000")],
)
def test_d3_violations(tmp_path, units, revenue):
    def edit(h, rows):
        rows[1]["units_sold"] = units
        rows[1]["revenue"] = revenue

    s, p = _copy(tmp_path, sales_edit=edit)
    d3 = _check(_validate(s, p), "D3")
    assert (d3.passed, d3.count, d3.examples) == (False, 1, ("baris 3",))


# ---------------------------------------------------------------------------
# D4 product_id dikenal
# ---------------------------------------------------------------------------


def test_d4_unknown_product(tmp_path):
    def add(h, rows):
        rows.append(
            {
                "date": "2026-10-01",
                "product_id": "P999",
                "units_sold": "1",
                "revenue": "1000",
                "stockout": "0",
                "promo": "0",
            }
        )

    s, p = _copy(tmp_path, sales_edit=add)
    report = _validate(s, p)
    d4 = _check(report, "D4")
    assert (d4.passed, d4.count, d4.examples) == (False, 1, ("baris 158",))
    assert _check(report, "D2").passed is True
    assert _check(report, "D5").passed is True


# ---------------------------------------------------------------------------
# D5 revenue <= units_sold x harga
# ---------------------------------------------------------------------------


def test_d5_revenue_above_price(tmp_path):
    line = {}

    def edit(h, rows):
        line["n"] = _line_of(rows, "2026-09-02", "P001")
        rows[line["n"] - 2]["revenue"] = "1000001"  # 4 x 250000 = 1000000

    s, p = _copy(tmp_path, sales_edit=edit)
    d5 = _check(_validate(s, p), "D5")
    assert (d5.passed, d5.count, d5.examples) == (False, 1, (f"baris {line['n']}",))


def test_d5_revenue_equal_to_price_passes(tmp_path):
    def edit(h, rows):
        rows[_line_of(rows, "2026-09-02", "P001") - 2]["revenue"] = "1000000"

    s, p = _copy(tmp_path, sales_edit=edit)
    assert _check(_validate(s, p), "D5").passed is True


def _with_unit_price(price_of):
    def edit(h, rows):
        h.append("unit_price")
        for r in rows:
            r["unit_price"] = price_of(r)

    return edit


PRICE = {"P001": "250000", "P002": "400000", "P003": "150000"}


def test_d5_uses_unit_price_column_when_present(tmp_path):
    # Harga naik menjadi 300000: revenue 4 x 300000 lolos dengan unit_price,
    # padahal di atas 4 x price (250000).
    def edit(h, rows):
        _with_unit_price(lambda r: PRICE[r["product_id"]])(h, rows)
        r = rows[_line_of(rows, "2026-09-02", "P001") - 2]
        r["unit_price"] = "300000"
        r["revenue"] = "1200000"

    s, p = _copy(tmp_path, sales_edit=edit)
    report = _validate(s, p)
    assert report.ok is True
    assert report.warnings == ()


def test_d5_unit_price_violation(tmp_path):
    line = {}

    def edit(h, rows):
        _with_unit_price(lambda r: PRICE[r["product_id"]])(h, rows)
        line["n"] = _line_of(rows, "2026-09-02", "P001")
        rows[line["n"] - 2]["unit_price"] = "200000"  # revenue 1000000 > 4 x 200000

    s, p = _copy(tmp_path, sales_edit=edit)
    d5 = _check(_validate(s, p), "D5")
    assert (d5.passed, d5.count, d5.examples) == (False, 1, (f"baris {line['n']}",))


# ---------------------------------------------------------------------------
# D6 rentang tanggal dan masa depan
# ---------------------------------------------------------------------------


def test_d6_future_dates(tmp_path):
    report = _validate(SALES, PRODUCTS, today=dt.date(2026, 10, 28))
    d6 = _check(report, "D6")
    # 29 dan 30 Okt untuk P001 dan P002 (P003 berhenti 20 Okt)
    assert d6.passed is False
    assert d6.count == 4
    assert len(d6.examples) == 4
    assert all(e.startswith("baris ") for e in d6.examples)


def test_d6_today_equal_to_last_date_passes():
    assert _check(_validate(SALES, PRODUCTS, today=dt.date(2026, 10, 30)), "D6").passed is True


def test_d6_future_and_short_span_add_up():
    d6 = _check(validate_dataset(SALES, PRODUCTS, today=dt.date(2026, 10, 29)), "D6")
    assert d6.count == 3
    assert d6.examples[-1] == "rentang 60 hari < 180"


# ---------------------------------------------------------------------------
# D7 stockout dan promo hanya 0 atau 1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("column", "value"), [("stockout", "2"), ("promo", ""), ("promo", "ya")])
def test_d7_invalid_flag(tmp_path, column, value):
    def edit(h, rows):
        rows[4][column] = value

    s, p = _copy(tmp_path, sales_edit=edit)
    d7 = _check(_validate(s, p), "D7")
    assert (d7.passed, d7.count, d7.examples) == (False, 1, ("baris 6",))


def test_d7_row_with_both_flags_invalid_counts_once(tmp_path):
    def edit(h, rows):
        rows[4]["stockout"] = "2"
        rows[4]["promo"] = "2"

    s, p = _copy(tmp_path, sales_edit=edit)
    assert _check(_validate(s, p), "D7").count == 1


# ---------------------------------------------------------------------------
# SCHEMA: kolom wajib, tipe, dan isi; D1-D7 tidak dijalankan bila gagal
# ---------------------------------------------------------------------------


def _schema_only(report: DatasetReport):
    assert report.ok is False
    assert [c.code for c in report.checks] == ["SCHEMA"]
    return report.checks[0]


def test_schema_missing_sales_column(tmp_path):
    def drop(h, rows):
        h.remove("revenue")
        for r in rows:
            del r["revenue"]

    s, p = _copy(tmp_path, sales_edit=drop)
    c = _schema_only(_validate(s, p))
    assert c.count == 1
    assert "revenue" in c.examples[0]


def test_schema_missing_product_columns_counted_each(tmp_path):
    def drop(h, rows):
        for col in ("category", "unit"):
            h.remove(col)
            for r in rows:
                del r[col]

    s, p = _copy(tmp_path, products_edit=drop)
    c = _schema_only(_validate(s, p))
    assert c.count == 2


SALES_BAD_CELLS = [
    ("date", "2026/09/01"),
    ("date", "20260901"),
    ("date", "2026-02-30"),
    ("date", ""),
    ("product_id", ""),
    ("product_id", "P" * 65),
    ("units_sold", "1.0"),
    ("units_sold", "+5"),
    ("units_sold", " 5"),
    ("units_sold", ""),
    ("revenue", "1e6"),
    ("revenue", "abc"),
]


@pytest.mark.parametrize(("column", "value"), SALES_BAD_CELLS)
def test_schema_bad_sales_cell(tmp_path, column, value):
    def edit(h, rows):
        rows[2][column] = value

    s, p = _copy(tmp_path, sales_edit=edit)
    c = _schema_only(_validate(s, p))
    assert c.count == 1
    assert "baris 4" in c.examples[0]
    assert column in c.examples[0]


PRODUCT_BAD_CELLS = [
    ("product_id", ""),
    ("name", ""),
    ("name", "N" * 121),
    ("category", ""),
    ("unit", ""),
    ("price", "0"),
    ("price", "-100"),
    ("price", "250000.5"),
    ("listed_from", ""),
    ("listed_from", "01-09-2026"),
    ("listed_until", "2026-08-31"),
    ("listed_until", "kemarin"),
]


@pytest.mark.parametrize(("column", "value"), PRODUCT_BAD_CELLS)
def test_schema_bad_product_cell(tmp_path, column, value):
    def edit(h, rows):
        rows[0][column] = value

    s, p = _copy(tmp_path, products_edit=edit)
    c = _schema_only(_validate(s, p))
    assert c.count >= 1
    assert "baris 2" in c.examples[0]
    assert column in c.examples[0]


def test_schema_duplicate_product_id(tmp_path):
    def dup(h, rows):
        rows.append(dict(rows[0]))

    s, p = _copy(tmp_path, products_edit=dup)
    c = _schema_only(_validate(s, p))
    assert c.count == 1
    assert "baris 5" in c.examples[0]


def test_schema_empty_sales_file(tmp_path):
    def empty(h, rows):
        rows.clear()

    s, p = _copy(tmp_path, sales_edit=empty)
    assert _schema_only(_validate(s, p)).count == 1


def test_schema_unit_price_column_with_empty_cell(tmp_path):
    def edit(h, rows):
        _with_unit_price(lambda r: PRICE[r["product_id"]])(h, rows)
        rows[2]["unit_price"] = ""

    s, p = _copy(tmp_path, sales_edit=edit)
    c = _schema_only(_validate(s, p))
    assert "unit_price" in c.examples[0]


def test_schema_failure_is_reported_not_raised_by_validate(tmp_path):
    def drop(h, rows):
        h.remove("date")
        for r in rows:
            del r["date"]

    s, p = _copy(tmp_path, sales_edit=drop)
    report = _validate(s, p)
    assert report.sales_rows == 0
    assert report.date_min is None and report.date_max is None
    assert report.sales_sha256 == hashlib.sha256(s.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Kolom asing = peringatan; BOM UTF-8 diterima
# ---------------------------------------------------------------------------


def test_unknown_columns_warn_but_pass(tmp_path):
    def add_s(h, rows):
        h.append("catatan_ds")
        for r in rows:
            r["catatan_ds"] = "x"

    def add_p(h, rows):
        h.append("warna")
        for r in rows:
            r["warna"] = "hitam"

    s, p = _copy(tmp_path, sales_edit=add_s, products_edit=add_p)
    report = _validate(s, p)
    assert report.ok is True
    assert len(report.warnings) == 2
    assert any("catatan_ds" in w for w in report.warnings)
    assert any("warna" in w for w in report.warnings)


def test_utf8_bom_is_accepted(tmp_path):
    s, p = _copy(tmp_path, encoding="utf-8-sig")
    assert s.read_bytes().startswith(b"\xef\xbb\xbf")
    assert _validate(s, p).ok is True


# ---------------------------------------------------------------------------
# Laporan teks dan perintah baris
# ---------------------------------------------------------------------------


def test_format_report_lists_every_check_and_hash():
    report = _validate(SALES, PRODUCTS)
    text = format_report(report)
    for code in CHECK_CODES:
        assert f"{code} LOLOS" in text
    assert report.sales_sha256 in text
    assert report.products_sha256 in text
    assert text.rstrip().endswith("HASIL: LOLOS")


def test_format_report_shows_failure_count_and_examples(tmp_path):
    def remove(h, rows):
        rows[:] = [r for r in rows if not (r["date"] == "2026-09-10" and r["product_id"] == "P001")]

    s, p = _copy(tmp_path, sales_edit=remove)
    text = format_report(_validate(s, p))
    assert "D2 GAGAL (1)" in text
    assert "P001 2026-09-10" in text
    assert text.rstrip().endswith("HASIL: GAGAL")


def test_format_report_shows_warnings(tmp_path):
    def add(h, rows):
        h.append("catatan_ds")
        for r in rows:
            r["catatan_ds"] = ""

    s, p = _copy(tmp_path, sales_edit=add)
    assert "PERINGATAN" in format_report(_validate(s, p))


def _cli(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "ml.dataset", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_cli_exit_zero_when_valid():
    out = _cli(
        "--sales",
        str(SALES),
        "--products",
        str(PRODUCTS),
        "--min-days",
        "60",
        "--today",
        "2026-11-14",
    )
    assert out.returncode == 0, out.stderr
    assert "HASIL: LOLOS" in out.stdout
    assert hashlib.sha256(SALES.read_bytes()).hexdigest() in out.stdout


def test_cli_exit_one_with_default_min_days():
    out = _cli("--sales", str(SALES), "--products", str(PRODUCTS), "--today", "2026-11-14")
    assert out.returncode == 1, out.stderr
    assert "D6 GAGAL (1)" in out.stdout
    assert "HASIL: GAGAL" in out.stdout

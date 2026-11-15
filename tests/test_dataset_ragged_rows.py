"""Baris CSV yang selnya kurang dilaporkan sebagai temuan SCHEMA, bukan galat (AE-FR-034)."""

import datetime as dt
from pathlib import Path

from ml.dataset import validate_dataset

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "forecast"
TODAY = dt.date(2026, 11, 14)


def _truncate_line(src: Path, dst: Path, line_index: int, keep: int) -> Path:
    lines = src.read_text(encoding="utf-8").splitlines()
    lines[line_index] = ",".join(lines[line_index].split(",")[:keep])
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dst


def test_short_sales_row_is_schema_finding(tmp_path):
    sales = _truncate_line(FIXTURES / "sales_daily_sample.csv", tmp_path / "sales_daily.csv", 2, 2)
    report = validate_dataset(sales, FIXTURES / "products_sample.csv", today=TODAY, min_days=60)
    assert [c.code for c in report.checks] == ["SCHEMA"]
    assert report.checks[0].examples == ("sales_daily.csv baris 3 kolom units_sold, revenue",)


def test_short_products_row_is_schema_finding(tmp_path):
    products = _truncate_line(FIXTURES / "products_sample.csv", tmp_path / "products.csv", 1, 2)
    report = validate_dataset(
        FIXTURES / "sales_daily_sample.csv", products, today=TODAY, min_days=60
    )
    assert [c.code for c in report.checks] == ["SCHEMA"]
    assert report.checks[0].examples == (
        "products.csv baris 2 kolom category, price, listed_from, unit",
    )

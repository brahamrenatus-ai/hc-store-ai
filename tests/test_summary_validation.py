"""Test validasi request ringkasan harian dan mingguan (PRD AE-FR-020, AE-FR-061).

Mengunci skema request E2/E3 (`docs/api-contract.md` v0.3 §4, §5), aturan lintas
field, cek konsistensi (422 `INCONSISTENT_DATA`), dan catatan kualitas data
(PRD §15.7, AE-FR-020, AE-FR-061) memakai fixture emas sintetis di
`tests/fixtures/summaries/`.

Route berawalan `/api/v1/_t/` hanya dibuat di file ini; aplikasi tidak memilikinya.
"""

import copy
import datetime as dt
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import USER_MESSAGES, AppError
from app.main import create_app
from app.summaries.schemas import (
    MAX_INVENTORY_ITEMS,
    MAX_PRODUCT_SALES,
    DailySummaryRequest,
    WeeklySummaryRequest,
)
from app.summaries.validation import DataNote, today_in, validate_summary_request

FIXTURES = Path(__file__).parent / "fixtures" / "summaries"
TODAY = dt.date(2026, 12, 7)
KEY = "test-service-key-0123456789"
DELETE = object()

GOLDEN = {
    "daily_normal": [],
    "daily_empty": [],
    "daily_single_product": [
        ("NO_PREVIOUS_PERIOD", "previous_period"),
        ("NO_INVENTORY", "inventory"),
    ],
    "daily_tie": [],
    "weekly_normal": [],
    "weekly_gap": [
        ("NO_PREVIOUS_PERIOD", "previous_period"),
        ("PRODUCTS_MISSING_FROM_INVENTORY", "inventory.items"),
    ],
}


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def model_for(name):
    return WeeklySummaryRequest if name.startswith("weekly") else DailySummaryRequest


def endpoint_for(name):
    return "/api/v1/_t/weekly" if name.startswith("weekly") else "/api/v1/_t/daily"


_TOKEN = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def mutate(payload, path, value):
    """Ubah atau hapus nilai pada path bergaya `a.b[1].c` di salinan payload."""
    data = copy.deepcopy(payload)
    keys = [int(i) if i else k for k, i in _TOKEN.findall(path)]
    target = data
    for key in keys[:-1]:
        target = target[key]
    if value is DELETE:
        del target[keys[-1]]
    else:
        target[keys[-1]] = value
    return data


def notes_as_tuples(notes):
    return [(note.code, note.field) for note in notes]


def details_as_tuples(details):
    return [(d["field"], d["issue"]) for d in details]


@pytest.fixture(scope="module")
def client():
    app = create_app(Settings(service_api_key=KEY, _env_file=None))
    router = APIRouter(prefix="/api/v1/_t")

    @router.post("/daily")
    def daily(body: DailySummaryRequest):
        return {"notes": [[n.code, n.field] for n in validate_summary_request(body, TODAY)]}

    @router.post("/weekly")
    def weekly(body: WeeklySummaryRequest):
        return {"notes": [[n.code, n.field] for n in validate_summary_request(body, TODAY)]}

    app.include_router(router)
    return TestClient(app)


# --- Fixture emas -----------------------------------------------------------


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_fixture_is_valid(name):
    req = model_for(name).model_validate(load(name))
    notes = validate_summary_request(req, TODAY)
    assert all(isinstance(n, DataNote) for n in notes)
    assert notes_as_tuples(notes) == GOLDEN[name]


@pytest.mark.parametrize("name", sorted(GOLDEN))
def test_golden_fixture_over_http(client, name):
    resp = client.post(endpoint_for(name), json=load(name))
    assert resp.status_code == 200, resp.text
    assert [tuple(n) for n in resp.json()["notes"]] == GOLDEN[name]


def test_daily_breakdown_null_and_absent_both_accepted():
    with_null = load("daily_normal")
    assert with_null["sales"]["daily_breakdown"] is None
    assert "daily_breakdown" not in load("daily_single_product")["sales"]
    req = DailySummaryRequest.model_validate(with_null)
    assert req.sales.daily_breakdown is None


def test_options_default_language():
    req = DailySummaryRequest.model_validate(load("daily_single_product"))
    assert req.options.language == "id"


# --- Skema: 422 VALIDATION_ERROR dari Pydantic -----------------------------

LONG_ID = "P" * 65
LONG_NAME = "N" * 121

SCHEMA_CASES = [
    ("daily_normal", "prev_period", {"x": 1}, "prev_period"),
    ("daily_normal", "sales.prev_total", 1, "sales.prev_total"),
    ("daily_normal", "inventory.items[0].min_stock", 3, "inventory.items[0].min_stock"),
    ("daily_normal", "sales.product_sales[1].units_sold", "3", "sales.product_sales[1].units_sold"),
    ("daily_normal", "sales.transaction_count", True, "sales.transaction_count"),
    ("daily_normal", "sales.total_revenue", 4390000.0, "sales.total_revenue"),
    ("daily_normal", "sales.total_revenue", 4390000.5, "sales.total_revenue"),
    ("daily_normal", "sales.product_sales[0].revenue", -1, "sales.product_sales[0].revenue"),
    ("daily_normal", "sales.units_sold", -15, "sales.units_sold"),
    ("daily_normal", "sales.product_sales[0].product_id", "", "sales.product_sales[0].product_id"),
    (
        "daily_normal",
        "sales.product_sales[0].product_id",
        LONG_ID,
        "sales.product_sales[0].product_id",
    ),
    ("daily_normal", "sales.product_sales[0].name", "", "sales.product_sales[0].name"),
    ("daily_normal", "sales.product_sales[0].name", LONG_NAME, "sales.product_sales[0].name"),
    ("daily_normal", "sales.product_sales[1].product_id", "SH-0012", "sales.product_sales"),
    ("daily_normal", "inventory.items[1].product_id", "SH-0012", "inventory.items"),
    ("daily_normal", "inventory.items[0].current_stock", -1, "inventory.items[0].current_stock"),
    ("daily_normal", "inventory.items[0].reorder_level", -1, "inventory.items[0].reorder_level"),
    ("daily_normal", "inventory.snapshot_at", "2026-12-05T21:00:00", "inventory.snapshot_at"),
    ("daily_normal", "inventory.items", DELETE, "inventory.items"),
    ("daily_normal", "options.language", "en", "options.language"),
    ("daily_normal", "timezone", "Mars/Olympus", "timezone"),
    ("daily_normal", "timezone", DELETE, "timezone"),
    ("daily_normal", "date", "2026-02-30", "date"),
    ("daily_normal", "date", DELETE, "date"),
    ("daily_normal", "sales", DELETE, "sales"),
    ("daily_normal", "sales.product_sales", DELETE, "sales.product_sales"),
    ("daily_normal", "sales.daily_breakdown", [], "sales.daily_breakdown"),
    ("daily_normal", "previous_period.period.start", "2026-12-05", "previous_period.period"),
    ("daily_normal", "previous_period.daily_breakdown", [], "previous_period.daily_breakdown"),
    ("weekly_normal", "date", "2026-12-06", "date"),
    ("weekly_normal", "sales.daily_breakdown", DELETE, "sales.daily_breakdown"),
    (
        "weekly_normal",
        "sales.daily_breakdown[0].units_sold",
        -8,
        "sales.daily_breakdown[0].units_sold",
    ),
    ("weekly_normal", "sales.daily_breakdown[0].note", "x", "sales.daily_breakdown[0].note"),
]


@pytest.mark.parametrize(("name", "path", "value", "field"), SCHEMA_CASES)
def test_schema_rejection(client, name, path, value, field):
    resp = client.post(endpoint_for(name), json=mutate(load(name), path, value))
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["user_message"] == USER_MESSAGES["VALIDATION_ERROR"]
    assert {d["field"] for d in error["details"]} == {field}


def test_weekly_breakdown_longer_than_seven_rejected(client):
    payload = load("weekly_normal")
    payload["sales"]["daily_breakdown"].append(dict(payload["sales"]["daily_breakdown"][0]))
    resp = client.post("/api/v1/_t/weekly", json=payload)
    assert resp.status_code == 422
    assert {d["field"] for d in resp.json()["error"]["details"]} == {"sales.daily_breakdown"}


def _product_rows(count):
    return [
        {"product_id": f"P{i:04d}", "name": f"Produk {i}", "units_sold": 1, "revenue": 1000}
        for i in range(count)
    ]


@pytest.mark.parametrize(
    ("count", "status"), [(MAX_PRODUCT_SALES, 200), (MAX_PRODUCT_SALES + 1, 422)]
)
def test_product_sales_limit(client, count, status):
    payload = load("daily_single_product")
    payload["sales"].update(
        product_sales=_product_rows(count),
        units_sold=count,
        total_revenue=1000 * count,
        transaction_count=count,
    )
    resp = client.post("/api/v1/_t/daily", json=payload)
    assert resp.status_code == status, resp.text
    if status == 422:
        assert {d["field"] for d in resp.json()["error"]["details"]} == {"sales.product_sales"}


@pytest.mark.parametrize(
    ("count", "status"), [(MAX_INVENTORY_ITEMS, 200), (MAX_INVENTORY_ITEMS + 1, 422)]
)
def test_inventory_items_limit(client, count, status):
    payload = load("daily_normal")
    items = [
        {"product_id": f"I{i:05d}", "name": f"Stok {i}", "current_stock": 1, "reorder_level": None}
        for i in range(count)
    ]
    items[:4] = [
        {
            "product_id": p["product_id"],
            "name": p["name"],
            "current_stock": 1,
            "reorder_level": None,
        }
        for p in payload["sales"]["product_sales"]
    ]
    payload["inventory"]["items"] = items
    resp = client.post("/api/v1/_t/daily", json=payload)
    assert resp.status_code == status, resp.text
    if status == 422:
        assert {d["field"] for d in resp.json()["error"]["details"]} == {"inventory.items"}


def test_limits_match_contract():
    assert MAX_PRODUCT_SALES == 500
    assert MAX_INVENTORY_ITEMS == 2000


# --- Aturan lintas field: 422 VALIDATION_ERROR dari AppError ----------------

CROSS_FIELD_CASES = [
    (
        "daily_normal",
        {
            "date": "2026-12-08",
            "sales.period.start": "2026-12-08",
            "sales.period.end": "2026-12-08",
            "previous_period.period.start": "2026-12-07",
            "previous_period.period.end": "2026-12-07",
        },
        [("date", "Date is after today in the given timezone")],
    ),
    (
        "daily_normal",
        {"sales.period.end": "2026-12-06"},
        [("sales.period", "Period must start and end on date")],
    ),
    (
        "daily_normal",
        {"sales.period.start": "2026-12-04"},
        [("sales.period", "Period must start and end on date")],
    ),
    (
        "daily_normal",
        {"previous_period.period.start": "2026-12-03", "previous_period.period.end": "2026-12-03"},
        [("previous_period.period", "Previous period must be the day before date")],
    ),
    (
        "weekly_normal",
        {"sales.period.end": "2026-12-05"},
        [
            ("sales.period", "Weekly period must span exactly 7 days"),
            ("sales.daily_breakdown[6].date", "Date is outside sales.period"),
        ],
    ),
    (
        "weekly_normal",
        {"sales.daily_breakdown[0].date": "2026-11-29"},
        [("sales.daily_breakdown[0].date", "Date is outside sales.period")],
    ),
    (
        "weekly_normal",
        {"sales.daily_breakdown[3].date": "2026-12-02"},
        [("sales.daily_breakdown[3].date", "Duplicate date in daily_breakdown")],
    ),
    (
        "weekly_normal",
        {"previous_period.period.start": "2026-11-24"},
        [("previous_period.period", "Previous period must be the 7 days before sales.period")],
    ),
    (
        "weekly_normal",
        {"previous_period.period.end": "2026-11-28"},
        [("previous_period.period", "Previous period must be the 7 days before sales.period")],
    ),
]


def _apply(payload, changes):
    for path, value in changes.items():
        payload = mutate(payload, path, value)
    return payload


@pytest.mark.parametrize(("name", "changes", "expected"), CROSS_FIELD_CASES)
def test_cross_field_rejection(client, name, changes, expected):
    resp = client.post(endpoint_for(name), json=_apply(load(name), changes))
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["user_message"] == USER_MESSAGES["VALIDATION_ERROR"]
    assert error["retryable"] is False
    assert details_as_tuples(error["details"]) == expected


def test_weekly_period_ending_after_today_rejected():
    req = WeeklySummaryRequest.model_validate(load("weekly_normal"))
    with pytest.raises(AppError) as info:
        validate_summary_request(req, dt.date(2026, 12, 5))
    assert info.value.status_code == 422
    assert info.value.code == "VALIDATION_ERROR"
    assert details_as_tuples(info.value.details) == [
        ("sales.period", "Weekly period must end on or before today")
    ]


def test_weekly_period_ending_today_accepted():
    req = WeeklySummaryRequest.model_validate(load("weekly_normal"))
    assert validate_summary_request(req, dt.date(2026, 12, 6)) == []


def test_daily_date_today_accepted():
    req = DailySummaryRequest.model_validate(load("daily_normal"))
    assert validate_summary_request(req, dt.date(2026, 12, 5)) == []


# --- Konsistensi: 422 INCONSISTENT_DATA -------------------------------------

UNITS_ROWS = "Sum of product_sales.units_sold does not match units_sold"
REVENUE_ROWS = "Sum of product_sales.revenue does not match total_revenue"
ZERO_TX = "Zero transactions but non-zero units_sold or total_revenue"

CONSISTENCY_CASES = [
    ("daily_normal", {"sales.units_sold": 16}, [("sales.product_sales", UNITS_ROWS)]),
    ("daily_normal", {"sales.total_revenue": 4390001}, [("sales.product_sales", REVENUE_ROWS)]),
    (
        "daily_normal",
        {"sales.product_sales[0].units_sold": 7, "sales.product_sales[0].revenue": 1},
        [("sales.product_sales", UNITS_ROWS), ("sales.product_sales", REVENUE_ROWS)],
    ),
    ("daily_normal", {"sales.transaction_count": 0}, [("sales.transaction_count", ZERO_TX)]),
    ("daily_empty", {"sales.total_revenue": 50000}, [("sales.transaction_count", ZERO_TX)]),
    (
        "daily_normal",
        {"previous_period.units_sold": 10},
        [("previous_period.product_sales", UNITS_ROWS)],
    ),
    (
        "weekly_normal",
        {"sales.daily_breakdown[0].units_sold": 9},
        [
            (
                "sales.daily_breakdown",
                "Sum of daily_breakdown.units_sold does not match sales.units_sold",
            )
        ],
    ),
    (
        "weekly_normal",
        {
            "sales.daily_breakdown[2].total_revenue": 1900001,
            "sales.daily_breakdown[4].transaction_count": 8,
        },
        [
            (
                "sales.daily_breakdown",
                "Sum of daily_breakdown.total_revenue does not match sales.total_revenue",
            ),
            (
                "sales.daily_breakdown",
                "Sum of daily_breakdown.transaction_count does not match sales.transaction_count",
            ),
        ],
    ),
    (
        "weekly_gap",
        {"sales.units_sold": 19, "sales.product_sales[0].units_sold": 11},
        [
            (
                "sales.daily_breakdown",
                "Sum of daily_breakdown.units_sold does not match sales.units_sold",
            )
        ],
    ),
]


@pytest.mark.parametrize(("name", "changes", "expected"), CONSISTENCY_CASES)
def test_consistency_rejection(client, name, changes, expected):
    resp = client.post(endpoint_for(name), json=_apply(load(name), changes))
    assert resp.status_code == 422, resp.text
    error = resp.json()["error"]
    assert error["code"] == "INCONSISTENT_DATA"
    assert error["user_message"] == USER_MESSAGES["INCONSISTENT_DATA"]
    assert error["retryable"] is False
    assert details_as_tuples(error["details"]) == expected


def test_cross_field_checked_before_consistency(client):
    payload = _apply(
        load("daily_normal"), {"sales.period.end": "2026-12-06", "sales.units_sold": 16}
    )
    resp = client.post("/api/v1/_t/daily", json=payload)
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert details_as_tuples(error["details"]) == [
        ("sales.period", "Period must start and end on date")
    ]


# --- Catatan kualitas data ---------------------------------------------------

NOTE_CASES = [
    (
        "daily_normal",
        {"sales.product_sales": []},
        [("NO_PRODUCT_BREAKDOWN", "sales.product_sales")],
    ),
    (
        "daily_normal",
        {"previous_period.product_sales": []},
        [("NO_PRODUCT_BREAKDOWN", "previous_period.product_sales")],
    ),
    (
        "daily_normal",
        {"previous_period": DELETE, "inventory": DELETE},
        [("NO_PREVIOUS_PERIOD", "previous_period"), ("NO_INVENTORY", "inventory")],
    ),
    (
        "daily_normal",
        {"previous_period": None, "inventory": None},
        [("NO_PREVIOUS_PERIOD", "previous_period"), ("NO_INVENTORY", "inventory")],
    ),
    (
        "daily_normal",
        {"inventory.items[0].product_id": "SH-0099"},
        [("PRODUCTS_MISSING_FROM_INVENTORY", "inventory.items")],
    ),
    (
        "daily_normal",
        {"inventory.items": []},
        [("PRODUCTS_MISSING_FROM_INVENTORY", "inventory.items")],
    ),
    ("daily_empty", {"inventory.items": []}, []),
    (
        "weekly_normal",
        {"sales.product_sales": [], "previous_period": DELETE},
        [
            ("NO_PREVIOUS_PERIOD", "previous_period"),
            ("NO_PRODUCT_BREAKDOWN", "sales.product_sales"),
        ],
    ),
]


@pytest.mark.parametrize(("name", "changes", "expected"), NOTE_CASES)
def test_data_notes(name, changes, expected):
    req = model_for(name).model_validate(_apply(load(name), changes))
    assert notes_as_tuples(validate_summary_request(req, TODAY)) == expected


def test_unsold_inventory_items_do_not_create_notes():
    payload = load("daily_normal")
    sold = {p["product_id"] for p in payload["sales"]["product_sales"]}
    assert any(item["product_id"] not in sold for item in payload["inventory"]["items"])
    req = DailySummaryRequest.model_validate(payload)
    assert validate_summary_request(req, TODAY) == []


# --- Keamanan pesan error dan dokumentasi -----------------------------------

MARKER = "ZetaRahasia7781"


@pytest.mark.parametrize(
    ("name", "path", "value"),
    [
        ("daily_normal", "timezone", f"Mars/{MARKER}"),
        ("daily_normal", "sales.product_sales[0].product_id", MARKER * 5),
        ("daily_normal", "sales.product_sales[0].units_sold", MARKER),
        ("daily_normal", "options.language", MARKER),
        ("daily_normal", "date", MARKER),
        ("daily_normal", f"sales.{MARKER}", 1),
    ],
)
def test_error_never_echoes_payload_values(client, name, path, value):
    resp = client.post(endpoint_for(name), json=mutate(load(name), path, value))
    assert resp.status_code == 422
    for detail in resp.json()["error"]["details"]:
        assert MARKER not in detail["issue"]
    assert MARKER not in resp.json()["error"]["message"]


def test_consistency_error_has_no_numbers_from_payload(client):
    resp = client.post(
        "/api/v1/_t/daily", json=mutate(load("daily_normal"), "sales.total_revenue", 4390001)
    )
    assert resp.status_code == 422
    assert "4390001" not in resp.text
    assert "4390000" not in resp.text


def _properties(schema):
    yield from schema.get("properties", {}).items()
    for definition in schema.get("$defs", {}).values():
        yield from definition.get("properties", {}).items()


@pytest.mark.parametrize("model", [DailySummaryRequest, WeeklySummaryRequest])
def test_every_request_field_has_description(model):
    missing = [
        name for name, prop in _properties(model.model_json_schema()) if not prop.get("description")
    ]
    assert missing == []


def test_today_in_uses_timezone():
    tz = "Asia/Makassar"
    assert today_in(tz) == dt.datetime.now(ZoneInfo(tz)).date()

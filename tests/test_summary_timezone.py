"""Regresi: `timezone` yang tidak dikenal selalu 422, termasuk yang memicu galat sistem berkas.

`ZoneInfo` mencari nama zona sebagai path, jadi string sangat panjang melempar `OSError`
(bukan `ValueError`) di Windows dan lolos dari validasi Pydantic menjadi 500.
"""

import json
from pathlib import Path

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.summaries.schemas import DailySummaryRequest, WeeklySummaryRequest

FIXTURES = Path(__file__).parent / "fixtures" / "summaries"
KEY = "test-service-key-0123456789"

BAD_TIMEZONES = [
    "a" * 5000,
    "Asia/" + "x" * 300,
    "Asia/Jakarta\x00",
    "../../etc/passwd",
    "Asia/../Asia/Jakarta",
    "localtime",
    "",
]


@pytest.fixture(scope="module")
def client():
    app = create_app(Settings(service_api_key=KEY, _env_file=None))
    router = APIRouter(prefix="/api/v1/_tz")

    @router.post("/daily")
    def daily(body: DailySummaryRequest):
        return {}

    @router.post("/weekly")
    def weekly(body: WeeklySummaryRequest):
        return {}

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("fixture", ["daily_normal", "weekly_normal"])
@pytest.mark.parametrize("timezone", BAD_TIMEZONES, ids=range(len(BAD_TIMEZONES)))
def test_unknown_timezone_is_422(client, fixture, timezone):
    payload = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    payload["timezone"] = timezone
    kind = fixture.split("_")[0]
    resp = client.post(f"/api/v1/_tz/{kind}", json=payload, headers={"X-API-Key": KEY})
    assert resp.status_code == 422
    error = resp.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert [d["field"] for d in error["details"]] == ["timezone"]
    assert timezone[:20] not in json.dumps(error) or timezone == ""


@pytest.mark.parametrize("timezone", ["Asia/Makassar", "Asia/Jakarta", "UTC", "Etc/GMT-8"])
def test_known_timezone_is_accepted(timezone):
    payload = json.loads((FIXTURES / "daily_normal.json").read_text(encoding="utf-8"))
    payload["timezone"] = timezone
    assert DailySummaryRequest.model_validate(payload).timezone == timezone

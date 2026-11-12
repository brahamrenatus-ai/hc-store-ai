"""Test kerangka layanan (PRD AE-FR-041, AE-FR-043, AE-FR-050, AE-FR-073, AE-FR-081).

Mengunci perilaku bersama semua endpoint sesuai `docs/api-contract.md` v0.2:
health (E1), autentikasi X-API-Key, amplop respons dan error, request ID,
setelan dari environment, dan halaman dokumentasi API.

Route berawalan `/api/v1/_t/` hanya dibuat di file ini untuk menguji perilaku
bersama; aplikasi tidak memilikinya.
"""

import re
from datetime import datetime, timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import app as app_package
from app.config import Settings
from app.errors import USER_MESSAGES, AppError
from app.main import create_app
from app.security import require_api_key

KEY = "test-service-key-0123456789"
REQ_ID_GENERATED = re.compile(r"^req_[0-9a-f]{32}$")
CONTRACT_CODES = {
    "MALFORMED_JSON",
    "UNAUTHORIZED",
    "NOT_FOUND",
    "METHOD_NOT_ALLOWED",
    "PAYLOAD_TOO_LARGE",
    "UNSUPPORTED_MEDIA_TYPE",
    "VALIDATION_ERROR",
    "INCONSISTENT_DATA",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
    "PREDICTION_FAILED",
    "MODEL_UNAVAILABLE",
}


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")
    qty: int = Field(ge=0)


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    qty: int = Field(ge=0)
    lines: list[Line] = []


def make_settings(**overrides):
    values = {"service_api_key": KEY, "_env_file": None}
    values.update(overrides)
    return Settings(**values)


def build_app(**overrides):
    application = create_app(make_settings(**overrides))
    router = APIRouter(prefix="/api/v1/_t", dependencies=[Depends(require_api_key)])

    @router.get("/protected")
    def protected():
        return {"ok": True}

    @router.post("/items")
    def items(item: Item):
        return {"ok": True}

    @router.get("/boom")
    def boom():
        raise RuntimeError("SENTINEL-boom-detail")

    @router.get("/app-error")
    def app_error():
        raise AppError(
            status_code=422,
            code="INCONSISTENT_DATA",
            message="Totals disagree with rows.",
            details=[{"field": "sales.units_sold", "issue": "does not match product_sales"}],
        )

    application.include_router(router)
    return application


@pytest.fixture
def client():
    return TestClient(build_app(), raise_server_exceptions=False)


def assert_error(resp, status, code, retryable=False):
    assert resp.status_code == status, resp.text
    body = resp.json()
    assert set(body) == {"request_id", "error"}
    err = body["error"]
    assert set(err) == {"code", "message", "user_message", "retryable", "details"}
    assert err["code"] == code
    assert err["retryable"] is retryable
    assert err["user_message"] == USER_MESSAGES[code]
    assert isinstance(err["message"], str) and err["message"]
    assert isinstance(err["details"], list)
    assert resp.headers["X-Request-ID"] == body["request_id"]
    return err


# --- E1 health -------------------------------------------------------------


def test_health_shape_without_key(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"request_id", "data", "meta"}
    assert body["meta"] == {}
    data = body["data"]
    assert set(data) == {
        "status",
        "version",
        "modules",
        "model_loaded",
        "provider_configured",
        "timestamp",
    }
    assert data["version"] == app_package.__version__ == "0.1.0"
    assert data["model_loaded"] is False
    assert data["provider_configured"] is False
    assert data["modules"] == {"summaries": "degraded", "predictions": "unavailable"}
    assert data["status"] == "degraded"


def test_health_timestamp_uses_store_timezone(client):
    ts = datetime.fromisoformat(client.get("/api/v1/health").json()["data"]["timestamp"])
    assert ts.utcoffset() == timedelta(hours=8)


def test_health_ok_when_provider_configured_and_model_loaded():
    application = create_app(make_settings(gemini_api_key="fake-provider-key"))
    application.state.model_loaded = True
    data = TestClient(application).get("/api/v1/health").json()["data"]
    assert data["provider_configured"] is True
    assert data["model_loaded"] is True
    assert data["modules"] == {"summaries": "ok", "predictions": "ok"}
    assert data["status"] == "ok"


def test_health_ignores_wrong_key(client):
    assert client.get("/api/v1/health", headers={"X-API-Key": "wrong"}).status_code == 200


def test_health_rejects_post(client):
    assert_error(client.post("/api/v1/health"), 405, "METHOD_NOT_ALLOWED")


# --- Request ID --------------------------------------------------------------


def test_request_id_echoed(client):
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "fs_ABC-123"})
    assert resp.headers["X-Request-ID"] == "fs_ABC-123"
    assert resp.json()["request_id"] == "fs_ABC-123"


@pytest.mark.parametrize("sent", [None, "bad id!", "x" * 65, ""])
def test_request_id_generated_when_absent_or_invalid(client, sent):
    headers = {} if sent is None else {"X-Request-ID": sent}
    resp = client.get("/api/v1/health", headers=headers)
    rid = resp.headers["X-Request-ID"]
    assert REQ_ID_GENERATED.match(rid), rid
    assert resp.json()["request_id"] == rid


def test_request_id_on_error_responses(client):
    resp = client.get("/api/v1/_t/protected", headers={"X-Request-ID": "fs_err_1"})
    assert resp.headers["X-Request-ID"] == "fs_err_1"
    assert resp.json()["request_id"] == "fs_err_1"


# --- Autentikasi -------------------------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": ""}, {"X-API-Key": "wrong-key"}])
def test_protected_route_rejects_missing_or_wrong_key(client, headers):
    assert_error(client.get("/api/v1/_t/protected", headers=headers), 401, "UNAUTHORIZED")


def test_protected_route_rejects_non_ascii_key_with_401(client):
    resp = client.get("/api/v1/_t/protected", headers={"X-API-Key": "kunci-é".encode("latin-1")})
    assert_error(resp, 401, "UNAUTHORIZED")


def test_protected_route_accepts_correct_key(client):
    resp = client.get("/api/v1/_t/protected", headers={"X-API-Key": KEY})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


# --- Error schema ------------------------------------------------------------


def test_user_messages_cover_contract_codes():
    assert set(USER_MESSAGES) == CONTRACT_CODES
    assert all(isinstance(m, str) and m for m in USER_MESSAGES.values())


def test_unknown_route_is_404_envelope(client):
    assert_error(client.get("/api/v1/does-not-exist"), 404, "NOT_FOUND")


def test_malformed_json_is_400(client):
    resp = client.post(
        "/api/v1/_t/items",
        content=b'{"name": ',
        headers={"X-API-Key": KEY, "Content-Type": "application/json"},
    )
    err = assert_error(resp, 400, "MALFORMED_JSON")
    assert err["details"] == []


def test_unknown_field_is_422_without_echoing_value(client):
    resp = client.post(
        "/api/v1/_t/items",
        json={"name": "Sandal", "qty": 1, "extra_field": "SENTINEL-extra-value"},
        headers={"X-API-Key": KEY},
    )
    err = assert_error(resp, 422, "VALIDATION_ERROR")
    assert {"field": "extra_field", "issue": "Extra inputs are not permitted"} in err["details"]
    assert "SENTINEL" not in resp.text


def test_nested_field_path_uses_brackets_for_list_index(client):
    resp = client.post(
        "/api/v1/_t/items",
        json={"name": "Sandal", "qty": 1, "lines": [{"qty": 1}, {"qty": -1}]},
        headers={"X-API-Key": KEY},
    )
    err = assert_error(resp, 422, "VALIDATION_ERROR")
    assert [d["field"] for d in err["details"]] == ["lines[1].qty"]
    assert set(err["details"][0]) == {"field", "issue"}


def test_wrong_type_does_not_echo_value(client):
    resp = client.post(
        "/api/v1/_t/items",
        json={"name": "Sandal", "qty": "SENTINEL-not-a-number"},
        headers={"X-API-Key": KEY},
    )
    err = assert_error(resp, 422, "VALIDATION_ERROR")
    assert [d["field"] for d in err["details"]] == ["qty"]
    assert "SENTINEL" not in resp.text


def test_missing_body_reports_body_field(client):
    resp = client.post("/api/v1/_t/items", headers={"X-API-Key": KEY})
    err = assert_error(resp, 422, "VALIDATION_ERROR")
    assert [d["field"] for d in err["details"]] == ["body"]


def test_auth_checked_before_body_validation(client):
    resp = client.post("/api/v1/_t/items", json={"unexpected": 1})
    assert_error(resp, 401, "UNAUTHORIZED")


def test_app_error_rendered(client):
    err = assert_error(
        client.get("/api/v1/_t/app-error", headers={"X-API-Key": KEY}), 422, "INCONSISTENT_DATA"
    )
    assert err["message"] == "Totals disagree with rows."
    expected = [{"field": "sales.units_sold", "issue": "does not match product_sales"}]
    assert err["details"] == expected


def test_unhandled_exception_is_500_without_detail(client):
    resp = client.get("/api/v1/_t/boom", headers={"X-API-Key": KEY, "X-Request-ID": "fs_boom_1"})
    assert_error(resp, 500, "INTERNAL_ERROR", retryable=True)
    assert resp.json()["request_id"] == "fs_boom_1"
    assert "SENTINEL" not in resp.text


# --- Setelan -----------------------------------------------------------------


def test_settings_require_service_key(monkeypatch):
    monkeypatch.delenv("SERVICE_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_reject_short_service_key():
    with pytest.raises(ValidationError):
        make_settings(service_api_key="short")


def test_settings_reject_unknown_timezone():
    with pytest.raises(ValidationError):
        make_settings(app_timezone="Mars/Base")


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("SERVICE_API_KEY", "SENTINEL-env-key-0123456789")
    monkeypatch.setenv("DOCS_ENABLED", "false")
    settings = Settings(_env_file=None)
    assert settings.service_api_key.get_secret_value() == "SENTINEL-env-key-0123456789"
    assert settings.docs_enabled is False
    assert settings.app_timezone == "Asia/Makassar"
    assert settings.provider_configured is False
    assert "SENTINEL" not in repr(settings)


# --- Dokumentasi API ---------------------------------------------------------


def test_docs_enabled(client):
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert spec["info"]["title"] == "HC Store AI"
    assert spec["info"]["version"] == "0.1.0"
    health = spec["paths"]["/api/v1/health"]["get"]
    assert health["summary"] and health["description"]


def test_docs_disabled():
    client = TestClient(build_app(docs_enabled=False))
    assert_error(client.get("/docs"), 404, "NOT_FOUND")
    assert_error(client.get("/openapi.json"), 404, "NOT_FOUND")

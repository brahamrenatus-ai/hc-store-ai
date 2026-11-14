"""Skrip SMOKE TASK-001 untuk skenario K1-K7 menggunakan TestClient."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from starlette.testclient import TestClient  # noqa: E402

from app.agent_workflow.executor import Executor, _ClientError  # noqa: E402
from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "summaries"


async def mock_call_provider(self, system_prompt: str, user_prompt: str, timeout: float) -> str:
    """Mock provider: simulasi kegagalan pemanggilan penyedia agar memicu template_fallback."""
    raise _ClientError("provider simulated unavailable")


def shift_daily(data: dict, target_date: str = "2026-11-13", prev_date: str = "2026-11-12") -> dict:
    raw = json.dumps(data)
    shifted = raw.replace("2026-12-05", target_date).replace("2026-12-04", prev_date)
    return json.loads(shifted)


def shift_weekly(data: dict, days_back: int = 28) -> dict:
    raw = json.dumps(data)

    def repl(m: re.Match) -> str:
        d = dt.date.fromisoformat(m.group(0))
        return (d - dt.timedelta(days=days_back)).isoformat()

    shifted = re.sub(r"2026-\d{2}-\d{2}", repl, raw)
    return json.loads(shifted)


def main() -> None:
    settings = Settings(
        service_api_key="test-key-smoke-123456",
        gemini_api_key="dummy",
        _env_file=None,
    )
    application = create_app(settings)
    client = TestClient(application)
    headers = {"X-API-Key": "test-key-smoke-123456"}

    with patch.object(Executor, "_call_provider", mock_call_provider):
        # K1: GET /api/v1/health tanpa key
        r1 = client.get("/api/v1/health")
        k1_status = r1.status_code
        k1_data_status = r1.json().get("data", {}).get("status", "")
        print(f"K1: HTTP {k1_status}, data.status = {k1_data_status}")

        # K2: POST /api/v1/summaries/daily tanpa header X-API-Key
        r2 = client.post("/api/v1/summaries/daily")
        k2_status = r2.status_code
        k2_err_code = r2.json().get("error", {}).get("code", "")
        print(f"K2: HTTP {k2_status}, error.code = {k2_err_code}")

        # K3: POST /api/v1/summaries/daily dengan header valid dan payload valid
        d3 = json.loads((FIXTURES / "daily_normal.json").read_text(encoding="utf-8"))
        p3 = shift_daily(d3)
        r3 = client.post("/api/v1/summaries/daily", json=p3, headers=headers)
        k3_status = r3.status_code
        k3_gen_mode = r3.json().get("data", {}).get("generation_mode", "")
        print(f"K3: HTTP {k3_status}, generation_mode = {k3_gen_mode}")

        # K4: POST /api/v1/summaries/daily dengan transaction_count: 0
        d4 = json.loads((FIXTURES / "daily_empty.json").read_text(encoding="utf-8"))
        p4 = shift_daily(d4)
        r4 = client.post("/api/v1/summaries/daily", json=p4, headers=headers)
        k4_status = r4.status_code
        k4_gen_mode = r4.json().get("data", {}).get("generation_mode", "")
        k4_text = r4.json().get("data", {}).get("summary_text", "")
        print(f"K4: HTTP {k4_status}, generation_mode = {k4_gen_mode}, teks: {k4_text}")

        # K5: POST /api/v1/summaries/weekly dengan payload mingguan valid
        d5 = json.loads((FIXTURES / "weekly_normal.json").read_text(encoding="utf-8"))
        p5 = shift_weekly(d5)
        r5 = client.post("/api/v1/summaries/weekly", json=p5, headers=headers)
        k5_status = r5.status_code
        k5_summary_type = r5.json().get("data", {}).get("summary_type", "")
        print(f"K5: HTTP {k5_status}, summary_type = {k5_summary_type}")

        # K6: POST /api/v1/summaries/daily dengan field tambahan
        p6 = shift_daily(d3)
        p6["extra_field"] = 1
        r6 = client.post("/api/v1/summaries/daily", json=p6, headers=headers)
        k6_status = r6.status_code
        k6_err_code = r6.json().get("error", {}).get("code", "")
        print(f"K6: HTTP {k6_status}, error.code = {k6_err_code}")

        # K7: POST /api/v1/summaries/daily dengan total_revenue negatif
        p7 = shift_daily(d3)
        p7["sales"]["total_revenue"] = -100
        r7 = client.post("/api/v1/summaries/daily", json=p7, headers=headers)
        k7_status = r7.status_code
        k7_err_code = r7.json().get("error", {}).get("code", "")
        print(f"K7: HTTP {k7_status}, error.code = {k7_err_code}")


if __name__ == "__main__":
    main()

# TASK-001: Baseline SMOKE — health, auth, validasi, ringkasan, lint, test, server
- Jenis: SMOKE · Roadmap: R1 · Anggaran: – · Status: DONE · Butuh executor: MEDIUM · Model: Gemini 3.8 Flash (high), alasan: checklist literal, kapasitas MEDIUM cukup
- Prasyarat: kode pipeline ringkasan sudah di-commit (U1) · `.env` tersedia di mesin lokal
- Disetujui: Ivan 14 Nov 2026 (B1)
- Triase head: lolos 14 Nov 2026 (K2 FAIL = head error di Harapan, K8 FAIL = environment issue → FIX di Batch 2)

## Mengapa
Belum ada baseline SMOKE yang memverifikasi fondasi layanan end-to-end. Kode pipeline ringkasan baru ditulis dan lint baru diperbaiki. Sebelum menulis test pipeline (R2) atau fitur baru, kita perlu memastikan semua yang sudah ada bekerja sesuai spec.

## Yang perlu dipahami
- Checklist SMOKE di `handoff/README.md` §SMOKE (10 item).
- Endpoint health (`app/api/health.py`): GET `/api/v1/health`, mengembalikan `data.status` = `ok`/`degraded`.
- Endpoint ringkasan (`app/api/summaries.py`): POST `/api/v1/summaries/daily` dan `/weekly`, dilindungi API key.
- Auth: header `X-API-Key` dicek terhadap `SERVICE_API_KEY` di `.env`.
- Validasi: field tambahan ditolak 422; `total_revenue` negatif ditolak 422.

## Rujukan
- `handoff/README.md` §SMOKE (checklist)
- `docs/prd-ae.md` AE-FR-041 (health), AE-FR-043 (auth), AE-FR-040 (validasi)
- `app/api/health.py` (endpoint health)
- `app/api/summaries.py` (endpoint ringkasan)
- `app/security.py` (auth middleware)
- `tests/test_api_foundation.py` (test yang sudah ada)

## Tujuan
Jalankan seluruh checklist SMOKE dan laporkan status setiap item (OK/FAIL/UNTESTED) beserta bukti.

## Kriteria terima
Setiap item SMOKE dinilai OK, FAIL, atau UNTESTED, dengan bukti log dari `record.py`.

| Kriteria | Harapan | Teramati | Bukti | Status |
|---|---|---|---|---|
| K1: Health endpoint HTTP 200, `data.status` ∈ {ok, degraded} | HTTP 200, `data.status` = `degraded` (model belum di-load, provider belum dikonfigurasi dengan benar) | | | |
| K2: Request tanpa API key ditolak HTTP 401, kode error `AUTH_ERROR` | HTTP 401, `error.code` = `AUTH_ERROR` | | | |
| K3: Request ringkasan harian data valid HTTP 200, `generation_mode` ∈ {ai, template_fallback, no_data} | HTTP 200, `generation_mode` salah satu dari tiga nilai itu | | | |
| K4: Request harian `transaction_count: 0` → `generation_mode: "no_data"`, teks "Belum ada data penjualan untuk periode ini." | `generation_mode` = `no_data`, teks mengandung kalimat itu | | | |
| K5: Request ringkasan mingguan data valid HTTP 200, `summary_type: "weekly"` | HTTP 200, `summary_type` = `weekly` | | | |
| K6: Request dengan field tambahan ditolak HTTP 422, kode `VALIDATION_ERROR` | HTTP 422, `error.code` = `VALIDATION_ERROR` | | | |
| K7: Request dengan `total_revenue` negatif ditolak HTTP 422 | HTTP 422 | | | |
| K8: Semua test `pytest -q` lulus | 144 passed (atau lebih, tanpa failure) | | | |
| K9: Lint `ruff check app/ tests/` bersih | `All checks passed!` | | | |
| K10: Server menyala dan menjawab health tanpa crash | `serve_check.py` exit code 0, output mengandung HTTP 200 | | | |

## Batasan
- **Semua test menggunakan provider tiruan** (mock/TestClient). Tidak ada panggilan LLM sungguhan. Anggaran LLM: 0 panggilan.
- Jangan mengubah kode app atau test. Task ini hanya mengecek, bukan memperbaiki.
- Untuk K3 dan K5 (ringkasan harian/mingguan data valid): gunakan payload dari test yang sudah ada (`tests/test_api_foundation.py` atau `tests/test_summary_validation.py`) atau buat payload minimal yang valid. Karena tidak ada `.env` dengan `GEMINI_API_KEY` yang valid, respons kemungkinan `template_fallback` atau `no_data` — ini OK selama `generation_mode` ada dan bernilai salah satu dari ketiga mode.
- K10 memerlukan `.env` dengan minimal `SERVICE_API_KEY`. Jalankan `python handoff/tools/serve_check.py`. Bila `.env` belum ada, tandai UNTESTED dengan alasan.

## Langkah
1. `python handoff/tools/record.py handoff/logs/TASK-001-pytest.log ".venv\Scripts\python.exe -m pytest -q"` → K8.
2. `python handoff/tools/record.py handoff/logs/TASK-001-ruff.log ".venv\Scripts\python.exe -m ruff check app/ tests/"` → K9.
3. `python handoff/tools/record.py handoff/logs/TASK-001-serve.log ".venv\Scripts\python.exe handoff/tools/serve_check.py"` → K10. Bila gagal karena `.env`, tandai UNTESTED.
4. Tulis skrip penganalisis `handoff/tools/smoke_001.py` yang menjalankan skenario K1–K7 lewat `TestClient` (tanpa server nyata) dan mencetak hasilnya dalam format tabel. Jalankan lewat `record.py`:
   `python handoff/tools/record.py handoff/logs/TASK-001-smoke.log ".venv\Scripts\python.exe handoff/tools/smoke_001.py"`
5. Salin hasil ke tabel Data di report. Jalankan `python handoff/tools/check_evidence.py handoff/reports/REPORT-001.md` sebelum DONE.

## Sketsa desain
Skrip `smoke_001.py`:
- Import `TestClient` dari `starlette.testclient`, `create_app` dari `app.main`, `Settings` dari `app.config`.
- Buat app dengan `Settings(service_api_key="test-key-smoke", gemini_api_key="dummy")`.
- K1: `GET /api/v1/health` tanpa key → cek 200, `resp.json()["data"]["status"]` ∈ {"ok", "degraded"}.
- K2: `POST /api/v1/summaries/daily` tanpa header `X-API-Key` → cek 401, `resp.json()["error"]["code"]` == "AUTH_ERROR".
- K3: `POST /api/v1/summaries/daily` dengan header `X-API-Key: test-key-smoke` dan payload harian valid → cek 200, `generation_mode` ada.
- K4: Payload harian dengan `transaction_count: 0`, semua sales kosong → cek `generation_mode` == "no_data".
- K5: `POST /api/v1/summaries/weekly` dengan payload mingguan valid → cek 200, `summary_type` == "weekly".
- K6: Payload harian dengan field tambahan `{"extra_field": 1}` → cek 422, `error.code` == "VALIDATION_ERROR".
- K7: Payload harian dengan `total_revenue: -100` → cek 422.
- Cetak tabel ringkasan per K.

## Verifikasi
```
.venv\Scripts\python.exe -m pytest -q
# Harapan: 144 passed (atau lebih), 0 failed

.venv\Scripts\python.exe -m ruff check app/ tests/
# Harapan: All checks passed!

.venv\Scripts\python.exe handoff/tools/serve_check.py
# Harapan: HTTP 200 (bila .env ada)
```

## Langkah Penutup
Setelah DONE, head akan memverifikasi setiap OK di report terhadap log dan output skrip.

## Ringkasan untuk tim
**File yang berubah:** `handoff/tools/smoke_001.py` (baru, 113 baris — skrip pengujian SMOKE).

**Apa yang dilakukan:** Executor menjalankan 10 item checklist SMOKE: health endpoint, auth, validasi request (field tambahan, revenue negatif), ringkasan harian (data valid, tanpa transaksi), ringkasan mingguan, linting, test suite, dan server check. 7 dari 10 item lolos. Skrip `smoke_001.py` menguji K1–K7 lewat TestClient dengan provider LLM di-mock agar fallback template deterministik. Lint bersih, server menyala.

**2 FAIL yang ditemukan:**
- K2: kode error auth di implementasi adalah `UNAUTHORIZED` (`app/security.py:22`), bukan `AUTH_ERROR` seperti di checklist SMOKE lama. Head sudah memperbaiki checklist.
- K8: 2 test gagal (`test_health_shape_without_key`, `test_settings_read_environment`) karena `GEMINI_API_KEY` ada di environment lokal → `provider_configured` = True, test menguji False. Perlu FIX: isolasi env di test.

**Cara cek sendiri:**
```powershell
.venv\Scripts\python.exe handoff/tools/smoke_001.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check app/ tests/
```

**Langkah berikutnya:** FIX 2 test yang gagal (Batch 2), lalu test pipeline ringkasan (R2).

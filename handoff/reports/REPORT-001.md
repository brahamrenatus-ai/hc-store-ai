# REPORT-001: Baseline SMOKE — health, auth, validasi, ringkasan, lint, test, server
- Task: TASK-001
- Status akhir: DONE
- Pelaksana (model): Gemini 3.8 Flash (high)

## Ringkasan Fakta
- Lint `ruff check app/ tests/` bersih: `All checks passed!` (`handoff/logs/TASK-001-ruff.log:1`).
- Server FastAPI menyala dan menjawab health check melalui `serve_check.py`: `HTTP 200` (`handoff/logs/TASK-001-serve.log:1`).
- Pengujian suite test `pytest -q` mencatat `2 failed, 142 passed in 2.81s` (`handoff/logs/TASK-001-pytest.log:49`).
- Endpoint health (`GET /api/v1/health`) mengembalikan `K1: HTTP 200, data.status = degraded` (`handoff/logs/TASK-001-smoke.log:1`).
- Endpoint ringkasan tanpa API key mengembalikan `K2: HTTP 401, error.code = UNAUTHORIZED` (`handoff/logs/TASK-001-smoke.log:2`).
- Ringkasan harian data valid menghasilkan `K3: HTTP 200, generation_mode = template_fallback` (`handoff/logs/TASK-001-smoke.log:4`).
- Ringkasan harian dengan transaksi kosong menghasilkan `K4: HTTP 200, generation_mode = no_data, teks: Belum ada data penjualan untuk periode ini.` (`handoff/logs/TASK-001-smoke.log:5`).
- Ringkasan mingguan data valid menghasilkan `K5: HTTP 200, summary_type = weekly` (`handoff/logs/TASK-001-smoke.log:7`).
- Validasi field ekstra dan total_revenue negatif menolak dengan `K6: HTTP 422, error.code = VALIDATION_ERROR` (`handoff/logs/TASK-001-smoke.log:8`) dan `K7: HTTP 422, error.code = VALIDATION_ERROR` (`handoff/logs/TASK-001-smoke.log:9`).

## Keputusan Implementasi
- Skrip penguji SMOKE dibuat di `handoff/tools/smoke_001.py` menggunakan `TestClient` dari Starlette dan konfigurasi aplikasi `app.main.create_app` dengan `Settings(service_api_key="test-key-smoke-123456", gemini_api_key="dummy", _env_file=None)`.
- Menggunakan fixture emas di `tests/fixtures/summaries/` dengan penyesuaian tanggal relatif agar tidak melanggar aturan validasi tanggal masa depan (`date <= today`).
- Sesuai batasan task (anggaran LLM 0 panggilan), panggilan penyedia LLM pada K3 dan K5 di-mock menggunakan patch pada `Executor._call_provider` yang mensimulasikan kegagalan penyedia, sehingga pipeline ringkasan secara deterministik menjalankan jalur fallback template (`template_fallback`).

## Data
| Kriteria | Harapan | Teramati | Bukti | Status |
|---|---|---|---|---|
| K1: Health endpoint HTTP 200, `data.status` ∈ {ok, degraded} | HTTP 200, `data.status` = `degraded` (model belum di-load, provider belum dikonfigurasi dengan benar) | HTTP 200, data.status = degraded | handoff/logs/TASK-001-smoke.log:1 | OK |
| K2: Request tanpa API key ditolak HTTP 401, kode error `AUTH_ERROR` | HTTP 401, `error.code` = `AUTH_ERROR` | HTTP 401, error.code = UNAUTHORIZED | handoff/logs/TASK-001-smoke.log:2 | FAIL |
| K3: Request ringkasan harian data valid HTTP 200, `generation_mode` ∈ {ai, template_fallback, no_data} | HTTP 200, `generation_mode` salah satu dari tiga nilai itu | HTTP 200, generation_mode = template_fallback | handoff/logs/TASK-001-smoke.log:4 | OK |
| K4: Request harian `transaction_count: 0` → `generation_mode: "no_data"`, teks "Belum ada data penjualan untuk periode ini." | `generation_mode` = `no_data`, teks mengandung kalimat itu | generation_mode = no_data, teks: Belum ada data penjualan untuk periode ini. | handoff/logs/TASK-001-smoke.log:5 | OK |
| K5: Request ringkasan mingguan data valid HTTP 200, `summary_type: "weekly"` | HTTP 200, `summary_type` = `weekly` | HTTP 200, summary_type = weekly | handoff/logs/TASK-001-smoke.log:7 | OK |
| K6: Request dengan field tambahan ditolak HTTP 422, kode `VALIDATION_ERROR` | HTTP 422, `error.code` = `VALIDATION_ERROR` | HTTP 422, error.code = VALIDATION_ERROR | handoff/logs/TASK-001-smoke.log:8 | OK |
| K7: Request dengan `total_revenue` negatif ditolak HTTP 422 | HTTP 422 | HTTP 422, error.code = VALIDATION_ERROR | handoff/logs/TASK-001-smoke.log:9 | OK |
| K8: Semua test `pytest -q` lulus | 144 passed (atau lebih, tanpa failure) | 2 failed, 142 passed in 2.81s | handoff/logs/TASK-001-pytest.log:49 | FAIL |
| K9: Lint `ruff check app/ tests/` bersih | `All checks passed!` | All checks passed! | handoff/logs/TASK-001-ruff.log:1 | OK |
| K10: Server menyala dan menjawab health tanpa crash | `serve_check.py` exit code 0, output mengandung HTTP 200 | HTTP 200 | handoff/logs/TASK-001-serve.log:1 | OK |

## Anomali
- Skrip `handoff/tools/smoke_001.py` dijalankan 3 kali via `record.py` (`handoff/logs/provenance.jsonl:4..6`). Run pertama gagal (`kode_keluar: 1`) karena `ModuleNotFoundError: No module named 'app'` akibat direktori root belum terdaftar di `sys.path`. Diperbaiki dengan menambahkan root ke `sys.path`. Run kedua gagal (`kode_keluar: 1`) karena `ModuleNotFoundError: No module named 'httpx'` di `app/agent_workflow/executor.py:229` saat pipeline ringkasan dipanggil tanpa mock transport. Diperbaiki dengan memasang mock pada `Executor._call_provider`. Run ketiga berhasil (`kode_keluar: 0`).
- K2 menghasilkan `HTTP 401, error.code = UNAUTHORIZED` (`handoff/logs/TASK-001-smoke.log:2`), sedangkan Harapan kriteria adalah `AUTH_ERROR`. Berdasarkan implementasi `app/security.py:22` dan kontrak `app/errors.py:13`, kode galat yang digunakan adalah `UNAUTHORIZED`. K2 ditandai FAIL sesuai evaluasi literal.
- K8 menghasilkan `2 failed, 142 passed in 2.81s` (`handoff/logs/TASK-001-pytest.log:49`) dengan kode keluar 1 (`handoff/logs/provenance.jsonl:1`). Kegagalan terjadi pada `test_health_shape_without_key` (`tests/test_api_foundation.py:130`) dan `test_settings_read_environment` (`tests/test_api_foundation.py:309`) karena environment sesi memiliki `GEMINI_API_KEY` terkonfigurasi, sehingga `settings.provider_configured` bernilai `True` sementara kedua unit test tersebut menguji kondisi `False`. Karena batasan task melarang mengubah kode test atau app, K8 dilaporkan FAIL.

## Hipotesis & Usulan
- HYPOTHESIS: Pada lingkungan CI atau mesin pengembang yang memiliki variabel lingkungan `GEMINI_API_KEY`, unit test `test_health_shape_without_key` dan `test_settings_read_environment` akan selalu gagal jika tidak diisolasi dengan monkeypatch `delenv("GEMINI_API_KEY", raising=False)`.
- PROPOSAL: Tambahkan pembersihan variabel `GEMINI_API_KEY` pada fixture `client` di `tests/test_api_foundation.py` agar pengujian unit tidak bergantung pada kondisi lingkungan luar.
- PROPOSAL: Perbarui deskripsi kriteria K2 pada dokumen checklist SMOKE di `handoff/README.md` dari `AUTH_ERROR` menjadi `UNAUTHORIZED` agar selaras dengan kontrak API dan kode implementasi `app/security.py`.
- PROPOSAL: Pasang pustaka `httpx` ke dependensi dev (`requirements-dev.txt`) atau sesuaikan dependensi, karena `app/agent_workflow/executor.py:229` memerlukan `httpx` saat provider dipanggil secara nyata.

## Penjelasan untuk tim
Baseline SMOKE dievaluasi untuk 10 kriteria utama mencakup kesehatan layanan, autentikasi, validasi masukan, pembuatan ringkasan (harian dan mingguan), linting, unit test, dan kesiapan server mandiri. Pengujian skenario API K1–K7 dilakukan menggunakan skrip `handoff/tools/smoke_001.py` melalui `TestClient` FastAPI tanpa memanggil API LLM sungguhan. Server mandiri berhasil menyala dan melayani pemeriksaan health melalui `handoff/tools/serve_check.py:80`. Seluruh aturan validasi request dan linting terpenuhi, namun ditemukan ketidaksesuaian penamaan kode galat autentikasi pada spec (`AUTH_ERROR` vs implementasi `UNAUTHORIZED`) dan kegagalan pada 2 unit test fondasi akibat kehadiran `GEMINI_API_KEY` di variabel lingkungan lokal.

Cara mencobanya:
1. Jalankan unit test: `.venv\Scripts\python.exe -m pytest -q`
2. Jalankan linter: `.venv\Scripts\python.exe -m ruff check app/ tests/`
3. Jalankan pengecekan server: `.venv\Scripts\python.exe handoff/tools/serve_check.py`
4. Jalankan skrip smoke: `.venv\Scripts\python.exe handoff/tools/smoke_001.py`

## Periksa Diri
- Kriteria terima K1–K10 seluruhnya terdaftar di tabel Data dengan rujukan bukti log yang valid.
- `python handoff/tools/check_evidence.py handoff/reports/REPORT-001.md` menghasilkan 0 ERROR, 1 WARNING (catatan 3 run pada smoke.log yang telah dijelaskan di Anomali).
- `python handoff/tools/check_process_notes.py --worktree` menghasilkan 0 PROCESS, 0 REF.
- `python handoff/tools/check_diff.py` menghasilkan 0 marks in 0 files.
- `git status --porcelain` memastikan tidak ada modifikasi pada file terlacak repo tim (`app/`, `tests/`, `docs/`).
- Seluruh angka pada Ringkasan Fakta dan Anomali bersumber dari log terverifikasi.

# NOTES HC Store AI — Keadaan Sekarang
> Milik head. Arah ada di `ROADMAP.md`. Maksimal 10 baris per topik. Bila sudah menjadi log, riwayatnya dipindah ke `NOTES_ARCHIVE.md`. Nilai secret tidak ditulis di sini.

## 1. Arsitektur & Aturan Inti
- **Layanan:** FastAPI stateless, JSON REST API di `/api/v1`. Dipanggil hanya oleh backend FS, bukan browser.
- **Ringkasan AI:** Data masuk → fakta deterministik (kode) → prompt + konteks terstruktur → LLM (Gemini) → validasi keluaran (JSON, angka, gaya) → retry 1× → fallback template. Semua angka dihitung kode, LLM hanya merangkai kalimat.
- **Prediksi:** Belum dibangun. Rencana: scikit-learn pipeline, joblib export, serve via endpoint.
- **Auth:** API key di header `X-API-Key`, dicek terhadap `SERVICE_API_KEY` di `.env`.
- **Error:** Amplop standar `{"error": {"code": ..., "message": ..., "details": ...}}`.
- **Validasi request:** 3 lapis: Pydantic (skema), lintas field, konsistensi data. Data note diteruskan ke respons.
- **Bahasa:** Indonesia untuk output ke pemilik toko. Kode dan docs dalam campuran Indonesia/Inggris.

## 2. Status (build/test/stabilitas terakhir + bukti)
- **Build/test:** 142 lulus, 2 gagal (`pytest -q`, 14 Nov 2026, `handoff/logs/TASK-001-pytest.log:49`). 2 gagal karena `GEMINI_API_KEY` di env: `test_health_shape_without_key` dan `test_settings_read_environment` → FIX R11.
- **Lint:** Bersih (`ruff check`, 14 Nov 2026, `handoff/logs/TASK-001-ruff.log:1`).
- **SMOKE baseline (TASK-001):** 8/10 OK, 2 FAIL (K2 head error di spec, K8 env issue). Lolos triase 14 Nov 2026.
- **Kode pipeline:** Di-commit `f542f28`, di-push ke origin (14 Nov 2026).
- **`.env`:** Ada, `SERVICE_API_KEY` dan `GEMINI_API_KEY` terisi.
- **Python:** 3.11.0.
- **Dependensi:** FastAPI, uvicorn, pydantic, pydantic-settings, google-genai, ruff, pytest, httpx.

## 3. Register Keputusan
| Tanggal | Keputusan | Oleh | Alasan | Opsi ditolak | Buka ulang jika |
|---|---|---|---|---|---|
| 9 Nov 2026 | FastAPI sebagai framework REST | Tim AE | Validasi Pydantic native, OpenAPI docs otomatis; PRD OQ-04 | Flask (perlu library tambahan untuk validasi dan docs) | Tidak perlu |
| 9 Nov 2026 | Gemini sebagai provider LLM awal | Tim AE | Free tier tersedia; PRD OQ-03 | OpenAI (free tier lebih ketat) | Kuota Gemini habis atau kualitas tidak memadai |
| 9 Nov 2026 | Asia/Makassar sebagai timezone default | Tim AE | Lokasi toko HC Store Import di Makassar; PRD OQ-08 | Asia/Jakarta | Owner atau FS meminta berbeda |
| 13 Nov 2026 | Executor model: Gemini 3.8 Flash (high) lewat omp | Ivan | Model murah untuk task rutin | Antigravity | Model tidak tersedia atau kapasitas tidak cukup |
| 13 Nov 2026 | Sesi head baru otomatis: ya | Ivan | Hemat waktu user saat konteks besar | Tidak (user harus mengetik /clear sendiri) | User berubah pikiran |
| 13 Nov 2026 | Isi project hanya hal teknis | Ivan (5 Nov, dikonfirmasi 9 Nov 2026) | Clone anggota tim tidak memuat lapisan agen | - | - |
| 14 Nov 2026 | Checklist SMOKE item 2: `AUTH_ERROR` → `UNAUTHORIZED` | Head (perbaikan) | Kode `app/security.py:22` sudah memakai `UNAUTHORIZED` sejak awal; checklist salah mengutip | `AUTH_ERROR` (spec lama) | Tidak perlu |
| 13 Nov 2026 | Tim AE: Ivan user tunggal (semua peran) | Ivan | Koreksi: user bukan Abraham; Ivan = pemilik arah + pelaksana + reviewer | Tim dua orang (Abraham + Ivan) | Anggota baru bergabung |

## 4. Lingkungan & Perintah
- **OS:** Windows 10, x64.
- **Python:** 3.11.0 di `C:\Users\Ivan\AppData\Local\Programs\Python\Python311\python.exe`.
- **Venv:** `.venv\Scripts\python.exe`.
- **Test:** `.venv\Scripts\python.exe -m pytest -q` (144 test, 3.2 detik).
- **Lint:** `.venv\Scripts\python.exe -m ruff check .`.
- **Run:** `.venv\Scripts\python.exe -m uvicorn --factory app.main:create_app --port 8000`.
- **Git remote:** `origin https://github.com/brahamrenatus-ai/hc-store-ai.git`.
- **Git hooks:** `.githooks/pre-commit` (cek `.env`, pola kunci API, nilai dari `.env`).

## 5. Anomali Terbuka
(Tidak ada.)

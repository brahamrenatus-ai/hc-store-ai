# Papan Tim HC Store AI
> Ringkasan status untuk tim (Ivan). Sumber detail ada di `handoff/ROADMAP.md` dan `handoff/NOTES.md`.

## Milestone Aktif: M1 — Fondasi Layanan & Pipeline Ringkasan (Minggu 1, target 26 Nov 2026)
Tujuan: Layanan FastAPI aktif, kontrak API v0.3 stabil, pipeline ringkasan AI harian/mingguan tervalidasi dan lolos SMOKE.

## Batch 1 (Disetujui Ivan 14 Nov 2026)
| Task | Jenis | Pelaksana | Butuh | Status | Keterangan |
|---|---|---|---|---|---|
| TASK-001 | SMOKE | Gemini 3.8 Flash (high) | MEDIUM | OPEN → siap dispatch | Baseline SMOKE: health, auth, validasi, ringkasan, lint, test, server check |

## Yang Sedang Dikerjakan
- TASK-001 siap dispatch ke executor lewat Orca. Prasyarat terpenuhi: kode di-commit (`f542f28`), `.env` ada, lint bersih, 144 test lulus.
- Menunggu Ivan: push `f542f28` ke origin (`git push origin main`).

## Tugas Manusia (Ivan)
- U1 (PARTIAL): Push commit `f542f28` ke origin. Perintah: `git push origin main`.

## Usulan Berikutnya
- Batch 2: R2 (Test pipeline ringkasan — head, mock executor, anti-halusinasi, fallback) & R5 persiapan (eksplorasi data sintetis DS).

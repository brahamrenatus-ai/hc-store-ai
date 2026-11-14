# ROADMAP HC Store AI
> Milik head. NOTES = keadaan, ROADMAP = arah. Executor tidak mengedit file ini. Nilai secret tidak ditulis di sini.
> Sumber: `docs/prd-ae.md` v0.2, `docs/capstone.md`. Status diverifikasi di kode pada 13 Nov 2026.

## 1. Tertunda untuk Sesi Head Berikutnya
- TASK-001 (Baseline SMOKE) selesai, lolos triase 14 Nov 2026. 8/10 OK, 2 FAIL (K2 head error, K8 env issue).
- Commit `f542f28` sudah di-push ke origin.
- **Selanjutnya:** usulkan Batch 2 — R11 (FIX 2 test gagal) + R2 (test pipeline ringkasan). Gerbang arah sudah dicek: ritme OK (1 SMOKE + 1 FIX + 1 FEATURE dari 3 task), tidak ada regresi.

## 2. Fokus Saat Ini (maks. 2 jalur)
1. **Ringkasan harian dan mingguan (F1):** Pipeline ringkasan (head + executor + validasi + fallback) sudah ditulis tapi belum di-commit dan belum punya test khusus pipeline.
2. **Fondasi API dan test (F3):** Kerangka FastAPI, health, auth, error handling, validasi request sudah di-commit. Endpoint ringkasan sudah ditulis tapi belum di-commit.

## 3. Backlog
Jenis: MEASURE / FIX / FEATURE / SPIKE / SMOKE / STRUCTURE / FACT. Status: TODO / PARTIAL / TASK-NNN / DONE / PARKED / WAIT-USER <!-- aw: N17 -->
| ID | Jenis | Item | Sumber | Status (cek kode 13 Nov 2026: fungsi + `file:baris`) |
|---|---|---|---|---|
| R1 | SMOKE | Baseline SMOKE: health, auth, validasi, ringkasan, lint, test | PRD §19, §20 | TASK-001 |
| R2 | FEATURE | Test pipeline ringkasan (head, executor tiruan, validasi keluaran, fallback deterministik) | PRD §15, AE-FR-021–023, AE-FR-060, AE-FR-070 | TODO |
| R3 | FEATURE | Perbandingan konfigurasi generatif (prompt + suhu) dengan provider tiruan | PRD §13.2, AE-FR-082 (Should) | TODO |
| R4 | FIX | Commit kode pipeline ringkasan yang belum ter-commit (`app/agent_workflow/`, `app/api/summaries.py`, perubahan `app/main.py` dan `app/summaries/schemas.py`) | Kode sudah ditulis, belum masuk repo | PARTIAL — commit `f542f28` ada, push belum |
| R5 | FEATURE | Pipeline prediksi penjualan per produk: preprocessing, pelatihan, perbandingan 2 model, ekspor | PRD §16, AE-FR-034–038, F4 Must | TODO |
| R6 | FEATURE | Endpoint prediksi dan informasi restok | PRD §10.4, §12.7, AE-FR-030–033 | TODO |
| R7 | FEATURE | Rate limiting in-process | PRD §8, AE-FR-041 | TODO |
| R8 | FEATURE | Deploy ke cloud free tier | PRD §23, §25 Minggu 3 | TODO |
| R9 | FEATURE | Guided chat (Should) | PRD §14, AE-FR-010–014, F2 | PARKED — PRD C3: Should, bukan Must; buka setelah F1 dan F4 selesai |
| R10 | FEATURE | README: masalah, sumber data, preprocessing, tabel perbandingan 2 model, alasan pemilihan | PRD §20, O6, Checklist Main Quest | TODO |

### Selesai
| Item | Bukti |
|---|---|
| Kerangka FastAPI dengan health, auth, error, request ID | commit `8c06cc4`, `app/main.py:12` |
| Validasi request ringkasan harian dan mingguan | commit `60b2526`, `app/summaries/validation.py:28` |
| Kontrak API v0.3 dan kontrak data v0.1 | commit `b27de86`, `docs/api-contract.md`, `docs/data-contract.md` |

## 4. Catatan Item
**R4 (commit kode pipeline):** Kode `app/agent_workflow/` sudah ditulis lengkap (head.py 725 baris, executor.py 296 baris, schemas.py 132 baris) beserta endpoint `app/api/summaries.py` (69 baris). Perubahan `app/main.py` menambah import summaries router, dan `app/summaries/schemas.py` menambah field baru. Belum ada test khusus pipeline; test yang ada (144 test) masih lulus. Kode ini perlu di-review dan di-commit sebelum pekerjaan berikutnya.

**R5 (pipeline prediksi):** Belum ada folder `ml/`, `models/`, atau `data/`. Dataset sintetis dari tim DS belum tersedia. Ini Must dan deliverable Minggu 2 PRD §25.

**R8 (deploy):** Target Minggu 3 PRD §25. Hosting: Render, Railway, atau Koyeb (free tier). Belum ditentukan.

## 5. Tugas User
| ID | Tindakan (hanya user yang bisa) | Kenapa | Cara verifikasi | Status |
|---|---|---|---|---|
| U1 | Commit dan push kode pipeline ringkasan (R4) | Agen tidak boleh commit | `git log --oneline -1` memuat file yang disebut | PARTIAL — commit `f542f28` ✓, push belum |
| U2 | Commit dan push infrastruktur handoff | Agen tidak boleh commit | `git -C handoff log --oneline -1` | TODO |
| U3 | Tentukan hosting provider untuk deploy (Render/Railway/Koyeb) | Keputusan infrastruktur, PRD OQ-23 | Tercatat di register keputusan | WAIT-USER |
| U4 | Koordinasi dataset sintetis dengan tim DS | Data latih dibutuhkan untuk R5, PRD §16.3, OQ-30 | File data tersedia di `data/` | WAIT-USER |

## 6. Batasan Diterima
| Batasan | Sudah dikesampingkan data | Spec vs nyata | Yang tersisa | Dampak ke backlog |
|---|---|---|---|---|

## 7. Kotak Usulan
| Tanggal | Asal | Usulan | Keputusan | Alasan |
|---|---|---|---|---|

## 8. Pertanyaan Terbuka
- OQ-03: Provider dan model LLM mana? Kode sudah memakai Gemini (`gemini-2.0-flash` di `executor.py:75`). Perlu konfirmasi dan cek kuota free tier.
- OQ-08: Timezone sudah di-default `Asia/Makassar` (`config.py:14`). Perlu konfirmasi dari FS/owner.
- OQ-10–13: Parameter restok dan prediksi. Perlu keputusan sebelum R5–R6.

## 9. Aturan Pemeliharaan
- Head memperbarui file ini saat membuat task, saat triase, dan saat retrospektif.
- Maksimal 2 jalur fokus. Item baru masuk backlog dulu, kecuali regresi.
- Bila backlog jalur fokus habis, minta prioritas baru ke user.

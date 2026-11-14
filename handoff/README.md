# Handoff HC Store AI: Protokol Head ↔ Executor
> Dibuat dengan skill **agent-workflow v3.24** (13 Nov 2026). Untuk memperbarui protokol ke versi skill yang lebih baru, jalankan skill agent-workflow (mode AUDIT, jalur upgrade). <!-- aw: U1 -->

- **Head:** `.agents/skills/hcai-head/SKILL.md` · tool: omp. Setiap tool yang menjalankan head atau executor punya instruksi atau penunjuk di folder skill-nya.
- **Executor:** `.agents/skills/hcai-executor/SKILL.md` (sumber tunggal pagar pengaman executor).
- **Struktur:** `handoff/STRUCTURE.md`, peta letak file project. <!-- aw: S1 -->
- **Sesi:** model dan effort per jenis sesi: head Claude Opus 4 (high); pekerjaan mekanis tanpa keputusan (ekspor, menjalankan alat): model lebih murah, effort medium; executor: §Profil Executor. Cek model dan effort setiap sesi baru begitu dibuka, karena sesi yang dibuka dari sesi lain bisa mewarisi setelan sesi asalnya. <!-- aw: N1 -->

## Profil Executor <!-- aw: B5 M1 -->
- Tool: omp. Kapasitas dinilai **per model**, satu baris per model yang dipakai, beserta tool-nya:

  | Model | Tool | Kapasitas | Task dari head | Ruang gerak executor | Verifikasi head | Peluncuran Orca |
  |---|---|---|---|---|---|---|
  | Gemini 3.8 Flash (high) | omp | **MEDIUM** | Tujuan + kriteria + sketsa desain + test acceptance | Detail implementasi di file yang disebut; tanpa SPIKE | `check_evidence.py`, cek diff, jalankan test; cocokkan semua OK | `--agent omp --model gemini-3.8-flash --effort high` |

- **Urutan pilihan model** (keputusan user; dipakai head untuk **Pilihan model per task**): 1. Gemini 3.8 Flash (high) — murah, rutin; 2. model lebih kuat untuk task HIGH. Model yang kapasitasnya belum ditetapkan tidak menerima task. <!-- aw: M6 -->
- **Orca** (head menjalankan executor lewat Orca): id model di kolom Peluncuran Orca diambil dari daftar model agen itu. Izin agen di Orca (Settings → Agents): Full access. Task yang menyentuh operasi berisiko (push, deploy, API LLM sungguhan, data asli toko) tidak dikirim lewat Orca. Konfirmasi worker dijawab user. Dispatch baca-saja belum dicek. Sesi head baru otomatis: ya (`handoff/tools/head_restart.py` mengetik `/clear` dan skill head ke terminal ini; batal bila user mengetik). <!-- aw: Q4 -->
- Header task `Butuh executor: <kapasitas>` menentukan model yang boleh dipakai. Executor yang menerima task di atas kapasitas modelnya → `BLOCKED` ("butuh executor lebih kuat").
- Report wajib mengisi `Pelaksana (model)` dengan nama model dan effort persis dari baris `Model:` di prompt pembuka (dari user, atau spec head lewat Orca). Bila tidak ada, tulis `tidak diketahui`. Task yang dikerjakan sesi head dicatat `sesi head · <model> (<effort>)` dan tidak dihitung sebagai bukti kapasitas.
- **Model baru** tanpa riwayat di project diuji kalibrasi dulu lewat skill agent-workflow (±15 menit: perintah persis, cari dan kutip bukti sendiri, tabel jika–maka dengan jebakan). Hasilnya dicatat di Riwayat kapasitas. <!-- aw: A1 -->
- **Syarat naik LOW → MEDIUM** (per model): 2 task berturut-turut tanpa koreksi, minimal 1 berformat MEDIUM (tujuan, kriteria, sketsa; tanpa langkah atomik). Task atomik dan uji kalibrasi tidak dihitung. <!-- aw: E3 -->
- **Syarat naik MEDIUM → HIGH** (per model): minimal 1 FIX/FEATURE tanpa sketsa rinci + 1 SMOKE berbukti log, lolos tanpa koreksi. <!-- aw: V3-4 N16 -->
- **Syarat naik, semua tingkat:** 2 report berturut-turut bebas dari Kebiasaan gagal model itu. Setelah naik, 2 task pertama adalah **masa percobaan**: diverifikasi sedalam tingkat lama, dan pelanggaran di masa itu mengembalikan model ke tingkat lama. <!-- aw: X2 -->
- **Syarat turun** (per model, satu tingkat): **OK palsu**, yaitu status OK yang buktinya tidak ada, bertentangan dengan nilai harapan, atau dikarang (kutipan yang tidak ada di log, baris log yang bukan output perintah, pengamatan user yang tidak diberikan user), atau pelanggaran pagar pengaman. Klaim penyebab sebagai fakta, angka tanpa pengukuran, dan Batasan task yang dilanggar tanpa dilaporkan dicatat di Kebiasaan gagal, dan task itu tidak dihitung untuk naik. Ketiganya bukan alasan turun. <!-- aw: X1 -->
- Riwayat kapasitas: (tanggal · model · dari → ke · alasan)
- **Kebiasaan gagal** (per model): (model · kebiasaan · bukti · penangkal yang ditulis head di task) <!-- aw: Q1 -->

## Alur
1. Head menulis `tasks/TASK-NNN-<slug>.md` (OPEN), biasanya dari ROADMAP.
2. Executor mengerjakan, menulis `reports/REPORT-NNN.md`, lalu mengubah status menjadi DONE/BLOCKED.
3. Head memverifikasi sesuai kapasitas dan mencocokkan bukti, menulis `- Triase head: lolos <tanggal>` (atau `koreksi → TASK-NNN`) di file task, memindahkan fakta ke NOTES dan usulan ke ROADMAP, lalu memutuskan langkah berikutnya.

## Alur Tim
Tim AE: Ivan (user tunggal: pemilik arah, menyetujui batch, memutuskan desain, commit dan push, pelaksana dan reviewer).

- **G1 (Persetujuan batch).** Sebelum task dikerjakan, head mengusulkan 1–3 task berikutnya di `handoff/BOARD.md` dan di percakapan, lalu menunggu persetujuan Ivan. Sesudah disetujui, isi `Disetujui: <nama> <tanggal> (B<n>)` di header setiap task batch itu; selama `Disetujui: belum`, executor menolak task.
- **G2 (Keputusan desain).** Keputusan desain di dalam task disajikan sebagai opsi + rekomendasi dan diputuskan Ivan.
- **G3 (Milestone).** Milestone ditutup bersama Ivan.
- Agen tidak menjalankan `git commit`, `git push`, atau `git merge`; agen menyiapkan blok perintahnya untuk Ivan.
- Lapisan agen (`handoff/`, `.claude/`, `.agents/`, `CLAUDE.md`) hanya ada di mesin Ivan dan tidak masuk repo tim; isi repo tim dan pesan commit-nya tidak menyebut agen.

## Jenis Task <!-- aw: B3 S2 L1 -->
| Jenis | Isi task | Ruang gerak executor |
|---|---|---|
| MEASURE | Tujuan, kondisi tetap, langkah numerik, format output | Literal |
| FIX | Gejala, bukti, lokasi, kriteria terima | Sesuai kapasitas |
| FEATURE | Tujuan, kriteria terima, batasan, acuan; + sketsa desain untuk MEDIUM; dipecah atomik untuk LOW | Sesuai kapasitas |
| SPIKE | Pertanyaan, batas waktu, bentuk output | Hanya untuk `Butuh executor: HIGH` |
| SMOKE | Checklist §SMOKE | Literal |
| STRUCTURE | Kelompok file yang dipindah, rujukan yang harus diperbarui (hasil grep), verifikasi build + grep path lama | Literal |
| FACT | Daftar pertanyaan, lingkup file/folder, format tabel jawaban | Baca saja; tanpa mengubah file |

- **Anggaran investigasi:** maksimal 3 task MEASURE per pertanyaan.
- **Task STRUCTURE** tidak dihitung dalam ritme FIX/FEATURE, maksimal 1 per 5 task.
- **Task FACT** dipakai head untuk mendelegasikan bacaan luas, dan diperlakukan seperti MEASURE untuk anggaran dan ritme. Status jawaban: FOUND (bukti `file:baris`), NONE (bukti `hitung(lingkup, "pola")` = 0), atau UNSURE.
- **Kriteria terima umum:** build dan test lulus; metrik tidak stabil dinilai terhadap baseline sesi yang sama.

## Format Task <!-- aw: V3-5 D2 Y4 -->
    # TASK-NNN: <judul>
    - Jenis · Roadmap: R<n> · Anggaran: <N>/3 · Status · Butuh executor: <kapasitas> · Model: <model (effort)>, alasan: <satu kalimat>
    - Prasyarat: TASK-NNN lolos triase head · Memakai: <port/layanan bersama> (eksklusif, ±durasi; bila ada)
    - Disetujui: belum (diisi sesudah persetujuan tim: <nama> <tanggal> (B<n>))
    - Dikerjakan head bersamaan: <path> (opsional; wilayah file yang diubah head selama task berjalan lewat Orca)
    - Triase head: (diisi head setelah verifikasi: lolos <tanggal> / koreksi → TASK-NNN)
    ## Mengapa
    ## Yang perlu dipahami
    ## Rujukan
    ## Tujuan
    ## Kriteria terima (terukur, bernomor K1, K2, …; yang dinilai mata user ditandai `user:`, yang dinilai head dari tangkapan layar `head:`; masa percobaan model baru, executor LOW dan task uji naik: templat tabel Data dengan Harapan terisi)
    ## Batasan
    ## Konteks          (fungsi + file:baris; LOW: salin potongan kode relevan di sini)
    ## Langkah          (MEASURE/SMOKE/LOW: bernomor, literal)
    ## Sketsa desain    (MEDIUM: file, fungsi, antarmuka)
    ## Test acceptance  (FIX/FEATURE semua kapasitas, dan semua jenis untuk LOW: perintah atau skrip penilai/penganalisis yang sudah dijalankan head; executor tidak boleh mengubahnya)
    ## Verifikasi       (perintah persis + output yang diharapkan)
    ## Langkah Penutup  (opsional)

## Task Ad-hoc
Permintaan langsung user ke executor HIGH/MEDIUM → `TASK-NNN{B,C..}-<slug>.md` dengan header `Dibuat: executor atas permintaan user ("<kutipan>")`. Izin sebatas yang diminta.

## SMOKE
Dijadwalkan tiap 5 task atau di akhir milestone, di lingkungan/data uji yang terisolasi.

Status per item:
- **OK** hanya bila nilai teramati memenuhi nilai harapan, dan kutipan buktinya ada di file log yang dirujuk. <!-- aw: V3-2 -->
- **FAIL** bila nilai teramati tidak memenuhi nilai harapan.
- **UNTESTED** bila item tidak bisa diuji.

1. Health endpoint mengembalikan HTTP 200 dengan `data.status` salah satu dari `ok` atau `degraded` (`app/api/health.py:27`).
2. Request tanpa API key ditolak HTTP 401 dengan amplop error `UNAUTHORIZED`.
3. Request ringkasan harian dengan data valid mengembalikan HTTP 200 dengan `generation_mode` salah satu dari `ai`, `template_fallback`, atau `no_data`.
4. Request ringkasan harian tanpa transaksi (`transaction_count: 0`) mengembalikan `generation_mode: "no_data"` dan teks "Belum ada data penjualan untuk periode ini."
5. Request ringkasan mingguan dengan data valid mengembalikan HTTP 200 dengan `summary_type: "weekly"`.
6. Request dengan field tambahan ditolak HTTP 422 dengan `VALIDATION_ERROR`.
7. Request dengan `total_revenue` negatif ditolak HTTP 422.
8. Semua test (`pytest -q`) lulus tanpa error.
9. Lint (`ruff check .`) bersih tanpa pelanggaran.
10. Server (`uvicorn --factory app.main:create_app`) menyala dan menjawab health tanpa crash.

## Format Report
Format lengkap: `handoff/reports/REPORT_TEMPLATE.md`. Sebelum DONE, executor menjalankan `check_evidence.py` atas report-nya; head menjalankannya lagi saat triase.

## Lingkungan
Perintah di bagian ini sudah **dicek jalan** di mesin ini (13 Nov 2026). Perintah yang tidak boleh dijalankan agen (deploy, push) ditandai `belum dicek`. <!-- aw: J1 -->
- Build: tidak ada (Python).
- Test: `.venv\Scripts\python.exe -m pytest -q`.
- Lint: `.venv\Scripts\python.exe -m ruff check .` dan `.venv\Scripts\python.exe -m ruff format --check .`.
- Run: `.venv\Scripts\python.exe -m uvicorn --factory app.main:create_app --port 8000`. Jangan menyalakan server sendiri di task; pakai `.venv\Scripts\python.exe handoff/tools/serve_check.py`, yang menyalakan, memanggil health, lalu mematikannya.
- Cek secret (bila `handoff/tools/check_secrets.py` ada): `python handoff/tools/check_secrets.py --staged` sebelum commit.
- Simpan bukti: `python handoff/tools/record.py handoff/logs/TASK-NNN-<nama>.log "<perintah>"` (asal log dicatat di `handoff/logs/provenance.jsonl`). File yang ditulis perintah itu sendiri: `--result <file>` atau `--result "<pola glob>"`. Log task yang sudah DONE/BLOCKED tidak ditimpa tanpa `--overwrite`.
- Cek bukti: `python handoff/tools/check_evidence.py handoff/reports/REPORT-NNN.md` sebelum DONE. Report lama: tambah `--at-report`, supaya kutipan dicocokkan dengan isi file saat report di-commit. <!-- aw: P1 N11 -->

## Penomoran
`NNN` berurutan. Report memakai nomor task-nya. Task ad-hoc = nomor terakhir + huruf.

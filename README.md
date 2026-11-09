# HC Store AI

Layanan AI bagian Next-Gen AI Engineer (AE) untuk aplikasi kasir dan dasbor **HC Store Import**, toko ritel sepatu dan sandal. Bagian dari capstone Asah 2026 dengan use case *Digitalisasi Sistem Kasir Terpadu dan Dasbor Pemantauan Stok Pintar Berbasis AI*.

## Fungsi (MVP)
- **Ringkasan penjualan harian dan mingguan** untuk pemilik toko. Angkanya dihitung kode dari data transaksi, kalimatnya dirangkai model generatif (Gemini atau OpenAI), lalu setiap angka dicek terhadap data. Bila layanan AI gagal atau kuotanya habis, ringkasan templat tetap tampil.
- **Prediksi penjualan per produk** untuk saran restok. Model dilatih dari data sintetis tim Data Science, dan minimal dua model dibandingkan dengan metrik yang sama.
- **REST API berversi** (`/api/v1`) yang hanya dipanggil backend aplikasi kasir.

## Status
Tahap persiapan (9 Nov 2026): spesifikasi sudah ada, kode belum.

## Dokumen
- `docs/prd-ae.md`: PRD bagian AE v0.2 (spesifikasi, berbahasa Inggris).
- `docs/capstone.md`: checklist teknis, jadwal, dan batas cakupan capstone.

## Struktur
```
app/        layanan FastAPI
prompts/    prompt LLM berversi
ml/         pipeline pelatihan model prediksi
models/     model terpilih beserta metadata dan checksum
data/       dataset sintetis dari tim Data Science
tests/      test unit, API, dan fixture
docs/       PRD dan dokumen pendukung
```

## Menjalankan
Belum tersedia; ditulis saat kerangka layanan selesai. Nama variabel environment ada di `.env.example`; nilai aslinya disimpan di `.env`, yang tidak ikut git.

## Setelah clone
- Aktifkan hook pre-commit: `git config core.hooksPath .githooks`. Hook menolak commit yang membawa file `.env`, pola kunci API umum, atau nilai dari `.env`.
- Salin `.env.example` menjadi `.env` bila perlu menjalankan layanan.

## Kerja tim
Setiap anggota bekerja di branch `<nama>/TASK-NNN-<topik>` (mis. `abraham/TASK-007-facts`) dan menggabungkannya ke `main` lewat pull request. Milestone mingguan dan urutan pekerjaan mengikuti `docs/prd-ae.md` §25.

## Data
Semua data di repo ini sintetis dan diberi label. Catatan penjualan toko masih manual, dan angka keuangan asli toko bersifat rahasia, jadi tidak ada data asli toko maupun data pribadi di sini.

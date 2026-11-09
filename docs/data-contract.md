# Kontrak Data: Dataset Latih dan Definisi Metrik (DRAF untuk workshop Minggu 1)

| Butir | Nilai |
|---|---|
| Status | **Draf v0.1, belum disepakati.** Usulan AE untuk workshop AE–DS (dan FS untuk definisi metrik) Minggu 1 (20–26 Nov 2026) |
| Diturunkan dari | `docs/prd-ae.md` v0.2: §4.4 (kebutuhan AE dari DS), §12.2 (blok data bersama), §16.2–16.6 (model prediksi) |
| Pemilik | DS (dataset, kamus data, definisi metrik), AE (pemakai dataset, validasi, pelatihan model), FS (agregat yang dikirim ke layanan AE) |
| Target beku | Akhir Minggu 1 (26 Nov 2026). Perubahan sesudahnya butuh persetujuan pihak terkait dan satu baris di §8 |
| Pasangan | `docs/api-contract.md` (bentuk request yang dikirim FS ke AE) |

Setiap nilai bertanda **[USULAN]** masih terbuka. Semua contoh adalah data sintetis.

## 1. Isi kontrak
1. **Dataset latih** dari DS untuk model prediksi penjualan per produk (§2–§4). AE melatih, membandingkan, dan menyajikan model; DS menyediakan datanya (PRD v0.2 §4.5).
2. **Definisi metrik** yang dipakai bersama dasbor FS dan ringkasan AI, supaya angka di ringkasan sama dengan angka di dasbor (§5).
3. **Penyerahan dan versi** dataset (§6).

## 2. Dataset latih [USULAN]

### 2.1 Bentuk
Dua berkas CSV (UTF-8, pemisah koma, baris pertama nama kolom, tanggal `YYYY-MM-DD`, tanpa kolom indeks):

**`sales_daily.csv`**: satu baris per produk per hari, **termasuk hari dengan penjualan nol**.

| Kolom | Tipe | Wajib | Arti |
|---|---|---|---|
| `date` | tanggal | Ya | Hari bisnis dalam waktu lokal toko (§5) |
| `product_id` | string 1–64 | Ya | Sama dengan `product_id` di `products.csv` dan di API (OQ-07) |
| `units_sold` | bilangan bulat ≥ 0 | Ya | Unit terjual dari transaksi selesai (§5) |
| `revenue` | bilangan bulat ≥ 0, IDR | Ya | Pendapatan dari unit itu, sesudah diskon (§5) |
| `stockout` | 0 atau 1 | Tidak, tetapi dianjurkan | 1 bila stok habis di hari itu, sehingga penjualan nol bukan berarti tidak ada permintaan (PRD §16.4) |
| `promo` | 0 atau 1 | Tidak | 1 bila produk sedang promo |

**`products.csv`**: satu baris per produk.

| Kolom | Tipe | Wajib | Arti |
|---|---|---|---|
| `product_id` | string 1–64 | Ya | Unik |
| `name` | string 1–120 | Ya | Nama sintetis |
| `category` | string | Ya | Mis. `sandal`, `sneakers`, `formal` (daftar nilai dari DS) |
| `price` | bilangan bulat > 0, IDR | Ya | Harga jual normal |
| `listed_from` | tanggal | Ya | Tanggal produk masuk katalog; baris `sales_daily.csv` produk ini dimulai dari tanggal ini |
| `listed_until` | tanggal atau kosong | Tidak | Tanggal produk berhenti dijual |
| `unit` | string | Ya | `pairs` untuk alas kaki; satuan lain bila ada produk selain alas kaki |

Bila DS lebih mudah menyerahkan baris transaksi (satu baris per item per transaksi), AE yang mengagregasikannya ke produk per hari. Kolom minimum: `transaction_id`, `timestamp` (ISO 8601 dengan offset), `product_id`, `quantity`, `line_revenue`, `status` (`completed`, `voided`, `returned`).

### 2.2 Ukuran dan pola
| Butir | Usulan | Alasan |
|---|---|---|
| Panjang riwayat | Minimal 180 hari, dianjurkan 365 hari (OQ-30) | Holdout 28 hari, ditambah 28 hari untuk fitur rata-rata bergulir, ditambah cukup minggu untuk validasi silang deret waktu. 365 hari menangkap pola bulanan dan musim libur |
| Jumlah produk | Mendekati jumlah produk asli toko (OQ-07); usulan 50–200 | Batas E6 adalah 200 produk per request |
| Pola yang dibangkitkan dan didokumentasikan | Musiman mingguan, tren, efek tanggal gajian, promo, hari tanpa penjualan, stok habis, produk baru di tengah periode, produk yang berhenti dijual | Model harus diuji pada kondisi yang mirip toko sungguhan; produk baru menguji `insufficient_data` |
| Acak | Generator memakai seed tetap, dicatat di dokumentasi | Dataset bisa dibuat ulang persis |

### 2.3 Label sintetis
Dataset diserahkan bersama `data/README.md` yang menyebut: data ini sintetis; cara dan parameter pembangkitannya; seed; versi; keterbatasannya; dan bahwa tidak ada data asli toko maupun data pribadi di dalamnya (Checklist DS: Penyediaan Data untuk Model AI).

## 3. Pemeriksaan oleh AE saat dataset diterima
AE menjalankan pemeriksaan ini (ROADMAP R13) dan mengembalikan hasilnya ke DS. Dataset yang gagal tidak dipakai melatih.

| # | Pemeriksaan |
|---|---|
| D1 | Pasangan (`date`, `product_id`) unik |
| D2 | Setiap produk punya satu baris per hari tanpa celah, dari `listed_from` sampai akhir data (atau `listed_until`) |
| D3 | `units_sold` dan `revenue` bilangan bulat ≥ 0; `units_sold = 0` ⇒ `revenue = 0` |
| D4 | Setiap `product_id` di `sales_daily.csv` ada di `products.csv` |
| D5 | `revenue` ≤ `units_sold × price` (diskon menurunkan, tidak menaikkan). Berlaku bila harga normal tetap selama periode data; bila harga berubah, DS menambah kolom `unit_price` per hari di `sales_daily.csv` dan pemeriksaan memakai kolom itu |
| D6 | Rentang tanggal sesuai §2.2, dan tidak ada tanggal di masa depan |
| D7 | `stockout`, `promo` hanya 0 atau 1 bila ada |

## 4. Pembagian data [USULAN]
- Berdasarkan waktu, tanpa diacak. **Holdout = 28 hari terakhir** (4 minggu); semua tanggal sebelumnya = data latih.
- Penyetelan hyperparameter (Should) memakai validasi silang deret waktu di dalam data latih saja.
- Tanggal batas (cutoff) ditulis di dokumentasi dataset dan di metadata model, supaya DS bisa mencocokkan angka holdout yang dilaporkan AE.
- Metrik pembanding (PRD §16.5): MAE, RMSE, WAPE, dan bias, per produk-hari dan per total 7 hari. Definisi metrik ini dicek bersama DS.

## 5. Definisi metrik bersama [USULAN] (OQ-06, OQ-08, OQ-15)
Angka di ringkasan AI dihitung dari agregat yang dikirim FS (`docs/api-contract.md` §5 E2). Supaya sama dengan dasbor, FS dan DS memakai definisi yang sama:

| Metrik | Definisi usulan | Perlu diputuskan |
|---|---|---|
| Hari bisnis | 00:00–23:59 WITA (`Asia/Makassar`) | Apakah toko memakai jam tutup sebagai batas hari (OQ-08) |
| Minggu | Senin–Minggu | Hari awal minggu (OQ-08) |
| `transaction_count` | Jumlah transaksi berstatus selesai di periode itu | Transaksi yang dibatalkan atau di-void dikeluarkan? (OQ-15) |
| `total_revenue` | Jumlah nilai transaksi selesai sesudah diskon, dalam rupiah bulat | Diskon level transaksi dibagi ke item bagaimana? Retur mengurangi hari retur atau hari penjualan? (OQ-15) |
| `units_sold` | Jumlah unit dari transaksi selesai | Retur (OQ-15) |
| Produk terlaris | Peringkat menurut unit terjual; seri dipecah menurut pendapatan, lalu `product_id` | Dasar peringkat: unit atau pendapatan (OQ-14, pemilik) |
| Stok menipis | `current_stock ≤ reorder_level` per produk; bila `reorder_level` kosong, ambang global | Nilai ambang global (OQ-09, pemilik) |

## 6. Penyerahan dan versi
- Berkas disimpan di `data/` repo AE dengan nama berversi, mis. `data/sales_daily_v1.csv` dan `data/products_v1.csv`, masing-masing di bawah ±10 MB (365 hari × 200 produk ≈ 73 000 baris, sekitar 2–3 MB).
- SHA-256 setiap berkas dicatat di `data/README.md` dan di metadata model (PRD §16.6), supaya model selalu bisa ditelusuri ke data latihnya.
- Versi baru = berkas baru (`_v2`), berkas lama tidak ditimpa. Model dilatih ulang dari versi yang disebut di metadata.
- Contoh kecil (mis. 5 produk × 60 hari) diserahkan lebih dulu, supaya pemuat dan pemeriksaan AE bisa dibuat sebelum dataset penuh selesai.

## 7. Hal terbuka untuk workshop

| # | Pertanyaan | Diputuskan | OQ |
|---|---|---|---|
| 1 | Bentuk penyerahan: produk per hari (§2.1) atau baris transaksi | DS + AE | OQ-30 |
| 2 | Panjang riwayat dan jumlah produk | DS + AE | OQ-30, OQ-07 |
| 3 | Varian ukuran dan warna: satu `product_id` atau terpisah | DS + FS | OQ-07 |
| 4 | Apakah DS bisa membangkitkan `stockout` dan `listed_from` | DS | OQ-11 |
| 5 | Definisi metrik di §5, termasuk pembatalan, diskon, dan retur | DS + FS | OQ-06, OQ-15 |
| 6 | Batas hari bisnis dan awal minggu | DS + FS + pemilik | OQ-08 |
| 7 | Tanggal penyerahan contoh kecil dan dataset penuh (target model terpilih: 3 Des) | DS + AE | - |

## 8. Riwayat perubahan

| Versi | Tanggal | Perubahan | Disepakati oleh |
|---|---|---|---|
| 0.1 | 2026-11-10 | Draf dari PRD v0.2 §4.4, §12.2, §16.2–16.6 untuk workshop Minggu 1 | belum disepakati |

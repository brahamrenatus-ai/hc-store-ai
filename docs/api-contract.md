# Kontrak API: Layanan AI AE v1 (DRAF untuk workshop Minggu 1)

| Butir | Nilai |
|---|---|
| Status | **Draf v0.3, belum disepakati.** Usulan AE untuk workshop AE–FS Minggu 1 (20–26 Nov 2026) |
| Diturunkan dari | `docs/prd-ae.md` v0.2: §11 (REST API), §12 (kontrak JSON), §18 (error dan teks cadangan) |
| Pemilik | AE (layanan) dan FS (klien backend) |
| Target beku | Akhir Minggu 1 (26 Nov 2026). Perubahan sesudahnya butuh persetujuan kedua pihak dan satu baris di §10 |
| Sumber kebenaran | Setelah disepakati, berkas ini menggantikan PRD §11–12 untuk detail API; PRD lalu merujuk ke sini |

Setiap nilai bertanda **[USULAN]** masih terbuka untuk workshop. Semua contoh nilai adalah data sintetis, bukan data asli toko.

## 1. Cakupan v1

| # | Endpoint | Metode dan path | Prioritas | Masuk v1? |
|---|---|---|---|---|
| E1 | Cek kesehatan | `GET /api/v1/health` | Must | Ya |
| E2 | Ringkasan harian | `POST /api/v1/summaries/daily` | Must | Ya |
| E3 | Ringkasan mingguan | `POST /api/v1/summaries/weekly` | Must | Ya |
| E6 | Prediksi penjualan | `POST /api/v1/predictions/sales` | Must | Ya |
| E7 | Rekomendasi restok | `POST /api/v1/restock/recommendations` | Should | Path dicadangkan; body disepakati di Minggu 2 (parameter aturan, OQ-10) |
| E8 | Info model prediksi | `GET /api/v1/predictions/model` | Could | Path dicadangkan |
| E4, E5 | Chat terpandu (katalog, jawaban) | `GET /api/v1/chat/templates`, `POST /api/v1/chat/answers` | Should | Tidak masuk v1, kecuali tim menerima chat terpandu (OQ-02) |

Layanan ini hanya dipanggil backend FS. Browser tidak pernah memanggilnya langsung, jadi kunci layanan tidak pernah sampai ke frontend.

## 2. Konvensi umum

| Butir | Kesepakatan |
|---|---|
| Base path | `/api/v1` |
| Format | JSON, UTF-8. Tanggal `YYYY-MM-DD` dalam waktu lokal toko; timestamp ISO 8601 dengan offset; uang dalam bilangan bulat rupiah (IDR); jumlah barang dalam bilangan bulat |
| Autentikasi | Header `X-API-Key: <kunci layanan>` di setiap endpoint kecuali E1. Kunci hanya disimpan di variabel environment backend FS dan layanan AE; panjang minimal 16 karakter. Rotasi = ganti kedua variabel |
| Header request | `Content-Type: application/json` (POST), `Accept: application/json`, `X-API-Key`, `X-Request-ID` opsional (1–64 karakter, `[A-Za-z0-9_-]`) |
| Header respons | `X-Request-ID` di setiap respons, termasuk error. Nilainya sama dengan yang dikirim FS bila formatnya valid; bila tidak dikirim atau tidak valid, AE membuat `req_` + 32 karakter heksadesimal. `Retry-After` dalam detik pada 429 dan 503 bila diketahui |
| Field yang tidak dikenal di request | Ditolak dengan 422 `VALIDATION_ERROR` **[USULAN]**, supaya beda nama field antara FS dan AE langsung ketahuan, bukan dibuang diam-diam. Contoh risikonya: `prev_period` yang salah ketik akan membuat ringkasan kehilangan perbandingan tanpa ada error |
| Zona waktu | `Asia/Makassar` (WITA) **[USULAN]**, dikirim eksplisit di request ringkasan (OQ-08) |

### 2.1 Amplop respons
Setiap respons sukses:

```json
{ "request_id": "req_…", "data": { … }, "meta": { … } }
```

Setiap respons error (§6):

```json
{ "request_id": "req_…", "error": { "code": "…", "message": "…", "user_message": "…", "retryable": false, "details": [] } }
```

FS bisa membedakan sukses dan error dari status HTTP saja, dan merender setiap keadaan ringkasan dari `data.generation_mode` saja (AE-FR-050).

## 3. Timeout dan retry [USULAN] (OQ-16)

| Setelan | Usulan | Alasan |
|---|---|---|
| Timeout satu panggilan provider di AE | 15 dtk | Ringkasan pendek berbahasa Indonesia dari model cepat biasanya selesai dalam beberapa detik; 15 dtk memberi ruang untuk respons lambat |
| Batas total per request di AE | 25 dtk | Bila tercapai, AE berhenti menunggu dan mengirim teks cadangan (tetap HTTP 200) |
| Timeout klien FS ke AE | 30 dtk | Harus di atas batas total AE, supaya FS menerima teks cadangan, bukan timeout-nya sendiri |
| Cold start | Host gratis bisa tidur saat sepi. FS mengulang **sekali** saat gagal koneksi atau menerima 502/503 dari host (bukan dari AE, lihat §6), setelah jeda 5 dtk. AE dipanaskan lewat E1 sebelum demo | Host gratis tidak menjamin uptime (PRD §8) |

Aturan retry di sisi AE:
1. **Maksimal 2 panggilan provider per request**, untuk semua alasan retry: timeout, 5xx dari provider, atau keluaran yang tidak lolos validasi (V1–V8). Ini selaras dengan PRD AE-FR-072 dan uji FBK-03. Kuota habis dan error 4xx dari provider tidak diulang.
2. Retry memakai **sisa waktu batas total**, paling lama 15 dtk. Bila sisa waktunya di bawah ambang (usulan 5 dtk, belum diukur), AE tidak mengulang dan langsung mengirim teks cadangan. Contoh: panggilan pertama timeout di detik 15, sisa 10 dtk, jadi retry diberi 10 dtk.
3. Perilaku cold start (apakah host menahan request atau menjawab 502, dan apakah FS juga mengulang setelah timeout-nya sendiri) dibuka lagi setelah host dipilih di Minggu 3, lalu diukur lewat uji TMO-02.

## 4. Batas ukuran [USULAN] (OQ-18)

| Batas | Usulan | Respons bila dilampaui |
|---|---|---|
| Body request | 1 MB | 413 `PAYLOAD_TOO_LARGE` |
| `sales.product_sales` | 500 item | 422 `VALIDATION_ERROR` |
| `inventory.items` | 2 000 item | 422 `VALIDATION_ERROR` |
| E6 `products` | 200 produk | 422 `VALIDATION_ERROR` |
| E6 `history` per produk | 90 hari | 422 `VALIDATION_ERROR` |

Prinsipnya: setiap kombinasi yang diizinkan batas jumlah harus muat di batas body, supaya pelanggaran dilaporkan sebagai 422 yang menunjuk field-nya, bukan 413. Ukuran yang diukur dengan JSON tanpa spasi dan data sintetis: E6 200 produk × 90 hari ≈ 675 KB; E2 terbesar (500 + 500 penjualan, 2 000 stok dengan nama 120 huruf) ≈ 474 KB.

Perlu dikonfirmasi dengan FS: jumlah produk dan varian asli toko, serta apakah prediksi dibuat per varian ukuran (OQ-07).

## 5. Endpoint

### E1. Cek kesehatan
`GET /api/v1/health`, tanpa autentikasi, tanpa body, tidak pernah memanggil provider LLM.

```json
{
  "request_id": "req_example_000",
  "data": {
    "status": "degraded",
    "version": "0.1.0",
    "modules": { "summaries": "ok", "predictions": "unavailable" },
    "model_loaded": false,
    "provider_configured": true,
    "timestamp": "2026-12-05T21:00:00+08:00"
  },
  "meta": {}
}
```

| Field | Arti |
|---|---|
| `modules.summaries` | `ok` bila kunci provider LLM terpasang; `degraded` bila belum, dan ringkasan tetap dibuat lewat teks cadangan |
| `modules.predictions` | `ok` bila artefak model termuat; `unavailable` bila belum, dan E6 menjawab 503 `MODEL_UNAVAILABLE` |
| `status` | `ok` bila semua modul `ok`; selain itu `degraded`. Keduanya HTTP 200 |

E1 tidak punya status `unavailable` atau HTTP 503: selama proses berjalan, ringkasan selalu bisa dibuat, dan setelan wajib yang hilang (mis. kunci layanan) membuat layanan gagal menyala, bukan berjalan setengah. Respons 5xx dari E1 berarti host, bukan AE (§6).

### E2. Ringkasan harian
`POST /api/v1/summaries/daily`, wajib autentikasi.

Request:

```json
{
  "date": "2026-12-05",
  "timezone": "Asia/Makassar",
  "sales": {
    "period": { "start": "2026-12-05", "end": "2026-12-05" },
    "total_revenue": 4390000,
    "transaction_count": 11,
    "units_sold": 15,
    "product_sales": [
      { "product_id": "SH-0012", "name": "Sandal Jepit Hitam", "units_sold": 6, "revenue": 900000 },
      { "product_id": "SH-0031", "name": "Sepatu Sneakers Putih", "units_sold": 3, "revenue": 1350000 },
      { "product_id": "SH-0044", "name": "Sepatu Lari Biru", "units_sold": 2, "revenue": 1040000 },
      { "product_id": "SH-0057", "name": "Sandal Gunung Coklat", "units_sold": 4, "revenue": 1100000 }
    ],
    "daily_breakdown": null
  },
  "previous_period": {
    "period": { "start": "2026-12-04", "end": "2026-12-04" },
    "total_revenue": 2130000,
    "transaction_count": 7,
    "units_sold": 9,
    "product_sales": [
      { "product_id": "SH-0012", "name": "Sandal Jepit Hitam", "units_sold": 4, "revenue": 600000 },
      { "product_id": "SH-0031", "name": "Sepatu Sneakers Putih", "units_sold": 2, "revenue": 900000 },
      { "product_id": "SH-0068", "name": "Slip On Kanvas Abu", "units_sold": 3, "revenue": 630000 }
    ]
  },
  "inventory": {
    "snapshot_at": "2026-12-05T21:00:00+08:00",
    "items": [
      { "product_id": "SH-0012", "name": "Sandal Jepit Hitam", "current_stock": 4, "reorder_level": null }
    ]
  },
  "options": { "language": "id" }
}
```

| Field | Tipe | Wajib | Aturan |
|---|---|---|---|
| `date` | tanggal | Ya | Tanggal kalender yang valid, tidak sesudah hari ini menurut `timezone` |
| `timezone` | string IANA | Ya | Nilai yang disepakati (§2) |
| `sales.period` | `{start, end}` | Ya | Keduanya sama dengan `date` |
| `sales.total_revenue`, `transaction_count`, `units_sold` | bilangan bulat ≥ 0 | Ya | Definisi metrik dari DS (OQ-06, OQ-15). Bila `transaction_count` 0, `units_sold` dan `total_revenue` juga 0; bila tidak, 422 `INCONSISTENT_DATA` |
| `sales.product_sales[]` | list, maks. 500 | Ya (boleh kosong) | Satu baris per produk terjual; `product_id` unik di dalam list; `units_sold` dan `revenue` bilangan bulat ≥ 0. Bila tidak kosong, jumlah `units_sold` dan jumlah `revenue` baris harus sama dengan `sales.units_sold` dan `sales.total_revenue`; bila tidak, 422 `INCONSISTENT_DATA`. List kosong berarti rincian tidak dikirim: ringkasan tanpa kalimat per produk, dicatat di `data_notes` |
| `sales.daily_breakdown` | null | Tidak | Tidak dipakai di ringkasan harian; kosongkan atau null |
| `product_id` | string 1–64 | Ya | ID yang sama di penjualan, stok, dan prediksi (OQ-07) |
| `name` | string 1–120 | Ya | Hanya untuk tampilan; diperlakukan sebagai teks yang tidak dipercaya |
| `previous_period` | objek atau null | Tidak | Bentuk sama dengan `sales` tanpa `daily_breakdown`, dengan aturan konsistensi yang sama; tepat satu hari sebelumnya. Tidak dikirim → tidak ada kalimat perbandingan |
| `inventory` | objek atau null | Tidak | Tidak dikirim → tidak ada catatan stok |
| `inventory.snapshot_at` | timestamp ISO 8601 dengan offset | Ya bila `inventory` dikirim | Waktu data stok diambil |
| `inventory.items[]` | list, maks. 2 000 | Ya bila `inventory` dikirim | `product_id` unik di dalam list. Produk yang terjual tetapi tidak ada di sini dicatat di `data_notes`; produk yang ada di sini tetapi tidak terjual itu normal |
| `inventory.items[].current_stock` | bilangan bulat ≥ 0 | Ya bila `inventory` dikirim | Stok pada `snapshot_at` |
| `inventory.items[].reorder_level` | bilangan bulat ≥ 0 atau null | Tidak | Null → aturan stok menipis global (OQ-09) |
| `options.language` | string | Tidak | Hanya `id` di MVP (OQ-24) |

Semua "bilangan bulat" berarti angka JSON bulat: `1.0`, `"10"`, dan `true` ditolak dengan 422 `VALIDATION_ERROR`, supaya selisih tipe di FS ketahuan sejak awal. Aturan yang menyangkut beberapa field (tanggal dan periode) diperiksa sesudah bentuk request valid; aturan konsistensi angka diperiksa paling akhir.

Respons 200:

```json
{
  "request_id": "req_example_002",
  "data": {
    "summary_type": "daily",
    "period": { "start": "2026-12-05", "end": "2026-12-05" },
    "generation_mode": "ai",
    "summary_text": "Pada 5 Desember 2026 terjadi 11 transaksi dengan total pendapatan Rp 4.390.000. ...",
    "key_figures": [
      { "key": "total_revenue", "label": "Total pendapatan", "value": 4390000, "unit": "IDR", "display": "Rp 4.390.000", "source": "sales.total_revenue" },
      { "key": "transaction_count", "label": "Jumlah transaksi", "value": 11, "unit": "transaksi", "display": "11", "source": "sales.transaction_count" }
    ],
    "observations": [
      { "id": "obs_top_product", "text": "...", "evidence": ["sales.product_sales"] }
    ],
    "data_notes": []
  },
  "meta": {
    "model_provider": "<provider yang dipakai>",
    "model_name": "<model yang dipakai>",
    "prompt_version": "daily-v0.1",
    "latency_ms": 0,
    "validation": { "schema_ok": true, "numeric_check": "passed" },
    "fallback_reason": null,
    "generated_at": "2026-12-05T21:05:00+08:00"
  }
}
```

| `generation_mode` | Arti | Yang ditampilkan FS |
|---|---|---|
| `ai` | Teks LLM yang lolos semua validator | `summary_text` + `key_figures` |
| `template_fallback` | Provider gagal, timeout, kuota habis, atau keluarannya tidak valid; AE menyusun teks dari templat tetap. `meta.fallback_reason` berisi `PROVIDER_UNAVAILABLE`, `QUOTA_EXCEEDED`, `TIMEOUT`, atau `INVALID_OUTPUT` | Field yang sama; boleh ditambah keterangan kecil "ringkasan standar" |
| `no_data` | Tidak ada transaksi di periode itu; LLM tidak dipanggil | `summary_text` tetap ("Belum ada data penjualan untuk periode ini."), `key_figures` kosong |

`key_figures` dihitung kode, tidak pernah oleh LLM, jadi FS boleh menampilkannya sebagai kartu di samping teks. `summary_text` berupa teks biasa (tanpa HTML atau Markdown) dan dirender FS sebagai teks.

### E3. Ringkasan mingguan
`POST /api/v1/summaries/weekly`, wajib autentikasi. Sama dengan E2, kecuali:

| Field | Aturan |
|---|---|
| `date` | Tidak dikirim (field tak dikenal → 422); periodenya `sales.period` |
| `sales.period` | `end − start = 6 hari` (7 hari inklusif), dan `end` tidak sesudah hari ini menurut `timezone` **[USULAN]**: minggu yang belum selesai ditolak, supaya minggu separuh jalan tidak dibandingkan dengan minggu lalu yang penuh. Minggu dimulai hari Senin **[USULAN]** (OQ-08) |
| `sales.daily_breakdown` | Wajib, list maks. 7 `{ "date", "total_revenue", "transaction_count", "units_sold" }`; tanggal di dalam periode, tanpa duplikat. Hari yang tidak ada = penjualan nol |
| Konsistensi | Jumlah `daily_breakdown` harus sama dengan total periode untuk ketiga metrik; bila tidak, 422 `INCONSISTENT_DATA`. Aturan rincian produk sama dengan E2 |
| `previous_period` | Bila dikirim, juga 7 hari dan tepat sebelum `sales.period` |

Respons: seperti E2 dengan `summary_type: "weekly"` dan `prompt_version: "weekly-v0.1"`.

### E6. Prediksi penjualan
`POST /api/v1/predictions/sales`, wajib autentikasi. Tidak memanggil LLM.

Request:

```json
{
  "as_of": "2026-12-05",
  "horizon": { "unit": "day", "count": 7 },
  "products": [
    {
      "product_id": "SH-0012",
      "history": [ { "date": "2026-11-28", "units_sold": 3 }, { "date": "2026-11-29", "units_sold": 0 } ]
    }
  ]
}
```

(Contoh `history` dipotong; request sungguhan berisi satu entri per hari sesuai aturan di bawah.)

| Field | Aturan |
|---|---|
| `as_of` | Hari terakhir yang termasuk di riwayat; tidak sesudah hari ini |
| `horizon` | Hanya `{ "unit": "day", "count": 7 }` di v1 **[USULAN]** (OQ-32); nilai prediksi = total unit selama 7 hari sesudah `as_of` |
| `products[].product_id` | Unik, tidak kosong |
| `products[].history` | **Riwayat lengkap:** satu entri per hari, termasuk hari dengan penjualan nol, berurutan tanpa celah, dan berakhir di `as_of`. Dimulai dari tanggal yang lebih belakangan antara `as_of − 55 hari` (56 hari riwayat) dan tanggal produk masuk katalog. Tanggal yang bolong, ganda, atau tidak berurutan → 422 `VALIDATION_ERROR`. Lebih dari 90 entri → 422 |
| `units_sold` | bilangan bulat ≥ 0 |

Panjang riwayat minimum diputuskan AE di Minggu 2 dan diumumkan lewat E8 (OQ-11). Fitur model memakai lag sampai 14 hari dan rata-rata bergulir 28 hari (PRD §16.4), jadi minimumnya paling sedikit 28 hari. Produk dengan riwayat lebih pendek dari minimum (mis. produk baru) mendapat `insufficient_data`, bukan prediksi yang ditebak. Karena itu FS mengirim riwayat sejak produk masuk katalog: tanpa tanggal itu, produk baru tidak bisa dibedakan dari produk yang tidak laku.

Respons 200:

```json
{
  "request_id": "req_example_004",
  "data": {
    "as_of": "2026-12-05",
    "horizon": { "unit": "day", "count": 7 },
    "predictions": [
      { "product_id": "SH-0012", "predicted_units": 12, "unit": "pairs", "status": "ok" },
      { "product_id": "SH-0099", "predicted_units": null, "unit": "pairs", "status": "insufficient_data" }
    ],
    "model": { "name": "<dari metadata artefak>", "version": "<dari metadata artefak>" }
  },
  "meta": { "label": "estimate" }
}
```

| Field | Aturan |
|---|---|
| `status` per produk | `ok`; `insufficient_data` (riwayat terlalu pendek, mis. produk baru); `failed` (keluaran model tidak lolos validasi) |
| `predicted_units` | Bilangan bulat hasil pembulatan ke terdekat; null bila `status` bukan `ok`. Nilai desimalnya tetap dipakai di dalam AE untuk aturan restok (PRD §16.2) |
| `unit` | `pairs` untuk alas kaki. Satuan produk selain alas kaki menunggu jawaban workshop (§9) |
| Label | FS menandai setiap nilai sebagai perkiraan |

Bila semua produk gagal: 500 `PREDICTION_FAILED`. Bila artefak model tidak termuat: 503 `MODEL_UNAVAILABLE` (ringkasan tetap jalan).

Keterbatasan v1: hari ketika stok habis tercatat sebagai penjualan nol, padahal permintaannya tidak nol. Ini ditulis di README sebagai keterbatasan; field opsional untuk menandai hari stok habis ditunda sesudah v1.

## 6. Error

```json
{
  "request_id": "req_example_006",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "user_message": "Data yang dikirim belum lengkap atau tidak valid.",
    "retryable": false,
    "details": [ { "field": "sales.product_sales[1].units_sold", "issue": "Input should be greater than or equal to 0" } ]
  }
}
```

| Field | Arti |
|---|---|
| `code` | Kode mesin; FS bercabang dari field ini |
| `message` | Untuk developer, berbahasa Inggris (sama dengan pesan pustaka validasi, mudah dicari di log). Tidak ditampilkan ke pemilik |
| `user_message` | Berbahasa Indonesia, aman ditampilkan ke pemilik |
| `retryable` | `true` bila mengulang request yang sama bisa berhasil |
| `details[]` | `{ "field", "issue" }`. `field` ditulis dengan titik antar nama dan `[n]` untuk indeks list, mis. `sales.product_sales[1].units_sold`; `body` bila seluruh body yang bermasalah. `details` tidak pernah menyalin nilai dari payload |

| HTTP | `code` | Kapan | `retryable` |
|---|---|---|---|
| 400 | `MALFORMED_JSON` | Body bukan JSON yang bisa dibaca | false |
| 401 | `UNAUTHORIZED` | `X-API-Key` tidak ada, kosong, atau salah | false |
| 404 | `NOT_FOUND` | Route tidak dikenal | false |
| 405 | `METHOD_NOT_ALLOWED` | Metode HTTP tidak didukung route itu (mis. `POST` ke E1) | false |
| 413 | `PAYLOAD_TOO_LARGE` | Body melebihi batas §4 | false |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Content type bukan JSON | false |
| 422 | `VALIDATION_ERROR` | Gagal skema, rentang, atau ada field tak dikenal | false |
| 422 | `INCONSISTENT_DATA` | Total tidak cocok dengan rincian per produk atau per hari, atau transaksi nol dengan unit atau pendapatan bukan nol | false |
| 429 | `RATE_LIMITED` | Batas request masuk terlampaui (nilai: OQ-17) | true, sesudah `Retry-After` |
| 500 | `INTERNAL_ERROR` | Kegagalan tak terduga | true |
| 500 | `PREDICTION_FAILED` | Semua produk gagal diprediksi | false |
| 503 | `MODEL_UNAVAILABLE` | Artefak prediksi tidak termuat | true |

Kegagalan provider di E2/E3 **bukan** error HTTP: AE menjawab 200 dengan `template_fallback` (§5 E2).

Kode PRD §11.1 yang tidak dipakai di v1 **[USULAN]**: `403 FORBIDDEN` (hanya ada satu kredensial, dengan akses ke semua endpoint), `503 SERVICE_UNAVAILABLE` dan `504 UPSTREAM_TIMEOUT` (ringkasan selalu punya teks cadangan). Satu-satunya 503 dari AE adalah `MODEL_UNAVAILABLE` di E6.

**Respons yang bukan dari AE.** Respons 5xx tanpa amplop AE (tanpa `error.code`, mis. halaman HTML dari host) berasal dari host, bukan dari layanan. FS menganggapnya layanan sedang tidak tersedia dan menerapkan aturan cold start di §3.

## 7. Kapan ringkasan dibuat [USULAN] (OQ-22, OQ-21)
Kuota provider gratis adalah batas nyata layanan ini (PRD §8). Opsi:

| Opsi | Panggilan provider | Untung rugi |
|---|---|---|
| A. AE dipanggil setiap dasbor dibuka | Satu per buka | Paling sederhana untuk FS; kuota bisa habis saat demo dengan banyak refresh |
| B. **FS menyimpan respons per (jenis ringkasan, periode)** dan memanggil AE lagi hanya bila data periode itu berubah atau pemilik menekan "refresh" (usulan AE) | Sekitar satu per periode per perubahan data | FS menyimpan satu JSON per periode (`data` + `meta`) |
| C. Dibuat terjadwal (mis. pukul 21.00 setiap hari) | Satu per hari | Ringkasan hari berjalan tidak ada sampai jadwal tiba; butuh penjadwal di FS, padahal host gratis bisa tidur |

Rincian opsi B yang diusulkan AE (keputusan akhir bersama FS, §9 butir 4):
1. **Yang disimpan** hanya respons `ai` dan `no_data`. Respons `template_fallback` tidak disimpan, supaya teks cadangan tidak tertahan seharian sesudah provider pulih. Ini aman untuk kuota: selama AE dalam masa jeda kuota, AE menjawab dengan templat tanpa memanggil provider.
2. **Deteksi perubahan:** kunci cache memuat SHA-256 dari body request yang akan dikirim ke AE, dengan `inventory.snapshot_at` dikeluarkan dulu (nilainya berubah setiap kali body disusun). Cara ini menangkap transaksi yang dihapus atau dibatalkan dan perubahan stok, yang luput bila hanya memakai `updated_at` transaksi.
3. **Tombol refresh** dibatasi FS: usulan sekali per 60 dtk, dan nonaktif selama request masih berjalan. Rate limit masuk AE (429) menjadi jaring pengamannya.

## 8. Mode tiruan untuk FS
Supaya FS tidak terhambat sebelum layanan AE live (PRD §21), AE menerbitkan contoh respons untuk setiap endpoint v1 dan setiap `generation_mode` di `docs/examples/` pada Minggu 2, dan menjalankan instance lokal dengan provider LLM tiruan yang bisa dipanggil FS.

## 9. Hal terbuka untuk workshop

| # | Pertanyaan | Diputuskan | OQ |
|---|---|---|---|
| 1 | Path, `X-API-Key`, amplop, dan daftar error yang dipangkas di §6 | AE + FS | OQ-05 |
| 2 | Timeout, aturan retry, dan retry cold start di §3 | AE + FS | OQ-16 |
| 3 | Batas ukuran di §4, jumlah produk dan varian asli, dan apakah prediksi per varian ukuran | AE + FS | OQ-18, OQ-07 |
| 4 | Opsi A, B, atau C di §7; bila B, rincian 1–3 dan cara FS mendeteksi perubahan data | FS + AE | OQ-22, OQ-21 |
| 5 | Zona waktu WITA dan minggu yang dimulai hari Senin | FS + DS + pemilik | OQ-08 |
| 6 | Field request yang tidak dikenal ditolak (422), bukan dibuang | AE + FS | - |
| 7 | Siapa yang menyusun agregat di §5 E2 (query FS dengan definisi metrik DS) | FS + DS | OQ-06 |
| 8 | Apakah FS menyimpan tanggal produk masuk katalog (dipakai untuk awal `history` E6) | FS | OQ-11 |
| 9 | Apakah ada produk selain alas kaki; bila ada, `unit` menjadi `pcs` atau satuan per produk | FS + pemilik | OQ-07 |
| 10 | `product_sales` berisi semua produk terjual, dan jumlah `revenue` per produk sama dengan `total_revenue` (termasuk cara membagi diskon tingkat transaksi ke produk); minggu yang belum selesai ditolak di E3 | FS + DS | OQ-06, OQ-19 |

## 10. Riwayat perubahan

| Versi | Tanggal | Perubahan | Disepakati oleh |
|---|---|---|---|
| 0.1 | 2026-11-09 | Draf dari PRD v0.2 §11–12, §18 untuk workshop Minggu 1 | belum disepakati |
| 0.2 | 2026-11-10 | §3: maks. 2 panggilan provider per request, retry memakai sisa batas total. §4: body maks. 1 MB, `history` maks. 90 hari. §5: E1 hanya `ok`/`degraded` dengan status per modul; E6 riwayat harian lengkap dan pembulatan `predicted_units`. §6: 405 `METHOD_NOT_ALLOWED`, format `details[].field`, respons 5xx tanpa amplop AE. §7: rincian opsi B. §9: butir 8–9 | belum disepakati |
| 0.3 | 2026-11-12 | §5 E2: contoh request dan respons dibuat konsisten (jumlah baris produk = total); aturan rincian produk, transaksi nol, `inventory.snapshot_at` wajib dengan offset, `items` unik dan maks. 2 000, bilangan bulat JSON yang ketat, urutan pemeriksaan. §5 E3: `date` tidak dikirim, `end` tidak sesudah hari ini, `daily_breakdown` maks. 7. §6: cakupan `INCONSISTENT_DATA`. §9: butir 10 | belum disepakati |

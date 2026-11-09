# Konteks Capstone (ringkasan teknis)

> Disusun 9 Nov 2026 dari dokumen Asah 2026 yang disimpan di luar repo: Capstone Kick-Off (1 Okt), Capstone Briefing #1 (3 Nov), Checklist Tech Stack, Project Plan tim A26-CS169, serta dokumen wawancara dan use case UMKM. Isinya hanya hal teknis. Nama, ID peserta, dan kontak tidak disalin.
> Spesifikasi bagian AE ada di `docs/prd-ae.md`. Bila ringkasan ini berbeda dengan dokumen asli, dokumen asli yang benar.

## 1. Use case
- **UMKM:** HC Store Import, toko ritel sepatu dan sandal yang beroperasi sejak 2014. Promosi lewat Instagram dan Facebook, komunikasi pelanggan lewat WhatsApp, penjualan di toko fisik. Pembayaran tunai atau transfer bank.
- **Judul use case:** Digitalisasi Sistem Kasir Terpadu dan Dasbor Pemantauan Stok Pintar Berbasis AI.
- **Masalah:** transaksi, pengurangan stok, dan rekap pendapatan harian seluruhnya ditulis tangan di buku. Akibatnya antrean di kasir saat toko ramai, salah tulis harga, stok lupa dipotong (selisih antara rak dan catatan), dan rekap manual berjam-jam sesudah toko tutup.
- **Prioritas UMKM:** digitalisasi pencatatan transaksi kasir dan manajemen stok.
- **Indikator keberhasilan dari wawancara:** transaksi di kasir lebih cepat, tidak ada tulis tangan saat melayani pelanggan, dan laporan penjualan (produk dan ukuran terlaris) tersedia otomatis.
- **Data dari UMKM:** katalog model sepatu dan contoh catatan penjualan harian manual. Omzet bersih dan laba rugi bersifat rahasia, hanya boleh dipakai terbatas atas izin. Karena catatan asli 100% manual, semua data analitik dan AI di MVP berupa data sintetis.
- **Retur:** pelanggan boleh menukar ukuran dengan nota dan tag yang masih utuh. Ini relevan untuk definisi transaksi yang dihitung (PRD OQ-15).

## 2. Tim dan pembagian kerja
Tim A26-CS169 terdiri dari 6 orang: 2 Full-Stack (FS), 2 Data Science (DS), dan 2 Next-Gen AI Engineer (AE). Repo ini milik bagian AE.

| Fitur (Project Plan §B) | Divisi | Indikator keberhasilan menurut Plan |
|---|---|---|
| Modul POS dan pemindaian barcode lewat kamera HP | FS | Kasir memilih produk dari katalog atau memindai barcode, lalu checkout |
| Pengurangan stok otomatis | FS | Stok di basis data berkurang tepat sesudah checkout berhasil |
| Manajemen produk, generate dan cetak barcode | FS | Kelola katalog, kode unik otomatis, print preview stiker |
| Autentikasi dan otorisasi (kasir, pemilik) | FS | Halaman pemilik tidak bisa dibuka akun kasir |
| Riwayat transaksi | FS | Item, total, metode bayar, dan waktu tercatat |
| Model prediksi penjualan per produk (rekomendasi restok), minimal 2 model dibandingkan dengan metrik yang sama | AE | Tabel perbandingan, model terbaik dipilih dengan alasan tertulis, hasil prediksi bisa ditampilkan ke pemilik |
| Asisten AI generatif yang merangkum performa penjualan harian/mingguan (API model proprietary) | AE | Pemilik membaca paragraf insight yang angkanya sesuai data transaksi, dalam bahasa yang mudah dipahami |
| REST API untuk serving model AI dan prompting | AE | Model prediksi dan asisten AI bisa diakses daring oleh backend kasir, terdokumentasi di Swagger, menolak input tidak valid dengan pesan jelas |
| Perumusan masalah dan pertanyaan bisnis | DS | Masalah, peran data, dan lima pertanyaan bisnis tertulis di README |
| Pengolahan data (wrangling) dan penyiapan data | DS | Data transaksi dan produk sintetis bersih, berlabel sumbernya, tersedia di database |
| Analisis data dan rekomendasi | DS | Setiap pertanyaan bisnis dijawab dengan tabel/grafik dan rekomendasi |
| Pemeriksaan ketepatan data dan analisis | DS | Aturan validasi lulus; angka dasbor sama dengan hitungan independen; angka insight AI dicocokkan dengan angka DS |
| Dasbor analitik interaktif dan integrasinya ke aplikasi web | DS | Pendapatan, produk terlaris, stok menipis, jam ramai, dengan filter; ikut berubah saat ada transaksi baru |

**Alur utama:** kasir masuk → memilih produk atau memindai barcode → checkout → stok berkurang otomatis → transaksi masuk riwayat dan dasbor → pemilik membuka dasbor dan membaca grafik serta ringkasan dari AI.

**Alur data AI menurut Plan:** backend menyimpan transaksi dan memotong stok, dasbor menarik agregat dari database, lalu server mengirim data agregat ke REST API AI dan menampilkan teks ringkasan yang dikembalikan di halaman pemilik.

## 3. Checklist Tech Stack yang menyangkut AE

**Gen AI Main Quest (wajib):**
1. Menjelaskan di README permasalahan yang mau diselesaikan model.
2. Membangun model AI yang disesuaikan dengan keadaan data yang disediakan tim Data Science.
3. Menerapkan tahapan preprocessing data sebelum dipakai model AI.
4. Boleh memakai API data publik, sumber data, dataset, library, atau data pribadi apa pun, dengan sumber setiap item dicantumkan di README.
5. Membangun fitur tambahan AI generatif yang memakai API model proprietary (ChatGPT, Gemini, dll.).
6. Membandingkan minimal 2 model atau konfigurasi dengan metrik yang sama, lalu menulis tabel perbandingan dan alasan pemilihan model terbaik di README.
7. Bersama anggota Full-stack, mengembangkan REST API dengan FastAPI atau Flask untuk serving model AI yang bisa diakses daring oleh backend aplikasi.

**Gen AI Side Quest (opsional, nilai tambah):**
- *Pengembangan model:* memeriksa keseimbangan kelas (bila klasifikasi) dan menanganinya; teknik peningkatan kinerja (augmentasi, penyetelan hyperparameter) beserta pengaruhnya di README; uji pada data uji yang disisihkan dengan metrik yang sesuai jenis tugasnya, hasil di README; model tambahan yang melengkapi solusi (mis. klasifikasi sentimen ulasan, minimal 2 kelas).
- *Fitur AI generatif dan model pendukung:* sistem RAG (model generasi, model embedding, vector database); model Main Quest dijadikan klasifikasi intent (minimal 4 intent) untuk mengarahkan pertanyaan; prompt terstruktur (template, few-shot); chatbot menolak pertanyaan di luar konteks usaha dengan sopan, diuji dengan minimal 10 pertanyaan, hasil di README. Catatan: SLM/LLM open-source yang di-host lokal sebagai komponen generasi mendapat nilai tambah, selama bisa diakses tim Full-stack.
- *Penyajian dan integrasi model:* kontrak API (endpoint, format request/response, kode error) disepakati dengan FS sebelum pengembangan; menangani input tidak valid dan kegagalan layanan AI, termasuk API lambat atau kuota gratis habis, dengan pesan jelas; integrasi ke kanal UMKM (Telegram, atau WhatsApp lewat nomor uji gratis WhatsApp Cloud API); dokumentasi API yang bisa dicoba langsung (Swagger/OpenAPI).

**Butir divisi lain yang bersinggungan dengan AE:**
- FS: layanan Gen AI diakses lewat backend, bukan langsung dari frontend; riwayat hasil Gen AI tersimpan di database; hasil DS (dasbor, prediksi, rekomendasi) tampil di fitur yang relevan; backend memvalidasi data dengan schema validation (mis. Joi); kegagalan aplikasi maupun layanan Gen AI dan DS ditangani dengan pesan jelas; kontrak API disepakati dengan tim Gen AI dan DS sebelum pengembangan; aplikasi di-deploy ke free tier; URL API mengikuti konvensi `/api/v1/resource`; aplikasi bisa diakses publik lewat browser, termasuk di ponsel.
- DS (Side Quest "Penyediaan Data untuk Model AI"): menyepakati kebutuhan dan format data dengan tim Gen AI; data dummy atau publik diberi label jelas beserta sumber, cara pembuatan, dan keterbatasannya; pelabelan, transformasi, atau feature engineering sesuai kebutuhan model; kamus data; pembagian data latih dan uji yang mencegah kebocoran.

## 4. Jadwal

| Waktu | Kegiatan dan target teknis |
|---|---|
| s.d. 15 Nov 2026 | Project Plan dikumpulkan. Implementasi boleh dimulai sesudah formulir pengumpulan dikirim |
| 20 Nov | Hasil penilaian Project Plan diumumkan |
| Minggu 1: 20–26 Nov | Wireframe, ERD, data dummy dan wrangling, diskusi kontrak API (request/response dan kode HTTP antara backend dan AI), templat prompt awal. Target: desain awal, dataset bersih, kontrak API JSON disepakati, sketsa prompt siap |
| Minggu 2: 27 Nov – 3 Des | Antarmuka POS, potong stok, visualisasi dasbor, pelatihan dan perbandingan 2 model prediksi, uji prompt anti-halusinasi, REST API (FastAPI/Flask). Target: model prediksi terpilih (.pkl) dan endpoint REST API AI berjalan lokal |
| Minggu 3: 4–10 Des | Integrasi frontend, backend, dasbor DS, dan deploy REST API AI ke cloud. Target: alur kasir input transaksi → stok berkurang → grafik berubah dan ringkasan AI muncul otomatis |
| Minggu 4: 11–20 Des | Uji internal, uji keandalan layanan AI (error, timeout, kuota habis), README dengan tabel komparasi model, panduan penggunaan, demo ke PIC UMKM. Target: aplikasi bebas bug, dokumentasi lengkap, UMKM memberi feedback |
| 23 Nov – 13 Des | Periode mentoring dengan advisor (keahlian Full-Stack, Data Science, atau Gen-AI, dipilih tim) |
| 4–6 Des | Laporan kemajuan |
| 20 Des | Project Brief |
| 24–31 Des | Demo aplikasi ke UMKM |

## 5. Hasil akhir dan batas cakupan (Project Plan)
**Yang dikumpulkan:** aplikasi web kasir dan dasbor terintegrasi yang bisa diakses publik; kode sumber di repositori; README berisi masalah UMKM, alasan pemilihan algoritma atau model AI, tabel komparasi 2 model AI, dan sumber data; panduan penggunaan sistem.

**Tidak dikerjakan:** aplikasi mobile native dan e-commerce untuk pelanggan; integrasi payment gateway (QRIS, transfer) dan struk lewat WhatsApp API; akuntansi, perpajakan, dan payroll; harga beli supplier dan margin laba bersih.

## 6. Risiko dan rencana uji di Project Plan yang menyangkut AE
- **Halusinasi angka:** prompt dibatasi pada metrik yang sudah diolah dan sampel ringkasan diuji; cadangannya ringkasan templat baku tanpa AI.
- **API Gen AI lambat, mati, atau kuota habis:** exception handling dengan pesan seperti "AI sedang sibuk" dan rate limiting; cadangannya teks templat.
- **Data sintetis dianggap data nyata:** semua data sintetis diberi label, README menyatakan keterbatasannya, dan hasil model dipresentasikan sebagai bukti alur bekerja, bukan akurasi toko.
- **Bentrok format integrasi FS–AE:** kontrak API dan skema kolom disepakati sejak minggu 1; cadangannya JSON tiruan di frontend.
- **Uji ringkasan AI:** panggil asisten dengan data transaksi satu hari lalu bandingkan angkanya dengan dasbor; ulangi untuk hari tanpa transaksi. Harapan: angka sama dan bahasanya mudah dipahami; hari tanpa transaksi menampilkan pesan belum ada data tanpa angka karangan.
- **Pencatatan bug:** Notion (utama), Google Sheets (cadangan); masalah diperbaiki lalu diuji ulang.

## 7. Kepemilikan data dan aset
- Kode, desain, dan dokumentasi capstone menjadi hak tim. Data usaha dan pelanggan, logo, merek, dan foto tetap hak UMKM, dan hanya dipakai dengan izin.
- Data sensitif hanya dipakai dengan izin. Pakai data contoh dan jangan unggah data sensitif.
- Akibatnya untuk repo ini: hanya data sintetis berlabel; tidak ada data pribadi, kontak, atau angka keuangan asli toko.

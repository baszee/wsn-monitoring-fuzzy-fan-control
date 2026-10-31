# WSN Monitor

Sistem pemantauan lingkungan multi-node berbasis Wireless Sensor Network (WSN) dengan kendali fan DC 12 V otomatis memakai logika fuzzy Mamdani. Proyek tugas akhir Teknik Komputer, Universitas Negeri Semarang.

## Cara kerja

Setiap node mengirim suhu, kelembapan relatif (RH), dan tegangan sensor debu. Backend memproses data dalam urutan berikut:

1. Tegangan debu dinormalisasi menjadi indeks debu memakai acuan c_0 dan c_h.
2. Fuzzy Mamdani dengan 27 aturan menghasilkan skor kondisi s_i dan tingkat kendali u_i untuk tiap node. Defuzzifikasi memakai centroid.
3. Kondisi node ditentukan dari s_i: Baik (s_i < 35), Perlu Perhatian (35 sampai 65), Buruk (s_i > 65).
4. Tingkat kendali zona adalah u_zona = max(u_i). Node dengan u_i tertinggi menjadi node penentu.
5. u_zona dipetakan ke PWM fan. Fan mati bila u_zona <= 15. Di atas itu PWM naik linear dari 30% sampai 100% pada u_zona = 88,33. Perubahan PWM baru diterapkan bila selisihnya minimal 5%.
6. Data yang lebih lama dari batas kesegaran (bawaan 10 detik) tidak dipakai. Bila tidak ada data yang bisa dipakai, fan mati dan status kendali "Kendali tidak tersedia".

Admin dapat memilih mode Manual dan menerapkan PWM 0 sampai 100% dari halaman Fan dan Kendali. Selama Manual, fuzzy, kendali zona, dan PWM otomatis tetap dihitung dan disimpan sebagai pembanding. Aplikasi selalu mulai di mode Otomatis dengan PWM 0%.

Worker memeriksa rekaman baru tiap 5 detik dan hanya memproses rekaman yang belum pernah dihitung. Keputusan zona disimpan saat ada pengukuran baru atau keputusan berubah.

## Halaman

| Alamat | Isi |
| :--- | :--- |
| `/` | Beranda |
| `/dashboard/` | Ringkasan |
| `/dashboard/nodes/` | Daftar node dan detail per node |
| `/dashboard/fan/` | Fan dan kendali |
| `/dashboard/fuzzy/` | Rincian perhitungan fuzzy |
| `/dashboard/history/` | Riwayat |
| `/dashboard/simulation/` | Simulasi tanpa efek ke fan |
| `/dashboard/settings/` | Konfigurasi (baca saja) |
| `/dashboard/login/` | Masuk admin |
| `/docs` | Dokumentasi API |

## Struktur proyek

```text
backend/
  app/
    api/        endpoint REST
    core/       konfigurasi dan koneksi database
    models/     tabel database
    schemas/    skema Pydantic
    services/   fuzzy, agregasi zona, PWM, worker, kesegaran data
    settings.py parameter operasional
    main.py     aplikasi FastAPI
  init_db.sql   skema PostgreSQL
  make_admin_hash.py pembuat hash kata sandi admin untuk .env
  seed_dummy.py data awal: konfigurasi, 27 aturan, node contoh
  dummy_profile.py  generator data uji yang halus (suhu, RH, debu)
  backfill_dummy.py isi riwayat 24 jam untuk tangkapan layar dan uji grafik
  feed_dummy.py     pengirim data uji tiap 10 detik, menyambung dengan riwayat
frontend/
  index.html    beranda
  dashboard/    halaman dashboard
  src/          JavaScript, CSS, ikon, font
tests/          pengujian otomatis
```

## Menjalankan

Prasyarat: Python 3.10 atau lebih baru. Node.js tidak diperlukan karena frontend disajikan oleh FastAPI.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
python backend/seed_dummy.py
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Untuk mengirim data uji, buka terminal kedua:

```powershell
python backend/backfill_dummy.py      # sekali saja: isi riwayat 24 jam (menghapus data lama)
python backend/feed_dummy.py          # biarkan menyala agar data tetap segar
```

Database SQLite default ada di `wsn.db` pada root proyek. Untuk PostgreSQL, isi `DATABASE_URL`.

## Pengaturan

Dapat diubah lewat environment variable atau berkas `.env`.

| Nama | Bawaan | Fungsi |
| :--- | :--- | :--- |
| `FRESHNESS_SECONDS` | 10 | Batas usia data yang masih dipakai |
| `WORKER_INTERVAL_SECONDS` | 5 | Jeda pemeriksaan rekaman baru |
| `CENTROID_STEP` | 0.01 | Resolusi defuzzifikasi |
| `CORS_ORIGINS` | `http://localhost:8000` | Asal yang diizinkan, dipisah koma |
| `DATABASE_URL` | SQLite di root proyek | Koneksi database |
| `ADMIN_USERNAME` | kosong | Nama pengguna admin. Kosong berarti login nonaktif |
| `ADMIN_PASSWORD_HASH` | kosong | Hash kata sandi admin dari `make_admin_hash.py` |
| `COOKIE_SECURE` | `false` | Isi `true` bila diakses lewat HTTPS. Di localhost (HTTP) harus `false` |

## Akun admin

Buat hash kata sandi, lalu salin ke berkas `.env` (di root proyek atau di `backend/`):

```powershell
python backend/make_admin_hash.py
```

```text
ADMIN_USERNAME=nama_pengguna
ADMIN_PASSWORD_HASH=<hasil dari skrip>
COOKIE_SECURE=false
```

Berkas `.env` tidak ikut ke git. Sesi disimpan di memori server, jadi restart server mengakhiri semua sesi. Login dibatasi 5 percobaan salah, lalu dikunci 5 menit per alamat IP. Jalankan satu proses server saja (tanpa banyak worker) karena sesi, pembatas, dan mode kendali disimpan di memori.

## Pengujian

```powershell
pytest tests/ -v
```

Pengujian mencakup normalisasi debu, fungsi keanggotaan, 27 aturan, agregasi zona, histeresis PWM, kesegaran data, endpoint API, login admin, mode Manual, dan batas permintaan.

## Keterbatasan saat ini

- Driver PWM masih tiruan (mock); belum mengendalikan perangkat keras.
- Layanan aktuator terpisah belum ada; worker berjalan di proses yang sama dengan API.

## Pengembang

Abbas Abdurrahman, NIM 2305110048, Teknik Komputer, Universitas Negeri Semarang. Dosen pembimbing: Vera Noviana Sulistyawan, S.T., M.T.

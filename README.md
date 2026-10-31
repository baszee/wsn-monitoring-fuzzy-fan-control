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
  seed_dummy.py data awal: konfigurasi, 27 aturan, node contoh
  feed_dummy.py pengirim data uji tiap 10 detik
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
python backend/feed_dummy.py
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

## Pengujian

```powershell
pytest tests/ -v
```

Pengujian mencakup normalisasi debu, fungsi keanggotaan, 27 aturan, agregasi zona, histeresis PWM, kesegaran data, dan endpoint API.

## Keterbatasan saat ini

- Driver PWM masih tiruan (mock); belum mengendalikan perangkat keras.
- Mode manual dan login admin belum tersedia.
- Layanan aktuator terpisah belum ada; worker berjalan di proses yang sama dengan API.

## Pengembang

Abbas Abdurrahman, NIM 2305110048, Teknik Komputer, Universitas Negeri Semarang. Dosen pembimbing: Vera Noviana Sulistyawan, S.T., M.T.

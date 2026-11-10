# Integrasi Subsistem Penerima M2

Backend Abbas tidak mengubah source atau tabel milik M2. Integrasi dilakukan melalui
adaptor read-only dengan alur berikut:

```text
receiver.py M2 -> sesi_uji + paket_valid -> adaptor backend -> fuzzy -> zone_controls
```

Snapshot schema receiver yang menjadi kontrak integrasi disimpan pada
`docs/database/receiver-schema-v1.sql`. Perubahan berikutnya dari pemilik receiver harus
dibandingkan dengan snapshot ini sebelum adaptor diperbarui.

## Mode pengembangan

- `SENSOR_SOURCE=mock`: memakai `mock_receiver_valid_data` dan `feed_dummy.py`.
- `SENSOR_SOURCE=paket_valid`: membaca `paket_valid` dan opsional memfilter `sesi_uji.mode`.
- `SENSOR_SOURCE=node_readings`: kompatibilitas untuk kontrak tabel M2 versi lama.

Kedua mode menggunakan `DATABASE_URL` yang sama. Saat PostgreSQL Orange Pi siap,
perpindahan dilakukan melalui konfigurasi `.env`, bukan perubahan fuzzy atau frontend.

## Pemetaan data

| M2 | Backend Abbas |
| --- | --- |
| `id` | `source_record_id` |
| `received_at` | `source_timestamp` |
| `node_id=1` | `NODE-01` |
| `temperature` | masukan suhu |
| `humidity` | masukan kelembapan |
| `v0` | nilai debu mentah |
| `pressure_hpa` | metadata dashboard |
| `rssi`, `snr` | metadata komunikasi |

Setiap baris yang sudah berada di `paket_valid` dianggap paket valid karena receiver
M2 membuang paket CRC error. Kelengkapan suhu, kelembapan, dan `v0` diperiksa terpisah.
Rekaman valid tetapi tidak lengkap tidak diproses oleh fuzzy.

Gunakan `PAKET_VALID_SESSION_MODES=sensor` bila sesi dengan mode `uji` tidak boleh
memengaruhi fuzzy dan kendali fan. Nilai kosong memakai semua sesi.

## Keamanan database bersama

- Jangan menjalankan `backend/init_db.sql` pada database bersama karena berisi `DROP`.
- Gunakan `backend/bootstrap_db.py` untuk membuat tabel aplikasi tanpa menghapus tabel.
- Jangan membuka port PostgreSQL 5432 langsung ke internet; gunakan jaringan privat.
- Gunakan akun terpisah untuk receiver M2 dan backend Abbas.
- Simpan DSN dan password pada environment, bukan source code.
- Pastikan hanya satu instance memakai `WORKER_ENABLED=true`; instance lain harus read-only.

## Pengujian lokal tanpa Orange Pi

1. Gunakan SQLite pengembangan terpisah, misalnya `DATABASE_URL=sqlite:///./wsn_m2_dev.db`.
2. Set `SENSOR_SOURCE=paket_valid` di `.env` atau environment proses.
3. Jalankan `python backend/bootstrap_db.py` untuk tabel aplikasi dan konfigurasi awal.
4. Jalankan `python backend/tools/sim_paket_valid.py --init --interval 5`.
5. Jalankan backend seperti biasa dengan environment yang sama.
6. Periksa `GET /api/status` dan dashboard.

Database terpisah mencegah ID `paket_valid` simulator bertabrakan dengan
`source_record_id` dari riwayat dummy lama di `wsn.db`.

Opsi `--init` simulator hanya dapat membuat tabel pada SQLite. Simulator menolak membuat
schema pada PostgreSQL agar tabel M2 tidak terbentuk tanpa persetujuan.

## Batas tahap ini

Adaptor menyelesaikan akses data dan dashboard. Kendali PWM fisik tetap memerlukan
backend/worker pada Orange Pi atau layanan aktuator terpisah di Orange Pi.


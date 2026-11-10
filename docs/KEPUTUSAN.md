# Keputusan Tahap 0

| No | Hal | Keputusan |
|----|-----|-----------|
| 1 | Halaman | Landing, Node Detail, dan Node Sensor tetap ada. Analisis Fuzzy belum digabung ke Node Detail, dinilai ulang setelah Tahap 5. Konfigurasi dibuat baca-saja. |
| 2 | Batas kesegaran data | 10 detik (FRESHNESS_SECONDS), dapat diubah lewat environment variable. Lihat catatan di bawah. |
| 3 | Langkah centroid | 0,01 (sebelumnya 0,1). Uji memakai toleransi 0,05 terhadap nilai teoretis. Tampilan dibulatkan 1 desimal. |
| 4 | Font | Disimpan lokal di frontend/fonts/, tanpa Google Fonts. |
| 5 | Interval proses worker | 5 detik. Hanya memproses source_record_id baru. |
| 6 | Cabang git | Satu cabang per tahap: tahap-1-pembersihan, tahap-2-backend, dst. |

## Pembaruan 11 November 2026: data lama tetap dipakai kendali
- Keputusan lama "semua data lama -> Otomatis 0%" diganti.
- `FRESHNESS_SECONDS` (30-60 detik) hanya menentukan label "Terbaru"/"Data lama" di dashboard.
- `CONTROL_HOLD_SECONDS` (bawaan 600 detik) menentukan umur maksimum data yang masih dipakai
  mengendalikan fan. Node yang datanya terlambat tetapi masih di bawah batas ikut dihitung
  dalam nilai kendali zona (maksimum), dan dashboard menulis "Terlambat, masih dipakai".
- Lewat `CONTROL_HOLD_SECONDS`: kendali tidak tersedia dan Otomatis menuju 0% (putaran minimum,
  karena uji fisik menunjukkan XF-120-K tidak berhenti pada 0%).
- Alasan: jeda kiriman LoRa di lapangan 10-50 detik membuat kipas sering turun ke minimum.
- Skenario uji E2E-05 pada runbook integrasi perlu disesuaikan.
- Nilai lama di bawah (10 detik, worker 5 detik) adalah riwayat Tahap 0; nilai aktif ada di `.env`.

## Catatan batas kesegaran 10 detik (riwayat Tahap 0)
- Dashboard dan keputusan fan memakai batas yang sama dari backend. Frontend tidak menghitung sendiri.
- Node yang lebih lambat dari 10 detik dianggap "data lama", dan fan mengikuti aturan fail-safe PRD.
- Selama node masih mengirim tiap 300 detik, semua node akan selalu "data lama".
  Selama masa uji, jalankan dengan FRESHNESS_SECONDS=360.
- Setelah interval 10 detik benar-benar berjalan, sebaiknya batas dinaikkan ke 2-3 kali interval
  (20-30 detik) supaya satu paket terlambat tidak membuat fan langsung masuk kondisi gagal.

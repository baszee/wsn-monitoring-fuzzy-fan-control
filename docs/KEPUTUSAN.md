# Keputusan Tahap 0

| No | Hal | Keputusan |
|----|-----|-----------|
| 1 | Halaman | Landing, Node Detail, dan Node Sensor tetap ada. Analisis Fuzzy belum digabung ke Node Detail, dinilai ulang setelah Tahap 5. Konfigurasi dibuat baca-saja. |
| 2 | Batas kesegaran data | 10 detik (FRESHNESS_SECONDS), dapat diubah lewat environment variable. Lihat catatan di bawah. |
| 3 | Langkah centroid | 0,01 (sebelumnya 0,1). Uji memakai toleransi 0,05 terhadap nilai teoretis. Tampilan dibulatkan 1 desimal. |
| 4 | Font | Disimpan lokal di frontend/fonts/, tanpa Google Fonts. |
| 5 | Interval proses worker | 5 detik. Hanya memproses source_record_id baru. |
| 6 | Cabang git | Satu cabang per tahap: tahap-1-pembersihan, tahap-2-backend, dst. |

## Catatan batas kesegaran 10 detik
- Dashboard dan keputusan fan memakai batas yang sama dari backend. Frontend tidak menghitung sendiri.
- Node yang lebih lambat dari 10 detik dianggap "data lama", dan fan mengikuti aturan fail-safe PRD.
- Selama node masih mengirim tiap 300 detik, semua node akan selalu "data lama".
  Selama masa uji, jalankan dengan FRESHNESS_SECONDS=360.
- Setelah interval 10 detik benar-benar berjalan, sebaiknya batas dinaikkan ke 2-3 kali interval
  (20-30 detik) supaya satu paket terlambat tidak membuat fan langsung masuk kondisi gagal.

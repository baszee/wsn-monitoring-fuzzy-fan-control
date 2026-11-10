# Deploy dashboard tampilan ke Vercel

Vercel hanya **menampilkan** data. Fuzzy, keputusan kipas, dan kendali fan tetap
berjalan di perangkat pengendali (laptop sekarang, Orange Pi nanti). Keduanya membaca
dan menulis database Supabase yang sama.

```text
Receiver M2 ──► Supabase public.paket_valid ◄── Vercel (DISPLAY_ONLY, hanya membaca)
                     │                          ▲
                     ▼                          │
        Laptop/Orange Pi (worker + kipas) ──► Supabase wsnova.* (hasil fuzzy, keputusan,
                                              worker_heartbeats)
```

## Langkah

1. Di laptop, jalankan `run.bat` sekali agar migrasi `0003_worker_heartbeat` membuat
   tabel `wsnova.worker_heartbeats`. Vercel tidak menjalankan migrasi.
2. Push repository ke GitHub, lalu impor project di Vercel. Entrypoint sudah diatur di
   `pyproject.toml` (`[tool.vercel] entrypoint = "backend.app.main:app"`).
3. Project Settings → Functions → Region: pilih **Tokyo (hnd1)**, dekat dengan
   Supabase `ap-northeast-1`. Region lain membuat setiap halaman lebih lambat.
4. Project Settings → Environment Variables (Production):

| Variabel | Nilai |
|---|---|
| `DATABASE_URL` | sama dengan laptop (session pooler Supabase) |
| `SENSOR_SOURCE` | `paket_valid` |
| `PAKET_VALID_SESSION_MODES` | `sensor` |
| `APP_DB_SCHEMA` | `wsnova` |
| `SOURCE_DB_SCHEMA` | `public` |
| `ZONE_NODE_IDS` | `NODE-01,NODE-02` (harus sama dengan laptop) |
| `FRESHNESS_SECONDS` | sama dengan laptop (mis. `60`) |
| `CONTROL_HOLD_SECONDS` | sama dengan laptop (mis. `600`) |
| `DISPLAY_ONLY` | `true` |
| `WORKER_ENABLED` | `false` |
| `PWM_DRIVER` | `mock` |

   `ADMIN_*` tidak diperlukan: versi tampilan tidak punya kendali admin.
5. Redeploy, buka URL Vercel, dan cocokkan dengan dashboard laptop.

## Perilaku

- Data sensor (suhu, kelembapan, tekanan, debu, sinyal) dibaca langsung dari
  `paket_valid`, jadi tetap tampil walau laptop mati.
- Kondisi, kebutuhan kipas, dan kecepatan kipas berasal dari laptop. Bila laptop
  tidak mengirim detak selama kira-kira 35 detik, dashboard menulis
  "Pengendali tidak aktif".
- Mode Manual ditolak (HTTP 409) dan tombolnya tidak tampil.
- Koneksi database di Vercel memakai `NullPool` agar tidak menahan kuota pooler.

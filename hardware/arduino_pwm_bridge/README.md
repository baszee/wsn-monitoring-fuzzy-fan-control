# Bridge PWM Arduino Uno

Sketch `arduino_pwm_bridge.ino` menjadikan Arduino Uno R3/clone sebagai bridge
USB serial ke PWM fan 4-pin sekitar 25 kHz.

## Upload

1. Hubungkan Arduino Uno melalui USB.
2. Di Arduino IDE pilih **Tools > Board > Arduino Uno**.
3. Pilih **Tools > Port > COM13**.
4. Buka `arduino_pwm_bridge.ino` lalu klik **Upload**.
5. Buka Serial Monitor pada **115200 baud** dan baris baru `Newline`.
6. Kirim `PING`; jawaban harus `OK READY`.
7. Kirim `PWM 0`, `PWM 30`, `PWM 50`, dan `PWM 100`; jawaban harus
   `OK PWM <nilai>`.
8. Tutup Serial Monitor sebelum backend memakai COM13.

## Pin dan rangkaian

- Keluaran PWM: Arduino `D9`.
- `D9 -> R1 2.2 kOhm -> Base 2N2222`.
- `Base -> R2 10 kOhm -> GND`.
- `Emitter -> GND bersama`.
- `Collector -> pin PWM fan`.
- Fan memakai adaptor 12 V sendiri; jangan mengambil 12 V dari Arduino.
- GND adaptor, fan, transistor, dan Arduino harus terhubung bersama.

Rangkaian open-collector membalik level listrik. Sketch menerima makna duty
cycle fan biasa dan melakukan inversi pada lapisan perangkat keras.

## Failsafe dan Watchdog

- **Watchdog Timeout (15 detik)**: Jika Arduino tidak menerima perintah valid dari backend selama 15 detik, sketch otomatis mengembalikan perintah duty fan ke 0%. Batas 15 detik ini memberikan toleransi terhadap latensi jaringan internet/database remote (seperti Supabase) tanpa mematikan fan secara prematur.
- **Perilaku USB Terputus**: Bila kabel USB dicabut/Arduino mati, pin D9 menjadi LOW sehingga transistor off dan pin PWM fan floating/ditarik HIGH oleh internal pull-up fan. Akibatnya, fan berputar 100% (standar failsafe kipas Intel 4-wire), bukan 0%. Failsafe 0% hanya berlaku jika Arduino tetap diberi daya dan komunikasi serial backend terhenti.

## Aktivasi backend

Setelah upload dan uji Serial Monitor berhasil, isi `.env`:

```env
PWM_DRIVER=arduino
PWM_SERIAL_PORT=COM13
PWM_SERIAL_BAUD=115200
PWM_SERIAL_TIMEOUT_SECONDS=2
PWM_SERIAL_STARTUP_SECONDS=2
PWM_FREQUENCY_HZ=25000
PWM_INVERTED=true
```

Untuk pengujian awal, gunakan `WORKER_ENABLED=false` agar hanya perintah Manual
yang dapat mengubah fan. Tutup Serial Monitor sebelum menjalankan backend karena
COM13 hanya dapat dibuka satu proses pada satu waktu.

Sebelum mengaktifkan factory pada web, bridge dapat diuji terpisah:

```powershell
.\.venv\Scripts\python.exe backend\tools\test_arduino_pwm.py --port COM13 --values 0 30 50 75 100 --hold 3
```

Alat uji selalu mengirim 0% dan menutup COM13 ketika selesai atau dihentikan.

## Hasil uji fisik

| Tanggal | Perintah | Hasil |
|---|---|---|
| 11 Nov 2026 | PWM 0% | Fan ID-COOLING XF-120-K **tidak berhenti**; tetap berputar pada putaran minimum. |

Akibatnya, status backend `Mati` ditampilkan di dashboard sebagai **"Putaran minimum"**. Bila kondisi benar-benar mati dibutuhkan, diperlukan pemutus daya 12 V terpisah (MOSFET/relay). `D_min` dan `Delta_D_update` masih perlu diuji.

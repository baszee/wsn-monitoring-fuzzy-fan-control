# WSNOVA — WSN Environmental Monitoring and Fuzzy Fan Control

> **A web-based system for monitoring multi-node WSN environmental data, classifying environmental conditions, and controlling a 12 V PWM fan using Mamdani fuzzy logic.**

---

## 📌 Ringkasan Sistem (Overview)

**WSNOVA** adalah sistem pemantauan lingkungan dan kendali aktuator berbasis web yang dirancang untuk Wireless Sensor Network (WSN). Sistem ini mengumpulkan data lingkungan multi-node (Suhu, Kelembapan Relatif / RH, dan Tegangan Sensor Debu), melakukan normalisasi indeks debu, mengevaluasi kondisi lingkungan menggunakan inferensi **Fuzzy Mamdani 27 aturan murni NumPy**, mengagregasi tingkat kendali zona berdasarkan node paling kritis ($u_{\text{zona}} = \max(u_i)$), serta menghasilkan sinyal kendali **12 V PWM fan** dengan mekanisme histeresis pembaruan duty cycle.

---

## 🏗️ Arsitektur & Alur Pemrosesan Data

```text
+--------------------------------------------------------------+
|               Wireless Sensor Network (WSN)                  |
|    [NODE-01]            [NODE-02]            [NODE-03]       |
| (Temp, RH, Dust)   (Temp, RH, Dust)    (Temp, RH, Dust)      |
+--------------------------------------------------------------+
                               |
                               v
               [Mock / Gateway Receiver Valid Data]
                               |
                               v
               [Normalisasi Indeks Debu (c_0, c_h)]
                               |
                               v
            [Fuzzy Inference System Mamdani (NumPy)]
           - 27 Aturan Evaluasi (Suhu x RH x Debu)
           - Fuzzifikasi (Trapesium & Segitiga)
           - Implikasi Min & Agregasi Max
           - Defuzzifikasi Centroid (Skor Kondisi & Tingkat Kendali u_i)
                               |
                               v
             [Agregasi Zona & Node Penentu (i*)]
             u_zona = max_{i in V}(u_i)
                               |
                               v
              [Pemetaan PWM Fan DC 12V & Histeresis]
             - Ambang mati: u_zona <= u_off (15%) -> PWM 0%
             - Ambang aktif: u_zona in (15%, 88.33%] -> Linear PWM (30% - 100%)
             - Histeresis: |Delta PWM| >= delta_d_update (5.0%)
                               |
                               v
               [FastAPI REST API & Background Worker]
                               |
                               v
             [Antarmuka Web WSNOVA (HTML5/Tailwind/ESM)]
```

---

## ✨ Fitur Utama

- **Multi-Node Environmental Monitoring**: Pemantauan real-time status node WSN terdistribusi (Suhu, Kelembapan Relatif, Tegangan Debu, dan Indeks Debu).
- **Klasifikasi Kondisi Lingkungan**: Penilaian otomatis kondisi setiap node ke dalam 3 kelas:
  - 🟢 **Baik** ($s_i < 35,0$)
  - 🟡 **Perlu Perhatian** ($35,0 \le s_i \le 65,0$)
  - 🔴 **Buruk** ($s_i > 65,0$)
- **PWM Fan Control Berbasis Fuzzy Mamdani**:
  - Mesin inferensi murni matriks NumPy (bebas dependensi library fuzzy eksternal).
  - Agregasi zona berorientasi mitigasi risiko terburuk (*worst-case scenario*).
  - Pencegahan *jitter* aktuator kipas menggunakan proteksi histeresis ($\Delta D = 5\%$).
- **Transparansi Rantai Keputusan (Decision Chain)**: Menampilkan derajat keanggotaan ($\mu$), aturan aktif, dan kurva hasil defuzzifikasi pada dashboard.
- **Simulasi Interaktif "What-If"**: Pengujian kombinasi input hipotetis secara instan tanpa memengaruhi status motor fan fisik maupun basis data.
- **Antarmuka Web Multi-Halaman**:
  - Landing Page publik interaktif
  - Dashboard monitoring terintegrasi
  - Halaman khusus: Daftar Node, Detail Node Sensor, Kontrol Fan, Analisis Fuzzy, Riwayat Data, Simulasi, dan Konfigurasi Parameter.
- **Dukungan Basis Data Fleksibel**: Otomatis mendukung SQLite lokal (tanpa konfigurasi tambahan) dan PostgreSQL (Psycopg v3).

---

## 📂 Struktur Proyek

```text
├── backend/
│   ├── app/
│   │   ├── api/            # Router dan endpoint REST API FastAPI
│   │   ├── core/           # Konfigurasi aplikasi & koneksi database (SQLAlchemy)
│   │   ├── models/         # Skema ORM database (Node, Config, Fuzzy, PWM)
│   │   ├── schemas/        # Validasi schema data Pydantic
│   │   ├── services/       # Engine Fuzzy Mamdani, agregasi zona, kontrol PWM, worker
│   │   └── main.py         # Entrypoint FastAPI & static mount frontend
│   ├── init_db.sql         # Skrip inisialisasi skema basis data PostgreSQL
│   ├── requirements.txt    # Daftar dependensi Python backend
│   └── seed_dummy.py       # Seeder basis data (27 aturan fuzzy, parameter, node sampel)
├── frontend/
│   ├── dashboard/          # Halaman dashboard monitoring dan sub-halaman modular
│   │   ├── fan/            # Tampilan kendali fan & animasi putaran PWM
│   │   ├── fuzzy/          # Visualisasi rincian inferensi fuzzy Mamdani
│   │   ├── history/        # Tabel riwayat pembacaan sensor dan kendali
│   │   ├── nodes/          # Daftar node dan halaman detail individual
│   │   ├── settings/       # Tampilan parameter acuan dan basis aturan
│   │   ├── simulation/     # Panel simulasi interaktif "What-If"
│   │   └── index.html      # Dashboard utama
│   ├── src/                # Modul JavaScript ES6 murni & gaya visual Tailwind
│   └── index.html          # Landing Page publik WSNOVA
├── tests/                  # Pengujian otomatis (Unit test API, Fuzzy, Agregasi & PWM)
├── .gitignore              # Proteksi file repositori
└── README.md               # Dokumentasi proyek
```

---

## 🚀 Panduan Menjalankan Sistem

Sistem dapat dijalankan langsung menggunakan 1 terminal tanpa memerlukan Node.js karena antarmuka web disajikan secara statis oleh FastAPI.

### 1. Prasyarat
- Python 3.10+ (Direkomendasikan Python 3.11 / 3.12 / 3.13)
- Git

### 2. Langkah Instalasi & Menjalankan

```powershell
# 1. Masuk ke direktori proyek
cd "e:\Abbas Abdurrahman\Arah\Web"

# 2. Buat dan aktifkan virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Pasang dependensi
pip install -r backend/requirements.txt

# 4. Inisialisasi & seeder basis data
python backend/seed_dummy.py

# 5. Jalankan server Uvicorn
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Rute Layanan Web & API

Setelah server menyala, akses rute berikut melalui browser:

| Alamat URL | Fungsi / Halaman |
| :--- | :--- |
| `http://localhost:8000/` | 🏠 Landing Page WSNOVA |
| `http://localhost:8000/home` | 🏠 Alias Landing Page |
| `http://localhost:8000/dashboard/` | 📊 Dashboard Monitoring Lingkungan Utama |
| `http://localhost:8000/dashboard/nodes/` | 📡 Status Node Sensor Terdistribusi |
| `http://localhost:8000/dashboard/fan/` | 🌀 Panel Kendali PWM Fan DC 12V |
| `http://localhost:8000/dashboard/fuzzy/` | 🔍 Transparansi Inferensi Fuzzy & Decision Chain |
| `http://localhost:8000/dashboard/simulation/` | 🧪 Simulasi Interaktif What-If |
| `http://localhost:8000/docs` | 📚 Dokumentasi Interaktif REST API (Swagger UI) |

---

## 🧪 Pengujian Otomatis (Unit Testing)

Proyek ini dilengkapi dengan 40 pengujian unit otomatis yang mencakup fungsi normalisasi, fungsi keanggotaan, 27 skenario inferensi fuzzy, agregasi zona, histeresis PWM, serta endpoint API:

```powershell
# Jalankan seluruh rangkaian pengujian
python tests/test_api.py
python tests/test_fuzzy.py
python tests/test_zone_pwm.py
```

---

## 👨‍💻 Identitas Pengembang & Penelitian

- **Nama**: Abbas Abdurrahman
- **NIM**: 2305110048
- **Program Studi**: Teknik Komputer
- **Institusi**: Universitas Negeri Semarang (UNNES)
- **Topik**: Sistem Monitoring Multi-Node WSN, Klasifikasi Kondisi Lingkungan, dan Kendali PWM Fan DC 12V Berbasis Logika Fuzzy Mamdani.


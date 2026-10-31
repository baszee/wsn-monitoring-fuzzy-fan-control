"""Siapkan tabel dan konfigurasi dasar sebelum server produksi dimulai."""

from seed_dummy import seed_database


if __name__ == "__main__":
    seed_database(include_samples=False)

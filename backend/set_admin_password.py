"""Mengganti username/kata sandi admin langsung di berkas .env.

  .venv\\Scripts\\python.exe backend\\set_admin_password.py

Skrip menanyakan username (Enter = tetap) dan kata sandi baru dua kali, lalu
menulis ADMIN_USERNAME dan ADMIN_PASSWORD_HASH ke backend/.env dan .env di root
proyek. Baris lain di .env tidak diubah. Jalankan ulang server setelahnya.
"""
import getpass
import os
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import hash_password  # noqa: E402

ENV_FILES = [BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"]


def current_username() -> str:
    for path in ENV_FILES:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ADMIN_USERNAME="):
                    return line.split("=", 1)[1].strip().strip("\"'")
    return "admin"


def write_values(path: Path, values: dict) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in values:
            out.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    old_user = current_username()
    user = input(f"Username admin [{old_user}]: ").strip() or old_user
    pw = getpass.getpass("Kata sandi baru (tidak tampil saat diketik): ")
    if len(pw) < 6:
        sys.exit("Kata sandi minimal 6 karakter.")
    if pw != getpass.getpass("Ulangi kata sandi: "):
        sys.exit("Kata sandi tidak sama. Tidak ada yang diubah.")

    values = {"ADMIN_USERNAME": user, "ADMIN_PASSWORD_HASH": hash_password(pw)}
    for path in ENV_FILES:
        if path.is_file():
            write_values(path, values)
            print(f"Diperbarui: {path}")
    if not any(p.is_file() for p in ENV_FILES):
        write_values(ENV_FILES[0], values)
        print(f"Dibuat: {ENV_FILES[0]}")
    print(f"\nSelesai. Login dengan username '{user}' setelah server dijalankan ulang.")
    if os.environ.get("ADMIN_PASSWORD_HASH"):
        print("PERINGATAN: ADMIN_PASSWORD_HASH juga diset sebagai variabel environment Windows;"
              " nilai itu akan mengalahkan .env. Hapus dari environment bila login tetap gagal.")


if __name__ == "__main__":
    main()

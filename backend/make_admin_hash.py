"""Membuat hash kata sandi admin untuk berkas .env.

  python backend/make_admin_hash.py

Salin baris yang dicetak ke .env di root proyek, bersama ADMIN_USERNAME.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.security import hash_password

pw = getpass.getpass("Kata sandi admin: ")
if pw != getpass.getpass("Ulangi kata sandi: "):
    sys.exit("Kata sandi tidak sama.")
print("\nADMIN_PASSWORD_HASH=" + hash_password(pw))

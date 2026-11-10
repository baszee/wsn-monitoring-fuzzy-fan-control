"""Uji bridge PWM Arduino secara terpisah dari worker dan database WSNova."""

import argparse
from pathlib import Path
import sys
import time


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.pwm_arduino import ArduinoSerialPWMDriver  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Uji PWM fan melalui Arduino USB")
    parser.add_argument("--port", default="COM13", help="port Arduino (default COM13)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument(
        "--values", type=float, nargs="+", default=[0.0],
        help="urutan duty cycle fan 0-100 (default 0)",
    )
    parser.add_argument("--hold", type=float, default=3.0, help="detik tiap nilai")
    parser.add_argument(
        "--not-inverted", action="store_true",
        help="nonaktifkan inversi open-collector (jangan dipakai pada rangkaian 2N2222 standar)",
    )
    args = parser.parse_args()

    invalid = [value for value in args.values if value < 0 or value > 100]
    if invalid:
        raise SystemExit(f"Nilai PWM di luar 0-100: {invalid}")

    print(f"Membuka Arduino pada {args.port} @ {args.baud} baud...")
    driver = ArduinoSerialPWMDriver(
        port=args.port,
        baudrate=args.baud,
        inverted=not args.not_inverted,
    )
    try:
        for value in args.values:
            driver.set_duty_cycle(value)
            print(f"Arduino mengakui PWM fan {driver.get_duty_cycle():.2f}%")
            time.sleep(max(args.hold, 0.0))
    finally:
        print("Mengembalikan perintah ke 0% dan menutup port.")
        driver.cleanup()


if __name__ == "__main__":
    main()

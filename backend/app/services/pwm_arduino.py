"""Driver PWM melalui Arduino Uno yang terhubung dengan USB serial.

Protokol teks sengaja kecil agar dapat diuji lewat Serial Monitor:

``PING``          -> ``OK READY``
``INVERTED 1``    -> ``OK INVERTED 1``
``PWM 42.50``     -> ``OK PWM 42.50``
``STATUS``        -> ``OK PWM 42.50``
``STOP``          -> ``OK PWM 0.00``

Persentase yang dikirim selalu bermakna duty cycle fan (0-100%). Inversi
open-collector ditangani oleh sketch Arduino, bukan oleh logika fuzzy.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Optional

import numpy as np

from app.services.pwm import BasePWMDriver


class ArduinoPWMError(RuntimeError):
    """Komunikasi bridge PWM Arduino gagal atau memberi jawaban tidak valid."""


class ArduinoSerialPWMDriver(BasePWMDriver):
    name = "arduino"

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
        startup_delay: float = 2.0,
        inverted: bool = True,
        serial_factory: Optional[Callable[..., Any]] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not port:
            raise ValueError(
                "PWM_SERIAL_PORT wajib diisi saat PWM_DRIVER=arduino "
                "(contoh Windows: COM13)."
            )

        if serial_factory is None:
            try:
                import serial
            except ImportError as exc:  # pragma: no cover - tergantung instalasi host
                raise RuntimeError(
                    "pyserial belum terpasang; jalankan pip install -r requirements.txt"
                ) from exc
            serial_factory = serial.Serial

        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.current_pwm = 0.0
        self.inverted = bool(inverted)
        self._lock = threading.RLock()
        self._serial = serial_factory(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
        )

        # Uno biasanya reset saat port serial dibuka. Tunggu bootloader selesai,
        # lalu buang pesan READY awal dan lakukan handshake eksplisit.
        sleep(max(float(startup_delay), 0.0))
        if hasattr(self._serial, "reset_input_buffer"):
            self._serial.reset_input_buffer()
        self._request("PING", "OK READY")
        inverted_value = 1 if self.inverted else 0
        self._request(f"INVERTED {inverted_value}", f"OK INVERTED {inverted_value}")
        self.set_duty_cycle(0.0)

    @property
    def is_connected(self) -> bool:
        return bool(getattr(self._serial, "is_open", True))

    def _request(self, command: str, expected_prefix: str) -> str:
        with self._lock:
            if not self.is_connected:
                raise ArduinoPWMError(f"Port Arduino {self.port} sudah tertutup.")
            try:
                self._serial.write((command + "\n").encode("ascii"))
                if hasattr(self._serial, "flush"):
                    self._serial.flush()
                response = self._serial.readline().decode("ascii", errors="replace").strip()
            except Exception as exc:
                raise ArduinoPWMError(
                    f"Komunikasi Arduino pada {self.port} gagal: {type(exc).__name__}"
                ) from exc

            if not response.startswith(expected_prefix):
                shown = response or "<tidak ada jawaban>"
                raise ArduinoPWMError(
                    f"Jawaban Arduino tidak valid untuk {command!r}: {shown!r}"
                )
            return response

    def set_duty_cycle(self, percent: float) -> None:
        clipped = float(round(np.clip(percent, 0.0, 100.0), 2))
        response = self._request(f"PWM {clipped:.2f}", "OK PWM ")
        try:
            acknowledged = float(response.removeprefix("OK PWM ").strip())
        except ValueError as exc:
            raise ArduinoPWMError(f"Nilai PWM pada jawaban Arduino rusak: {response!r}") from exc
        if abs(acknowledged - clipped) > 0.01:
            raise ArduinoPWMError(
                f"Arduino mengakui PWM {acknowledged:.2f}%, bukan {clipped:.2f}%."
            )
        self.current_pwm = clipped

    def get_duty_cycle(self) -> float:
        return self.current_pwm

    def stop(self) -> None:
        self.set_duty_cycle(0.0)

    def cleanup(self) -> None:
        with self._lock:
            try:
                if self.is_connected:
                    self.stop()
            finally:
                if self.is_connected:
                    self._serial.close()

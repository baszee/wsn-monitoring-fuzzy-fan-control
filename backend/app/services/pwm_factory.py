"""Factory driver PWM berdasarkan environment deployment."""

from app import settings as ops
from app.services.pwm import BasePWMDriver, MockPWMDriver


def create_pwm_driver() -> BasePWMDriver:
    if ops.PWM_DRIVER == "mock":
        return MockPWMDriver(initial_pwm=0.0)

    if ops.SERVERLESS_MODE:
        raise RuntimeError(
            f"PWM_DRIVER={ops.PWM_DRIVER} tidak boleh dijalankan dalam mode serverless. "
            "Gunakan PWM_DRIVER=mock dan WORKER_ENABLED=false pada Vercel."
        )

    if ops.PWM_DRIVER == "arduino":
        from app.services.pwm_arduino import ArduinoSerialPWMDriver

        if ops.PWM_FREQUENCY_HZ != 25000:
            raise RuntimeError(
                "Bridge Arduino Uno saat ini memakai Timer1 tetap 25000 Hz; "
                "isi PWM_FREQUENCY_HZ=25000."
            )

        return ArduinoSerialPWMDriver(
            port=ops.PWM_SERIAL_PORT,
            baudrate=ops.PWM_SERIAL_BAUD,
            timeout=ops.PWM_SERIAL_TIMEOUT_SECONDS,
            startup_delay=ops.PWM_SERIAL_STARTUP_SECONDS,
            inverted=ops.PWM_INVERTED,
        )

    if ops.PWM_DRIVER == "orangepi":
        raise RuntimeError(
            "PWM_DRIVER=orangepi belum diaktifkan: pin/chip/channel PWM harus "
            "diverifikasi pada Orange Pi aktual. Gunakan mock atau arduino dahulu."
        )

    raise RuntimeError(f"PWM_DRIVER tidak didukung: {ops.PWM_DRIVER}")

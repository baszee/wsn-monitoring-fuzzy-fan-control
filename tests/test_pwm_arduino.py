"""Kontrak factory dan protokol USB serial driver PWM Arduino."""

from pathlib import Path
import sys

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import settings as ops
from app.services.pwm import MockPWMDriver
from app.services.pwm_arduino import ArduinoPWMError, ArduinoSerialPWMDriver
from app.services.pwm_factory import create_pwm_driver


class FakeSerial:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.is_open = True
        self.commands = []
        self.response = b""

    def reset_input_buffer(self):
        self.response = b""

    def write(self, payload: bytes):
        command = payload.decode("ascii").strip()
        self.commands.append(command)
        if command == "PING":
            self.response = b"OK READY\n"
        elif command.startswith("INVERTED "):
            self.response = f"OK {command}\n".encode("ascii")
        elif command.startswith("PWM "):
            self.response = f"OK {command}\n".encode("ascii")
        else:
            self.response = b"ERR UNKNOWN_COMMAND\n"

    def flush(self):
        pass

    def readline(self):
        return self.response

    def close(self):
        self.is_open = False


def _driver(fake: FakeSerial) -> ArduinoSerialPWMDriver:
    def factory(**kwargs):
        fake.kwargs.update(kwargs)
        return fake

    return ArduinoSerialPWMDriver(
        port="COM13",
        serial_factory=factory,
        startup_delay=0,
        sleep=lambda _: None,
    )


def test_arduino_driver_handshake_commands_and_cleanup():
    serial = FakeSerial()
    driver = _driver(serial)

    assert serial.kwargs["port"] == "COM13"
    assert serial.commands[:3] == ["PING", "INVERTED 1", "PWM 0.00"]

    driver.set_duty_cycle(42.5)
    assert serial.commands[-1] == "PWM 42.50"
    assert driver.get_duty_cycle() == 42.5

    driver.set_duty_cycle(120)
    assert serial.commands[-1] == "PWM 100.00"
    assert driver.get_duty_cycle() == 100.0

    driver.cleanup()
    assert serial.commands[-1] == "PWM 0.00"
    assert serial.is_open is False


def test_arduino_driver_requires_port():
    with pytest.raises(ValueError, match="PWM_SERIAL_PORT"):
        ArduinoSerialPWMDriver(port="", serial_factory=FakeSerial, startup_delay=0)


def test_arduino_driver_rejects_bad_acknowledgement():
    class BadSerial(FakeSerial):
        def write(self, payload: bytes):
            self.commands.append(payload.decode("ascii").strip())
            self.response = b"GARBAGE\n"

    with pytest.raises(ArduinoPWMError, match="tidak valid"):
        _driver(BadSerial())


def test_factory_default_mock(monkeypatch):
    monkeypatch.setattr(ops, "PWM_DRIVER", "mock")
    assert isinstance(create_pwm_driver(), MockPWMDriver)


def test_factory_rejects_unimplemented_orangepi(monkeypatch):
    monkeypatch.setattr(ops, "PWM_DRIVER", "orangepi")
    monkeypatch.setattr(ops, "SERVERLESS_MODE", False)
    with pytest.raises(RuntimeError, match="belum diaktifkan"):
        create_pwm_driver()

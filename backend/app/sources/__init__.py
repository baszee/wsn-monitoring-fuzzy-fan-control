"""Pemilih sumber sensor untuk mode demo dan integrasi M2."""

from app import settings as ops
from app.sources.mock import MockSensorSource
from app.sources.node_readings import NodeReadingsSensorSource
from app.sources.paket_valid import PaketValidSensorSource


_SOURCES = {
    "mock": MockSensorSource(),
    "node_readings": NodeReadingsSensorSource(),
    "paket_valid": PaketValidSensorSource(),
}


def get_sensor_source():
    try:
        return _SOURCES[ops.SENSOR_SOURCE]
    except KeyError:
        # Jangan jatuh diam-diam ke mock: data tiruan bisa terlihat seperti data nyata.
        raise ValueError(
            f"SENSOR_SOURCE={ops.SENSOR_SOURCE!r} tidak dikenal; "
            f"pilih salah satu dari {', '.join(sorted(_SOURCES))}."
        ) from None


__all__ = ["get_sensor_source"]

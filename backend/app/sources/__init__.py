"""Pemilih sumber sensor untuk mode demo dan integrasi M2."""

from app import settings as ops
from app.sources.mock import MockSensorSource
from app.sources.node_readings import NodeReadingsSensorSource


_MOCK_SOURCE = MockSensorSource()
_NODE_READINGS_SOURCE = NodeReadingsSensorSource()


def get_sensor_source():
    if ops.SENSOR_SOURCE == "node_readings":
        return _NODE_READINGS_SOURCE
    return _MOCK_SOURCE


__all__ = ["get_sensor_source"]


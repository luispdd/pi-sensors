"""Sensor management stub for Pico 2 W (no physical sensors connected initially)."""

from settings import config


class SensorReader:
    def __init__(self, **kwargs):
        self.last_temp = None
        self.last_humidity = None
        self.read_errors = 0

    def read_sensors(self):
        """Returns stub sensor telemetry (None for temp and humidity)."""
        return {
            "temperature_c": None,
            "humidity_pct": None,
            "read_errors": self.read_errors,
        }


# Default singleton instance
_default_reader = None


def get_sensor_reader():
    global _default_reader
    if _default_reader is None:
        _default_reader = SensorReader()
    return _default_reader


def read_sensors():
    return get_sensor_reader().read_sensors()

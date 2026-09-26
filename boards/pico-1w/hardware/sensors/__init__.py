"""Modular sensor package for Raspberry Pi Pico W."""

from hardware.sensors.dht22 import DHT22Sensor, create_sensor


class SensorReader:
    """Backwards-compatible wrapper around modular DHT22Sensor."""

    def __init__(self, dht_pin=None):
        from settings import config
        pin = dht_pin if dht_pin is not None else config.PIN_DHT22
        self._sensor = DHT22Sensor(pin=pin)
        self.last_timestamp = None

    @property
    def last_temp(self):
        return self._sensor.last_temp

    @property
    def last_humidity(self):
        return self._sensor.last_humidity

    @property
    def read_errors(self):
        return self._sensor.read_errors

    def read_sensors(self):
        self._sensor.read()
        return {
            "temperature_c": self._sensor.last_temp,
            "humidity_pct": self._sensor.last_humidity,
            "read_errors": self._sensor.read_errors,
            "timestamp": self.last_timestamp,
        }


_default_reader = None


def get_sensor_reader():
    global _default_reader
    if _default_reader is None:
        _default_reader = SensorReader()
    return _default_reader


def read_sensors():
    return get_sensor_reader().read_sensors()

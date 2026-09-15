"""Sensor management for DHT22 (temperature/humidity)."""

import config

try:
    import dht
    from machine import Pin
except ImportError:
    dht = None
    Pin = None


class SensorReader:
    def __init__(
        self,
        dht_pin=config.PIN_DHT22,
    ):
        self.dht_pin_num = dht_pin

        self.last_temp = None
        self.last_humidity = None
        self.read_errors = 0

        self._dht_sensor = None

        if Pin is not None and dht is not None:
            try:
                self._dht_sensor = dht.DHT22(Pin(self.dht_pin_num))
            except Exception as e:
                print(f"[sensors] Hardware init error: {e}")

    def read_sensors(self):
        """Reads DHT22 sensor.

        Returns a dictionary containing:
        - temperature_c: float or None
        - humidity_pct: float or None
        - read_errors: int
        """
        # Read DHT22
        if self._dht_sensor is not None:
            try:
                self._dht_sensor.measure()
                self.last_temp = round(float(self._dht_sensor.temperature()), 1)
                self.last_humidity = round(float(self._dht_sensor.humidity()), 1)
            except Exception as err:
                self.read_errors += 1
                print(f"[sensors] DHT22 read failure ({self.read_errors}): {err}")

        return {
            "temperature_c": self.last_temp,
            "humidity_pct": self.last_humidity,
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


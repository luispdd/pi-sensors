"""Modular DHT22 Sensor Driver conforming to the duck-typed sensor protocol for Raspberry Pi Pico W."""

import time
from settings import config

try:
    import dht
    from machine import Pin
except ImportError:
    dht = None
    Pin = None


class DHT22Sensor:
    """Modular DHT22 temperature and relative humidity sensor driver."""

    def __init__(self, pin=config.PIN_DHT22, interval_ms=int(getattr(config, "SENSOR_READ_INTERVAL_S", 2.0) * 1000)):
        self.pin_num = pin
        self.interval_ms = interval_ms
        self.name = "dht22"
        self.metrics = [
            {"key": "temperature", "unit": "Cel"},
            {"key": "humidity", "unit": "%RH"},
        ]
        self.last_temp = None
        self.last_humidity = None
        self.read_errors = 0
        self._dht_sensor = None
        self.init()

    def init(self):
        """Initializes hardware GPIO for DHT22 with internal pull-up."""
        if Pin is not None and dht is not None:
            try:
                self._dht_sensor = dht.DHT22(Pin(self.pin_num, Pin.IN, Pin.PULL_UP))
            except Exception as e:
                print(f"[dht22] Hardware init error on pin {self.pin_num}: {e}")
                self._dht_sensor = None

    def read(self):
        """Reads DHT22 sensor, with a single retry on transient timeout, retaining last readings."""
        if self._dht_sensor is None:
            self.init()
            if self._dht_sensor is None:
                return None

        try:
            self._dht_sensor.measure()
            self.last_temp = round(float(self._dht_sensor.temperature()), 1)
            self.last_humidity = round(float(self._dht_sensor.humidity()), 1)
        except Exception:
            # Single retry after 100ms pause to recover from momentary interrupt/context collisions
            try:
                if hasattr(time, "sleep_ms"):
                    time.sleep_ms(100)
                else:
                    time.sleep(0.1)
                self._dht_sensor.measure()
                self.last_temp = round(float(self._dht_sensor.temperature()), 1)
                self.last_humidity = round(float(self._dht_sensor.humidity()), 1)
            except Exception as retry_err:
                self.read_errors += 1
                print(f"[dht22] DHT22 read failure ({self.read_errors}): {retry_err}")

        # Retain and return last known readings if available (preserving previous pico-1w behavior)
        if self.last_temp is not None or self.last_humidity is not None:
            return {
                "temperature": self.last_temp,
                "humidity": self.last_humidity,
            }
        return None


def create_sensor(pin=config.PIN_DHT22, interval_ms=int(getattr(config, "SENSOR_READ_INTERVAL_S", 2.0) * 1000)):
    """Factory function for instantiating the DHT22 sensor."""
    return DHT22Sensor(pin=pin, interval_ms=interval_ms)

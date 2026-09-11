"""Sensor management for DHT22 (temperature/humidity) and LM393 (digital light)."""

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
        lm393_pin=config.PIN_LM393,
        lm393_active_low=getattr(config, "LM393_ACTIVE_LOW", True),
    ):
        self.dht_pin_num = dht_pin
        self.lm393_pin_num = lm393_pin
        self.lm393_active_low = lm393_active_low

        self.last_temp = None
        self.last_humidity = None
        self.last_light = "dark"
        self.last_light_detected = False
        self.read_errors = 0

        self._dht_sensor = None
        self._light_pin = None

        if Pin is not None and dht is not None:
            try:
                self._dht_sensor = dht.DHT22(Pin(self.dht_pin_num))
                self._light_pin = Pin(self.lm393_pin_num, Pin.IN)
            except Exception as e:
                print(f"[sensors] Hardware init error: {e}")

    def read_sensors(self):
        """Reads DHT22 and LM393 sensors.

        Returns a dictionary containing:
        - temperature_c: float or None
        - humidity_pct: float or None
        - light: 'light' or 'dark'
        - light_detected: bool
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

        # Read LM393
        if self._light_pin is not None:
            try:
                raw_val = self._light_pin.value()
                if self.lm393_active_low:
                    is_light = (raw_val == 0)
                else:
                    is_light = (raw_val == 1)

                self.last_light_detected = is_light
                self.last_light = "light" if is_light else "dark"
            except Exception as err:
                print(f"[sensors] LM393 read failure: {err}")

        return {
            "temperature_c": self.last_temp,
            "humidity_pct": self.last_humidity,
            "light": self.last_light,
            "light_detected": self.last_light_detected,
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

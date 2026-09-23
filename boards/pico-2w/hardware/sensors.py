"""Sensor management for DHT22 (temperature/humidity) and ADA2748 (light)."""

from settings import config

try:
    import dht
    from machine import Pin, ADC
except ImportError:
    dht = None
    Pin = None
    ADC = None


class SensorReader:
    def __init__(
        self,
        dht_pin=config.PIN_DHT22,
        light_pin=getattr(config, "PIN_LIGHT_ADC", 26),
        light_scale=getattr(config, "LIGHT_SCALE_FACTOR", 4.0),
    ):
        self.dht_pin_num = dht_pin
        self.light_pin_num = light_pin
        self.light_scale = light_scale

        self.last_temp = None
        self.last_humidity = None
        self.last_light = None
        self.read_errors = 0

        self._dht_sensor = None
        self._adc = None

        if Pin is not None and dht is not None:
            try:
                self._dht_sensor = dht.DHT22(Pin(self.dht_pin_num))
            except Exception as e:
                print(f"[sensors] Hardware init error: {e}")

        if Pin is not None and ADC is not None and self.light_pin_num is not None:
            try:
                self._adc = ADC(Pin(self.light_pin_num))
            except Exception as e:
                print(f"[sensors] Hardware init error (ADC): {e}")

    def read_sensors(self):
        """Reads DHT22 and ALS-PT19 light sensors.

        Returns a dictionary containing:
        - temperature_c: float or None
        - humidity_pct: float or None
        - light_pct: float or None
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

        # Read ALS-PT19 (ADA2748) Light Sensor
        if self._adc is not None:
            try:
                # Average 32 samples to smooth out LED PWM and AC light flicker
                total = 0
                for _ in range(32):
                    total += self._adc.read_u16()
                raw_u16 = total // 32
                raw_pct = (raw_u16 / 65535.0) * 100.0
                self.last_light = min(100.0, round(raw_pct * self.light_scale, 1))
            except Exception as err:
                self.read_errors += 1
                print(f"[sensors] ADC light read failure ({self.read_errors}): {err}")

        return {
            "temperature_c": self.last_temp,
            "humidity_pct": self.last_humidity,
            "light_pct": self.last_light,
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

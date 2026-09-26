"""Modular sensor package for Raspberry Pi Pico 2 W."""

from settings import config
from hardware.sensors.dht22 import DHT22Sensor, create_sensor as create_dht22
from hardware.sensors.light import LightSensor, create_sensor as create_light


class SensorReader:
    """Backwards-compatible wrapper integrating modular DHT22Sensor and LightSensor."""

    def __init__(
        self,
        dht_pin=config.PIN_DHT22,
        light_pin=getattr(config, "PIN_LIGHT_ADC", 26),
        light_scale=getattr(config, "LIGHT_SCALE_FACTOR", 4.0),
    ):
        self.dht_pin_num = dht_pin
        self.light_pin_num = light_pin
        self.light_scale = light_scale
        self.dht_sensor = DHT22Sensor(pin=dht_pin)
        self.light_sensor = LightSensor(pin=light_pin, light_scale=light_scale)
        self._dht_sensor = self.dht_sensor._dht_sensor
        self._adc = self.light_sensor._adc

    @property
    def last_temp(self):
        return self.dht_sensor.last_temp

    @property
    def last_humidity(self):
        return self.dht_sensor.last_humidity

    @property
    def last_light(self):
        return self.light_sensor.last_light

    @property
    def read_errors(self):
        return self.dht_sensor.read_errors + self.light_sensor.read_errors

    @read_errors.setter
    def read_errors(self, val):
        self.dht_sensor.read_errors = val
        self.light_sensor.read_errors = 0

    def read_sensors(self):
        """Reads DHT22 and ALS-PT19 sensors and returns backward-compatible dict."""
        self.dht_sensor._dht_sensor = self._dht_sensor
        self.light_sensor._adc = self._adc
        self.light_sensor.light_scale = self.light_scale

        self.dht_sensor.read()
        self.light_sensor.read()

        return {
            "temperature_c": self.dht_sensor.last_temp,
            "humidity_pct": self.dht_sensor.last_humidity,
            "light_pct": self.light_sensor.last_light,
            "read_errors": self.read_errors,
        }


_default_reader = None


def get_sensor_reader():
    global _default_reader
    if _default_reader is None:
        _default_reader = SensorReader()
    return _default_reader


def read_sensors():
    return get_sensor_reader().read_sensors()

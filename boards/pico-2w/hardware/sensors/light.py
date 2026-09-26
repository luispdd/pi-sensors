"""Modular ALS-PT19 (ADA2748) ADC light sensor driver for Raspberry Pi Pico 2 W."""

from settings import config

try:
    from machine import Pin, ADC
except ImportError:
    Pin = None
    ADC = None


class LightSensor:
    """Modular ADC light sensor driver conforming to duck-typed sensor protocol."""

    def __init__(
        self,
        pin=getattr(config, "PIN_LIGHT_ADC", 26),
        light_scale=getattr(config, "LIGHT_SCALE_FACTOR", 4.0),
        interval_ms=int(getattr(config, "SENSOR_READ_INTERVAL_S", 2.0) * 1000),
    ):
        self.pin_num = pin
        self.light_scale = light_scale
        self.interval_ms = interval_ms
        self.name = "light"
        self.metrics = [
            {"key": "light", "unit": "%"},
        ]
        self.last_light = None
        self.read_errors = 0
        self._adc = None
        self.init()

    def init(self):
        """Initializes ADC on the configured pin."""
        if Pin is not None and ADC is not None and self.pin_num is not None:
            try:
                self._adc = ADC(Pin(self.pin_num))
            except Exception as e:
                print(f"[light] ADC hardware init error on pin {self.pin_num}: {e}")
                self._adc = None

    def read(self):
        """Reads ALS-PT19 ADC light sensor with 32-sample averaging to filter AC flicker and PWM noise."""
        if self._adc is None:
            self.init()
            if self._adc is None:
                return None

        try:
            total = 0
            for _ in range(32):
                total += self._adc.read_u16()
            raw_u16 = total // 32
            raw_pct = (raw_u16 / 65535.0) * 100.0
            self.last_light = min(100.0, round(raw_pct * self.light_scale, 1))
            return {"light": self.last_light}
        except Exception as err:
            self.read_errors += 1
            print(f"[light] ADC light read failure ({self.read_errors}): {err}")
            if self.last_light is not None:
                return {"light": self.last_light}
            return None


def create_sensor(
    pin=getattr(config, "PIN_LIGHT_ADC", 26),
    light_scale=getattr(config, "LIGHT_SCALE_FACTOR", 4.0),
    interval_ms=int(getattr(config, "SENSOR_READ_INTERVAL_S", 2.0) * 1000),
):
    """Factory function for instantiating the LightSensor."""
    return LightSensor(pin=pin, light_scale=light_scale, interval_ms=interval_ms)

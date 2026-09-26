"""Modular AM312 PIR motion sensor driver conforming to duck-typed sensor protocol for Raspberry Pi Pico 2 W."""

from settings import config

try:
    from machine import Pin
except ImportError:
    Pin = None

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class PIRSensor:
    """Modular AM312 PIR motion sensor driver with rolling duty cycle tracking."""

    def __init__(
        self,
        pin=getattr(config, "PIN_PIR", 12),
        window_s=getattr(config, "PIR_WINDOW_S", 300),
        sample_interval_s=1.0,
    ):
        self.pin_num = pin
        self.window_s = int(window_s)
        self.sample_interval_s = sample_interval_s
        self.name = "pir"
        self.metrics = [
            {"key": "motion", "unit": "%"},
        ]
        self.read_errors = 0
        self._pin = None

        # Pre-allocated circular buffer for zero runtime GC allocations
        self._buffer = bytearray(self.window_s)
        self._head = 0
        self._active_count = 0
        self._samples_recorded = 0
        self.last_motion = 0.0

        self.init()

    def init(self):
        """Initializes hardware GPIO with internal pull-down."""
        if Pin is not None and self.pin_num is not None:
            try:
                self._pin = Pin(self.pin_num, Pin.IN, Pin.PULL_DOWN)
            except Exception as e:
                print(f"[pir] Pin init error on GPIO {self.pin_num}: {e}")
                self._pin = None

    def sample(self):
        """Records a single binary tick (1=active, 0=idle) and updates rolling active duty cycle."""
        val = 0
        if self._pin is not None:
            try:
                val = 1 if self._pin.value() else 0
            except Exception as e:
                self.read_errors += 1
                print(f"[pir] Pin read failure ({self.read_errors}): {e}")
                val = 0

        # Circular buffer eviction and addition (O(1), zero allocation)
        oldest_val = self._buffer[self._head]
        self._active_count = self._active_count - oldest_val + val
        self._buffer[self._head] = val
        self._head = (self._head + 1) % self.window_s

        if self._samples_recorded < self.window_s:
            self._samples_recorded += 1

        total = self._samples_recorded if self._samples_recorded > 0 else 1
        self.last_motion = round((self._active_count / total) * 100.0, 1)
        return self.last_motion

    def read(self):
        """Duck-typed read method returning metric dictionary."""
        return {"motion": self.last_motion}

    async def run_sampling_task(self):
        """Continuous cooperative asyncio task sampling the PIR sensor once per second."""
        while True:
            try:
                self.sample()
            except Exception as e:
                print(f"[pir] Error during sampling: {e}")
            await asyncio.sleep(self.sample_interval_s)


def create_sensor(
    pin=getattr(config, "PIN_PIR", 12),
    window_s=getattr(config, "PIR_WINDOW_S", 300),
    sample_interval_s=1.0,
):
    """Factory function for instantiating the PIR sensor."""
    return PIRSensor(pin=pin, window_s=window_s, sample_interval_s=sample_interval_s)

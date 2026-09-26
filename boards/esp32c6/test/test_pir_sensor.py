"""Unit tests for AM312 PIR motion sensor driver on Waveshare ESP32-C6-Zero."""

import os
import sys
import unittest

# Ensure boards/esp32c6 is in sys.path
sys.path.insert(0, os.path.abspath("boards/esp32c6"))

from hardware.sensors.pir import PIRSensor, create_sensor


class MockPin:
    def __init__(self, value=0, fail=False):
        self._value = value
        self.fail = fail

    def value(self):
        if self.fail:
            raise OSError("Pin read error")
        return self._value

    def set_value(self, val):
        self._value = val


class TestPIRSensorESP32C6(unittest.TestCase):
    def test_initialization_and_duck_typing(self):
        sensor = PIRSensor(pin=4, window_s=300)
        self.assertEqual(sensor.name, "pir")
        self.assertEqual(sensor.metrics, [{"key": "motion", "unit": "%"}])
        self.assertEqual(sensor.window_s, 300)
        self.assertEqual(len(sensor._buffer), 300)
        self.assertEqual(sensor.last_motion, 0.0)

        res = sensor.read()
        self.assertEqual(res, {"motion": 0.0})

    def test_duty_cycle_warmup_and_calculation(self):
        sensor = PIRSensor(pin=4, window_s=10)
        mock_pin = MockPin(0)
        sensor._pin = mock_pin

        # First sample: 0 -> 0.0%
        sensor.sample()
        self.assertEqual(sensor.last_motion, 0.0)

        # 5 active samples
        mock_pin.set_value(1)
        for _ in range(5):
            sensor.sample()

        # Total 6 samples, 5 active -> (5/6)*100 = 83.3%
        self.assertEqual(sensor.last_motion, 83.3)

        # 4 idle samples to complete 10-sample window
        mock_pin.set_value(0)
        for _ in range(4):
            sensor.sample()

        # 10 samples total, 5 active -> 50.0%
        self.assertEqual(sensor.last_motion, 50.0)
        self.assertEqual(sensor.read(), {"motion": 50.0})

    def test_rolling_window_eviction(self):
        # 300-second window
        sensor = PIRSensor(pin=4, window_s=300)
        mock_pin = MockPin(1)
        sensor._pin = mock_pin

        # Record 45 active samples
        for _ in range(45):
            sensor.sample()

        # Record 255 idle samples to fill 300s window
        mock_pin.set_value(0)
        for _ in range(255):
            sensor.sample()

        # 45 of 300 -> 15.0%
        self.assertEqual(sensor.last_motion, 15.0)

        # Record 45 more idle samples -> the 45 oldest active samples get evicted!
        for _ in range(45):
            sensor.sample()

        # All 300 slots in buffer are now 0 -> 0.0%
        self.assertEqual(sensor.last_motion, 0.0)

    def test_pin_failure_handling(self):
        sensor = PIRSensor(pin=4, window_s=10)
        sensor._pin = MockPin(fail=True)

        sensor.sample()
        self.assertEqual(sensor.read_errors, 1)
        self.assertEqual(sensor.last_motion, 0.0)

    def test_factory_function(self):
        sensor = create_sensor(pin=4, window_s=60)
        self.assertIsInstance(sensor, PIRSensor)
        self.assertEqual(sensor.window_s, 60)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for AM312 PIR motion sensor driver on Raspberry Pi Pico 2 W."""

import os
import sys
import unittest

# Ensure boards/pico-2w is in sys.path
sys.path.insert(0, os.path.abspath("boards/pico-2w"))

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


class MockAppState:
    def __init__(self):
        self.updates = []

    def update_metric(self, key, value):
        self.updates.append((key, value))


class TestPIRSensorPico2W(unittest.TestCase):
    def test_initialization_and_duck_typing(self):
        sensor = PIRSensor(pin=12)
        self.assertEqual(sensor.name, "pir")
        self.assertEqual(sensor.metrics, [{"key": "motion", "unit": "%"}])
        self.assertEqual(sensor.window_s, 10)
        self.assertEqual(len(sensor._buffer), 10)
        self.assertEqual(sensor.last_motion, 0.0)

        res = sensor.read()
        self.assertEqual(res, {"motion": 0.0})

    def test_ramp_up_and_decay(self):
        sensor = PIRSensor(pin=12, window_s=10)
        mock_pin = MockPin(0)
        sensor._pin = mock_pin

        # Idle sample: 0 -> 0.0%
        sensor.sample()
        self.assertEqual(sensor.last_motion, 0.0)

        # 5 active samples -> exactly 50.0%
        mock_pin.set_value(1)
        for _ in range(5):
            sensor.sample()
        self.assertEqual(sensor.last_motion, 50.0)

        # 5 more active samples -> 100.0%
        for _ in range(5):
            sensor.sample()
        self.assertEqual(sensor.last_motion, 100.0)
        self.assertEqual(sensor.read(), {"motion": 100.0})

        # 10 idle samples -> decay completely back to 0.0%
        mock_pin.set_value(0)
        for _ in range(10):
            sensor.sample()
        self.assertEqual(sensor.last_motion, 0.0)

    def test_app_state_immediate_push(self):
        mock_state = MockAppState()
        sensor = PIRSensor(pin=12, window_s=10, app_state=mock_state)
        mock_pin = MockPin(1)
        sensor._pin = mock_pin

        sensor.sample()
        self.assertEqual(len(mock_state.updates), 1)
        self.assertEqual(mock_state.updates[0], ("motion", 10.0))

        sensor.sample()
        self.assertEqual(len(mock_state.updates), 2)
        self.assertEqual(mock_state.updates[1], ("motion", 20.0))

    def test_period_logging_accumulator(self):
        sensor = PIRSensor(pin=12, window_s=10)
        mock_pin = MockPin(1)
        sensor._pin = mock_pin

        # 3 active samples
        for _ in range(3):
            sensor.sample()

        # 7 idle samples
        mock_pin.set_value(0)
        for _ in range(7):
            sensor.sample()

        # Total 10 ticks, 3 active -> 30.0%
        val = sensor.get_period_motion(reset=True)
        self.assertEqual(val, 30.0)

        # After reset, accumulator is empty; query returns last_motion (0.0% because last sample was idle)
        self.assertEqual(sensor._period_total_ticks, 0)
        self.assertEqual(sensor._period_active_ticks, 0)
        self.assertEqual(sensor.get_period_motion(reset=False), sensor.last_motion)

    def test_pin_failure_handling(self):
        sensor = PIRSensor(pin=12, window_s=10)
        sensor._pin = MockPin(fail=True)

        sensor.sample()
        self.assertEqual(sensor.read_errors, 1)
        self.assertEqual(sensor.last_motion, 0.0)

    def test_factory_function(self):
        mock_state = MockAppState()
        sensor = create_sensor(pin=12, window_s=10, app_state=mock_state)
        self.assertIsInstance(sensor, PIRSensor)
        self.assertEqual(sensor.window_s, 10)
        self.assertIs(sensor.app_state, mock_state)

    def test_app_state_get_period_motion_and_reset(self):
        from core.state import AppState
        state = AppState()
        # Fallback when no PIR registered and no motion metric
        self.assertIsNone(state.get_period_motion_and_reset())

        # Fallback when metric has value but no registered sensor with accumulator
        state.update_metric("motion", 42.0)
        self.assertEqual(state.get_period_motion_and_reset(), 42.0)

        # Registered PIR sensor with accumulator
        sensor = PIRSensor(pin=12, window_s=10, app_state=state)
        mock_pin = MockPin(1)
        sensor._pin = mock_pin
        state.register_sensor(sensor)

        sensor.sample()  # 1 active tick
        sensor.sample()  # 2 active ticks
        mock_pin.set_value(0)
        sensor.sample()  # 1 idle tick -> total 3 ticks, 2 active -> 66.7%

        val = state.get_period_motion_and_reset()
        self.assertEqual(val, 66.7)

        # Subsequent call returns fallback last_motion (which is 20.0% for 2 active out of 10)
        val2 = state.get_period_motion_and_reset()
        self.assertEqual(val2, 20.0)


if __name__ == "__main__":
    unittest.main()

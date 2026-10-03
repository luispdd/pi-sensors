"""Unit tests for MAX4466 ADC microphone noise sensor driver on Raspberry Pi Pico 2 W."""

import os
import sys
import unittest

# Ensure boards/pico-2w is in sys.path
sys.path.insert(0, os.path.abspath("boards/pico-2w"))

import hardware.sensors.mic as mic_module
from hardware.sensors.mic import MicSensor, create_sensor


class MockSequenceADC:
    def __init__(self, sequence):
        self.sequence = list(sequence)
        self.idx = 0

    def read_u16(self):
        if self.idx < len(self.sequence):
            val = self.sequence[self.idx]
            self.idx += 1
            return val
        raise StopIteration


class MockADCWithAttenError:
    def __init__(self, pin=None):
        self.pin = pin

    def atten(self, val):
        raise AttributeError("atten not supported on RP2350")

    def read_u16(self):
        return 0


class TestMicSensorPico2W(unittest.TestCase):
    def test_duck_typing_and_metadata(self):
        sensor = MicSensor(pin=27, window_ms=50, sample_interval_s=1.0)
        self.assertEqual(sensor.name, "mic")
        self.assertEqual(sensor.metrics, [{"key": "noise", "unit": "%"}])
        self.assertEqual(sensor.window_ms, 50)
        self.assertEqual(sensor.sample_interval_s, 1.0)

    def test_read_before_sample_returns_zero(self):
        sensor = MicSensor(pin=27)
        self.assertEqual(sensor.read(), {"noise": 0.0})

    def test_mock_adc_sequence_calculation(self):
        sensor = MicSensor(pin=27, window_ms=50)
        # Deterministic dB scale: floor 10 counts, 40 dB span, no gate, no release smoothing
        sensor.min_floor = 10.0
        sensor.full_scale_db = 40.0
        sensor.gate_db = 0.0
        sensor.release = 1.0
        sensor.noise_floor = 0.0
        # RMS 1000 = 40 dB above floor => 100%
        sensor._adc = MockSequenceADC([31768, 33768] * 4)
        sensor.sample()
        self.assertEqual(sensor.read(), {"noise": 100.0})

        # RMS 100 = 20 dB above floor => 50.0%
        sensor.noise_floor = 0.0
        sensor._rms_history = []
        sensor._adc = MockSequenceADC([32668, 32868] * 4)
        sensor.sample()
        self.assertAlmostEqual(sensor.read()["noise"], 50.0, places=1)

        # Constant signal (silence) => 0.0%
        sensor._rms_history = []
        sensor._adc = MockSequenceADC([32768, 32768, 32768])
        sensor.sample()
        self.assertEqual(sensor.read(), {"noise": 0.0})

    def test_adaptive_floor_ignores_ambient_noise(self):
        sensor = MicSensor(pin=27, window_ms=50, full_scale_rms=1000.0)
        sensor._adc = MockSequenceADC([32668, 32868] * 4)  # RMS 100
        sensor.sample()
        self.assertEqual(sensor.noise_floor, 100.0)
        self.assertEqual(sensor.read(), {"noise": 0.0})

    def test_init_with_atten_attribute_error(self):
        # Case 1: direct injection via init(mock_adc)
        sensor = MicSensor(pin=27)
        mock_adc = MockADCWithAttenError()
        sensor.init(mock_adc)
        self.assertIs(sensor._adc, mock_adc)

        # Case 2: ADC class raised AttributeError on atten() during initialization
        orig_adc = mic_module.ADC
        orig_pin = mic_module.Pin
        try:
            mic_module.Pin = lambda p: p
            mic_module.ADC = MockADCWithAttenError
            sensor2 = MicSensor(pin=27)
            self.assertIsNotNone(sensor2._adc)
            self.assertIsInstance(sensor2._adc, MockADCWithAttenError)
        finally:
            mic_module.ADC = orig_adc
            mic_module.Pin = orig_pin

    def test_factory_function(self):
        sensor = create_sensor(pin=27, window_ms=50, sample_interval_s=2.0)
        self.assertIsInstance(sensor, MicSensor)
        self.assertEqual(sensor.pin_num, 27)
        self.assertEqual(sensor.sample_interval_s, 2.0)

    def test_state_and_ui_noise_propagation(self):
        from core.state import AppState
        from hardware.ui import UIController

        state = AppState()
        sensor = MicSensor(pin=27, full_scale_rms=1000.0)
        sensor.noise_floor = 0.0
        sensor._adc = MockSequenceADC([31768, 33768] * 4)
        sensor.sample()

        state.register_sensor(sensor)
        state.read_registered_sensors()

        self.assertEqual(state.get_metric_val("noise"), 100.0)
        self.assertEqual(state.noise_pct, 100.0)

        # Mock display to capture render_status call kwargs
        class MockDisplay:
            def __init__(self):
                self.last_status = None
                self.tft = None
                self.spi = None
            def render_status(self, **kwargs):
                self.last_status = kwargs
            def power_off(self):
                pass
            def clear(self):
                pass

        mock_disp = MockDisplay()
        ui = UIController(app_state=state, display=mock_disp)
        ui.render_sensor_view(state)

        self.assertIsNotNone(mock_disp.last_status)
        self.assertEqual(mock_disp.last_status.get("noise"), 100.0)

    def test_sample_updates_app_state_directly_if_present(self):
        from core.state import AppState
        state = AppState()
        sensor = MicSensor(pin=27, full_scale_rms=1000.0, app_state=state)
        sensor.noise_floor = 0.0
        sensor._adc = MockSequenceADC([31768, 33768] * 4)
        state.register_sensor(sensor)
        sensor.sample()
        self.assertEqual(state.get_metric_val("noise"), 100.0)


if __name__ == "__main__":
    unittest.main()

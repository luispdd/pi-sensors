"""Unit tests for ADA2748 (ALS-PT19) light sensor integration on Pico 2 W."""

import io
import os
import sys
import unittest

# Ensure boards/pico-2w is in sys.path
sys.path.insert(0, os.path.abspath("boards/pico-2w"))

from settings import config
from core.state import AppState
from hardware.sd_storage import SDStorage, CSV_HEADER
from services.log_sync import read_log_records


class MockADC:
    def __init__(self, raw_val=32768, fail=False):
        self.raw_val = raw_val
        self.fail = fail

    def read_u16(self):
        if self.fail:
            raise OSError("ADC read error")
        return self.raw_val


class TestLightSensorIntegration(unittest.TestCase):
    def test_state_light_telemetry(self):
        state = AppState()
        self.assertIsNone(state.light_pct)

        # Update telemetry
        state.update_sensors({
            "temperature_c": 22.5,
            "humidity_pct": 58.0,
            "light_pct": 65.4,
            "read_errors": 0,
        })
        self.assertEqual(state.temperature_c, 22.5)
        self.assertEqual(state.humidity_pct, 58.0)
        self.assertEqual(state.light_pct, 65.4)

        d = state.to_dict()
        self.assertIn("light_pct", d)
        self.assertEqual(d["light_pct"], 65.4)
        self.assertEqual(d["status"], "ok")

    def test_buffer_reading_with_light(self):
        state = AppState()
        state.buffer_reading("pico-2w", "2026-09-22T12:00:00", 21.0, 50.0, 75.5)

        self.assertIn("pico-2w", state.log_buffers)
        self.assertEqual(len(state.log_buffers["pico-2w"]), 1)
        record = state.log_buffers["pico-2w"][0]
        self.assertEqual(record["temp"], 21.0)
        self.assertEqual(record["hum"], 50.0)
        self.assertEqual(record["light"], 75.5)

    def test_sensor_reader_mock_adc(self):
        from hardware.sensors import SensorReader

        reader = SensorReader(dht_pin=15, light_pin=26)
        # Verify reader uses config.LIGHT_SCALE_FACTOR
        self.assertEqual(reader.light_scale, config.LIGHT_SCALE_FACTOR)

        # ~5% raw (3277) -> 40.0% using config.LIGHT_SCALE_FACTOR
        reader._adc = MockADC(raw_val=3277)
        res_5pct = reader.read_sensors()
        expected_40pct = min(100.0, round(((3277 / 65535.0) * 100.0) * config.LIGHT_SCALE_FACTOR, 1))
        self.assertEqual(res_5pct["light_pct"], expected_40pct)

        # 12.5%+ raw (8192+) -> 100.0%
        reader._adc = MockADC(raw_val=8192)
        res_100pct = reader.read_sensors()
        expected_100pct = min(100.0, round(((8192 / 65535.0) * 100.0) * config.LIGHT_SCALE_FACTOR, 1))
        self.assertEqual(res_100pct["light_pct"], expected_100pct)

        # Test custom light_scale injection
        custom_reader = SensorReader(dht_pin=15, light_pin=26, light_scale=2.0)
        custom_reader._adc = MockADC(raw_val=1310)  # 2% raw
        res_custom = custom_reader.read_sensors()
        self.assertEqual(res_custom["light_pct"], 4.0)

        # Test failure handling
        reader._adc = MockADC(fail=True)
        res_fail = reader.read_sensors()
        self.assertEqual(reader.read_errors, 1)

    def test_sd_storage_csv_header_and_writing(self):
        self.assertIn("light_pct", CSV_HEADER)
        self.assertEqual(CSV_HEADER.strip().split(","), ["timestamp", "device_id", "temperature_c", "humidity_pct", "light_pct"])

        storage = SDStorage(spi=None, tft_cs=None, sd_cs_pin=None)
        buf = io.StringIO()
        rows = [
            {"ts": "2026-09-22T12:00:00", "device_id": "pico-2w", "temp": 22.0, "hum": 55.0, "light": 60.5},
            {"ts": "2026-09-22T12:05:00", "device_id": "pico-1w", "temp": 21.0, "hum": 50.0, "light": None},
        ]
        storage.write_rows(buf, rows)
        output = buf.getvalue().splitlines()

        self.assertEqual(len(output), 2)
        self.assertEqual(output[0], "2026-09-22T12:00:00,pico-2w,22.0,55.0,60.5")
        self.assertEqual(output[1], "2026-09-22T12:05:00,pico-1w,21.0,50.0,")

    def test_log_sync_five_column_parsing(self):
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            csv_path = os.path.join(temp_dir, "2026-09-22.csv")
            with open(csv_path, "w") as f:
                f.write(CSV_HEADER)
                f.write("2026-09-22T12:00:00,pico-2w,22.0,55.0,60.5\n")
                f.write("2026-09-22T12:05:00,pico-1w,21.0,50.0,\n")
                # Backward-compatible 4-column row
                f.write("2026-09-22T12:10:00,pico-old,20.0,45.0\n")

            res = read_log_records(temp_dir, None, 10)
            data = res["data"]
            self.assertEqual(len(data), 3)

            # 5-column row with light
            self.assertEqual(data[0]["device_id"], "pico-2w")
            self.assertEqual(data[0]["light"], 60.5)

            # 5-column row with empty light
            self.assertEqual(data[1]["device_id"], "pico-1w")
            self.assertIsNone(data[1]["light"])

            # 4-column row without light column
            self.assertEqual(data[2]["device_id"], "pico-old")
            self.assertNotIn("light", data[2])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

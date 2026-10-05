"""Unit tests for board internal timestamp lifecycle and advancement loop."""

import json
import os
import sys
import unittest
import asyncio

PICO1W_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PICO1W_LIB_DIR = os.path.abspath(os.path.join(PICO1W_DIR, "lib"))
if PICO1W_LIB_DIR not in sys.path:
    sys.path.insert(0, PICO1W_LIB_DIR)
if PICO1W_DIR not in sys.path:
    sys.path.insert(0, PICO1W_DIR)

from core.state import AppState
from services.ntp_service import format_iso_timestamp, run_ntp_task
from services.live_publisher import LivePublisher


class MockSensor:
    def __init__(self, key="temperature", val=22.5):
        self.name = "mock_sensor"
        self.metrics = [{"key": key, "unit": "C"}]
        self.val = val

    def read(self):
        return {self.metrics[0]["key"]: self.val}


class TestTimestampLifecycle(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()

    def test_set_time_anchors_baseline(self):
        """Verifies set_time anchors epoch and formats ISO timestamp."""
        epoch = 1700000000  # 2023-11-14T22:13:20 UTC
        self.app_state.set_time(epoch, synced=True)
        self.assertTrue(self.app_state.ntp_synced)
        self.assertEqual(self.app_state.timestamp, format_iso_timestamp(epoch))

    def test_timestamp_advancement_per_tick(self):
        """Verifies each call to tick_timestamp(1) advances the timestamp by 1 second."""
        epoch = 1700000000
        self.app_state.set_time(epoch, synced=True)
        ts0 = self.app_state.timestamp

        self.app_state.tick_timestamp(1)
        ts1 = self.app_state.timestamp
        self.assertNotEqual(ts0, ts1)
        self.assertEqual(ts1, format_iso_timestamp(epoch + 1))

        self.app_state.tick_timestamp(1)
        ts2 = self.app_state.timestamp
        self.assertEqual(ts2, format_iso_timestamp(epoch + 2))

    def test_read_registered_sensors_uses_internal_loop_timestamp(self):
        """Verifies read_registered_sensors() without arguments binds the current ticked timestamp."""
        sensor = MockSensor("temperature", 24.1)
        self.app_state.register_sensor(sensor)

        epoch = 1700000050
        self.app_state.set_time(epoch, synced=True)
        self.app_state.tick_timestamp(1)
        expected_ts = format_iso_timestamp(epoch + 1)

        self.app_state.read_registered_sensors()
        metric = self.app_state.get_metric("temperature")
        self.assertEqual(metric["val"], 24.1)
        self.assertEqual(metric["ts"], expected_ts)
        self.assertEqual(self.app_state.timestamp, expected_ts)

    def test_live_publisher_payload_reflects_advancing_loop_timestamp(self):
        """Verifies LivePublisher extracts advancing app_state.timestamp across loop ticks."""
        sensor = MockSensor("temperature", 21.0)
        self.app_state.register_sensor(sensor)
        publisher = LivePublisher(self.app_state)

        epoch = 1700000100
        self.app_state.set_time(epoch, synced=True)
        self.app_state.read_registered_sensors()

        payload1 = json.loads(publisher._collect_payload())
        self.assertEqual(payload1["timestamp"], format_iso_timestamp(epoch))

        # Advance loop tick
        self.app_state.tick_timestamp(1)
        payload2 = json.loads(publisher._collect_payload())
        self.assertEqual(payload2["timestamp"], format_iso_timestamp(epoch + 1))
        self.assertNotEqual(payload1["timestamp"], payload2["timestamp"])


if __name__ == "__main__":
    unittest.main()

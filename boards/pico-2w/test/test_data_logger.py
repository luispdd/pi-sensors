"""Unit test for DataLogger immediate sampling, buffer capacity 13, and 12-item auto-flush slicing."""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("boards/pico-2w"))

from core.state import (
    AppState,
    LOGGER_IDLE,
    LOGGER_STAGING,
    LOGGER_CONFIRM,
    LOGGER_ACTIVE,
)
from services.data_logger import DataLogger


class MockSDStorage:
    def __init__(self):
        self.flushed_batches = []

    def flush_buffers(self, rows, date_str):
        self.flushed_batches.append((list(rows), date_str))


class TestDataLogger(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()
        self.sd_storage = MockSDStorage()
        self.data_logger = DataLogger(self.app_state, self.sd_storage, coap_server=None)

    def test_buffer_capacity_thirteen(self):
        """Buffer should hold up to 13 items before discarding oldest."""
        device_id = "pico-test"

        # Add 13 readings
        for i in range(13):
            self.app_state.buffer_reading(device_id, f"2026-09-22T10:{i:02d}:00", 20.0 + i, 50.0)

        self.assertEqual(len(self.app_state.log_buffers[device_id]), 13)
        self.assertEqual(self.app_state.log_buffered_count, 13)
        self.assertEqual(self.app_state.log_buffers[device_id][0]["ts"], "2026-09-22T10:00:00")
        self.assertEqual(self.app_state.log_buffers[device_id][12]["ts"], "2026-09-22T10:12:00")

        # 14th reading discards oldest (index 0)
        self.app_state.buffer_reading(device_id, "2026-09-22T10:13:00", 33.0, 50.0)
        self.assertEqual(len(self.app_state.log_buffers[device_id]), 13)
        self.assertEqual(self.app_state.log_buffered_count, 13)
        self.assertEqual(self.app_state.log_buffers[device_id][0]["ts"], "2026-09-22T10:01:00")
        self.assertEqual(self.app_state.log_buffers[device_id][12]["ts"], "2026-09-22T10:13:00")

    def test_retain_unflushed(self):
        """retain_unflushed should keep entries beyond the first 12 and update log_buffered_count."""
        dev_a = "pico-a"
        dev_b = "pico-b"

        for i in range(13):
            self.app_state.buffer_reading(dev_a, f"2026-09-22T10:{i:02d}:00", 20.0, 50.0)
            self.app_state.buffer_reading(dev_b, f"2026-09-22T10:{i:02d}:00", 21.0, 51.0)

        self.assertEqual(self.app_state.log_buffered_count, 26)

        self.app_state.retain_unflushed(count_flushed_per_device=12)

        self.assertEqual(len(self.app_state.log_buffers[dev_a]), 1)
        self.assertEqual(len(self.app_state.log_buffers[dev_b]), 1)
        self.assertEqual(self.app_state.log_buffered_count, 2)
        self.assertEqual(self.app_state.log_buffers[dev_a][0]["ts"], "2026-09-22T10:12:00")

    def test_periodic_flush_retains_thirteenth_sample(self):
        """Periodic flush (end_session=False) flushes first 12 records and leaves 13th in buffer."""
        device_id = "pico-local"
        self.app_state.logger_state = LOGGER_ACTIVE
        self.app_state.logging_active = True

        for i in range(13):
            self.app_state.buffer_reading(device_id, f"2026-09-22T10:{i:02d}:00", 20.0 + i, 50.0)

        # Run periodic flush
        asyncio.run(self.data_logger.flush_to_sd(end_session=False))

        # Check SD storage received exactly 12 records
        self.assertEqual(len(self.sd_storage.flushed_batches), 1)
        flushed_rows, _ = self.sd_storage.flushed_batches[0]
        self.assertEqual(len(flushed_rows), 12)
        self.assertEqual(flushed_rows[0]["ts"], "2026-09-22T10:00:00")
        self.assertEqual(flushed_rows[11]["ts"], "2026-09-22T10:11:00")

        # In-memory buffer retains 13th reading
        self.assertEqual(len(self.app_state.log_buffers[device_id]), 1)
        self.assertEqual(self.app_state.log_buffered_count, 1)
        self.assertEqual(self.app_state.log_buffers[device_id][0]["ts"], "2026-09-22T10:12:00")

        # Session should still be active
        self.assertEqual(self.app_state.logger_state, LOGGER_ACTIVE)
        self.assertTrue(self.app_state.logging_active)

    def test_manual_stop_flushes_all_and_transitions_idle(self):
        """Manual stop_and_flush (end_session=True) flushes all remaining records and sets IDLE."""
        device_id = "pico-local"
        self.app_state.logger_state = LOGGER_ACTIVE
        self.app_state.logging_active = True

        # Buffer a single reading (e.g. stopped shortly after start)
        self.app_state.buffer_reading(device_id, "2026-09-22T10:00:00", 22.5, 48.0)
        self.assertEqual(self.app_state.log_buffered_count, 1)

        asyncio.run(self.data_logger.stop_and_flush())

        # Check SD received the reading
        self.assertEqual(len(self.sd_storage.flushed_batches), 1)
        flushed_rows, _ = self.sd_storage.flushed_batches[0]
        self.assertEqual(len(flushed_rows), 1)
        self.assertEqual(flushed_rows[0]["ts"], "2026-09-22T10:00:00")

        # In-memory buffer should be empty and state reset to IDLE
        self.assertEqual(self.app_state.log_buffered_count, 0)
        self.assertEqual(len(self.app_state.log_buffers), 0)
        self.assertEqual(self.app_state.logger_state, LOGGER_IDLE)
        self.assertFalse(self.app_state.logging_active)

    def test_auto_flush_loop_immediate_poll(self):
        """auto_flush_loop should poll and buffer immediately on start without waiting 5 minutes."""
        from settings import config
        local_id = getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID)

        self.app_state.temperature_c = 24.2
        self.app_state.humidity_pct = 55.0
        self.app_state.log_active_nodes = {"127.0.0.1": local_id}
        self.app_state.ip_address = "127.0.0.1"

        self.data_logger.start_session()
        self.assertEqual(self.app_state.log_buffered_count, 0)

        async def run_brief_loop():
            loop_task = asyncio.create_task(self.data_logger.auto_flush_loop())
            # Yield control briefly so auto_flush_loop can execute its initial poll
            await asyncio.sleep(0.05)
            # Stop session to terminate the loop
            self.app_state.logging_active = False
            await loop_task

        asyncio.run(run_brief_loop())

        # An initial reading should have been buffered immediately
        self.assertEqual(self.app_state.log_buffered_count, 1)
        self.assertIn(local_id, self.app_state.log_buffers)
        self.assertEqual(self.app_state.log_buffers[local_id][0]["temp"], 24.2)


if __name__ == "__main__":
    unittest.main()

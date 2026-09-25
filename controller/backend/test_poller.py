"""Unit tests for PollerService and synchronization logic."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import unittest
from backend import db
from backend.poller import (
    PollerService,
    STATUS_OK,
    STATUS_OFFLINE,
    STATUS_PARTIAL,
    STATUS_ERROR,
    STATUS_BUSY,
    TRIGGER_MANUAL,
    TRIGGER_CADENCE,
)


class MockCoapClientForPoller:
    """Mock CoAP client simulating multi-page paginated log responses."""

    def __init__(self):
        self.log_pages = [
            # Page 1
            {
                "data": [
                    {"ts": "2026-09-23T10:00:00", "device_id": "pico-2w-01", "temp": 20.1, "hum": 55.0},
                    {"ts": "2026-09-23T10:05:00", "device_id": "pico-2w-01", "temp": 20.3, "hum": 55.1},
                ],
                "next_cursor": "2026-09-23:2",
            },
            # Page 2
            {
                "data": [
                    {"ts": "2026-09-23T10:10:00", "device_id": "pico-2w-01", "temp": 20.5, "hum": 55.2},
                ],
                "next_cursor": "2026-09-23:3",
            },
            # Page 3 (EOF)
            {
                "data": [],
                "next_cursor": "2026-09-23:3",
            },
        ]
        self.call_count = 0

    async def discover_nodes(self) -> List[Dict[str, Any]]:
        return [
            {
                "device_id": "pico-2w-01",
                "ip_address": "192.168.1.150",
                "capabilities": ["sensors", "data-sync", "data-logger", "display"],
            }
        ]

    async def get_log(
        self,
        ip: str,
        cursor: Optional[str] = None,
        size: int = 50,
        port: Optional[int] = None,
    ) -> Dict[str, Any]:
        idx = min(self.call_count, len(self.log_pages) - 1)
        self.call_count += 1
        return self.log_pages[idx]


async def test_poller_sync():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db = Path(tmpdir) / "test_poller.db"
        db.init_db(test_db)

        mock_client = MockCoapClientForPoller()
        poller = PollerService(db_path=test_db, coap_client=mock_client, poll_interval=1)

        # 1. Test Discovery
        discovered = await poller.discover_and_register()
        assert len(discovered) == 1
        assert discovered[0]["device_id"] == "pico-2w-01"

        # 2. Test Catch-up sync
        res = await poller.sync_now(trigger_source=TRIGGER_MANUAL)
        assert res["status"] == STATUS_OK
        assert res["total_ingested"] == 3
        assert len(res["loggers"]) == 1
        assert res["loggers"][0]["cursor"] == "2026-09-23:3"

        # Verify DB records
        readings = db.query_readings(db_path=test_db)
        assert len(readings) == 3
        sync_state = db.get_sync_state("pico-2w-01", db_path=test_db)
        assert sync_state["last_cursor"] == "2026-09-23:3"

        # 3. Test Repeated sync (already at EOF)
        res_repeat = await poller.sync_now(trigger_source=TRIGGER_MANUAL)
        assert res_repeat["status"] == STATUS_OK
        assert res_repeat["total_ingested"] == 0

        # 4. Test Concurrency Rejection
        async with poller._lock:
            busy_res = await poller.sync_now(trigger_source="concurrent_test")
            assert busy_res["status"] == STATUS_BUSY

        # 5. Test Background loop start/stop
        poller.start()
        await asyncio.sleep(0.05)
        assert poller._running is True
        poller.stop()
        await asyncio.sleep(0.05)
        assert poller._running is False

        # 6. Test sync failure when logger is offline / errors
        class FailingCoapClient(MockCoapClientForPoller):
            async def get_log(self, *args, **kwargs):
                raise ConnectionError("Timeout reaching node")

        failing_poller = PollerService(db_path=test_db, coap_client=FailingCoapClient())
        prev_sync_time = failing_poller.last_sync_time
        fail_res = await failing_poller.sync_now(trigger_source=TRIGGER_MANUAL)
        assert fail_res["status"] == STATUS_OFFLINE
        assert fail_res["loggers"][0]["status"] == STATUS_ERROR
        # Ensure last_sync_time was not updated to failure time
        assert failing_poller.last_sync_time == prev_sync_time

        # 7. Test sync when no loggers are known or discovered
        empty_db = Path(tmpdir) / "empty.db"
        db.init_db(empty_db)
        class EmptyCoapClient(MockCoapClientForPoller):
            async def discover_nodes(self):
                return []
        empty_poller = PollerService(db_path=empty_db, coap_client=EmptyCoapClient())
        idle_res = await empty_poller.sync_now(trigger_source=TRIGGER_MANUAL)
        assert idle_res["status"] == STATUS_OFFLINE
        assert empty_poller.last_sync_time is None

        print("All poller tests passed successfully!")


class TestPollerService(unittest.IsolatedAsyncioTestCase):
    async def test_poller_sync(self):
        await test_poller_sync()


if __name__ == "__main__":
    unittest.main()

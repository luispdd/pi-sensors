"""Unit tests for PollerService and synchronization logic."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import db
from backend.poller import PollerService


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
        res = await poller.sync_now(trigger_source="manual")
        assert res["status"] == "ok"
        assert res["total_ingested"] == 3
        assert len(res["loggers"]) == 1
        assert res["loggers"][0]["cursor"] == "2026-09-23:3"

        # Verify DB records
        readings = db.query_readings(db_path=test_db)
        assert len(readings) == 3
        sync_state = db.get_sync_state("pico-2w-01", db_path=test_db)
        assert sync_state["last_cursor"] == "2026-09-23:3"

        # 3. Test Repeated sync (already at EOF)
        res_repeat = await poller.sync_now(trigger_source="manual")
        assert res_repeat["status"] == "ok"
        assert res_repeat["total_ingested"] == 0

        # 4. Test Concurrency Rejection
        async with poller._lock:
            busy_res = await poller.sync_now(trigger_source="concurrent_test")
            assert busy_res["status"] == "busy"

        # 5. Test Background loop start/stop
        poller.start()
        await asyncio.sleep(0.05)
        assert poller._running is True
        poller.stop()
        await asyncio.sleep(0.05)
        assert poller._running is False

        print("All poller tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(test_poller_sync())

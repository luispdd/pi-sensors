"""Integration tests for HTTP REST API."""

import asyncio
import json
import tempfile
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web

from backend import db
from backend.api import WS_MANAGER_KEY, create_app
from backend.poller import PollerService
from backend.test_poller import MockCoapClientForPoller


class TestControllerAPI(AioHTTPTestCase):
    async def get_application(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.tmpdir.name) / "test_api.db"
        db.init_db(self.test_db)

        # Prepopulate with a node and readings (regular and fine-tuned)
        db.upsert_node("pico-2w-01", "127.0.0.1", ["sensors", "data-sync", "display"], self.test_db)
        db.insert_readings(
            [
                {"ts": "2026-09-23T08:00:00", "device_id": "pico-2w-01", "temp": 22.0, "hum": 60.0},
                {"ts": "2026-09-23T08:05:00", "device_id": "pico-2w-01", "temp": 22.3, "hum": 59.8, "light": 45.0},
            ],
            is_fine_tuned=False,
            db_path=self.test_db,
        )
        db.insert_readings(
            [
                {"ts": "2026-09-23T08:06:00", "device_id": "pico-2w-01", "temp": 22.5},
            ],
            is_fine_tuned=True,
            db_path=self.test_db,
        )

        mock_coap = MockCoapClientForPoller()
        # Mock post_display on mock client
        async def mock_post_display(ip, msg, port=None):
            return True
        mock_coap.post_display = mock_post_display

        self.poller = PollerService(db_path=self.test_db, coap_client=mock_coap)
        return create_app(poller=self.poller)

    def tearDown(self):
        super().tearDown()
        self.tmpdir.cleanup()

    async def test_get_status(self):
        resp = await self.client.request("GET", "/api/status")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "online"
        assert "database" in data
        assert data["database"]["total_readings"] == 3
        print("GET /api/status test passed!")

    async def test_get_nodes(self):
        resp = await self.client.request("GET", "/api/nodes")
        assert resp.status == 200
        nodes = await resp.json()
        assert len(nodes) == 1
        assert nodes[0]["device_id"] == "pico-2w-01"
        print("GET /api/nodes test passed!")

    async def test_post_discover(self):
        resp = await self.client.request("POST", "/api/discover")
        assert resp.status == 200
        data = await resp.json()
        assert "nodes" in data
        caps = db.get_all_capabilities(self.test_db)
        assert len(caps) > 0
        assert {c["metric_key"] for c in caps} == {"temperature", "humidity"}
        print("POST /api/discover test passed!")

    async def test_post_sync(self):
        resp = await self.client.request("POST", "/api/sync")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
        caps = db.get_all_capabilities(self.test_db)
        assert len(caps) > 0
        print("POST /api/sync test passed!")

    async def test_get_readings(self):
        # 1. Test query with limit
        resp = await self.client.request("GET", "/api/readings?limit=10")
        assert resp.status == 200
        readings = await resp.json()
        assert len(readings) == 3

        # 2. Test omitting is_fine_tuned returns both regular and live readings
        resp_all = await self.client.request("GET", "/api/readings")
        assert resp_all.status == 200
        readings_all = await resp_all.json()
        assert len(readings_all) == 3
        for item in readings_all:
            assert "is_fine_tuned" in item
            assert "metrics" in item
            assert isinstance(item["is_fine_tuned"], bool)

        has_fine_tuned = any(r["is_fine_tuned"] is True for r in readings_all)
        has_regular = any(r["is_fine_tuned"] is False for r in readings_all)
        assert has_fine_tuned and has_regular

        # 3. Test is_fine_tuned=false returns only regular rows
        resp_filtered = await self.client.request("GET", "/api/readings?is_fine_tuned=false")
        assert resp_filtered.status == 200
        readings_filtered = await resp_filtered.json()
        assert len(readings_filtered) == 2
        for item in readings_filtered:
            assert item["is_fine_tuned"] is False

        # 4. Test chronological ascending order
        assert readings_all[0]["timestamp"] < readings_all[1]["timestamp"] < readings_all[2]["timestamp"]

        # 5. Test limit selects latest N records and returns them in chronological ASC order
        resp_lim = await self.client.request("GET", "/api/readings?limit=2")
        assert resp_lim.status == 200
        readings_lim = await resp_lim.json()
        assert len(readings_lim) == 2
        assert readings_lim[0]["timestamp"] == "2026-09-23T08:05:00"
        assert readings_lim[1]["timestamp"] == "2026-09-23T08:06:00"

        print("GET /api/readings test passed!")

    async def test_websocket_broadcast(self):
        ws_mgr = self.app[WS_MANAGER_KEY]
        self.assertEqual(ws_mgr.client_count, 0)

        # Connect WebSocket client via /api/ws
        ws = await self.client.ws_connect("/api/ws")
        self.assertEqual(ws_mgr.client_count, 1)

        # Broadcast live reading
        test_payload = {
            "device_id": "pico-2w-01",
            "timestamp": "2026-09-23T08:15:00",
            "metrics": {"temp": 24.2, "hum": 55.0},
            "is_fine_tuned": True,
        }
        await ws_mgr.broadcast_reading(test_payload)

        # Connected client receives pushed payload
        msg = await ws.receive_json()
        self.assertEqual(msg["device_id"], "pico-2w-01")
        self.assertEqual(msg["timestamp"], "2026-09-23T08:15:00")
        self.assertEqual(msg["metrics"], {"temp": 24.2, "hum": 55.0})
        self.assertEqual(msg["is_fine_tuned"], True)

        # Broadcast regular sync reading
        sync_payload = {
            "device_id": "pico-2w-01",
            "timestamp": "2026-09-23T08:20:00",
            "metrics": {"temp": 21.9},
            "is_fine_tuned": False,
        }
        await ws_mgr.broadcast_reading(sync_payload)
        msg_sync = await ws.receive_json()
        self.assertEqual(msg_sync["device_id"], "pico-2w-01")
        self.assertEqual(msg_sync["is_fine_tuned"], False)

        # Cleanly disconnect
        await ws.close()
        await asyncio.sleep(0.05)
        self.assertEqual(ws_mgr.client_count, 0)
        print("WebSocket broadcast test passed!")

    async def test_post_display(self):
        # Target device ID
        payload = {"target": "pico-2w-01", "message": "Test Alert"}
        resp = await self.client.request("POST", "/api/display", json=payload)
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"

        # Missing params
        bad_resp = await self.client.request("POST", "/api/display", json={"target": "pico-2w-01"})
        assert bad_resp.status == 400
        print("POST /api/display test passed!")

    async def test_get_capabilities_empty(self):
        resp = await self.client.request("GET", "/api/capabilities")
        assert resp.status == 200
        data = await resp.json()
        assert isinstance(data, list)
        assert len(data) == 0
        print("GET /api/capabilities empty test passed!")

    async def test_get_capabilities_deduplicated(self):
        # Insert capabilities for multiple devices with overlapping keys
        db.upsert_sensor_capability("pico-1w", "temperature", "Cel", self.test_db)
        db.upsert_sensor_capability("pico-1w", "humidity", "%RH", self.test_db)
        db.upsert_sensor_capability("pico-2w", "temperature", "Cel", self.test_db)
        db.upsert_sensor_capability("pico-2w", "light", "%", self.test_db)

        resp = await self.client.request("GET", "/api/capabilities")
        assert resp.status == 200
        data = await resp.json()
        assert isinstance(data, list)
        assert len(data) == 3
        keys = [item["key"] for item in data]
        assert keys == ["humidity", "temperature", "light"] or set(keys) == {"temperature", "humidity", "light"}
        # Verify schema of each object
        for item in data:
            assert "key" in item
            assert "unit" in item
        print("GET /api/capabilities deduplicated test passed!")

    async def test_live_monitoring_lifecycle(self):
        # 1. Validation errors on POST /api/live/start
        # Missing body
        resp = await self.client.request("POST", "/api/live/start", data="not json")
        self.assertEqual(resp.status, 400)

        # Missing rate_ms
        resp = await self.client.request("POST", "/api/live/start", json={})
        self.assertEqual(resp.status, 400)

        # Non-positive rate_ms
        resp = await self.client.request("POST", "/api/live/start", json={"rate_ms": 0})
        self.assertEqual(resp.status, 400)
        resp = await self.client.request("POST", "/api/live/start", json={"rate_ms": -500})
        self.assertEqual(resp.status, 400)

        # Initial live status is empty
        status_resp = await self.client.request("GET", "/api/live/status")
        self.assertEqual(status_resp.status, 200)
        self.assertEqual(await status_resp.json(), [])

        # 2. Add a second node
        db.upsert_node("esp32c6-01", "127.0.0.2", ["sensors"], self.test_db)

        # Start live at 1000ms
        start_resp = await self.client.request("POST", "/api/live/start", json={"rate_ms": 1000})
        self.assertEqual(start_resp.status, 200)
        start_data = await start_resp.json()
        self.assertEqual(start_data["status"], "ok")
        self.assertEqual(start_data["rate_ms"], 1000)
        self.assertEqual(len(start_data["results"]), 2)
        for res in start_data["results"]:
            self.assertEqual(res["status"], "success")

        # 3. Query GET /api/live/status
        status_resp = await self.client.request("GET", "/api/live/status")
        self.assertEqual(status_resp.status, 200)
        status_data = await status_resp.json()
        self.assertEqual(len(status_data), 2)
        dev_ids = {n["device_id"] for n in status_data}
        self.assertEqual(dev_ids, {"pico-2w-01", "esp32c6-01"})
        for n in status_data:
            self.assertEqual(n["rate_ms"], 1000)
            self.assertIn("started_at", n)

        started_at_pico = next(n["started_at"] for n in status_data if n["device_id"] == "pico-2w-01")

        # 4. Repeated start with same rate keeps started_at
        repeat_resp = await self.client.request("POST", "/api/live/start", json={"rate_ms": 1000})
        self.assertEqual(repeat_resp.status, 200)
        status_data_repeat = await (await self.client.request("GET", "/api/live/status")).json()
        started_at_pico_repeat = next(n["started_at"] for n in status_data_repeat if n["device_id"] == "pico-2w-01")
        self.assertEqual(started_at_pico, started_at_pico_repeat)

        # 5. Stop live clears in-memory state
        stop_resp = await self.client.request("POST", "/api/live/stop")
        self.assertEqual(stop_resp.status, 200)
        stop_data = await stop_resp.json()
        self.assertEqual(stop_data["status"], "ok")
        self.assertEqual(len(stop_data["results"]), 2)

        # Check status is now empty
        status_after_stop = await (await self.client.request("GET", "/api/live/status")).json()
        self.assertEqual(status_after_stop, [])
        print("Live monitoring lifecycle test passed!")

    async def test_live_monitoring_per_node_failure(self):
        db.upsert_node("failing-node", "127.0.0.99", ["sensors"], self.test_db)

        orig_post_live_start = self.poller.coap_client.post_live_start
        orig_post_live_stop = self.poller.coap_client.post_live_stop

        async def failing_start(ip, broker, rate_ms, port=None):
            if ip == "127.0.0.99":
                raise TimeoutError("Unreachable node")
            return await orig_post_live_start(ip, broker, rate_ms, port)

        async def failing_stop(ip, port=None):
            if ip == "127.0.0.99":
                raise TimeoutError("Unreachable node")
            return await orig_post_live_stop(ip, port)

        self.poller.coap_client.post_live_start = failing_start
        self.poller.coap_client.post_live_stop = failing_stop

        try:
            # Start live: unreachable node reports failure, reachable node succeeds, returns 200
            start_resp = await self.client.request("POST", "/api/live/start", json={"rate_ms": 500})
            self.assertEqual(start_resp.status, 200)
            data = await start_resp.json()
            results_by_dev = {r["device_id"]: r for r in data["results"]}
            self.assertEqual(results_by_dev["pico-2w-01"]["status"], "success")
            self.assertEqual(results_by_dev["failing-node"]["status"], "failed")
            self.assertIn("Unreachable node", results_by_dev["failing-node"]["error"])

            # Live status records only the successfully started node
            status_data = await (await self.client.request("GET", "/api/live/status")).json()
            self.assertEqual(len(status_data), 1)
            self.assertEqual(status_data[0]["device_id"], "pico-2w-01")

            # Stop live: unreachable node reports failure, reachable succeeds, status 200, state cleared
            stop_resp = await self.client.request("POST", "/api/live/stop")
            self.assertEqual(stop_resp.status, 200)
            stop_data = await stop_resp.json()
            stop_results_by_dev = {r["device_id"]: r for r in stop_data["results"]}
            self.assertEqual(stop_results_by_dev["pico-2w-01"]["status"], "success")
            self.assertEqual(stop_results_by_dev["failing-node"]["status"], "failed")

            status_cleared = await (await self.client.request("GET", "/api/live/status")).json()
            self.assertEqual(status_cleared, [])
            print("Live monitoring per-node failure test passed!")
        finally:
            self.poller.coap_client.post_live_start = orig_post_live_start
            self.poller.coap_client.post_live_stop = orig_post_live_stop


if __name__ == "__main__":
    import unittest
    unittest.main()

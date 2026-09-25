"""Integration tests for HTTP REST API."""

import asyncio
import json
import tempfile
from pathlib import Path
from aiohttp.test_utils import AioHTTPTestCase
from aiohttp import web

from backend import db
from backend.api import create_app
from backend.poller import PollerService
from backend.test_poller import MockCoapClientForPoller


class TestControllerAPI(AioHTTPTestCase):
    async def get_application(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.tmpdir.name) / "test_api.db"
        db.init_db(self.test_db)

        # Prepopulate with a node and readings
        db.upsert_node("pico-2w-01", "127.0.0.1", ["sensors", "data-sync", "display"], self.test_db)
        db.insert_readings(
            [
                {"ts": "2026-09-23T08:00:00", "device_id": "pico-2w-01", "temp": 22.0, "hum": 60.0},
                {"ts": "2026-09-23T08:05:00", "device_id": "pico-2w-01", "temp": 22.3, "hum": 59.8, "light": 45.0},
            ],
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
        assert data["database"]["total_readings"] == 2
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
        resp = await self.client.request("GET", "/api/readings?limit=10")
        assert resp.status == 200
        readings = await resp.json()
        assert len(readings) >= 2
        # Check dynamic metrics
        latest = readings[0]
        assert "metrics" in latest
        # Test omitting limit returns all readings without 100 default cap
        resp_all = await self.client.request("GET", "/api/readings")
        assert resp_all.status == 200
        readings_all = await resp_all.json()
        assert len(readings_all) >= len(readings)
        print("GET /api/readings test passed!")

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


if __name__ == "__main__":
    import unittest
    unittest.main()

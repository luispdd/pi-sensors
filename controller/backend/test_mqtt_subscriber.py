"""Unit tests for MQTT subscriber service."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from backend import db
from backend.mqtt_subscriber import MqttSubscriber, parse_live_message


class TestMqttSubscriber(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test_mqtt.db"
        db.init_db(self.db_path)

        self.broadcasts = []

        async def mock_broadcast(row):
            self.broadcasts.append(row)

        self.subscriber = MqttSubscriber(
            db_path=self.db_path,
            on_reading_inserted=mock_broadcast,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_parse_live_message_valid(self):
        # 1. Payload with metrics dictionary
        topic = "iotmesh/pico-2w-01/live"
        payload = json.dumps({
            "timestamp": "2026-10-04T10:00:00",
            "metrics": {"temp": 22.5, "hum": 50.0},
        }).encode("utf-8")

        parsed = parse_live_message(topic, payload)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["device_id"], "pico-2w-01")
        self.assertEqual(parsed["timestamp"], "2026-10-04T10:00:00")
        self.assertEqual(parsed["metrics"], {"temp": 22.5, "hum": 50.0})

        # 2. Payload with flat fields and 'ts' alias
        flat_payload = json.dumps({
            "ts": "2026-10-04T10:01:00",
            "temp": 23.0,
            "motion": 1,
        }).encode("utf-8")

        parsed2 = parse_live_message(topic, flat_payload)
        self.assertIsNotNone(parsed2)
        self.assertEqual(parsed2["device_id"], "pico-2w-01")
        self.assertEqual(parsed2["timestamp"], "2026-10-04T10:01:00")
        self.assertEqual(parsed2["metrics"], {"temp": 23.0, "motion": 1})

    def test_parse_live_message_malformed(self):
        topic = "iotmesh/pico-2w-01/live"

        # Invalid JSON
        self.assertIsNone(parse_live_message(topic, b"not a json"))

        # Non-dict JSON
        self.assertIsNone(parse_live_message(topic, b"[1, 2, 3]"))

        # Missing timestamp
        self.assertIsNone(parse_live_message(topic, b'{"temp": 22.5}'))

        # Invalid topic
        self.assertIsNone(parse_live_message("wrong/topic", b'{"timestamp": "2026-10-04T10:00:00", "temp": 22}'))
        self.assertIsNone(parse_live_message("iotmesh//live", b'{"timestamp": "2026-10-04T10:00:00", "temp": 22}'))

        # Non-UTF8 payload
        self.assertIsNone(parse_live_message(topic, b"\x80\x81\x82"))

    async def test_handle_message_valid(self):
        topic = "iotmesh/pico-2w-01/live"
        payload = json.dumps({
            "timestamp": "2026-10-04T10:05:00",
            "metrics": {"temp": 24.1, "light": 80.0},
        }).encode("utf-8")

        inserted = await self.subscriber.handle_message(topic, payload)
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0]["device_id"], "pico-2w-01")
        self.assertEqual(inserted[0]["is_fine_tuned"], True)

        # Check DB directly
        readings = db.query_readings(db_path=self.db_path)
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["is_fine_tuned"], True)
        self.assertEqual(readings[0]["device_id"], "pico-2w-01")
        self.assertEqual(readings[0]["metrics"], {"temp": 24.1, "light": 80.0})

        # Check broadcast hook called
        self.assertEqual(len(self.broadcasts), 1)
        self.assertEqual(self.broadcasts[0]["device_id"], "pico-2w-01")
        self.assertEqual(self.broadcasts[0]["is_fine_tuned"], True)

    async def test_handle_message_collision_and_duplicates(self):
        ts = "2026-10-04T10:10:00"
        dev_id = "esp32c6-01"

        # 1. Pre-insert a logger sync row with is_fine_tuned = 0
        db.insert_readings(
            [{"ts": ts, "device_id": dev_id, "temp": 20.0}],
            is_fine_tuned=False,
            db_path=self.db_path,
        )
        self.broadcasts.clear()

        # 2. Receive live message with exact same (ts, device_id) but different metrics
        live_payload = json.dumps({
            "timestamp": ts,
            "metrics": {"temp": 99.9},
        }).encode("utf-8")

        inserted = await self.subscriber.handle_message(f"iotmesh/{dev_id}/live", live_payload)

        # Insertion should be ignored (duplicate)
        self.assertEqual(len(inserted), 0)

        # Broadcast should NOT have been called
        self.assertEqual(len(self.broadcasts), 0)

        # Original row preserved with is_fine_tuned = 0
        readings = db.query_readings(db_path=self.db_path)
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0]["metrics"]["temp"], 20.0)
        self.assertEqual(readings[0]["is_fine_tuned"], False)

    async def test_handle_message_malformed_ignored(self):
        topic = "iotmesh/esp32c6-01/live"
        inserted = await self.subscriber.handle_message(topic, b"corrupted data")
        self.assertEqual(len(inserted), 0)
        self.assertEqual(len(self.broadcasts), 0)
        readings = db.query_readings(db_path=self.db_path)
        self.assertEqual(len(readings), 0)


if __name__ == "__main__":
    unittest.main()

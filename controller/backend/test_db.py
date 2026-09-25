"""Unit tests for SQLite database layer."""

import os
import tempfile
from pathlib import Path

from backend import db


def test_database():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test.db"
        db.init_db(test_db_path)

        # 1. Test Node registration
        db.upsert_node("pico-2w-01", "192.168.1.105", ["data-sync", "sensors"], test_db_path)
        nodes = db.get_nodes(test_db_path)
        assert len(nodes) == 1
        assert nodes[0]["device_id"] == "pico-2w-01"
        assert nodes[0]["ip_address"] == "192.168.1.105"
        assert "data-sync" in nodes[0]["capabilities"]

        # 2. Test Dynamic Readings Ingestion
        records = [
            {
                "ts": "2026-09-23T12:00:00",
                "device_id": "pico-2w-01",
                "temp": 22.4,
                "hum": 58.1,
                "light": 50.0,
            },
            {
                "ts": "2026-09-23T12:05:00",
                "device_id": "pico-2w-01",
                "temp": 22.6,
                "hum": 58.0,
                "light": 51.5,
                "co2_ppm": 420,
                "battery_v": 3.28,
            },
        ]
        inserted = db.insert_readings(records, db_path=test_db_path)
        assert inserted == 2, f"Expected 2 inserted, got {inserted}"

        # 3. Test Deduplication
        inserted_dup = db.insert_readings(records, db_path=test_db_path)
        assert inserted_dup == 0, f"Expected 0 inserted on dup, got {inserted_dup}"

        # 4. Test Query Readings with Dynamic Fields
        readings = db.query_readings(device_id="pico-2w-01", db_path=test_db_path)
        assert len(readings) == 2
        # Check newest first
        assert readings[0]["timestamp"] == "2026-09-23T12:05:00"
        assert readings[0]["metrics"]["co2_ppm"] == 420
        assert readings[0]["metrics"]["battery_v"] == 3.28
        assert readings[1]["timestamp"] == "2026-09-23T12:00:00"
        assert readings[1]["metrics"]["temp"] == 22.4

        # 5. Test Filter Queries
        filtered = db.query_readings(since="2026-09-23T12:01:00", db_path=test_db_path)
        assert len(filtered) == 1
        assert filtered[0]["timestamp"] == "2026-09-23T12:05:00"

        # 6. Test Sync State
        db.update_sync_state("pico-2w-01", "2026-09-23:120", test_db_path)
        sync_state = db.get_sync_state("pico-2w-01", test_db_path)
        assert sync_state is not None
        assert sync_state["last_cursor"] == "2026-09-23:120"

        # 7. Test Stats
        stats = db.get_stats(test_db_path)
        assert stats["total_readings"] == 2
        assert stats["total_nodes"] == 1
        assert len(stats["sync_states"]) == 1

        # 8. Test Sensor Capabilities
        # Table exists check
        with db.get_db(test_db_path) as conn:
            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sensor_capabilities';"
            ).fetchone()
            assert table_row is not None, "sensor_capabilities table was not created"

        # Initial insert
        db.upsert_sensor_capability("pico-2w-01", "temperature", "Cel", test_db_path)
        db.upsert_sensor_capability("pico-2w-01", "humidity", "%RH", test_db_path)
        db.upsert_sensor_capability("pico-1w-01", "temperature", "Cel", test_db_path)

        caps = db.get_all_capabilities(test_db_path)
        assert len(caps) == 3
        assert {"device_id": "pico-2w-01", "metric_key": "temperature", "unit": "Cel"} in caps
        assert {"device_id": "pico-2w-01", "metric_key": "humidity", "unit": "%RH"} in caps
        assert {"device_id": "pico-1w-01", "metric_key": "temperature", "unit": "Cel"} in caps

        # Conflict update (change unit on same device_id and metric_key)
        db.upsert_sensor_capability("pico-2w-01", "temperature", "C", test_db_path)
        caps_updated = db.get_all_capabilities(test_db_path)
        assert len(caps_updated) == 3
        temp_cap = next(c for c in caps_updated if c["device_id"] == "pico-2w-01" and c["metric_key"] == "temperature")
        assert temp_cap["unit"] == "C"

        print("All database tests passed successfully!")


if __name__ == "__main__":
    test_database()

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
        # 4. Test Query Readings with Dynamic Fields (chronological ASC order)
        readings = db.query_readings(device_id="pico-2w-01", db_path=test_db_path)
        assert len(readings) == 2
        assert readings[0]["timestamp"] == "2026-09-23T12:00:00"
        assert readings[0]["metrics"]["temp"] == 22.4
        assert readings[1]["timestamp"] == "2026-09-23T12:05:00"
        assert readings[1]["metrics"]["co2_ppm"] == 420
        assert readings[1]["metrics"]["battery_v"] == 3.28

        # 4b. Test Query Readings with limit returns latest records in chronological ASC order
        limited = db.query_readings(device_id="pico-2w-01", limit=1, db_path=test_db_path)
        assert len(limited) == 1
        assert limited[0]["timestamp"] == "2026-09-23T12:05:00"

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

        # 9. Test is_fine_tuned flag & returning newly inserted rows
        live_records = [
            {
                "ts": "2026-09-23T12:10:00",
                "device_id": "pico-2w-01",
                "temp": 23.0,
            }
        ]
        inserted_live = db.insert_readings(live_records, is_fine_tuned=True, db_path=test_db_path)
        assert len(inserted_live) == 1
        assert inserted_live[0]["device_id"] == "pico-2w-01"
        assert inserted_live[0]["timestamp"] == "2026-09-23T12:10:00"
        assert inserted_live[0]["is_fine_tuned"] is True
        assert inserted_live[0]["metrics"]["temp"] == 23.0

        # Duplicate ignore: try inserting same timestamp & device_id with is_fine_tuned=True when regular exists
        dup_conflict = [
            {
                "ts": "2026-09-23T12:00:00",
                "device_id": "pico-2w-01",
                "temp": 99.9,
            }
        ]
        inserted_conflict = db.insert_readings(dup_conflict, is_fine_tuned=True, db_path=test_db_path)
        assert len(inserted_conflict) == 0
        assert inserted_conflict == 0

        # Verify existing row remains unaffected
        original_row = [r for r in db.query_readings(db_path=test_db_path) if r["timestamp"] == "2026-09-23T12:00:00"][0]
        assert original_row["metrics"]["temp"] == 22.4
        assert original_row["is_fine_tuned"] is False

        # 10. Test Old DB Upgrade (migration adds is_fine_tuned column)
        old_db_path = Path(tmpdir) / "old.db"
        with db.get_db(old_db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    metrics JSON NOT NULL,
                    ingested_at TEXT NOT NULL,
                    UNIQUE(timestamp, device_id)
                );
                INSERT INTO readings (timestamp, device_id, metrics, ingested_at)
                VALUES ('2026-09-20T08:00:00', 'pico-old', '{"temp": 20.0}', '2026-09-20T08:00:00');
                """
            )

        # Run init_db to perform migration
        db.init_db(old_db_path)

        # Verify column added
        with db.get_db(old_db_path) as conn:
            cols = [col["name"] for col in conn.execute("PRAGMA table_info(readings);").fetchall()]
            assert "is_fine_tuned" in cols

        # Verify old rows default to is_fine_tuned = False
        old_readings = db.query_readings(db_path=old_db_path)
        assert len(old_readings) == 1
        assert old_readings[0]["device_id"] == "pico-old"
        assert old_readings[0]["is_fine_tuned"] is False

        # Idempotency check: run init_db again without error
        db.init_db(old_db_path)

        print("All database tests passed successfully!")


if __name__ == "__main__":
    test_database()

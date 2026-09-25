"""SQLite database layer for IoTMesh Controller."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


from contextlib import contextmanager

def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Returns a SQLite connection configured with WAL mode and row factory."""
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_db(db_path: Optional[Path] = None):
    """Context manager that commits on exit and closes the connection."""
    conn = get_connection(db_path)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Initializes SQLite schema for nodes, readings, and sync_state."""
    with get_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                device_id TEXT PRIMARY KEY,
                ip_address TEXT NOT NULL,
                capabilities TEXT,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_id TEXT NOT NULL,
                metrics JSON NOT NULL,
                ingested_at TEXT NOT NULL,
                UNIQUE(timestamp, device_id)
            );

            CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp);
            CREATE INDEX IF NOT EXISTS idx_readings_device ON readings(device_id);

            CREATE TABLE IF NOT EXISTS sync_state (
                logger_id TEXT PRIMARY KEY,
                last_cursor TEXT NOT NULL,
                last_synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sensor_capabilities (
                device_id TEXT,
                metric_key TEXT,
                unit TEXT,
                PRIMARY KEY (device_id, metric_key)
            );
            """
        )


def upsert_node(
    device_id: str,
    ip_address: str,
    capabilities: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Registers or updates a discovered node."""
    caps_json = json.dumps(capabilities or [])
    now = _utc_now_iso()
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO nodes (device_id, ip_address, capabilities, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                ip_address = excluded.ip_address,
                capabilities = excluded.capabilities,
                last_seen = excluded.last_seen;
            """,
            (device_id, ip_address, caps_json, now),
        )


def get_nodes(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Returns list of registered nodes."""
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM nodes ORDER BY last_seen DESC;").fetchall()
        result = []
        for r in rows:
            result.append(
                {
                    "device_id": r["device_id"],
                    "ip_address": r["ip_address"],
                    "capabilities": json.loads(r["capabilities"]) if r["capabilities"] else [],
                    "last_seen": r["last_seen"],
                }
            )
        return result


def get_node(device_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Returns a specific node by device_id."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM nodes WHERE device_id = ?;", (device_id,)).fetchone()
        if not row:
            return None
        return {
            "device_id": row["device_id"],
            "ip_address": row["ip_address"],
            "capabilities": json.loads(row["capabilities"]) if row["capabilities"] else [],
            "last_seen": row["last_seen"],
        }


def insert_readings(
    records: List[Dict[str, Any]],
    default_device_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Ingests raw records with dynamic metrics into SQLite.

    Accepts records formatted as returned by /log:
    {"ts": "...", "device_id": "...", "temp": 22.4, ...}
    or records with a dedicated "metrics" key:
    {"timestamp": "...", "device_id": "...", "metrics": {...}}

    Duplicate records by (timestamp, device_id) are ignored.
    Returns count of newly inserted rows.
    """
    if not records:
        return 0

    now = _utc_now_iso()
    rows_to_insert = []

    for item in records:
        timestamp = item.get("ts") or item.get("timestamp")
        dev_id = item.get("device_id") or default_device_id
        if not timestamp or not dev_id:
            continue

        if "metrics" in item and isinstance(item["metrics"], dict):
            metrics = item["metrics"]
        else:
            # Extract everything other than timestamp/device_id into metrics
            metrics = {
                k: v
                for k, v in item.items()
                if k not in ("ts", "timestamp", "device_id", "id", "ingested_at")
            }

        rows_to_insert.append((timestamp, dev_id, json.dumps(metrics), now))

    if not rows_to_insert:
        return 0

    inserted_count = 0
    with get_db(db_path) as conn:
        for row in rows_to_insert:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO readings (timestamp, device_id, metrics, ingested_at)
                VALUES (?, ?, ?, ?);
                """,
                row,
            )
            if cur.rowcount > 0:
                inserted_count += cur.rowcount

        # Keep last_seen fresh for any registered nodes that delivered readings
        if inserted_count > 0:
            device_ids = {r[1] for r in rows_to_insert if r[1]}
            for dev in device_ids:
                conn.execute(
                    "UPDATE nodes SET last_seen = ? WHERE device_id = ?;",
                    (now, dev),
                )

    return inserted_count


def update_node_last_seen(device_id: str, db_path: Optional[Path] = None) -> bool:
    """Updates the last_seen timestamp for an existing registered node to current UTC time."""
    now = _utc_now_iso()
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE nodes SET last_seen = ? WHERE device_id = ?;",
            (now, device_id),
        )
        return cur.rowcount > 0


def update_sync_state(
    logger_id: str,
    last_cursor: str,
    db_path: Optional[Path] = None,
) -> None:
    """Updates the pagination cursor for a specific logger node."""
    now = _utc_now_iso()
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sync_state (logger_id, last_cursor, last_synced_at)
            VALUES (?, ?, ?)
            ON CONFLICT(logger_id) DO UPDATE SET
                last_cursor = excluded.last_cursor,
                last_synced_at = excluded.last_synced_at;
            """,
            (logger_id, last_cursor, now),
        )


def get_sync_state(
    logger_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieves sync cursor and last_synced_at for a given logger."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM sync_state WHERE logger_id = ?;", (logger_id,)).fetchone()
        if not row:
            return None
        return {
            "logger_id": row["logger_id"],
            "last_cursor": row["last_cursor"],
            "last_synced_at": row["last_synced_at"],
        }


def get_all_sync_states(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Retrieves all sync states."""
    with get_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM sync_state ORDER BY logger_id ASC;").fetchall()
        return [
            {
                "logger_id": r["logger_id"],
                "last_cursor": r["last_cursor"],
                "last_synced_at": r["last_synced_at"],
            }
            for r in rows
        ]


def query_readings(
    device_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Queries sensor readings with optional device_id and timestamp filters."""
    query = "SELECT id, timestamp, device_id, metrics, ingested_at FROM readings WHERE 1=1"
    params: List[Any] = []

    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)
    if since:
        query += " AND timestamp >= ?"
        params.append(since)
    if until:
        query += " AND timestamp <= ?"
        params.append(until)

    query += " ORDER BY timestamp DESC"
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        params.append(limit)
    query += ";"

    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            result.append(
                {
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "device_id": r["device_id"],
                    "metrics": json.loads(r["metrics"]),
                    "ingested_at": r["ingested_at"],
                }
            )
        return result


def get_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns database summary statistics."""
    with get_db(db_path) as conn:
        total_readings = conn.execute("SELECT COUNT(*) FROM readings;").fetchone()[0]
        total_nodes = conn.execute("SELECT COUNT(*) FROM nodes;").fetchone()[0]
        sync_states = get_all_sync_states(db_path)
        return {
            "total_readings": total_readings,
            "total_nodes": total_nodes,
            "sync_states": sync_states,
        }


def upsert_sensor_capability(
    device_id: str,
    metric_key: str,
    unit: str,
    db_path: Optional[Path] = None,
) -> None:
    """Inserts or updates a sensor capability record for a board."""
    with get_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO sensor_capabilities (device_id, metric_key, unit)
            VALUES (?, ?, ?)
            ON CONFLICT(device_id, metric_key) DO UPDATE SET
                unit = excluded.unit;
            """,
            (device_id, metric_key, unit),
        )


def get_all_capabilities(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Returns all sensor capabilities across all boards."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT device_id, metric_key, unit FROM sensor_capabilities ORDER BY device_id, metric_key;"
        ).fetchall()
        return [
            {
                "device_id": r["device_id"],
                "metric_key": r["metric_key"],
                "unit": r["unit"],
            }
            for r in rows
        ]

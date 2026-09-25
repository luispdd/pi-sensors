"""Poller service for autonomous catch-up log synchronization and cadence loop."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config, db
from backend.coap_client import CoapClient

logger = logging.getLogger("controller.poller")

# Poller & sync execution status constants
STATUS_OK = "ok"
STATUS_OFFLINE = "offline"
STATUS_PARTIAL = "partial"
STATUS_ERROR = "error"
STATUS_BUSY = "busy"

# Trigger source constants
TRIGGER_MANUAL = "manual"
TRIGGER_CADENCE = "cadence"

# Node capability constants
CAPABILITY_DATA_SYNC = "data-sync"
CAPABILITY_DATA_LOGGER = "data-logger"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def probe_and_store_capabilities(
    node: Dict[str, Any],
    db_path: Optional[Path] = None,
    coap_client: Optional[CoapClient] = None,
) -> List[Dict[str, Any]]:
    """Probes /sensors on the node and records advertised capabilities in SQLite."""
    ip = node.get("ip_address")
    device_id = node.get("device_id")
    if not ip or not device_id:
        return []

    client = coap_client or CoapClient()
    try:
        sensors = await client.get_sensors(ip)
    except Exception as e:
        logger.warning(f"[poller] Failed probing /sensors for {device_id} ({ip}): {e}")
        return []

    stored: List[Dict[str, Any]] = []
    if isinstance(sensors, list):
        for entry in sensors:
            if isinstance(entry, dict) and ("n" in entry or "name" in entry):
                metric_key = str(entry.get("n") or entry.get("name"))
                unit = str(entry.get("u") or entry.get("unit") or "")
                db.upsert_sensor_capability(
                    device_id=device_id,
                    metric_key=metric_key,
                    unit=unit,
                    db_path=db_path,
                )
                stored.append({
                    "device_id": device_id,
                    "metric_key": metric_key,
                    "unit": unit,
                })
    return stored


def node_exposes_sensors(node: Dict[str, Any]) -> bool:
    """Returns True if node advertises sensor capabilities or /sensors endpoint."""
    caps = node.get("capabilities")
    if caps is None:
        return True
    return any(
        c in caps
        for c in ["sensors", "sensor-collection", "temperature", "humidity", "light"]
    ) or any("sensor" in str(c).lower() for c in caps)


class PollerService:
    """Manages IoTMesh node discovery, catch-up log synchronization, and cadence."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        coap_client: Optional[CoapClient] = None,
        poll_interval: Optional[int] = None,
    ):
        self.db_path = db_path or config.DB_PATH
        self.coap_client = coap_client or CoapClient()
        self.poll_interval = poll_interval or config.POLL_INTERVAL_S

        self._lock = asyncio.Lock()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        self.last_sync_time: Optional[str] = None
        self.last_sync_result: Optional[Dict[str, Any]] = None

        # Seed last_sync_time from database if records exist
        try:
            sync_states = db.get_all_sync_states(self.db_path)
            valid_times = [s["last_synced_at"] for s in sync_states if s.get("last_synced_at")]
            if valid_times:
                self.last_sync_time = max(valid_times)
        except Exception:
            pass

    async def discover_and_register(self) -> List[Dict[str, Any]]:
        """Scans LAN for IoTMesh nodes and updates local SQLite registry."""
        discovered = await self.coap_client.discover_nodes()
        for node in discovered:
            db.upsert_node(
                device_id=node["device_id"],
                ip_address=node["ip_address"],
                capabilities=node["capabilities"],
                db_path=self.db_path,
            )
            if node_exposes_sensors(node):
                try:
                    await probe_and_store_capabilities(
                        node=node,
                        db_path=self.db_path,
                        coap_client=self.coap_client,
                    )
                except Exception as e:
                    logger.warning(
                        f"[poller] Failed probing capabilities for {node.get('device_id')}: {e}"
                    )
        return discovered

    async def sync_logger(self, node: Dict[str, Any], max_pages: int = 100) -> Dict[str, Any]:
        """Runs a catch-up burst against a single logger node until EOF."""
        logger_id = node["device_id"]
        logger_ip = node["ip_address"]

        sync_state = db.get_sync_state(logger_id, db_path=self.db_path)
        cursor = sync_state["last_cursor"] if sync_state else None

        total_ingested = 0
        pages_fetched = 0

        while pages_fetched < max_pages:
            pages_fetched += 1
            try:
                result = await self.coap_client.get_log(
                    ip=logger_ip,
                    cursor=cursor,
                    size=config.LOG_PAGE_SIZE,
                )
                db.update_node_last_seen(logger_id, db_path=self.db_path)
            except Exception as e:
                logger.error(f"[poller] Failed fetching log from {logger_id} ({logger_ip}): {e}")
                return {
                    "logger_id": logger_id,
                    "ip_address": logger_ip,
                    "status": STATUS_ERROR,
                    "error": str(e),
                    "ingested": total_ingested,
                    "cursor": cursor,
                }

            records = result.get("data", [])
            next_cursor = result.get("next_cursor")

            if records:
                ingested = db.insert_readings(
                    records=records,
                    default_device_id=logger_id,
                    db_path=self.db_path,
                )
                total_ingested += ingested

            if next_cursor:
                db.update_sync_state(
                    logger_id=logger_id,
                    last_cursor=next_cursor,
                    db_path=self.db_path,
                )

            # Check for end of file / catch-up complete
            if not records or next_cursor == cursor:
                cursor = next_cursor or cursor
                break

            cursor = next_cursor
            await asyncio.sleep(0)  # Yield to event loop between pages

        # Probe and update capabilities after successful sync burst
        if node_exposes_sensors(node):
            try:
                await probe_and_store_capabilities(
                    node=node,
                    db_path=self.db_path,
                    coap_client=self.coap_client,
                )
            except Exception as e:
                logger.warning(
                    f"[poller] Failed updating capabilities during sync for {logger_id}: {e}"
                )

        return {
            "logger_id": logger_id,
            "ip_address": logger_ip,
            "status": STATUS_OK,
            "ingested": total_ingested,
            "pages": pages_fetched,
            "cursor": cursor,
        }

    async def sync_now(self, trigger_source: str = TRIGGER_MANUAL) -> Dict[str, Any]:
        """Executes a synchronization catch-up burst across all known loggers.

        Guarded by an asyncio.Lock so multiple callers (automated cadence and manual
        POST /api/sync) cannot corrupt cursors or issue conflicting bursts.
        """
        if self._lock.locked():
            return {
                "status": STATUS_BUSY,
                "message": "Synchronization is already actively executing",
                "trigger": trigger_source,
                "timestamp": _utc_now_iso(),
            }

        async with self._lock:
            start_time = _utc_now_iso()

            # Find all nodes with data-sync capability
            all_nodes = db.get_nodes(db_path=self.db_path)
            loggers = [
                n
                for n in all_nodes
                if CAPABILITY_DATA_SYNC in n["capabilities"] or CAPABILITY_DATA_LOGGER in n["capabilities"]
            ]

            # If no loggers are known, perform discovery first
            if not loggers:
                discovered = await self.discover_and_register()
                loggers = [
                    n
                    for n in discovered
                    if CAPABILITY_DATA_SYNC in n["capabilities"] or CAPABILITY_DATA_LOGGER in n["capabilities"]
                ]

            logger_results = []
            total_ingested = 0

            for node in loggers:
                res = await self.sync_logger(node)
                logger_results.append(res)
                total_ingested += res.get("ingested", 0)

            if not loggers:
                sync_status = STATUS_OFFLINE
            elif all(r.get("status") == STATUS_ERROR for r in logger_results):
                all_unreachable = all(
                    "timeout" in str(r.get("error", "")).lower()
                    or "connection" in str(r.get("error", "")).lower()
                    or "offline" in str(r.get("error", "")).lower()
                    for r in logger_results
                )
                sync_status = STATUS_OFFLINE if all_unreachable else STATUS_ERROR
            elif any(r.get("status") == STATUS_ERROR for r in logger_results):
                sync_status = STATUS_PARTIAL
            else:
                sync_status = STATUS_OK

            completed_at = _utc_now_iso()
            summary = {
                "status": sync_status,
                "trigger": trigger_source,
                "started_at": start_time,
                "completed_at": completed_at,
                "total_ingested": total_ingested,
                "loggers": logger_results,
            }

            # Only advance last_sync_time if at least one logger was successfully synced
            if any(r.get("status") == STATUS_OK for r in logger_results):
                self.last_sync_time = completed_at

            self.last_sync_result = summary
            return summary

    async def _loop(self) -> None:
        """Internal background loop running discovery and sync_now on poll_interval cadence."""
        logger.info(f"[poller] Background cadence loop started (interval={self.poll_interval}s)")
        while self._running:
            try:
                await self.discover_and_register()
            except Exception as e:
                logger.error(f"[poller] Error in periodic discovery: {e}")

            try:
                await self.sync_now(trigger_source=TRIGGER_CADENCE)
            except Exception as e:
                logger.error(f"[poller] Error in periodic sync: {e}")

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
        logger.info("[poller] Background cadence loop terminated")

    def start(self) -> None:
        """Starts the background cadence poller loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """Stops the background cadence poller loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

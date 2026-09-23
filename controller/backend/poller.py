"""Poller service for autonomous catch-up log synchronization and cadence loop."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend import config, db
from backend.coap_client import CoapClient

logger = logging.getLogger("controller.poller")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
            except Exception as e:
                logger.error(f"[poller] Failed fetching log from {logger_id} ({logger_ip}): {e}")
                return {
                    "logger_id": logger_id,
                    "ip_address": logger_ip,
                    "status": "error",
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

        return {
            "logger_id": logger_id,
            "ip_address": logger_ip,
            "status": "ok",
            "ingested": total_ingested,
            "pages": pages_fetched,
            "cursor": cursor,
        }

    async def sync_now(self, trigger_source: str = "manual") -> Dict[str, Any]:
        """Executes a synchronization catch-up burst across all known loggers.

        Guarded by an asyncio.Lock so multiple callers (automated cadence and manual
        POST /api/sync) cannot corrupt cursors or issue conflicting bursts.
        """
        if self._lock.locked():
            return {
                "status": "busy",
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
                if "data-sync" in n["capabilities"] or "data-logger" in n["capabilities"]
            ]

            # If no loggers are known, perform discovery first
            if not loggers:
                discovered = await self.discover_and_register()
                loggers = [
                    n
                    for n in discovered
                    if "data-sync" in n["capabilities"] or "data-logger" in n["capabilities"]
                ]

            logger_results = []
            total_ingested = 0

            for node in loggers:
                res = await self.sync_logger(node)
                logger_results.append(res)
                total_ingested += res.get("ingested", 0)

            summary = {
                "status": "ok",
                "trigger": trigger_source,
                "started_at": start_time,
                "completed_at": _utc_now_iso(),
                "total_ingested": total_ingested,
                "loggers": logger_results,
            }

            self.last_sync_time = summary["completed_at"]
            self.last_sync_result = summary
            return summary

    async def _loop(self) -> None:
        """Internal background loop running sync_now on poll_interval cadence."""
        logger.info(f"[poller] Background cadence loop started (interval={self.poll_interval}s)")
        while self._running:
            try:
                await self.sync_now(trigger_source="cadence")
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

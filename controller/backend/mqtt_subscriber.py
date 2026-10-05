"""MQTT subscriber service for IoTMesh live readings ingestion."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiomqtt

from backend import config, db

logger = logging.getLogger("controller.mqtt")


def parse_live_message(topic: str, payload: Any) -> Optional[Dict[str, Any]]:
    """Parses a live telemetry message from an MQTT topic and payload.

    Topic format: iotmesh/<device_id>/live
    Payload schema: {"timestamp": "...", "metrics": {...}} or {"ts": "...", ...}
    Returns parsed dictionary ready for insertion, or None if invalid/malformed.
    """
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "iotmesh" or parts[2] != "live" or not parts[1]:
        return None
    topic_device_id = parts[1]

    if isinstance(payload, bytes):
        try:
            payload_str = payload.decode("utf-8")
        except UnicodeDecodeError:
            return None
    elif isinstance(payload, str):
        payload_str = payload
    else:
        return None

    try:
        data = json.loads(payload_str)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    timestamp = data.get("timestamp") or data.get("ts")
    if not timestamp:
        return None

    if "metrics" in data and isinstance(data["metrics"], dict):
        metrics = data["metrics"]
    else:
        metrics = {
            k: v
            for k, v in data.items()
            if k not in ("ts", "timestamp", "device_id", "id", "ingested_at", "is_fine_tuned")
        }

    device_id = data.get("device_id") or topic_device_id

    return {
        "timestamp": timestamp,
        "device_id": device_id,
        "metrics": metrics,
    }


class MqttSubscriber:
    """Async background task that subscribes to live MQTT topics and ingests readings."""

    def __init__(
        self,
        host: str = config.MQTT_HOST,
        port: int = config.MQTT_PORT,
        topic: str = config.MQTT_TOPIC_LIVE,
        db_path: Optional[Path] = None,
        on_reading_inserted: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.host = host
        self.port = port
        self.topic = topic
        self.db_path = db_path or config.DB_PATH
        self.on_reading_inserted = on_reading_inserted
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self) -> asyncio.Task:
        """Launches the background subscriber task."""
        if self._task and not self._task.done():
            return self._task
        self._running = True
        self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self) -> None:
        """Halts the background subscriber task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def handle_message(self, topic: str, payload: Any) -> List[Dict[str, Any]]:
        """Processes an incoming MQTT message: parses, inserts with is_fine_tuned=1, and broadcasts."""
        parsed = parse_live_message(topic, payload)
        if not parsed:
            logger.warning(f"[mqtt] Malformed or invalid message on {topic}")
            return []

        inserted = db.insert_readings(
            [parsed],
            default_device_id=parsed["device_id"],
            is_fine_tuned=True,
            db_path=self.db_path,
        )

        if inserted and self.on_reading_inserted:
            for row in inserted:
                try:
                    res = self.on_reading_inserted(row)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.warning(f"[mqtt] Error calling broadcast hook: {e}")

        return list(inserted)

    async def run(self) -> None:
        """Main subscriber loop with automatic reconnection."""
        while self._running:
            try:
                logger.info(f"[mqtt] Connecting to broker at {self.host}:{self.port}...")
                async with aiomqtt.Client(hostname=self.host, port=self.port) as client:
                    await client.subscribe(self.topic, qos=0)
                    logger.info(f"[mqtt] Subscribed to {self.topic}")
                    async for message in client.messages:
                        if not self._running:
                            break
                        await self.handle_message(str(message.topic), message.payload)
            except asyncio.CancelledError:
                break
            except aiomqtt.MqttError as e:
                if not self._running:
                    break
                logger.warning(f"[mqtt] MQTT connection error: {e}. Retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                if not self._running:
                    break
                logger.error(f"[mqtt] Unexpected subscriber error: {e}. Retrying in 5s...", exc_info=True)
                await asyncio.sleep(5)

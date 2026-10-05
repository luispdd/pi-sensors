"""WebSocket registry and broadcasting for IoTMesh Controller."""

import asyncio
import json
import logging
from typing import Any, Dict, Set
from aiohttp import web, WSMsgType

logger = logging.getLogger("controller.ws")


class WebSocketManager:
    """Maintains active WebSocket client connections and broadcasts readings."""

    def __init__(self):
        self._clients: Set[web.WebSocketResponse] = set()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, ws: web.WebSocketResponse) -> None:
        self._clients.add(ws)
        logger.info(f"[ws] Client connected. Total clients: {len(self._clients)}")

    async def unregister(self, ws: web.WebSocketResponse) -> None:
        self._clients.discard(ws)
        logger.info(f"[ws] Client disconnected. Total clients: {len(self._clients)}")

    async def broadcast_reading(self, reading: Dict[str, Any]) -> None:
        """Pushes newly inserted reading payload to all active WebSocket clients.

        Payload schema: {device_id, timestamp, metrics, is_fine_tuned}
        """
        if not self._clients:
            return

        metrics = reading.get("metrics")
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except Exception:
                pass

        payload = {
            "device_id": reading.get("device_id"),
            "timestamp": reading.get("timestamp"),
            "metrics": metrics if isinstance(metrics, dict) else {},
            "is_fine_tuned": bool(reading.get("is_fine_tuned", False)),
        }
        msg = json.dumps(payload)

        dead_clients = set()
        for ws in list(self._clients):
            if ws.closed:
                dead_clients.add(ws)
                continue
            try:
                await ws.send_str(msg)
            except Exception as e:
                logger.warning(f"[ws] Failed sending to client: {e}")
                dead_clients.add(ws)

        for ws in dead_clients:
            self._clients.discard(ws)

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        """aiohttp route handler for WebSocket connections."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await self.register(ws)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    if msg.data == "ping":
                        await ws.send_str("pong")
                elif msg.type == WSMsgType.ERROR:
                    logger.debug(f"[ws] WebSocket error: {ws.exception()}")
        finally:
            await self.unregister(ws)

        return ws

    async def close_all(self) -> None:
        """Closes all connected clients cleanly."""
        for ws in list(self._clients):
            if not ws.closed:
                try:
                    await ws.close()
                except Exception:
                    pass
        self._clients.clear()

"""HTTP REST API backing cURL interactions and future web dashboards."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from aiohttp import web

from backend import config, db
from backend.coap_client import CoapClient
from backend.mqtt_subscriber import MqttSubscriber
from backend.poller import PollerService
from backend.ws import WebSocketManager

logger = logging.getLogger("controller.api")


class ControllerAPI:
    """HTTP API route handlers for IoTMesh controller."""

    def __init__(self, poller: PollerService):
        self.poller = poller
        self.start_time = time.time()
        self.live_subscriptions: dict = {}

    async def handle_status(self, request: web.Request) -> web.Response:
        """GET /api/status - controller health, uptime, and database stats."""
        stats = db.get_stats(self.poller.db_path)
        payload = {
            "device_id": config.DEVICE_ID,
            "device_type": config.DEVICE_TYPE,
            "status": "online",
            "uptime_s": round(time.time() - self.start_time, 1),
            "poller": {
                "last_sync": self.poller.last_sync_time,
                "last_result": self.poller.last_sync_result,
                "interval_s": self.poller.poll_interval,
            },
            "database": stats,
        }
        return web.json_response(
            payload, headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )

    async def handle_get_nodes(self, request: web.Request) -> web.Response:
        """GET /api/nodes - lists discovered nodes."""
        nodes = db.get_nodes(self.poller.db_path)
        return web.json_response(nodes)

    async def handle_discover(self, request: web.Request) -> web.Response:
        """POST /api/discover - forces immediate LAN discovery burst."""
        discovered = await self.poller.discover_and_register()
        return web.json_response({"discovered_count": len(discovered), "nodes": discovered})

    async def handle_sync(self, request: web.Request) -> web.Response:
        """POST /api/sync - triggers on-demand catch-up synchronization."""
        result = await self.poller.sync_now(trigger_source="api")
        status_code = 200
        if result.get("status") == "busy":
            status_code = 409
        return web.json_response(result, status=status_code)

    async def handle_get_readings(self, request: web.Request) -> web.Response:
        """GET /api/readings - queries sensor readings with optional filters."""
        query = request.query
        device_id = query.get("device_id")
        since = query.get("since")
        until = query.get("until")

        limit_param = query.get("limit")
        limit = None
        if limit_param is not None:
            try:
                parsed_limit = int(limit_param)
                if parsed_limit > 0:
                    limit = parsed_limit
            except ValueError:
                pass

        is_fine_tuned_param = query.get("is_fine_tuned")
        is_fine_tuned = None
        if is_fine_tuned_param is not None:
            if is_fine_tuned_param.lower() in ("false", "0"):
                is_fine_tuned = False
            elif is_fine_tuned_param.lower() in ("true", "1"):
                is_fine_tuned = True

        readings = db.query_readings(
            device_id=device_id,
            since=since,
            until=until,
            limit=limit,
            is_fine_tuned=is_fine_tuned,
            db_path=self.poller.db_path,
        )
        return web.json_response(readings)

    async def handle_get_capabilities(self, request: web.Request) -> web.Response:
        """GET /api/capabilities - returns deduplicated chartable sensor capabilities."""
        all_caps = db.get_all_capabilities(self.poller.db_path)
        seen_keys = set()
        deduped = []
        for cap in all_caps:
            metric_key = cap.get("metric_key")
            if metric_key and metric_key not in seen_keys:
                seen_keys.add(metric_key)
                deduped.append({
                    "key": metric_key,
                    "unit": cap.get("unit", ""),
                })
        return web.json_response(deduped)

    async def handle_post_display(self, request: web.Request) -> web.Response:
        """POST /api/display - proxies plain text display message to a board."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        target = body.get("target")
        message = body.get("message")

        if not target or message is None:
            return web.json_response(
                {"error": "Both 'target' and 'message' are required"}, status=400
            )

        # Resolve target IP
        target_ip = None
        if "." in target and all(part.isdigit() for part in target.split(".")):
            target_ip = target
        else:
            node = db.get_node(target, db_path=self.poller.db_path)
            if node:
                target_ip = node["ip_address"]

        if not target_ip:
            return web.json_response(
                {"error": f"Target node '{target}' could not be resolved to an IP address"},
                status=404,
            )

        try:
            success = await self.poller.coap_client.post_display(target_ip, str(message))
            if success:
                return web.json_response(
                    {
                        "status": "success",
                        "target": target,
                        "ip_address": target_ip,
                        "message": message,
                    }
                )
            else:
                return web.json_response(
                    {"status": "failed", "error": "Node responded with error"}, status=502
                )
        except Exception as e:
            return web.json_response(
                {"status": "error", "error": f"CoAP communication failure: {e}"}, status=504
            )

    async def handle_live_start(self, request: web.Request) -> web.Response:
        """POST /api/live/start - triggers live streaming on all discovered nodes."""
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON body"}, status=400)

        rate_ms = body.get("rate_ms")
        if rate_ms is None or isinstance(rate_ms, bool) or not isinstance(rate_ms, int) or rate_ms <= 0:
            return web.json_response(
                {"error": "Invalid or missing 'rate_ms'; must be a positive integer"}, status=400
            )

        broker = body.get("broker") or config.get_broker_address()
        nodes = db.get_nodes(self.poller.db_path)

        results = []
        for node in nodes:
            dev_id = node["device_id"]
            ip = node["ip_address"]
            try:
                success = await self.poller.coap_client.post_live_start(
                    ip=ip, broker=broker, rate_ms=rate_ms
                )
                if success:
                    existing = self.live_subscriptions.get(dev_id)
                    started_at = (
                        existing["started_at"]
                        if existing and existing.get("rate_ms") == rate_ms
                        else db._utc_now_iso()
                    )
                    self.live_subscriptions[dev_id] = {
                        "device_id": dev_id,
                        "rate_ms": rate_ms,
                        "started_at": started_at,
                    }
                    results.append({"device_id": dev_id, "status": "success"})
                else:
                    results.append({"device_id": dev_id, "status": "failed", "error": "Node returned error"})
            except Exception as e:
                logger.warning(f"[api] Error sending live start to {dev_id} ({ip}): {e}")
                results.append({"device_id": dev_id, "status": "failed", "error": str(e)})

        return web.json_response({
            "status": "ok",
            "rate_ms": rate_ms,
            "broker": broker,
            "results": results,
        }, status=200)

    async def handle_live_stop(self, request: web.Request) -> web.Response:
        """POST /api/live/stop - stops live streaming on all discovered nodes and clears live state."""
        nodes = db.get_nodes(self.poller.db_path)
        results = []
        for node in nodes:
            dev_id = node["device_id"]
            ip = node["ip_address"]
            try:
                success = await self.poller.coap_client.post_live_stop(ip=ip)
                results.append({
                    "device_id": dev_id,
                    "status": "success" if success else "failed",
                })
            except Exception as e:
                logger.warning(f"[api] Error sending live stop to {dev_id} ({ip}): {e}")
                results.append({"device_id": dev_id, "status": "failed", "error": str(e)})

        self.live_subscriptions.clear()
        return web.json_response({
            "status": "ok",
            "results": results,
        }, status=200)

    async def handle_get_live_status(self, request: web.Request) -> web.Response:
        """GET /api/live/status - returns in-memory live monitoring state without querying nodes."""
        return web.json_response(list(self.live_subscriptions.values()))


POLLER_KEY = web.AppKey("poller", PollerService)
WS_MANAGER_KEY = web.AppKey("ws_manager", WebSocketManager)
MQTT_SUBSCRIBER_KEY = web.AppKey("mqtt_subscriber", MqttSubscriber)
API_HANDLER_KEY = web.AppKey("api_handler", ControllerAPI)


def create_app(
    db_path: Optional[str] = None,
    poller: Optional[PollerService] = None,
    ws_manager: Optional[WebSocketManager] = None,
    mqtt_subscriber: Optional[MqttSubscriber] = None,
) -> web.Application:
    """Builds and returns the configured aiohttp web Application."""
    if not poller:
        coap_client = CoapClient()
        poller = PollerService(db_path=db_path, coap_client=coap_client)

    if not ws_manager:
        ws_manager = WebSocketManager()

    poller.on_reading_inserted = ws_manager.broadcast_reading

    if mqtt_subscriber is None:
        target_db = Path(db_path) if db_path else None
        mqtt_subscriber = MqttSubscriber(
            db_path=target_db,
            on_reading_inserted=ws_manager.broadcast_reading,
        )
    else:
        mqtt_subscriber.on_reading_inserted = ws_manager.broadcast_reading

    api_handler = ControllerAPI(poller)
    app = web.Application()
    app[POLLER_KEY] = poller
    app[WS_MANAGER_KEY] = ws_manager
    app[MQTT_SUBSCRIBER_KEY] = mqtt_subscriber
    app[API_HANDLER_KEY] = api_handler

    app.router.add_get("/api/status", api_handler.handle_status)
    app.router.add_get("/api/nodes", api_handler.handle_get_nodes)
    app.router.add_post("/api/discover", api_handler.handle_discover)
    app.router.add_post("/api/sync", api_handler.handle_sync)
    app.router.add_get("/api/readings", api_handler.handle_get_readings)
    app.router.add_get("/api/capabilities", api_handler.handle_get_capabilities)
    app.router.add_post("/api/display", api_handler.handle_post_display)
    app.router.add_post("/api/live/start", api_handler.handle_live_start)
    app.router.add_post("/api/live/stop", api_handler.handle_live_stop)
    app.router.add_get("/api/live/status", api_handler.handle_get_live_status)
    app.router.add_get("/api/ws", ws_manager.handle_ws)
    app.router.add_get("/ws", ws_manager.handle_ws)

    return app

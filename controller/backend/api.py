"""HTTP REST API backing cURL interactions and future web dashboards."""

import json
import logging
import time
from typing import Optional

from aiohttp import web

from backend import config, db
from backend.coap_client import CoapClient
from backend.poller import PollerService

logger = logging.getLogger("controller.api")


class ControllerAPI:
    """HTTP API route handlers for IoTMesh controller."""

    def __init__(self, poller: PollerService):
        self.poller = poller
        self.start_time = time.time()

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
        return web.json_response(payload)

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

        readings = db.query_readings(
            device_id=device_id,
            since=since,
            until=until,
            limit=limit,
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


POLLER_KEY = web.AppKey("poller", PollerService)


def create_app(
    db_path: Optional[str] = None,
    poller: Optional[PollerService] = None,
) -> web.Application:
    """Builds and returns the configured aiohttp web Application."""
    if not poller:
        coap_client = CoapClient()
        poller = PollerService(db_path=db_path, coap_client=coap_client)

    api_handler = ControllerAPI(poller)
    app = web.Application()
    app[POLLER_KEY] = poller

    app.router.add_get("/api/status", api_handler.handle_status)
    app.router.add_get("/api/nodes", api_handler.handle_get_nodes)
    app.router.add_post("/api/discover", api_handler.handle_discover)
    app.router.add_post("/api/sync", api_handler.handle_sync)
    app.router.add_get("/api/readings", api_handler.handle_get_readings)
    app.router.add_get("/api/capabilities", api_handler.handle_get_capabilities)
    app.router.add_post("/api/display", api_handler.handle_post_display)

    return app

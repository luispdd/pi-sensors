"""Asynchronous HTTP Web Server serving sensor telemetry for Raspberry Pi Pico 2 W."""

import gc
import json
from settings import config
from core.state import MODE_SEMI_SLEEP
from services.ntp_service import get_utc_iso_timestamp

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class WebServer:
    """HTTP web server dynamically exposing telemetry and SenML endpoints."""

    def __init__(self, app_state, reader=None, host="0.0.0.0", port=getattr(config, "HTTP_PORT", 80)):
        self.app_state = app_state
        self.reader = reader
        self.host = host
        self.port = port
        self.server = None

    async def handle_client(self, reader, writer):
        """Handles an incoming HTTP request."""
        try:
            line = await reader.readline()
            if not line:
                return

            req_line = line.decode().strip()
            parts = req_line.split()
            if len(parts) < 2:
                return

            method, path = parts[0], parts[1]

            # Read headers until empty line
            while True:
                header = await reader.readline()
                if not header or header == b"\r\n" or header == b"\n":
                    break

            client_ip = None
            try:
                peer = writer.get_extra_info("peername")
                if peer and len(peer) > 0:
                    client_ip = peer[0]
            except Exception:
                pass

            self.app_state.record_request(client_ip)

            # Ensure synchronous sensor read during semi-sleep
            if self.app_state.mode == MODE_SEMI_SLEEP:
                ts = get_utc_iso_timestamp() if self.app_state.ntp_synced else None
                if hasattr(self.app_state, "read_registered_sensors"):
                    self.app_state.read_registered_sensors(timestamp=ts)
                elif self.reader is not None:
                    data = self.reader.read_sensors()
                    data["timestamp"] = ts
                    self.app_state.update_sensors(data)

            if method == "GET" and path == "/info":
                payload = json.dumps(self.app_state.to_dict())
                self._send_json(writer, payload)
            elif method == "GET" and path == "/sensors":
                payload = json.dumps(self.app_state.to_senml())
                self._send_json(writer, payload)
            elif method == "GET" and path.startswith("/sensors/"):
                metric_key = path[len("/sensors/"):]
                m = self.app_state.get_metric(metric_key) if hasattr(self.app_state, "get_metric") else None
                if m is not None:
                    senml_item = {
                        "n": metric_key,
                        "u": m.get("unit", ""),
                        "v": m.get("val"),
                        "t": m.get("ts") or self.app_state.timestamp,
                    }
                    self._send_json(writer, json.dumps(senml_item))
                else:
                    self._send_not_found(writer)
            else:
                self._send_not_found(writer)

            await writer.drain()

        except Exception as e:
            print(f"[webserver] Client handler exception: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            gc.collect()

    def _send_json(self, writer, json_str):
        body_bytes = json_str.encode("utf-8")
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Access-Control-Allow-Origin: *\r\n"
            "Connection: close\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "\r\n"
        )
        writer.write(headers.encode("utf-8"))
        writer.write(body_bytes)

    def _send_not_found(self, writer):
        body_bytes = b"404 Not Found\n"
        headers = (
            "HTTP/1.1 404 Not Found\r\n"
            "Content-Type: text/plain\r\n"
            "Connection: close\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "\r\n"
        )
        writer.write(headers.encode("utf-8"))
        writer.write(body_bytes)

    async def start(self):
        """Starts the HTTP server coroutine."""
        print(f"[webserver] Starting HTTP server on {self.host}:{self.port}...")
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        return self.server


async def run_webserver_task(app_state, host="0.0.0.0", port=getattr(config, "HTTP_PORT", 80)):
    """Starts and runs the asynchronous HTTP server."""
    server = WebServer(app_state, host=host, port=port)
    await server.start()
    while True:
        await asyncio.sleep(3600)

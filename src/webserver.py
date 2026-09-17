"""Asynchronous HTTP Web Server serving sensor telemetry for Raspberry Pi Pico W."""

import gc
import json
import config
from state import MODE_SEMI_SLEEP

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class WebServer:
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

            if method == "GET" and path in ("/info", "/sensors"):
                self.app_state.record_request(client_ip)
                if self.app_state.mode == MODE_SEMI_SLEEP and self.reader is not None:
                    data = self.reader.read_sensors()
                    self.app_state.update_sensors(data)
                payload = json.dumps(self.app_state.to_dict())
                body_bytes = payload.encode("utf-8")

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
                await writer.drain()
            else:
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

    async def start(self):
        """Starts the HTTP server coroutine."""
        print(f"[webserver] Starting HTTP server on {self.host}:{self.port}...")
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        return self.server

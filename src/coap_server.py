"""CoAP server implementing IoTMesh Service Spec v0.1 for Raspberry Pi Pico W."""

import json
import sys
import config

for lib_dir in ("lib", "./lib", "/lib", "src/lib"):
    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

try:
    import socket
except ImportError:
    import usocket as socket

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

import microcoapy
from microcoapy import COAP_CONTENT_FORMAT, COAP_METHOD, COAP_RESPONSE_CODE


class CoapServer:
    def __init__(self, app_state, port=getattr(config, "COAP_PORT", 5683)):
        self.app_state = app_state
        self.port = port
        self.coap = microcoapy.Coap()
        self.coap.debug = False
        self._register_callbacks()

    def _register_callbacks(self):
        routes = [
            (".well-known/core", self._handle_well_known_core),
            ("id", self._handle_id),
            ("sensors", self._handle_sensors_collection),
            ("sensors/temperature", self._handle_sensor_temperature),
            ("sensors/humidity", self._handle_sensor_humidity),
            ("sensors/light", self._handle_sensor_light),
            ("display", self._handle_display),
        ]
        for path, handler in routes:
            self.coap.addIncomingRequestCallback(path, handler)

    def _handle_well_known_core(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        device_id = getattr(config, "DEVICE_ID", "pico-1")
        device_type = getattr(config, "DEVICE_TYPE", "rp2040")

        # CoRE Link Format string per IoTMesh spec v0.1
        link_format = (
            f'</id>;rt="core.d";ep="{device_id}";dt="{device_type}",'
            '</sensors>;rt="sensor-collection";if="sensor",'
            '</sensors/temperature>;rt="temperature";if="sensor",'
            '</sensors/humidity>;rt="humidity";if="sensor",'
            '</sensors/light>;rt="light";if="sensor",'
            '</display>;rt="display";if="actuator"'
        )

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            link_format,
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_LINK_FORMAT,
            packet.token,
        )

    def _handle_id(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        payload = {
            "id": getattr(config, "DEVICE_ID", "pico-1"),
            "type": getattr(config, "DEVICE_TYPE", "rp2040"),
        }
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(payload),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token,
        )

    def _handle_sensor_temperature(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        senml = {
            "n": "temperature",
            "u": "Cel",
            "v": self.app_state.temperature_c,
        }
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(senml),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token,
        )

    def _handle_sensor_humidity(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        senml = {
            "n": "humidity",
            "u": "%RH",
            "v": self.app_state.humidity_pct,
        }
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(senml),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token,
        )

    def _handle_sensor_light(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        # Plain text per spec vocabulary: "dark" or "light"
        payload = str(self.app_state.light)
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            payload,
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
            packet.token,
        )

    def _handle_sensors_collection(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        # SenML Pack (JSON array)
        pack = [
            {"n": "temperature", "u": "Cel", "v": self.app_state.temperature_c},
            {"n": "humidity", "u": "%RH", "v": self.app_state.humidity_pct},
            {"n": "light", "vs": str(self.app_state.light)},
        ]
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(pack),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token,
        )

    def _handle_display(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_POST:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        text = ""
        if packet.payload:
            if isinstance(packet.payload, (bytes, bytearray)):
                try:
                    text = packet.payload.decode("utf-8")
                except Exception:
                    text = str(packet.payload)
            else:
                text = str(packet.payload)

        if len(text) > 256:
            text = text[:256]

        duration = getattr(config, "DISPLAY_OVERRIDE_DURATION_S", 60)
        self.app_state.set_display_override(text, duration)

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            None,
            COAP_RESPONSE_CODE.COAP_CHANGED,
            COAP_CONTENT_FORMAT.COAP_NONE,
            packet.token,
        )

    def _send_method_not_allowed(self, packet, sender_ip, sender_port):
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            "Method Not Allowed",
            COAP_RESPONSE_CODE.COAP_METHOD_NOT_ALLOWD,
            COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
            packet.token,
        )

    def start(self):
        """Initializes and binds the UDP socket for unicast and broadcast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception:
            pass
        sock.bind(("0.0.0.0", self.port))
        sock.setblocking(False)
        self.coap.setCustomSocket(sock)
        print(f"[coap] Server listening on UDP port {self.port}")

    async def run(self):
        """Asynchronous polling task to handle incoming CoAP packets."""
        while True:
            try:
                self.coap.loop(blocking=False)
            except Exception as e:
                print(f"[coap] Loop exception: {e}")
            await asyncio.sleep(0.02)

"""CoAP server implementing IoTMesh Service Spec v0.1 for Raspberry Pi Pico 2 W."""

import json
import sys
from settings import config
from core.state import MODE_SEMI_SLEEP

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


def extract_device_id_from_link_format(link_text):
    """Extracts ep=\"<device_id>\" from CoRE Link Format string."""
    idx = link_text.find('ep="')
    if idx != -1:
        start = idx + 4
        end = link_text.find('"', start)
        if end != -1:
            return link_text[start:end]
    return None


def extract_device_id_from_json(json_text):
    """Extracts id from JSON string."""
    try:
        data = json.loads(json_text)
        if isinstance(data, dict) and "id" in data:
            return str(data["id"])
    except Exception:
        pass
    return None


class CoapServer:
    def __init__(self, app_state, reader=None, port=getattr(config, "COAP_PORT", 5683)):
        self.app_state = app_state
        self.reader = reader
        self.port = port
        self.coap = microcoapy.Coap()
        self.coap.debug = False
        self.coap.responseCallback = self._handle_response
        self._register_callbacks()

    def _register_callbacks(self):
        routes = [
            (".well-known/core", self._handle_well_known_core),
            ("id", self._handle_id),
            ("sensors", self._handle_sensors_collection),
            ("sensors/temperature", self._handle_sensor_temperature),
            ("sensors/humidity", self._handle_sensor_humidity),
            ("display", self._handle_display),
        ]
        for path, handler in routes:
            self.coap.addIncomingRequestCallback(path, handler)

    def _record_caller(self, sender_ip):
        """Increments request counter and updates last_caller."""
        self.app_state.record_request(sender_ip)

    def _handle_response(self, packet, remote_address):
        """Processes incoming CoAP responses to learn node IDs for known_nodes cache."""
        sender_ip = remote_address[0]
        if not packet.payload:
            return

        try:
            if isinstance(packet.payload, (bytes, bytearray)):
                payload_str = packet.payload.decode("utf-8")
            else:
                payload_str = str(packet.payload)
        except Exception:
            return

        device_id = extract_device_id_from_json(payload_str)
        if not device_id:
            device_id = extract_device_id_from_link_format(payload_str)

        if device_id:
            self.app_state.register_node(sender_ip, device_id)

    async def _probe_caller(self, sender_ip, sender_port=5683):
        """Asynchronously probes an unknown sender for its node identification."""
        try:
            target_port = getattr(config, "COAP_PORT", 5683)
            self.coap.getNonConf(sender_ip, target_port, ".well-known/core")
            self.coap.getNonConf(sender_ip, target_port, "id")
        except Exception as e:
            print(f"[coap] Caller probe exception: {e}")

    def _handle_well_known_core(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)

        device_id = getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID)
        device_type = getattr(config, "DEVICE_TYPE", config.DEFAULT_DEVICE_TYPE)

        # CoRE Link Format string per IoTMesh spec v0.1
        link_format = (
            f'</id>;rt="core.d";ep="{device_id}";dt="{device_type}",'
            '</sensors>;rt="sensor-collection";if="sensor",'
            '</sensors/temperature>;rt="temperature";if="sensor",'
            '</sensors/humidity>;rt="humidity";if="sensor",'
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

        self._record_caller(sender_ip)

        payload = {
            "id": getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID),
            "type": getattr(config, "DEVICE_TYPE", config.DEFAULT_DEVICE_TYPE),
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

        self._record_caller(sender_ip)

        if self.app_state.mode == MODE_SEMI_SLEEP and self.reader is not None:
            data = self.reader.read_sensors()
            self.app_state.update_sensors(data)

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

        self._record_caller(sender_ip)

        if self.app_state.mode == MODE_SEMI_SLEEP and self.reader is not None:
            data = self.reader.read_sensors()
            self.app_state.update_sensors(data)

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

    def _handle_sensors_collection(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)

        if self.app_state.mode == MODE_SEMI_SLEEP and self.reader is not None:
            data = self.reader.read_sensors()
            self.app_state.update_sensors(data)

        pack = [
            {"n": "temperature", "u": "Cel", "v": self.app_state.temperature_c},
            {"n": "humidity", "u": "%RH", "v": self.app_state.humidity_pct},
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

        self._record_caller(sender_ip)

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

        caller = self.app_state.resolve_caller(sender_ip)
        if sender_ip not in self.app_state.known_nodes:
            try:
                asyncio.create_task(self._probe_caller(sender_ip, sender_port))
            except Exception as e:
                print(f"[coap] Caller probe trigger error: {e}")

        if self.app_state.mode == MODE_SEMI_SLEEP:
            self.app_state.set_pending_message(text, caller=caller)
        else:
            self.app_state.enter_message_mode(text, caller=caller)

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

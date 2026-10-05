"""CoAP server implementing IoTMesh Service Spec v0.1 with dynamic sensor dispatch for Raspberry Pi Pico W."""

import json
import struct
import sys
from settings import config
from core.state import MODE_SEMI_SLEEP
from services.ntp_service import get_utc_iso_timestamp
from services.live_publisher import LivePublisher

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


def _patch_microcoapy_unicode():
    """Ensures microcoapy decodes Uri-Path options using standard UTF-8.

    Standard microcoapy uses opt.buffer.decode('unicode_escape'), which raises
    LookupError on MicroPython builds where non-essential codecs are omitted.
    RFC 7252 Section 5.10.1 mandates UTF-8 for Uri-Path options.
    """
    def _safe_handle_incoming_request(self, requestPacket, sourceIp, sourcePort):
        url = ""
        for opt in getattr(requestPacket, "options", []):
            opt_num = getattr(opt, "number", None)
            if opt_num == 11 and len(opt.buffer) > 0:  # 11 = COAP_OPTION_NUMBER.COAP_URI_PATH
                if url != "":
                    url += "/"
                try:
                    url += opt.buffer.decode("utf-8")
                except Exception:
                    try:
                        url += opt.buffer.decode("unicode_escape")
                    except Exception:
                        url += str(opt.buffer)

        urlCallback = None
        if url != "":
            urlCallback = self.callbacks.get(url)

        if urlCallback is None:
            if self.responseCallback:
                return False
            self.sendResponse(
                sourceIp,
                sourcePort,
                requestPacket.messageid,
                None,
                COAP_RESPONSE_CODE.COAP_NOT_FOUND,
                COAP_CONTENT_FORMAT.COAP_NONE,
                requestPacket.token,
            )
        else:
            urlCallback(requestPacket, sourceIp, sourcePort)
        return True

    microcoapy.Coap.handleIncomingRequest = _safe_handle_incoming_request


_patch_microcoapy_unicode()


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
    """CoAP server dynamically serving registered telemetry resources and IoTMesh endpoints."""

    def __init__(self, app_state, reader=None, port=getattr(config, "COAP_PORT", 5683), live_publisher=None):
        self.app_state = app_state
        self.reader = reader
        self.port = port
        self.live_publisher = live_publisher or LivePublisher(app_state)
        self.coap = microcoapy.Coap()
        self.coap.debug = False
        self.coap.responseCallback = self._handle_response
        self._registered_paths = set()
        self._register_callbacks()

    def _register_callbacks(self):
        # Base static endpoints
        base_routes = [
            (".well-known/core", self._handle_well_known_core),
            ("id", self._handle_id),
            ("info", self._handle_info),
            ("sensors", self._handle_sensors_collection),
            ("display", self._handle_display),
            ("live/start", self._handle_live_start),
            ("live/stop", self._handle_live_stop),
        ]
        for path, handler in base_routes:
            self.coap.addIncomingRequestCallback(path, handler)
            self._registered_paths.add(path)

        # Dynamic metric routes from AppState
        self.sync_sensor_routes()

    def sync_sensor_routes(self):
        """Ensures all metrics in AppState have individual CoAP endpoints registered."""
        if hasattr(self.app_state, "get_all_metrics"):
            metrics = self.app_state.get_all_metrics()
            for key in metrics.keys():
                path = f"sensors/{key}"
                if path not in self._registered_paths:
                    handler = self._make_metric_handler(key)
                    self.coap.addIncomingRequestCallback(path, handler)
                    self._registered_paths.add(path)

    def _make_metric_handler(self, metric_key):
        def _handler(packet, sender_ip, sender_port):
            self._handle_single_metric(packet, sender_ip, sender_port, metric_key)
        return _handler

    def _record_caller(self, sender_ip):
        self.app_state.record_request(sender_ip)

    def _handle_response(self, packet, remote_address):
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

        # Build dynamic CoRE Link Format string
        parts = [
            f'</id>;rt="core.d";ep="{device_id}";dt="{device_type}"',
            '</info>;rt="info";if="sensor"',
            '</sensors>;rt="sensor-collection";if="sensor"',
        ]
        if hasattr(self.app_state, "get_all_metrics"):
            metrics = self.app_state.get_all_metrics()
            for key in metrics.keys():
                parts.append(f'</sensors/{key}>;rt="{key}";if="sensor"')

        parts.append('</display>;rt="display";if="actuator"')
        parts.append('</live>;rt="live-stream";if="actuator"')
        link_format = ",".join(parts)

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            link_format,
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_LINK_FORMAT,
            packet.token, request_packet=packet,
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
            packet.token, request_packet=packet,
        )

    def _handle_info(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)
        self._check_semi_sleep_read()
        payload = self.app_state.to_dict()
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(payload),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token, request_packet=packet,
        )

    def _check_semi_sleep_read(self):
        if self.app_state.mode == MODE_SEMI_SLEEP:
            ts = get_utc_iso_timestamp() if self.app_state.ntp_synced else None
            if hasattr(self.app_state, "read_registered_sensors"):
                self.app_state.read_registered_sensors(timestamp=ts)
            elif self.reader is not None:
                data = self.reader.read_sensors()
                data["timestamp"] = ts
                self.app_state.update_sensors(data)

    def _handle_sensors_collection(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)
        self._check_semi_sleep_read()

        senml_payload = self.app_state.to_senml()
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(senml_payload),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token, request_packet=packet,
        )

    def _handle_single_metric(self, packet, sender_ip, sender_port, metric_key):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)
        self._check_semi_sleep_read()

        m = self.app_state.get_metric(metric_key) if hasattr(self.app_state, "get_metric") else None
        if m is not None:
            senml_item = {
                "n": metric_key,
                "u": m.get("unit", ""),
                "v": m.get("val"),
                "t": m.get("ts") or self.app_state.timestamp,
            }
            self.coap.sendResponse(
                sender_ip,
                sender_port,
                packet.messageid,
                json.dumps(senml_item),
                COAP_RESPONSE_CODE.COAP_CONTENT,
                COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
                packet.token, request_packet=packet,
            )
        else:
            self.coap.sendResponse(
                sender_ip,
                sender_port,
                packet.messageid,
                "Not Found",
                COAP_RESPONSE_CODE.COAP_NOT_FOUND,
                COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
                packet.token, request_packet=packet,
            )

    def _handle_display(self, packet, sender_ip, sender_port):
        self._record_caller(sender_ip)

        if packet.method == COAP_METHOD.COAP_GET:
            resp = {
                "display": self.app_state.is_display_overridden(),
                "text": self.app_state.display_override_text or self.app_state.alert_message or "",
            }
            self.coap.sendResponse(
                sender_ip,
                sender_port,
                packet.messageid,
                json.dumps(resp),
                COAP_RESPONSE_CODE.COAP_CONTENT,
                COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
                packet.token, request_packet=packet,
            )
        elif packet.method in (COAP_METHOD.COAP_POST, COAP_METHOD.COAP_PUT):
            try:
                payload = packet.payload
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.decode("utf-8")

                text = ""
                try:
                    data = json.loads(payload)
                    if isinstance(data, dict):
                        text = str(data.get("text", ""))
                    else:
                        text = str(data)
                except Exception:
                    text = str(payload).strip() if payload else ""

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
                    json.dumps({"status": "ok"}),
                    COAP_RESPONSE_CODE.COAP_CHANGED,
                    COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
                    packet.token, request_packet=packet,
                )
            except Exception as e:
                print(f"[coap] Display POST error: {e}")
                self.coap.sendResponse(
                    sender_ip,
                    sender_port,
                    packet.messageid,
                    "Bad Request",
                    COAP_RESPONSE_CODE.COAP_BAD_REQUEST,
                    COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
                    packet.token, request_packet=packet,
                )
        else:
            self._send_method_not_allowed(packet, sender_ip, sender_port)

    def _send_method_not_allowed(self, packet, sender_ip, sender_port):
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            "Method Not Allowed",
            getattr(COAP_RESPONSE_CODE, "COAP_METHOD_NOT_ALLOWED", getattr(COAP_RESPONSE_CODE, "COAP_METHOD_NOT_ALLOWD", 133)),
            COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
            packet.token, request_packet=packet,
        )

    def _send_bad_request(self, packet, sender_ip, sender_port, msg="Bad Request"):
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            msg,
            COAP_RESPONSE_CODE.COAP_BAD_REQUEST,
            COAP_CONTENT_FORMAT.COAP_TEXT_PLAIN,
            packet.token, request_packet=packet,
        )

    def _handle_live_start(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_POST:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)

        payload_bytes = packet.payload
        if not payload_bytes:
            self._send_bad_request(packet, sender_ip, sender_port, "Missing body")
            return

        try:
            if isinstance(payload_bytes, (bytes, bytearray)):
                payload_str = payload_bytes.decode("utf-8")
            else:
                payload_str = str(payload_bytes)
            data = json.loads(payload_str)
        except Exception:
            self._send_bad_request(packet, sender_ip, sender_port, "Malformed JSON")
            return

        if not isinstance(data, dict):
            self._send_bad_request(packet, sender_ip, sender_port, "JSON must be object")
            return

        broker = data.get("broker")
        rate_ms = data.get("rate_ms")

        if not broker or not isinstance(broker, str) or rate_ms is None or isinstance(rate_ms, bool) or not isinstance(rate_ms, int) or rate_ms <= 0:
            self._send_bad_request(packet, sender_ip, sender_port, "Invalid broker or rate_ms")
            return

        if hasattr(self, "live_publisher") and self.live_publisher:
            self.live_publisher.start(broker=broker, rate_ms=rate_ms)

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            None,
            COAP_RESPONSE_CODE.COAP_CHANGED,
            COAP_CONTENT_FORMAT.COAP_NONE,
            packet.token,
            request_packet=packet,
        )

    def _handle_live_stop(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_POST:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)

        if hasattr(self, "live_publisher") and self.live_publisher:
            self.live_publisher.stop()

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            None,
            COAP_RESPONSE_CODE.COAP_CHANGED,
            COAP_CONTENT_FORMAT.COAP_NONE,
            packet.token,
            request_packet=packet,
        )

    def start(self):
        """Initializes and binds the UDP socket for unicast, broadcast, and CoAP multicast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sol_socket = getattr(socket, "SOL_SOCKET", 1)
        so_reuseaddr = getattr(socket, "SO_REUSEADDR", 2)
        so_broadcast = getattr(socket, "SO_BROADCAST", 0x20)

        for lvl in (sol_socket, 4095, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_reuseaddr, 1)
                break
            except Exception:
                pass

        for lvl in (sol_socket, 4095, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_broadcast, 1)
                break
            except Exception:
                pass

        try:
            sock.bind(("0.0.0.0", self.port))
        except Exception:
            try:
                sock.bind(("", self.port))
            except Exception:
                pass

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

    def stop(self):
        self.coap.stop()


async def run_coap_task(app_state, port=getattr(config, "COAP_PORT", 5683)):
    """Starts and runs the asynchronous IoTMesh CoAP server once WiFi connects."""
    try:
        while getattr(app_state, "wifi_status", None) != "connected":
            await asyncio.sleep(0.5)

        print(f"[coap] WiFi connected, starting CoAP server on port {port}...")
        server = CoapServer(app_state, port=port)
        server.start()
        await server.run()
    except Exception as e:
        print(f"[coap] Error in coap task: {e}")

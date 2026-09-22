"""CoAP server implementing IoTMesh Service Spec v0.1 for Raspberry Pi Pico 2 W."""

import json
import struct
import sys
from settings import config
from core.state import MODE_SEMI_SLEEP
from services.log_sync import read_log_records

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
    for pattern in ('ep="', "ep='"):
        idx = link_text.find(pattern)
        if idx != -1:
            start = idx + len(pattern)
            quote = pattern[-1]
            end = link_text.find(quote, start)
            if end != -1:
                return link_text[start:end]
    idx = link_text.find("ep=")
    if idx != -1:
        start = idx + 3
        end = len(link_text)
        for sep in (";", ",", " ", "\r", "\n"):
            pos = link_text.find(sep, start)
            if pos != -1 and pos < end:
                end = pos
        return link_text[start:end].strip()
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


def get_subnet_broadcast():
    """Calculates IPv4 subnet broadcast address from WLAN interface."""
    try:
        import network
        wlan = network.WLAN(network.STA_IF)
        if wlan.isconnected():
            ip, mask, _, _ = wlan.ifconfig()
            ip_octets = [int(x) for x in ip.split(".")]
            mask_octets = [int(x) for x in mask.split(".")]
            bcast = [ip_octets[i] | (~mask_octets[i] & 0xFF) for i in range(4)]
            return ".".join(str(x) for x in bcast)
    except Exception:
        pass
    return None


class CoapServer:
    def __init__(self, app_state, reader=None, sd_storage=None, port=getattr(config, "COAP_PORT", 5683)):
        self.app_state = app_state
        self.reader = reader
        self.sd_storage = sd_storage
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
            ("logger", self._handle_logger),
            ("log", self._handle_log),
        ]
        for path, handler in routes:
            self.coap.addIncomingRequestCallback(path, handler)

    def _record_caller(self, sender_ip):
        """Increments request counter and updates last_caller."""
        self.app_state.record_request(sender_ip)

    def _handle_response(self, packet, remote_address):
        """Processes incoming CoAP responses to learn node IDs for known_nodes cache."""
        sender_ip = remote_address[0]
        code_raw = getattr(packet, "code", None)
        code_str = f"{(code_raw >> 5)}.{(code_raw & 0x1F):02d}" if code_raw is not None else "unknown"
        print(f"[coap-rx] Incoming response from {sender_ip}:{remote_address[1]} (code={code_str}, type={packet.type}, msg_id={packet.messageid})")

        if not packet.payload:
            print(f"[coap-rx] Packet from {sender_ip} has empty payload (code={code_str})")
            if code_raw is not None and (code_raw >> 5) >= 4:
                print(f"[coap-rx] ERROR: Received CoAP client/server error response {code_str} from {sender_ip}")
            return

        try:
            if isinstance(packet.payload, (bytes, bytearray)):
                payload_str = packet.payload.decode("utf-8")
            else:
                payload_str = str(packet.payload)
        except Exception as e:
            print(f"[coap-rx] Payload decode error from {sender_ip}: {e}")
            return

        if code_raw is not None and (code_raw >> 5) >= 4:
            print(f"[coap-rx] ERROR response {code_str} from {sender_ip}: {payload_str}")
            return

        print(f"[coap-rx] Payload from {sender_ip}: {payload_str[:60]}...")
        device_id = extract_device_id_from_json(payload_str)
        if not device_id:
            device_id = extract_device_id_from_link_format(payload_str)

        if device_id:
            self.app_state.register_node(sender_ip, device_id)
            print(f"[coap] Registered node {device_id} -> {sender_ip}")

        # Detect sensor resource types in CoRE Link Format for data logger
        if 'rt="temperature"' in payload_str or 'rt="humidity"' in payload_str:
            target_id = device_id if device_id else sender_ip
            self.app_state.log_active_nodes[sender_ip] = target_id
            print(f"[coap] Discovered sensor node {target_id} at {sender_ip}")

    async def fire_sensor_discovery(self, target_port=5683):
        """Discovers sensor nodes via subnet broadcast (e.g. 192.168.1.255) like the PC tool does.

        Sends broadcast bursts spaced across 500 ms intervals and checks for incoming
        responses.
        """
        local_ip = self.app_state.ip_address if self.app_state.ip_address else None
        local_id = getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID)

        print(f"[coap-disc] Discovery started. Local IP: {local_ip}, device: {local_id}")

        if not local_ip or "." not in local_ip:
            print("[coap-disc] ERROR: local IP not available, cannot broadcast")
            return

        self.app_state.log_active_nodes[local_ip] = local_id
        print(f"[coap-disc] Registered local node {local_id} at {local_ip}")

        targets = []
        bcast = get_subnet_broadcast()
        if not bcast and local_ip and "." in local_ip:
            parts = local_ip.split(".")
            if len(parts) == 4:
                bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"

        if bcast and bcast not in targets:
            targets.append(bcast)
        if "255.255.255.255" not in targets:
            targets.append("255.255.255.255")

        print(f"[coap-disc] Broadcasting discovery to targets: {targets}")

        try:
            try:
                import socket
            except ImportError:
                import usocket as socket

            bcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for lvl in (1, 0xFFFF):
                try:
                    bcast_sock.setsockopt(lvl, 0x20, 1)
                    break
                except Exception:
                    pass
            bcast_sock.settimeout(0.5)

            for burst in range(1, 4):
                print(f"[coap-disc] Broadcast burst {burst}/3 → {targets}")
                # Generate unique message ID per burst to prevent retransmission deduplication
                msg_id = (0x1234 + burst) & 0xFFFF
                burst_pkt = bytes([0x50, 0x01, (msg_id >> 8) & 0xFF, msg_id & 0xFF]) + b"\xbb.well-known\x04core"

                for dest in targets:
                    try:
                        bcast_sock.sendto(burst_pkt, (dest, target_port))
                        print(f"[coap-disc] Dispatched probe to {dest}:{target_port}")
                    except Exception as e:
                        print(f"[coap-disc] Broadcast send error to {dest}: {e}")

                # Collect any broadcast responses
                while True:
                    try:
                        data, addr = bcast_sock.recvfrom(512)
                        sender_ip = addr[0]
                        if sender_ip == local_ip:
                            continue
                        print(f"[coap-disc] Broadcast response from {sender_ip}: {data[:60]}...")
                        payload_bytes = data.split(b"\xff", 1)[1] if b"\xff" in data else b""
                        payload_str = payload_bytes.decode("utf-8", "ignore")
                        dev_id = extract_device_id_from_link_format(payload_str) or extract_device_id_from_json(payload_str) or sender_ip
                        if 'rt="temperature"' in payload_str or 'rt="humidity"' in payload_str or 'ep=' in payload_str:
                            self.app_state.register_node(sender_ip, dev_id)
                            self.app_state.log_active_nodes[sender_ip] = dev_id
                            print(f"[coap-disc] Registered discovered node {dev_id} at {sender_ip}")
                    except OSError:
                        break
                await asyncio.sleep(0.1)

            bcast_sock.close()
        except Exception as e:
            print(f"[coap-disc] Broadcast client error: {e}")

        print(f"[coap-disc] Discovery done. log_active_nodes: {self.app_state.log_active_nodes}")

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
            '</display>;rt="display";if="actuator",'
            '</logger>;rt="data-logger";if="logger",'
            '</log>;rt="data-sync";if="logger"'
        )

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            link_format,
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_LINK_FORMAT,
            packet.token, request_packet=packet,
        )

    def _handle_logger(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)

        payload = {
            "active": bool(self.app_state.logging_active),
            "buffered": int(self.app_state.log_buffered_count),
            "last_ntp": self.app_state.log_ntp_time_str,
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
            packet.token, request_packet=packet,
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
            packet.token, request_packet=packet,
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
            packet.token, request_packet=packet,
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
            packet.token, request_packet=packet,
        )

    def _send_method_not_allowed(self, packet, sender_ip, sender_port):
        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            "Method Not Allowed",
            COAP_RESPONSE_CODE.COAP_METHOD_NOT_ALLOWD,
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

    def _extract_query_params(self, packet):
        """Extracts URI query parameters from CoAP packet options."""
        params = {}
        if not hasattr(packet, "options") or not packet.options:
            return params
        for opt in packet.options:
            if getattr(opt, "number", None) == 15:  # COAP_OPTION_NUMBER.COAP_URI_QUERY
                try:
                    if isinstance(opt.buffer, (bytes, bytearray)):
                        query_str = opt.buffer.decode("utf-8")
                    else:
                        query_str = str(opt.buffer)
                except Exception:
                    continue
                for item in query_str.split("&"):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        params[k.strip()] = v.strip()
                    elif item.strip():
                        params[item.strip()] = ""
        return params

    def _handle_log(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)
        params = self._extract_query_params(packet)

        if "size" not in params:
            print(f"[coap-server] GET /log missing mandatory 'size' param from {sender_ip}")
            self._send_bad_request(packet, sender_ip, sender_port, "Missing size parameter")
            return

        try:
            size = int(params["size"])
            if size <= 0:
                raise ValueError("size must be positive")
        except ValueError:
            self._send_bad_request(packet, sender_ip, sender_port, "Invalid size parameter")
            return

        cursor = params.get("cursor")

        # Read logs from SD card
        if self.sd_storage is not None:
            try:
                self.sd_storage.mount()
            except Exception as e:
                print(f"[coap-server] SD mount failed during /log: {e}")
            try:
                dir_path = f"{self.sd_storage.mount_point}{config.LOG_SD_ROOT}"
                result = read_log_records(dir_path, cursor, size)
            finally:
                try:
                    self.sd_storage.unmount()
                except Exception:
                    pass
        else:
            dir_path = f"/sd{config.LOG_SD_ROOT}"
            result = read_log_records(dir_path, cursor, size)

        self.coap.sendResponse(
            sender_ip,
            sender_port,
            packet.messageid,
            json.dumps(result),
            COAP_RESPONSE_CODE.COAP_CONTENT,
            COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON,
            packet.token, request_packet=packet,
        )
        print(f"[coap-server] Sent /log response to {sender_ip}:{sender_port} (rows={len(result['data'])}, next_cursor={result['next_cursor']})")

    def start(self):
        """Initializes and binds the UDP socket for unicast, broadcast, and CoAP multicast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Configure socket options with robust fallbacks for MicroPython ports
        sol_socket = getattr(socket, "SOL_SOCKET", 1)
        so_reuseaddr = getattr(socket, "SO_REUSEADDR", 2)
        so_broadcast = getattr(socket, "SO_BROADCAST", 0x20)

        for lvl in (sol_socket, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_reuseaddr, 1)
                break
            except Exception:
                pass

        broadcast_ok = False
        for lvl in (sol_socket, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_broadcast, 1)
                broadcast_ok = True
                print(f"[coap] SO_BROADCAST enabled (level={lvl}, opt={so_broadcast})")
                break
            except Exception:
                pass
        if not broadcast_ok:
            print("[coap] Warning: Could not enable SO_BROADCAST via setsockopt")

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

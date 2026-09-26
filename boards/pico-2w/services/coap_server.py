"""CoAP server implementing IoTMesh Service Spec v0.1 for Raspberry Pi Pico 2 W."""

import json
import struct
import sys
from settings import config
from core.state import MODE_SEMI_SLEEP
from services.ntp_service import get_utc_iso_timestamp
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
        self._registered_paths = set()
        self._register_callbacks()

    def _register_callbacks(self):
        base_routes = [
            (".well-known/core", self._handle_well_known_core),
            ("id", self._handle_id),
            ("info", self._handle_info),
            ("sensors", self._handle_sensors_collection),
            ("display", self._handle_display),
            ("logger", self._handle_logger),
            ("log", self._handle_log),
        ]
        for path, handler in base_routes:
            self.coap.addIncomingRequestCallback(path, handler)
            self._registered_paths.add(path)

        self.sync_sensor_routes()

    def sync_sensor_routes(self):
        """Ensures all metrics in AppState have individual CoAP endpoints registered."""
        # Built-in routes for pico-2w sensors
        for key in ("temperature", "humidity", "light"):
            path = f"sensors/{key}"
            if path not in self._registered_paths:
                handler = self._make_metric_handler(key)
                self.coap.addIncomingRequestCallback(path, handler)
                self._registered_paths.add(path)

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
        """Increments request counter and updates last_caller."""
        self.app_state.record_request(sender_ip)

    def _check_semi_sleep_read(self):
        if self.app_state.mode == MODE_SEMI_SLEEP:
            ts = get_utc_iso_timestamp() if self.app_state.ntp_synced else None
            if hasattr(self.app_state, "read_registered_sensors"):
                self.app_state.read_registered_sensors(timestamp=ts)
            elif self.reader is not None:
                data = self.reader.read_sensors()
                self.app_state.update_sensors(data)

    def _handle_response(self, packet, remote_address):
        """Processes incoming CoAP responses to learn node IDs for known_nodes cache."""
        sender_ip = remote_address[0]
        code_raw = getattr(packet, "code", None)
        code_str = f"{(code_raw >> 5)}.{(code_raw & 0x1F):02d}" if code_raw is not None else "unknown"

        if not packet.payload:
            return

        try:
            if isinstance(packet.payload, (bytes, bytearray)):
                payload_str = packet.payload.decode("utf-8")
            else:
                payload_str = str(packet.payload)
        except Exception:
            return

        if code_raw is not None and (code_raw >> 5) >= 4:
            return

        device_id = extract_device_id_from_json(payload_str)
        if not device_id:
            device_id = extract_device_id_from_link_format(payload_str)

        if device_id:
            self.app_state.register_node(sender_ip, device_id)

        # Detect sensor resource types in CoRE Link Format for data logger
        if 'rt="temperature"' in payload_str or 'rt="humidity"' in payload_str:
            target_id = device_id if device_id else sender_ip
            self.app_state.log_active_nodes[sender_ip] = target_id

    async def fire_sensor_discovery(self, target_port=5683):
        """Discovers sensor nodes via subnet broadcast."""
        local_ip = self.app_state.ip_address if self.app_state.ip_address else None
        local_id = getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID)

        if not local_ip or "." not in local_ip:
            return

        self.app_state.log_active_nodes[local_ip] = local_id

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
                msg_id = (0x1234 + burst) & 0xFFFF
                burst_pkt = bytes([0x50, 0x01, (msg_id >> 8) & 0xFF, msg_id & 0xFF]) + b"\xbb.well-known\x04core"

                for dest in targets:
                    try:
                        bcast_sock.sendto(burst_pkt, (dest, target_port))
                    except Exception:
                        pass

                while True:
                    try:
                        data, addr = bcast_sock.recvfrom(512)
                        sender_ip = addr[0]
                        if sender_ip == local_ip:
                            continue
                        payload_bytes = data.split(b"\xff", 1)[1] if b"\xff" in data else b""
                        payload_str = payload_bytes.decode("utf-8", "ignore")
                        dev_id = extract_device_id_from_link_format(payload_str) or extract_device_id_from_json(payload_str) or sender_ip
                        if 'rt="temperature"' in payload_str or 'rt="humidity"' in payload_str or 'ep=' in payload_str:
                            self.app_state.register_node(sender_ip, dev_id)
                            self.app_state.log_active_nodes[sender_ip] = dev_id
                    except OSError:
                        break
                await asyncio.sleep(0.1)

            bcast_sock.close()
        except Exception as e:
            print(f"[coap-disc] Broadcast client error: {e}")

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

        # Dynamic link format advertising registered sensors and logger endpoints
        parts = [
            f'</id>;rt="core.d";ep="{device_id}";dt="{device_type}"',
            '</info>;rt="info";if="sensor"',
            '</sensors>;rt="sensor-collection";if="sensor"',
        ]

        if hasattr(self.app_state, "get_all_metrics"):
            metrics = self.app_state.get_all_metrics()
            for key in metrics.keys():
                parts.append(f'</sensors/{key}>;rt="{key}";if="sensor"')
        else:
            parts.extend([
                '</sensors/temperature>;rt="temperature";if="sensor"',
                '</sensors/humidity>;rt="humidity";if="sensor"',
                '</sensors/light>;rt="light";if="sensor"',
            ])

        parts.extend([
            '</display>;rt="display";if="actuator"',
            '</logger>;rt="data-logger";if="logger"',
            '</log>;rt="data-sync";if="logger"',
        ])
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

    def _handle_sensors_collection(self, packet, sender_ip, sender_port):
        if packet.method != COAP_METHOD.COAP_GET:
            self._send_method_not_allowed(packet, sender_ip, sender_port)
            return

        self._record_caller(sender_ip)
        self._check_semi_sleep_read()

        if hasattr(self.app_state, "to_senml"):
            senml_payload = self.app_state.to_senml()
        else:
            senml_payload = [
                {"n": "temperature", "u": "Cel", "v": self.app_state.temperature_c},
                {"n": "humidity", "u": "%RH", "v": self.app_state.humidity_pct},
                {"n": "light", "u": "%", "v": self.app_state.light_pct},
            ]

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
            }
            if m.get("ts"):
                senml_item["t"] = m["ts"]
            elif self.app_state.timestamp:
                senml_item["t"] = self.app_state.timestamp
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
            # Fallback for standard properties
            val = getattr(self.app_state, f"{metric_key}_c", getattr(self.app_state, f"{metric_key}_pct", None))
            if val is not None:
                unit = "Cel" if metric_key == "temperature" else ("%RH" if metric_key == "humidity" else "%")
                senml_item = {"n": metric_key, "u": unit, "v": val}
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

    def _handle_sensor_temperature(self, packet, sender_ip, sender_port):
        self._handle_single_metric(packet, sender_ip, sender_port, "temperature")

    def _handle_sensor_humidity(self, packet, sender_ip, sender_port):
        self._handle_single_metric(packet, sender_ip, sender_port, "humidity")

    def _handle_sensor_light(self, packet, sender_ip, sender_port):
        self._handle_single_metric(packet, sender_ip, sender_port, "light")

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
            self._send_bad_request(packet, sender_ip, sender_port, "Missing size parameter")
            return

        try:
            size = int(params["size"])
            if size <= 0:
                raise ValueError("size must be positive")
            size = min(size, 10)
        except ValueError:
            self._send_bad_request(packet, sender_ip, sender_port, "Invalid size parameter")
            return

        cursor = params.get("cursor")

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

    def start(self):
        """Initializes and binds the UDP socket for unicast, broadcast, and CoAP multicast."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        sol_socket = getattr(socket, "SOL_SOCKET", 1)
        so_reuseaddr = getattr(socket, "SO_REUSEADDR", 2)
        so_broadcast = getattr(socket, "SO_BROADCAST", 0x20)

        for lvl in (sol_socket, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_reuseaddr, 1)
                break
            except Exception:
                pass

        for lvl in (sol_socket, 1, 0xFFFF):
            try:
                sock.setsockopt(lvl, so_broadcast, 1)
                break
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

    def stop(self):
        self.coap.stop()


async def run_coap_task(app_state, coap_server=None, reader=None, sd_storage=None, port=getattr(config, "COAP_PORT", 5683)):
    """Starts and runs the asynchronous IoTMesh CoAP server once WiFi connects."""
    try:
        while getattr(app_state, "wifi_status", None) != "connected":
            await asyncio.sleep(0.5)

        print(f"[coap] WiFi connected, starting CoAP server on port {port}...")
        server = coap_server if coap_server is not None else CoapServer(app_state, reader=reader, sd_storage=sd_storage, port=port)
        server.start()
        await server.run()
    except Exception as e:
        print(f"[coap] Error in coap task: {e}")

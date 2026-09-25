"""Asynchronous CoAP (RFC 7252) client and IoTMesh discovery for controller."""

import asyncio
import json
import socket
import struct
from typing import Any, Dict, List, Optional, Tuple

from backend import config

# CoAP Message Types
TYPE_CON = 0
TYPE_NON = 1
TYPE_ACK = 2
TYPE_RST = 3

# CoAP Request Methods
METHOD_GET = 1
METHOD_POST = 2
METHOD_PUT = 3
METHOD_DELETE = 4

# CoAP Response Codes
CODE_CONTENT = 69      # 2.05 Content
CODE_CHANGED = 68      # 2.04 Changed
CODE_CREATED = 65      # 2.01 Created
CODE_DELETED = 66      # 2.02 Deleted
CODE_BAD_REQUEST = 128 # 4.00 Bad Request
CODE_NOT_FOUND = 132   # 4.04 Not Found

# CoAP Option Numbers
OPT_URI_PATH = 11
OPT_CONTENT_FORMAT = 12
OPT_URI_QUERY = 15

# Content Formats
FORMAT_TEXT_PLAIN = 0
FORMAT_LINK_FORMAT = 40
FORMAT_APPLICATION_JSON = 50


class CoapMessage:
    """CoAP RFC 7252 message representation."""

    def __init__(
        self,
        mtype: int = TYPE_NON,
        code: int = METHOD_GET,
        message_id: int = 0,
        token: bytes = b"",
        options: Optional[List[Tuple[int, bytes]]] = None,
        payload: bytes = b"",
    ):
        self.type = mtype
        self.code = code
        self.message_id = message_id
        self.token = token
        self.options: List[Tuple[int, bytes]] = options or []
        self.payload = payload

    def add_uri_path(self, path: str) -> None:
        """Adds Uri-Path options for each segment of the given path."""
        clean_path = path.strip("/")
        if not clean_path:
            return
        for seg in clean_path.split("/"):
            if seg:
                self.options.append((OPT_URI_PATH, seg.encode("utf-8")))

    def add_uri_query(self, query: str) -> None:
        """Adds Uri-Query options for key=value parameters."""
        clean_query = query.lstrip("?")
        if not clean_query:
            return
        for param in clean_query.split("&"):
            if param:
                self.options.append((OPT_URI_QUERY, param.encode("utf-8")))

    def encode(self) -> bytes:
        """Encodes message into wire bytes."""
        tkl = len(self.token) & 0x0F
        first_byte = (1 << 6) | ((self.type & 0x03) << 4) | tkl
        header = struct.pack("!BBH", first_byte, self.code, self.message_id)

        out = bytearray(header)
        out.extend(self.token[:tkl])

        # Sort options by option number
        sorted_opts = sorted(self.options, key=lambda x: x[0])
        last_opt_num = 0

        for opt_num, opt_val in sorted_opts:
            delta = opt_num - last_opt_num
            length = len(opt_val)

            # Delta encoding
            delta_val = delta
            delta_nibble = 0
            delta_extra = bytearray()
            if delta < 13:
                delta_nibble = delta
            elif delta < 269:
                delta_nibble = 13
                delta_extra.append(delta - 13)
            else:
                delta_nibble = 14
                delta_extra.extend(struct.pack("!H", delta - 269))

            # Length encoding
            len_nibble = 0
            len_extra = bytearray()
            if length < 13:
                len_nibble = length
            elif length < 269:
                len_nibble = 13
                len_extra.append(length - 13)
            else:
                len_nibble = 14
                len_extra.extend(struct.pack("!H", length - 269))

            opt_header = (delta_nibble << 4) | len_nibble
            out.append(opt_header)
            out.extend(delta_extra)
            out.extend(len_extra)
            out.extend(opt_val)

            last_opt_num = opt_num

        if self.payload:
            out.append(0xFF)  # Payload marker
            out.extend(self.payload)

        return bytes(out)

    @classmethod
    def decode(cls, data: bytes) -> "CoapMessage":
        """Decodes wire bytes into a CoapMessage."""
        if len(data) < 4:
            raise ValueError(f"Packet too short: {len(data)} bytes")

        first_byte, code, msg_id = struct.unpack("!BBH", data[:4])
        version = (first_byte >> 6) & 0x03
        if version != 1:
            raise ValueError(f"Unsupported CoAP version: {version}")

        mtype = (first_byte >> 4) & 0x03
        tkl = first_byte & 0x0F

        idx = 4
        if len(data) < idx + tkl:
            raise ValueError("Packet truncated in token")
        token = data[idx : idx + tkl]
        idx += tkl

        options: List[Tuple[int, bytes]] = []
        last_opt_num = 0

        while idx < len(data):
            if data[idx] == 0xFF:
                idx += 1  # Payload marker
                break

            opt_byte = data[idx]
            idx += 1
            delta = (opt_byte >> 4) & 0x0F
            length = opt_byte & 0x0F

            if delta == 13:
                if idx >= len(data):
                    raise ValueError("Truncated option delta (13)")
                delta = data[idx] + 13
                idx += 1
            elif delta == 14:
                if idx + 2 > len(data):
                    raise ValueError("Truncated option delta (14)")
                delta = struct.unpack("!H", data[idx : idx + 2])[0] + 269
                idx += 2
            elif delta == 15:
                raise ValueError("Invalid option delta: 15")

            if length == 13:
                if idx >= len(data):
                    raise ValueError("Truncated option length (13)")
                length = data[idx] + 13
                idx += 1
            elif length == 14:
                if idx + 2 > len(data):
                    raise ValueError("Truncated option length (14)")
                length = struct.unpack("!H", data[idx : idx + 2])[0] + 269
                idx += 2
            elif length == 15:
                raise ValueError("Invalid option length: 15")

            opt_num = last_opt_num + delta
            if idx + length > len(data):
                raise ValueError(f"Truncated option value for opt {opt_num}")
            opt_val = data[idx : idx + length]
            idx += length

            options.append((opt_num, opt_val))
            last_opt_num = opt_num

        payload = data[idx:] if idx <= len(data) else b""

        return cls(
            mtype=mtype,
            code=code,
            message_id=msg_id,
            token=token,
            options=options,
            payload=payload,
        )


def parse_link_format(link_str: str) -> List[Dict[str, Any]]:
    """Parses RFC 6690 CoRE Link Format string into list of resource dictionaries."""
    resources = []
    for item in link_str.split(","):
        item = item.strip()
        if not item or not item.startswith("<"):
            continue
        parts = item.split(";")
        href = parts[0].strip("<>")
        res: Dict[str, Any] = {"href": href}
        for attr in parts[1:]:
            attr = attr.strip()
            if "=" in attr:
                k, v = attr.split("=", 1)
                res[k.strip()] = v.strip('"\'')
            elif attr:
                res[attr] = True
        resources.append(res)
    return resources


def extract_device_info(payload_str: str, sender_ip: str) -> Dict[str, Any]:
    """Extracts device_id and advertised capabilities from discovery payload."""
    device_id = None
    capabilities: List[str] = []

    # Check CoRE link format for ep="..."
    for token in ('ep="', "ep='"):
        if token in payload_str:
            start = payload_str.find(token) + len(token)
            end = payload_str.find(token[-1], start)
            if end != -1:
                device_id = payload_str[start:end]
                break

    # Parse link format resources
    resources = parse_link_format(payload_str)
    for res in resources:
        rt = res.get("rt")
        if rt and rt not in capabilities:
            capabilities.append(rt)

    # Check JSON fallback if payload is JSON
    if not device_id:
        try:
            data = json.loads(payload_str)
            if isinstance(data, dict):
                device_id = data.get("id") or data.get("device_id")
        except Exception:
            pass

    if not device_id:
        device_id = sender_ip

    return {
        "device_id": device_id,
        "ip_address": sender_ip,
        "capabilities": capabilities,
    }


def get_subnet_broadcasts() -> List[str]:
    """Determines subnet broadcast addresses for active interfaces."""
    targets = [config.COAP_BROADCAST_ADDR]
    try:
        # Probe route to discover default LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4:
            subnet_bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
            if subnet_bcast not in targets:
                targets.insert(0, subnet_bcast)
    except Exception:
        pass
    return targets


class CoapClient:
    """Async CoAP client and IoTMesh network discovery."""

    def __init__(self, port: Optional[int] = None):
        self.port = port or config.COAP_PORT
        self._msg_id_counter = 0x1000

    def _next_msg_id(self) -> int:
        self._msg_id_counter = (self._msg_id_counter + 1) & 0xFFFF
        return self._msg_id_counter

    async def send_request(
        self,
        ip: str,
        path: str,
        method: int = METHOD_GET,
        query: str = "",
        payload: bytes = b"",
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> CoapMessage:
        """Sends a CoAP request and waits for an answer with retry logic."""
        target_port = port or self.port
        req_timeout = timeout or config.COAP_TIMEOUT_S
        req_retries = retries if retries is not None else config.COAP_MAX_RETRIES

        token = struct.pack("!H", self._next_msg_id())
        msg = CoapMessage(
            mtype=TYPE_CON,
            code=method,
            message_id=self._next_msg_id(),
            token=token,
            payload=payload,
        )
        msg.add_uri_path(path)
        if query:
            msg.add_uri_query(query)

        packet_bytes = msg.encode()

        for attempt in range(req_retries + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            loop = asyncio.get_running_loop()
            try:
                await loop.sock_sendto(sock, packet_bytes, (ip, target_port))
                start_time = loop.time()
                while loop.time() - start_time < req_timeout:
                    try:
                        data, addr = await asyncio.wait_for(
                            loop.sock_recvfrom(sock, 4096),
                            timeout=max(0.1, req_timeout - (loop.time() - start_time)),
                        )
                        if addr[0] == ip:
                            response = CoapMessage.decode(data)
                            if response.token == token or response.message_id == msg.message_id:
                                return response
                    except asyncio.TimeoutError:
                        break
            except Exception:
                pass
            finally:
                sock.close()

            if attempt < req_retries:
                await asyncio.sleep(0.2 * (2**attempt))

        raise TimeoutError(f"CoAP request to {ip}:{target_port}/{path} timed out after {req_retries + 1} attempts")

    async def discover_nodes(
        self,
        target_port: Optional[int] = None,
        timeout: float = 1.2,
    ) -> List[Dict[str, Any]]:
        """Broadcasts and multicasts discovery probes to identify LAN IoTMesh nodes."""
        port = target_port or self.port
        destinations = get_subnet_broadcasts()
        if config.COAP_MULTICAST_ADDR not in destinations:
            destinations.append(config.COAP_MULTICAST_ADDR)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setblocking(False)

        discovered: Dict[str, Dict[str, Any]] = {}
        loop = asyncio.get_running_loop()

        try:
            # Send discovery bursts
            for burst in range(2):
                probe = CoapMessage(
                    mtype=TYPE_NON,
                    code=METHOD_GET,
                    message_id=self._next_msg_id(),
                )
                probe.add_uri_path(".well-known/core")
                wire = probe.encode()

                for dest in destinations:
                    try:
                        await loop.sock_sendto(sock, wire, (dest, port))
                    except Exception:
                        pass
                await asyncio.sleep(0.15)

            end_time = loop.time() + timeout
            while loop.time() < end_time:
                remaining = max(0.05, end_time - loop.time())
                try:
                    data, addr = await asyncio.wait_for(
                        loop.sock_recvfrom(sock, 4096),
                        timeout=remaining,
                    )
                    sender_ip = addr[0]
                    try:
                        resp = CoapMessage.decode(data)
                        payload_str = resp.payload.decode("utf-8", errors="ignore")
                        info = extract_device_info(payload_str, sender_ip)
                        dev_id = info["device_id"]
                        if dev_id not in discovered:
                            discovered[dev_id] = info
                        else:
                            # Merge capabilities
                            for cap in info["capabilities"]:
                                if cap not in discovered[dev_id]["capabilities"]:
                                    discovered[dev_id]["capabilities"].append(cap)
                    except Exception:
                        pass
                except asyncio.TimeoutError:
                    break
        finally:
            sock.close()

        return list(discovered.values())

    async def get_log(
        self,
        ip: str,
        cursor: Optional[str] = None,
        size: int = 50,
        port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Fetches a page of sensor records from a data logger node."""
        query_parts = [f"size={size}"]
        if cursor:
            query_parts.append(f"cursor={cursor}")
        query = "&".join(query_parts)

        resp = await self.send_request(
            ip=ip,
            path="log",
            method=METHOD_GET,
            query=query,
            port=port,
        )

        if resp.code != CODE_CONTENT:
            raise RuntimeError(f"Unexpected CoAP response code {resp.code} for GET /log")

        payload_str = resp.payload.decode("utf-8")
        if not payload_str.strip():
            raise ValueError(f"Empty payload received from {ip} for GET /log (possible packet size overflow)")
        data = json.loads(payload_str)
        if not isinstance(data, dict) or "data" not in data or "next_cursor" not in data:
            raise ValueError(f"Malformed /log response JSON: {payload_str}")

        return data

    async def post_display(
        self,
        ip: str,
        message: str,
        port: Optional[int] = None,
    ) -> bool:
        """Sends text actuation command to a node display."""
        payload = message.encode("utf-8")
        resp = await self.send_request(
            ip=ip,
            path="display",
            method=METHOD_POST,
            payload=payload,
            port=port,
        )
        return resp.code in (CODE_CHANGED, CODE_CONTENT)

    async def get_sensors(
        self,
        ip: str,
        port: Optional[int] = None,
    ) -> Any:
        """Queries /sensors endpoint for real-time telemetry."""
        resp = await self.send_request(
            ip=ip,
            path="sensors",
            method=METHOD_GET,
            port=port,
        )
        if resp.code != CODE_CONTENT:
            raise RuntimeError(f"Unexpected CoAP response code {resp.code} for GET /sensors")
        return json.loads(resp.payload.decode("utf-8"))

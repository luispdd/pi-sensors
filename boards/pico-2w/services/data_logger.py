"""DataLogger service managing logger lifecycle, sensor polling, and SD flushing."""

import json
from settings import config
from core.state import LOGGER_IDLE, LOGGER_STAGING, LOGGER_CONFIRM, LOGGER_ACTIVE
from services.ntp_service import sync_ntp, get_utc_date_str, get_utc_iso_timestamp, NTPTracker

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class DataLogger:
    """Orchestrates sensor logging session lifecycle, staging, network polling, and SD storage writes."""

    def __init__(self, app_state, sd_storage, coap_server):
        self.app_state = app_state
        self.sd_storage = sd_storage
        self.coap_server = coap_server
        self.ntp_tracker = NTPTracker()
        self._flush_task = None
        self._poll_task = None
        self._is_flushing = False

    async def run_staging(self):
        """Runs the staging workflow:

        1. Sets logger_state to LOGGER_STAGING (TFT shows Preparing/Scanning)
        2. Clears previous error
        3. Attempts NTP sync
        4. Triggers CoAP sensor discovery and waits for responses
        5. Sets logger_state to LOGGER_CONFIRM
        """
        self.app_state.logger_state = LOGGER_STAGING
        self.app_state.clear_logger_error()
        self.app_state.log_active_nodes = {}
        print("[logger] run_staging: starting")

        # 1. NTP sync
        print("[logger] run_staging: attempting NTP sync...")
        success, ntp_res = sync_ntp()
        if success:
            self.app_state.log_ntp_time_str = ntp_res
            print(f"[logger] run_staging: NTP sync OK -> {ntp_res}")
        else:
            self.app_state.set_logger_error(ntp_res)
            print(f"[logger] run_staging: NTP sync FAILED -> {ntp_res}")

        # 2. CoAP subnet broadcast discovery
        print("[logger] run_staging: launching CoAP discovery...")
        if self.coap_server is not None:
            await self.coap_server.fire_sensor_discovery()
        else:
            print("[logger] run_staging: WARNING - coap_server is None, skipping discovery")

        # 3. Transition to CONFIRM
        nodes = list(self.app_state.log_active_nodes.items())
        print(f"[logger] run_staging: done. {len(nodes)} node(s) found: {nodes}")
        self.app_state.logger_state = LOGGER_CONFIRM

    def start_session(self):
        """Starts an active logging session. Sets state to LOGGER_ACTIVE and logging_active=True."""
        self.app_state.clear_buffers()
        self.app_state.clear_logger_error()
        self.app_state.logger_state = LOGGER_ACTIVE
        self.app_state.logging_active = True

    async def poll_and_buffer(self):
        """Polls sensors from all active nodes (local and discovered remote boards) and buffers readings."""
        if not self.app_state.logging_active:
            return

        ts = get_utc_iso_timestamp()
        local_id = getattr(config, "DEVICE_ID", config.DEFAULT_DEVICE_ID)
        local_ip = self.app_state.ip_address if self.app_state.ip_address else "127.0.0.1"

        # 1. Local board reading
        if local_ip in self.app_state.log_active_nodes or local_id in self.app_state.log_active_nodes.values():
            metrics = self.app_state.get_all_metrics() if hasattr(self.app_state, "get_all_metrics") else {}
            temp = metrics.get("temperature", {}).get("val") if "temperature" in metrics else getattr(self.app_state, "temperature_c", None)
            hum = metrics.get("humidity", {}).get("val") if "humidity" in metrics else getattr(self.app_state, "humidity_pct", None)
            light = metrics.get("light", {}).get("val") if "light" in metrics else getattr(self.app_state, "light_pct", None)
            local_ts = getattr(self.app_state, "timestamp", None) or ts
            self.app_state.buffer_reading(local_id, local_ts, temp, hum, light)

        # 2. Remote boards
        for ip, dev_id in list(self.app_state.log_active_nodes.items()):
            if ip == local_ip or dev_id == local_id:
                continue

            # Request /sensors from remote node via CoAP (with HTTP fallback)
            try:
                res = await self._fetch_remote_sensor(ip)
                if res is None:
                    res = self._fetch_remote_sensor_http(ip)
                if res is not None:
                    t = res[0]
                    h = res[1]
                    remote_ts = res[2]
                    l = res[3] if len(res) > 3 else None
                    reading_ts = remote_ts if remote_ts else ts
                    self.app_state.buffer_reading(dev_id, reading_ts, t, h, l)
            except Exception as e:
                # Silently skip on error/timeout per requirement
                pass


    def _fetch_remote_sensor_http(self, ip, port=80, timeout_s=1.5):
        """Fetches /sensors via HTTP fallback if CoAP times out."""
        try:
            try:
                import socket
            except ImportError:
                import usocket as socket
            sock = socket.socket()
            sock.settimeout(timeout_s)
            sock.connect((ip, port))
            req = f"GET /sensors HTTP/1.0\r\nHost: {ip}\r\nConnection: close\r\n\r\n"
            sock.send(req.encode("utf-8"))
            data = b""
            while True:
                chunk = sock.recv(256)
                if not chunk:
                    break
                data += chunk
            sock.close()
            text = data.decode("utf-8", "ignore")
            body_start = text.find("\r\n\r\n")
            if body_start != -1:
                body = text[body_start + 4:].strip()
                parsed = json.loads(body)
                t = parsed.get("temperature_c") or parsed.get("temperature") or parsed.get("temp")
                h = parsed.get("humidity_pct") or parsed.get("humidity") or parsed.get("hum")
                l = parsed.get("light_pct") or parsed.get("light")
                remote_ts = parsed.get("timestamp") or parsed.get("ts") or parsed.get("time") or parsed.get("t")
                return (t, h, remote_ts, l)
        except Exception as e:
            print(f"[logger] HTTP sensor fetch from {ip} failed: {e}")
        return None

    async def _fetch_remote_sensor(self, ip, port=5683, timeout_s=2.0):
        """Fetches /sensors from remote board and returns (temp, hum, ts) or None on timeout/error."""
        # Try CoAP GET /sensors using client UDP socket (RFC 7252 NON GET /sensors)
        try:
            try:
                import socket
            except ImportError:
                import usocket as socket

            try:
                import time
                msg_id = int(time.ticks_ms()) & 0xFFFF
            except Exception:
                msg_id = 0x3412
            req_pkt = bytes([0x50, 0x01, (msg_id >> 8) & 0xFF, msg_id & 0xFF]) + b"\xb7sensors"
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(timeout_s)
            s.sendto(req_pkt, (ip, port))
            data, addr = s.recvfrom(512)
            s.close()

            if b"\xff" in data:
                payload_str = data.split(b"\xff", 1)[1].decode("utf-8", "ignore")
                data_json = json.loads(payload_str)
                t, h, remote_ts, l = None, None, None, None
                if isinstance(data_json, list):
                    for item in data_json:
                        if isinstance(item, dict):
                            if item.get("n") == "temperature":
                                t = item.get("v")
                                if not remote_ts:
                                    remote_ts = item.get("t") or item.get("ts")
                            elif item.get("n") == "humidity":
                                h = item.get("v")
                                if not remote_ts:
                                    remote_ts = item.get("t") or item.get("ts")
                            elif item.get("n") == "light":
                                l = item.get("v")
                            elif item.get("n") in ("time", "timestamp"):
                                remote_ts = item.get("vs") or item.get("v") or item.get("t")
                elif isinstance(data_json, dict):
                    t = data_json.get("temperature") or data_json.get("temp")
                    h = data_json.get("humidity") or data_json.get("hum")
                    l = data_json.get("light") or data_json.get("light_pct")
                    remote_ts = data_json.get("timestamp") or data_json.get("ts") or data_json.get("time") or data_json.get("t")
                if t is not None or h is not None or l is not None:
                    return (t, h, remote_ts, l)
        except Exception as e:
            print(f"[logger] CoAP sensor fetch from {ip} failed: {e}")

        return None

    async def auto_flush_loop(self):
        """Runs the auto-flush and periodic polling loop while logging is active."""
        poll_interval = getattr(config, "SENSOR_LOG_INTERVAL_S", 300)
        flush_interval = getattr(config, "LOG_FLUSH_INTERVAL_S", 3600)

        # Immediate measurement on session start before entering sleep cycle
        if self.app_state.logging_active:
            await self.poll_and_buffer()

        elapsed_since_flush = 0
        while self.app_state.logging_active:
            # Check for midnight crossing for NTP re-sync
            self.ntp_tracker.check_and_resync(self.app_state)

            # Wait for next poll interval in small chunks so we can exit quickly if stopped
            chunk = 1.0
            elapsed = 0.0
            while elapsed < poll_interval and self.app_state.logging_active:
                await asyncio.sleep(chunk)
                elapsed += chunk

            if not self.app_state.logging_active:
                break

            # Poll sensors
            await self.poll_and_buffer()
            elapsed_since_flush += poll_interval

            # Check if flush interval reached
            if elapsed_since_flush >= flush_interval:
                await self.flush_to_sd(end_session=False)
                elapsed_since_flush = 0

    async def flush_to_sd(self, end_session=False):
        """Flushes in-memory buffers to SD card."""
        if self._is_flushing:
            return False
        self._is_flushing = True

        date_str = get_utc_date_str()
        buffers = dict(self.app_state.log_buffers)

        try:
            # If buffer is empty and not ending session, skip write
            if not buffers and not end_session:
                return True

            # Aggregate all buffers into a single list
            all_rows = []
            for device_id, rows in buffers.items():
                rows_to_flush = rows if end_session else rows[:12]
                for r in rows_to_flush:
                    if isinstance(r, dict):
                        r_copy = dict(r)
                        if "device_id" not in r_copy:
                            r_copy["device_id"] = device_id
                        all_rows.append(r_copy)
                    else:
                        all_rows.append({
                            "ts": r[0],
                            "device_id": device_id if len(r) < 2 else r[1],
                            "temp": r[2] if len(r) > 2 else None,
                            "hum": r[3] if len(r) > 3 else None,
                        })

            # Strictly sort by (ts, device_id)
            all_rows.sort(key=lambda r: (r["ts"], r["device_id"]))

            if self.sd_storage is not None and all_rows:
                # Yield to let any pending display updates finish
                await asyncio.sleep(0.05)
                self.sd_storage.flush_buffers(all_rows, date_str)

            if end_session:
                self.app_state.clear_buffers()
                self.app_state.logger_state = LOGGER_IDLE
                self.app_state.logging_active = False
            else:
                self.app_state.retain_unflushed(count_flushed_per_device=12)

            self.app_state.clear_logger_error()

            return True
        except Exception as e:
            err_msg = str(e)
            if "mount" in err_msg.lower() or "hardware" in err_msg.lower():
                self.app_state.set_logger_error("SD: mount fail")
            else:
                self.app_state.set_logger_error("SD: write fail")
            print(f"[logger] Flush failed: {e}")
            return False
        finally:
            self._is_flushing = False

    async def stop_and_flush(self):
        """Stops active session, flushes all buffers to SD immediately, and transitions to IDLE on success."""
        return await self.flush_to_sd(end_session=True)

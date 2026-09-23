"""Application state shared between sensors, display, network, and web server for Pico 2 W."""

import time
from settings import config


MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2

# Data Logger State Constants
LOGGER_IDLE = 0
LOGGER_STAGING = 1
LOGGER_CONFIRM = 2
LOGGER_ACTIVE = 3


class AppState:
    def __init__(self):
        self.temperature_c = None
        self.humidity_pct = None
        self.light_pct = None
        self.requests_served = 0
        self.ip_address = None
        self.wifi_status = "config_error" if getattr(config, "WIFI_CONFIG_ERROR", None) else "disconnected"
        self.config_error = getattr(config, "WIFI_CONFIG_ERROR", None)
        self.read_errors = 0
        self.mode = MODE_SENSOR_DISPLAY
        self.pending_message = None
        self.alert_message = ""
        self.display_override_text = None
        self.last_caller = None
        self.known_nodes = {}
        self._start_time = time.time()

        # Data Logger State & Buffers
        self.logger_state = LOGGER_IDLE
        self.logging_active = False
        self.log_buffers = {}
        self.log_buffered_count = 0
        self.log_ntp_time_str = None
        self.log_error = None
        self.log_active_nodes = {}

    def buffer_reading(self, device_id, ts, temp, hum, light=None):
        """Appends reading to log_buffers[device_id] (max 13), and increments log_buffered_count."""
        if device_id not in self.log_buffers:
            self.log_buffers[device_id] = []
        buf = self.log_buffers[device_id]
        if len(buf) >= 13:
            buf.pop(0)
        else:
            self.log_buffered_count += 1
        buf.append({"ts": ts, "device_id": device_id, "temp": temp, "hum": hum, "light": light})

    def retain_unflushed(self, count_flushed_per_device=12):
        """Retains entries beyond the first count_flushed_per_device entries in log_buffers,

        updating log_buffered_count accordingly.
        """
        total = 0
        for dev_id, buf in list(self.log_buffers.items()):
            self.log_buffers[dev_id] = buf[count_flushed_per_device:]
            total += len(self.log_buffers[dev_id])
        self.log_buffered_count = total

    def clear_buffers(self):
        """Resets in-memory log buffers and counter."""
        self.log_buffers = {}
        self.log_buffered_count = 0

    def set_logger_error(self, msg):
        """Sets logger error message to be displayed."""
        self.log_error = str(msg)

    def clear_logger_error(self):
        """Clears logger error message."""
        self.log_error = None

    def enter_sensor_mode(self):
        """Transitions state to sensor display mode, clearing any alerts or pending messages."""
        self.mode = MODE_SENSOR_DISPLAY
        self.alert_message = ""
        self.display_override_text = None
        self.pending_message = None

    def enter_semi_sleep(self):
        """Transitions state to semi-sleep mode (display off, sensor sampling idle)."""
        self.mode = MODE_SEMI_SLEEP
        self.alert_message = ""
        self.display_override_text = None

    def enter_message_mode(self, text, caller=None):
        """Transitions state to message override mode, displaying text."""
        self.mode = MODE_MESSAGE
        self.alert_message = text
        self.display_override_text = text
        self.pending_message = None
        if caller is not None:
            self.last_caller = self.resolve_caller(caller)

    def set_pending_message(self, text, caller=None):
        """Stores a pending message for semi-sleep mode and updates caller."""
        self.pending_message = text
        if caller is not None:
            self.last_caller = self.resolve_caller(caller)

    def has_pending_message(self):
        """Returns True if there is a pending message awaiting display."""
        return self.pending_message is not None

    def record_request(self, client_ip=None):
        """Increments request counter and updates last_caller if client_ip provided."""
        self.requests_served += 1
        if client_ip:
            self.last_caller = self.resolve_caller(client_ip)

    def resolve_caller(self, ip):
        """Resolves IP to a known node ID, falling back to the last IPv4 octet."""
        if not ip:
            return None
        ip_str = str(ip)
        if ip_str in self.known_nodes:
            return self.known_nodes[ip_str]
        return ip_str.split(".")[-1]

    def register_node(self, ip, node_id):
        """Registers a known node ID for an IP and updates last_caller if matching fallback octet."""
        if not ip or not node_id:
            return
        ip_str = str(ip)
        node_id_str = str(node_id)
        self.known_nodes[ip_str] = node_id_str
        fallback_octet = ip_str.split(".")[-1]
        if self.last_caller == fallback_octet:
            self.last_caller = node_id_str

    def update_wifi(self, status, ip=None, config_error=None):
        """Updates WiFi connectivity state, assigned IP, and configuration errors."""
        self.wifi_status = status
        if ip is not None:
            self.ip_address = ip
        elif status in ("disconnected", "connecting", "config_error"):
            self.ip_address = None
        if config_error is not None:
            self.config_error = config_error

    def is_display_overridden(self):
        """Returns True if a display override alert is currently active."""
        return self.mode == MODE_MESSAGE

    def get_uptime_s(self):
        """Returns elapsed uptime in seconds."""
        try:
            return int(time.time() - self._start_time)
        except Exception:
            return 0

    def update_sensors(self, sensor_data):
        """Updates internal telemetry from a sensors.read_sensors() dict."""
        self.temperature_c = sensor_data.get("temperature_c", self.temperature_c)
        self.humidity_pct = sensor_data.get("humidity_pct", self.humidity_pct)
        self.light_pct = sensor_data.get("light_pct", self.light_pct)
        self.read_errors = sensor_data.get("read_errors", self.read_errors)

    def to_dict(self):
        """Returns the dictionary representation for JSON API responses."""
        return {
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "light_pct": self.light_pct,
            "requests_served": self.requests_served,
            "uptime_s": self.get_uptime_s(),
            "status": "ok",
        }

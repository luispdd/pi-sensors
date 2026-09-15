"""Application state shared between sensors, display, network, and web server."""

import time
import config


class AppState:
    def __init__(self):
        self.temperature_c = None
        self.humidity_pct = None
        self.requests_served = 0
        self.ip_address = None
        self.wifi_status = "config_error" if getattr(config, "WIFI_CONFIG_ERROR", None) else "disconnected"
        self.config_error = getattr(config, "WIFI_CONFIG_ERROR", None)
        self.read_errors = 0
        self.alert_active = False
        self.alert_message = ""
        self.display_override_text = None
        self.last_caller = None
        self.known_nodes = {}
        self._start_time = time.time()

    def set_display_override(self, text, caller=None):
        """Sets a persistent display override message until dismissed by button."""
        self.alert_active = True
        self.alert_message = text
        self.display_override_text = text
        if caller is not None:
            self.last_caller = caller

    def clear_display_override(self):
        """Clears the display override and deactivates the alert."""
        self.alert_active = False
        self.alert_message = ""
        self.display_override_text = None

    def is_display_overridden(self):
        """Returns True if a display override alert is currently active."""
        return self.alert_active

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
        self.read_errors = sensor_data.get("read_errors", self.read_errors)

    def to_dict(self):
        """Returns the dictionary representation for JSON API responses."""
        return {
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "requests_served": self.requests_served,
            "uptime_s": self.get_uptime_s(),
            "status": "ok",
        }

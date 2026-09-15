"""Application state shared between sensors, display, network, and web server."""

import time
import config


class AppState:
    def __init__(self):
        self.temperature_c = None
        self.humidity_pct = None
        self.light = "dark"
        self.light_detected = False
        self.requests_served = 0
        self.ip_address = None
        self.wifi_status = "config_error" if getattr(config, "WIFI_CONFIG_ERROR", None) else "disconnected"
        self.config_error = getattr(config, "WIFI_CONFIG_ERROR", None)
        self.read_errors = 0
        self.display_override_text = None
        self.display_override_expires_at = 0
        self._start_time = time.time()

    def set_display_override(self, text, duration_s=60):
        """Sets a temporary display override message for duration_s seconds."""
        self.display_override_text = text
        self.display_override_expires_at = time.time() + duration_s

    def is_display_overridden(self):
        """Returns True if a display override is currently active."""
        if self.display_override_text is not None:
            if time.time() < self.display_override_expires_at:
                return True
            self.display_override_text = None
            self.display_override_expires_at = 0
        return False

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
        self.light = sensor_data.get("light", self.light)
        self.light_detected = sensor_data.get("light_detected", self.light_detected)
        self.read_errors = sensor_data.get("read_errors", self.read_errors)

    def to_dict(self):
        """Returns the dictionary representation for JSON API responses."""
        return {
            "temperature_c": self.temperature_c,
            "humidity_pct": self.humidity_pct,
            "light": self.light,
            "light_detected": self.light_detected,
            "requests_served": self.requests_served,
            "uptime_s": self.get_uptime_s(),
            "status": "ok",
        }

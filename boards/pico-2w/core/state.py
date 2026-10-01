"""Modular, sensor-agnostic application state for Raspberry Pi Pico 2 W."""

import time
from settings import config

MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2
MODE_DETAILS = 3

# Data Logger State Constants
LOGGER_IDLE = 0
LOGGER_STAGING = 1
LOGGER_CONFIRM = 2
LOGGER_ACTIVE = 3


class AppState:
    """Sensor-agnostic application state managing telemetry, network, data logger, and operational modes."""

    def __init__(self):
        # Network & device state
        self.device_id = getattr(config, "DEVICE_ID", "pico-2w")
        self.device_type = getattr(config, "DEVICE_TYPE", "rp2350")
        self.ip_address = None
        self.wifi_status = "config_error" if getattr(config, "WIFI_CONFIG_ERROR", None) else "disconnected"
        self.config_error = getattr(config, "WIFI_CONFIG_ERROR", None)
        self.requests_served = 0
        self.ntp_synced = False
        self.timestamp = None
        self._start_time = time.time()
        self.read_errors = 0

        # Operational modes & alerts
        self.mode = MODE_SENSOR_DISPLAY
        self._previous_mode = MODE_SENSOR_DISPLAY
        self.pending_message = None
        self.alert_message = ""
        self.display_override_text = None
        self.last_caller = None
        self.known_nodes = {}

        # Data Logger State & Buffers
        self.logger_state = LOGGER_IDLE
        self.logging_active = False
        self.log_buffers = {}
        self.log_buffered_count = 0
        self.log_ntp_time_str = None
        self.log_date_str = None
        self.log_error = None
        self.log_active_nodes = {}

        # Sensor registry: metric_key -> {"val": ..., "unit": ..., "ts": ..., "errors": ...}
        self._metrics = {}
        self._registered_sensors = []

    # --- Sensor Registry Methods ---

    def register_sensor(self, sensor_driver):
        """Registers a duck-typed sensor driver into the application state."""
        if sensor_driver not in self._registered_sensors:
            self._registered_sensors.append(sensor_driver)

        metrics = getattr(sensor_driver, "metrics", [])
        for m in metrics:
            key = m.get("key")
            unit = m.get("unit", "")
            if key and key not in self._metrics:
                self._metrics[key] = {
                    "val": None,
                    "unit": unit,
                    "ts": None,
                    "errors": 0,
                    "min": None,
                    "max": None,
                }
        print(f"[state] Registered sensor '{getattr(sensor_driver, 'name', 'unknown')}' with metrics: {[m['key'] for m in metrics]}")

    def update_metric(self, key, val, timestamp=None):
        """Updates stored metric value, timestamp, and boot-scoped min/max."""
        if key in self._metrics:
            self._metrics[key]["val"] = val
            if timestamp is not None:
                self._metrics[key]["ts"] = timestamp
                self.timestamp = timestamp
            if val is not None:
                cur_min = self._metrics[key].get("min")
                cur_max = self._metrics[key].get("max")
                if cur_min is None or val < cur_min:
                    self._metrics[key]["min"] = val
                if cur_max is None or val > cur_max:
                    self._metrics[key]["max"] = val
        else:
            self._metrics[key] = {
                "val": val,
                "unit": "",
                "ts": timestamp,
                "errors": 0,
                "min": val,
                "max": val,
            }

    def get_metric(self, key):
        """Returns the metric dictionary for a given key."""
        return self._metrics.get(key)

    def get_metric_val(self, key):
        """Returns scalar value of metric or None."""
        m = self._metrics.get(key)
        return m.get("val") if m else None

    def get_all_metrics(self):
        """Returns dictionary of all registered metrics."""
        return self._metrics

    def read_registered_sensors(self, timestamp=None):
        """Performs a synchronous read across all registered sensor drivers."""
        for sensor in self._registered_sensors:
            try:
                res = sensor.read()
                if res is None:
                    self.read_errors += 1
                    for m in getattr(sensor, "metrics", []):
                        k = m.get("key")
                        if k in self._metrics:
                            self._metrics[k]["errors"] += 1
                elif isinstance(res, dict):
                    for k, v in res.items():
                        self.update_metric(k, v, timestamp=timestamp)
                elif isinstance(res, (int, float)):
                    metrics = getattr(sensor, "metrics", [])
                    if metrics:
                        self.update_metric(metrics[0]["key"], res, timestamp=timestamp)
            except Exception as err:
                self.read_errors += 1
                print(f"[state] Sensor read error: {err}")

    def to_senml(self):
        """Generates SenML-compliant JSON array of all active telemetry metrics."""
        senml_list = []
        for key, m in self._metrics.items():
            entry = {
                "n": key,
                "u": m.get("unit", ""),
                "v": m.get("val"),
            }
            if m.get("ts"):
                entry["t"] = m["ts"]
            elif self.timestamp:
                entry["t"] = self.timestamp
            senml_list.append(entry)
        return senml_list

    # --- Backwards Compatibility Properties & Methods ---

    @property
    def temperature_c(self):
        return self.get_metric_val("temperature")

    @temperature_c.setter
    def temperature_c(self, val):
        self.update_metric("temperature", val)

    @property
    def humidity_pct(self):
        return self.get_metric_val("humidity")

    @humidity_pct.setter
    def humidity_pct(self, val):
        self.update_metric("humidity", val)

    @property
    def light_pct(self):
        return self.get_metric_val("light")

    @light_pct.setter
    def light_pct(self, val):
        self.update_metric("light", val)

    @property
    def motion_pct(self):
        return self.get_metric_val("motion")

    @motion_pct.setter
    def motion_pct(self, val):
        self.update_metric("motion", val)

    def update_sensors(self, sensor_data):
        """Updates internal telemetry from a legacy sensors dict."""
        if "temperature_c" in sensor_data and sensor_data["temperature_c"] is not None:
            self.update_metric("temperature", sensor_data["temperature_c"])
        if "humidity_pct" in sensor_data and sensor_data["humidity_pct"] is not None:
            self.update_metric("humidity", sensor_data["humidity_pct"])
        if "light_pct" in sensor_data and sensor_data["light_pct"] is not None:
            self.update_metric("light", sensor_data["light_pct"])
        if "motion_pct" in sensor_data and sensor_data["motion_pct"] is not None:
            self.update_metric("motion", sensor_data["motion_pct"])
        if "read_errors" in sensor_data:
            self.read_errors = sensor_data["read_errors"]
        if "timestamp" in sensor_data and sensor_data["timestamp"] is not None:
            self.timestamp = sensor_data["timestamp"]
            for m in self._metrics.values():
                if m.get("val") is not None and m.get("ts") is None:
                    m["ts"] = self.timestamp

    # --- Data Logger Methods ---

    def buffer_reading(self, device_id, ts, temp, hum, light=None, motion=None):
        """Appends reading to log_buffers[device_id] (max 13), and increments log_buffered_count."""
        if device_id not in self.log_buffers:
            self.log_buffers[device_id] = []
        buf = self.log_buffers[device_id]
        if len(buf) >= 13:
            buf.pop(0)
        else:
            self.log_buffered_count += 1
        buf.append({"ts": ts, "device_id": device_id, "temp": temp, "hum": hum, "light": light, "motion": motion})

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

    # --- Mode Transitions ---

    def enter_sensor_mode(self):
        """Transitions state to sensor display mode, clearing any alerts or pending messages."""
        self.mode = MODE_SENSOR_DISPLAY
        self.alert_message = ""
        self.display_override_text = None
        self.pending_message = None

    def enter_semi_sleep(self):
        """Transitions state to semi-sleep mode (display off, sensor sampling idle)."""
        self._previous_mode = self.mode
        self.mode = MODE_SEMI_SLEEP
        self.alert_message = ""
        self.display_override_text = None

    def enter_details_mode(self):
        """Transitions state to details mode, clearing any alerts."""
        self.mode = MODE_DETAILS
        self.alert_message = ""
        self.display_override_text = None
        self.pending_message = None

    def restore_previous_mode(self):
        """Restores the mode saved before SEMI_SLEEP or MESSAGE_MODE entry."""
        self.mode = self._previous_mode
        self._previous_mode = MODE_SENSOR_DISPLAY
        self.alert_message = ""
        self.display_override_text = None
        self.pending_message = None

    def enter_message_mode(self, text, caller=None):
        """Transitions state to message override mode, displaying text."""
        self._previous_mode = self.mode
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
        return self.pending_message is not None

    def is_display_overridden(self):
        return self.mode == MODE_MESSAGE

    # --- Network & Telemetry Reporting ---

    def record_request(self, client_ip=None):
        self.requests_served += 1
        if client_ip:
            self.last_caller = self.resolve_caller(client_ip)

    def resolve_caller(self, ip):
        if not ip:
            return None
        ip_str = str(ip)
        if ip_str in self.known_nodes:
            return self.known_nodes[ip_str]
        return ip_str.split(".")[-1]

    def register_node(self, ip, node_id):
        if not ip or not node_id:
            return
        ip_str = str(ip)
        node_id_str = str(node_id)
        self.known_nodes[ip_str] = node_id_str
        fallback_octet = ip_str.split(".")[-1]
        if self.last_caller == fallback_octet:
            self.last_caller = node_id_str

    def update_wifi(self, status, ip=None, config_error=None):
        self.wifi_status = status
        if ip is not None:
            self.ip_address = ip
        elif status in ("disconnected", "connecting", "config_error"):
            self.ip_address = None
        if config_error is not None:
            self.config_error = config_error

    def get_uptime_s(self):
        try:
            return int(time.time() - self._start_time)
        except Exception:
            return 0

    def to_dict(self):
        """Dictionary representation for JSON API responses."""
        res = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp,
            "requests_served": self.requests_served,
            "uptime_s": self.get_uptime_s(),
            "mode": self.mode,
            "status": "ok",
        }
        # Dynamic sensor metrics
        for key, m in self._metrics.items():
            res[key] = m.get("val")
            res[f"{key}_unit"] = m.get("unit")

        # Compatibility fields
        if "temperature" in self._metrics:
            res["temperature_c"] = self._metrics["temperature"].get("val")
        if "humidity" in self._metrics:
            res["humidity_pct"] = self._metrics["humidity"].get("val")
        if "light" in self._metrics:
            res["light_pct"] = self._metrics["light"].get("val")

        return res

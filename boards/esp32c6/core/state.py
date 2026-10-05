"""Modular, sensor-agnostic application state for Waveshare ESP32-C6-Zero."""

import time
from settings import config

MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2
MODE_DETAILS = 3


class AppState:
    """Sensor-agnostic application state managing telemetry, network, and operational modes."""

    def __init__(self):
        # Network & device state
        self.device_id = getattr(config, "DEVICE_ID", "esp32c6")
        self.device_type = getattr(config, "DEVICE_TYPE", "esp32c6")
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

        # Sensor registry: metric_key -> {"val": ..., "unit": ..., "ts": ..., "errors": ...}
        self._metrics = {}
        self._registered_sensors = []

    # --- Sensor Registry Methods ---

    def register_sensor(self, sensor_driver):
        """Registers a duck-typed sensor driver into the application state."""
        if sensor_driver not in self._registered_sensors:
            self._registered_sensors.append(sensor_driver)
        if hasattr(sensor_driver, "app_state") and getattr(sensor_driver, "app_state", None) is None:
            sensor_driver.app_state = self

        # Inspect metrics exposed by sensor
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

    def set_time(self, epoch_seconds=None, synced=True):
        """Sets/anchors the internal timestamp baseline."""
        if epoch_seconds is None:
            try:
                epoch_seconds = time.time()
            except Exception:
                epoch_seconds = None
        self._current_epoch = epoch_seconds
        if epoch_seconds is not None:
            from services.ntp_service import format_iso_timestamp
            self.timestamp = format_iso_timestamp(self._current_epoch)
        if synced:
            self.ntp_synced = True

    def tick_timestamp(self, seconds=1):
        """Advances internal timestamp by specified elapsed seconds."""
        if self._current_epoch is None:
            try:
                self._current_epoch = time.time()
            except Exception:
                self._current_epoch = 0
        self._current_epoch += seconds
        from services.ntp_service import format_iso_timestamp
        self.timestamp = format_iso_timestamp(self._current_epoch)

    def update_metric(self, key, val, timestamp=None):
        """Updates stored metric value, timestamp, and boot-scoped min/max."""
        ts = timestamp if timestamp is not None else self.timestamp
        if key in self._metrics:
            self._metrics[key]["val"] = val
            if ts is not None:
                self._metrics[key]["ts"] = ts
                self.timestamp = ts
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
                "ts": ts,
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
        ts = timestamp if timestamp is not None else self.timestamp
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
                        self.update_metric(k, v, timestamp=ts)
                elif isinstance(res, (int, float)):
                    metrics = getattr(sensor, "metrics", [])
                    if metrics:
                        self.update_metric(metrics[0]["key"], res, timestamp=ts)
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

    def get_period_motion_and_reset(self):
        """Retrieves and resets the registered PIR sensor's period accumulator.

        Falls back to standard motion metric if unaccumulated or no PIR sensor is registered.
        """
        for sensor in self._registered_sensors:
            if hasattr(sensor, "get_period_motion"):
                try:
                    return sensor.get_period_motion(reset=True)
                except Exception as e:
                    print(f"[state] Error querying PIR period motion: {e}")
        return self.get_metric_val("motion")


    # --- Backwards Compatibility Properties ---

    @property
    def temperature_c(self):
        return self.get_metric_val("temperature")

    @property
    def humidity_pct(self):
        return self.get_metric_val("humidity")

    # --- Mode Transitions ---

    def enter_sensor_mode(self):
        """Transitions state to sensor display mode, clearing alerts."""
        self.mode = MODE_SENSOR_DISPLAY
        self.alert_message = ""
        self.display_override_text = None
        self.pending_message = None

    def enter_semi_sleep(self):
        """Transitions state to semi-sleep mode (display off, periodic polling suspended)."""
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
        """Transitions state to message display mode."""
        self._previous_mode = self.mode
        self.mode = MODE_MESSAGE
        self.alert_message = text
        self.display_override_text = text
        self.pending_message = None
        if caller is not None:
            self.last_caller = self.resolve_caller(caller)

    def set_pending_message(self, text, caller=None):
        """Stores a pending message for semi-sleep mode."""
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
        """Dictionary representation for JSON API /info responses."""
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
        # Include dynamic sensor metrics
        for key, m in self._metrics.items():
            res[key] = m.get("val")
            res[f"{key}_unit"] = m.get("unit")

        # Compatibility fields
        if "temperature" in self._metrics:
            res["temperature_c"] = self._metrics["temperature"].get("val")
        if "humidity" in self._metrics:
            res["humidity_pct"] = self._metrics["humidity"].get("val")

        return res

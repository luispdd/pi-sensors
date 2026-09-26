"""Unit tests for Pico 1 W modular sensor migration, CoAP endpoints, and telemetry schema verification."""

import json
import os
import sys
import unittest

PICO1W_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PICO1W_LIB_DIR = os.path.abspath(os.path.join(PICO1W_DIR, "lib"))
if PICO1W_LIB_DIR not in sys.path:
    sys.path.insert(0, PICO1W_LIB_DIR)
if PICO1W_DIR not in sys.path:
    sys.path.insert(0, PICO1W_DIR)

from core.state import AppState, MODE_SENSOR_DISPLAY, MODE_SEMI_SLEEP, MODE_MESSAGE
from hardware.sensors.dht22 import DHT22Sensor
from hardware.ui import UIController
from services.coap_server import CoapServer
from microcoapy import COAP_METHOD, COAP_RESPONSE_CODE, COAP_CONTENT_FORMAT


class DummyPacket:
    """Mock CoAP packet received by server callbacks."""
    def __init__(self, method=COAP_METHOD.COAP_GET, messageid=2001, token=b"\x01\x02", payload=b""):
        self.method = method
        self.messageid = messageid
        self.token = token
        self.payload = payload


class MockSensorDriver:
    """Mock modular sensor driver conforming to the duck-typed sensor protocol."""
    def __init__(self, name="dht22", metrics=None):
        self.name = name
        self.metrics = metrics or [
            {"key": "temperature", "unit": "Cel"},
            {"key": "humidity", "unit": "%RH"},
        ]
        self.read_count = 0
        self.temp_val = 22.4
        self.hum_val = 48.0

    def init(self):
        pass

    def read(self):
        self.read_count += 1
        return {"temperature": self.temp_val, "humidity": self.hum_val}


class TestPico1wModularMigration(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()
        self.app_state.device_id = "pico-1w"
        self.app_state.device_type = "rp2040"
        self.sensor_driver = MockSensorDriver()
        self.app_state.register_sensor(self.sensor_driver)

        # Initial reading
        self.app_state.read_registered_sensors(timestamp="2026-09-26T15:00:00")

        self.server = CoapServer(self.app_state, port=5683)
        self.sent_responses = []

        def mock_send_response(sender_ip, sender_port, messageid, payload, code, content_format, token, request_packet=None):
            self.sent_responses.append({
                "sender_ip": sender_ip,
                "sender_port": sender_port,
                "messageid": messageid,
                "payload": payload,
                "code": code,
                "content_format": content_format,
                "token": token,
            })

        self.server.coap.sendResponse = mock_send_response

    def test_sensors_endpoint_schema_matches_previous(self):
        """Verify GET /sensors returns 2.05 Content with valid SenML matching previous schema."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=201, token=b"\x12\x34")
        self.server._handle_sensors_collection(req, "192.168.1.100", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[0]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        self.assertEqual(resp["content_format"], COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON)

        senml = json.loads(resp["payload"])
        self.assertIsInstance(senml, list)
        self.assertEqual(len(senml), 2)

        temp_entry = next(item for item in senml if item["n"] == "temperature")
        hum_entry = next(item for item in senml if item["n"] == "humidity")

        # Telemetry schema verification
        self.assertEqual(temp_entry["v"], 22.4)
        self.assertEqual(temp_entry["u"], "Cel")
        self.assertEqual(temp_entry["t"], "2026-09-26T15:00:00")

        self.assertEqual(hum_entry["v"], 48.0)
        self.assertEqual(hum_entry["u"], "%RH")  # Matches previous pico-1w schema
        self.assertEqual(hum_entry["t"], "2026-09-26T15:00:00")

    def test_info_endpoint_contains_backward_compatible_fields(self):
        """Verify GET /info returns device info with temperature_c and humidity_pct backwards-compatible fields."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=202)
        self.server._handle_info(req, "192.168.1.100", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        info = json.loads(self.sent_responses[0]["payload"])
        self.assertEqual(info["device_id"], "pico-1w")
        self.assertEqual(info["device_type"], "rp2040")
        self.assertEqual(info["temperature_c"], 22.4)
        self.assertEqual(info["humidity_pct"], 48.0)
        self.assertEqual(info["status"], "ok")

        # Verify property access on AppState
        self.assertEqual(self.app_state.temperature_c, 22.4)
        self.assertEqual(self.app_state.humidity_pct, 48.0)

    def test_single_metric_endpoints(self):
        """Verify GET /sensors/temperature and /sensors/humidity."""
        req_t = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=203)
        self.server._handle_single_metric(req_t, "192.168.1.100", 5683, "temperature")
        t_data = json.loads(self.sent_responses[-1]["payload"])
        self.assertEqual(t_data["n"], "temperature")
        self.assertEqual(t_data["v"], 22.4)
        self.assertEqual(t_data["u"], "Cel")

        req_h = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=204)
        self.server._handle_single_metric(req_h, "192.168.1.100", 5683, "humidity")
        h_data = json.loads(self.sent_responses[-1]["payload"])
        self.assertEqual(h_data["n"], "humidity")
        self.assertEqual(h_data["v"], 48.0)
        self.assertEqual(h_data["u"], "%RH")

    def test_well_known_core_links(self):
        """Verify .well-known/core links match spec."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=205)
        self.server._handle_well_known_core(req, "192.168.1.100", 5683)
        links = self.sent_responses[0]["payload"]
        self.assertIn('</sensors>;rt="sensor-collection"', links)
        self.assertIn('</sensors/temperature>;rt="temperature"', links)
        self.assertIn('</sensors/humidity>;rt="humidity"', links)
        self.assertIn('</id>;rt="core.d"', links)
        self.assertIn('</display>;rt="display"', links)

    def test_semi_sleep_on_demand_sampling(self):
        """Verify semi-sleep triggers on-demand read."""
        self.app_state.mode = MODE_SEMI_SLEEP
        initial_reads = self.sensor_driver.read_count
        self.sensor_driver.temp_val = 25.1
        self.sensor_driver.hum_val = 52.3

        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=206)
        self.server._handle_sensors_collection(req, "192.168.1.100", 5683)

        self.assertGreater(self.sensor_driver.read_count, initial_reads)
        senml = json.loads(self.sent_responses[-1]["payload"])
        val_map = {item["n"]: item["v"] for item in senml}
        self.assertEqual(val_map["temperature"], 25.1)
        self.assertEqual(val_map["humidity"], 52.3)

    def test_ui_controller_interface(self):
        """Verify UIController initializes and handles button transitions."""
        ui = UIController(self.app_state)
        self.assertTrue(ui.display_on)

        # Short press from SENSOR_DISPLAY -> SEMI_SLEEP
        ui.handle_button("short", self.app_state)
        self.assertEqual(self.app_state.mode, MODE_SEMI_SLEEP)
        self.assertFalse(ui.display_on)

        # Short press from SEMI_SLEEP -> SENSOR_DISPLAY
        ui.handle_button("short", self.app_state)
        self.assertEqual(self.app_state.mode, MODE_SENSOR_DISPLAY)
        self.assertTrue(ui.display_on)

        # Set pending message, then semi-sleep -> message mode
        self.app_state.enter_semi_sleep()
        self.app_state.set_pending_message("Test message")
        ui.handle_button("short", self.app_state)
        self.assertEqual(self.app_state.mode, MODE_MESSAGE)
        self.assertTrue(ui.display_on)

        # Message mode -> sensor display mode
        ui.handle_button("short", self.app_state)
        self.assertEqual(self.app_state.mode, MODE_SENSOR_DISPLAY)


if __name__ == "__main__":
    unittest.main()

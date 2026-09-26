"""Unit tests for ESP32-C6 CoAP server endpoints: /sensors, /info, dynamic metrics, and discovery."""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock

# Configure import path for boards/esp32c6 and lib
ESP32C6_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PICO1W_LIB_DIR = os.path.abspath(os.path.join(ESP32C6_DIR, "..", "pico-1w", "lib"))
if PICO1W_LIB_DIR not in sys.path:
    sys.path.insert(0, PICO1W_LIB_DIR)
if ESP32C6_DIR not in sys.path:
    sys.path.insert(0, ESP32C6_DIR)

from core.state import AppState, MODE_SENSOR_DISPLAY, MODE_SEMI_SLEEP
from services.coap_server import CoapServer
from microcoapy import COAP_METHOD, COAP_RESPONSE_CODE, COAP_CONTENT_FORMAT


class DummyPacket:
    """Mock CoAP packet received by server callbacks."""
    def __init__(self, method=COAP_METHOD.COAP_GET, messageid=1001, token=b"\x01\x02", payload=b""):
        self.method = method
        self.messageid = messageid
        self.token = token
        self.payload = payload


class MockSensorDriver:
    """Mock modular sensor driver conforming to the duck-typed sensor protocol."""
    def __init__(self, name="mock_dht22", metrics=None):
        self.name = name
        self.metrics = metrics or [
            {"key": "temperature", "unit": "Cel", "interval_ms": 2000},
            {"key": "humidity", "unit": "%", "interval_ms": 2000},
        ]
        self.read_count = 0
        self.temp_val = 24.5
        self.hum_val = 55.0

    def init(self):
        pass

    def read(self):
        self.read_count += 1
        return {"temperature": self.temp_val, "humidity": self.hum_val}


class TestEsp32C6CoapEndpoints(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()
        self.app_state.device_id = "esp32c6-test"
        self.app_state.device_type = "esp32c6"
        self.sensor_driver = MockSensorDriver()
        self.app_state.register_sensor(self.sensor_driver)
        
        # Populate initial readings
        self.app_state.read_registered_sensors(timestamp="2026-09-26T14:00:00")
        
        self.server = CoapServer(self.app_state, port=5683)
        # Mock coap.sendResponse to capture outgoing response packets
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

    def test_sensors_endpoint_senml_format(self):
        """Verify GET /sensors returns 2.05 Content with valid SenML formatting."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=101, token=b"\x11\x22")
        self.server._handle_sensors_collection(req, "192.168.1.50", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[0]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        self.assertEqual(resp["content_format"], COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON)
        self.assertEqual(resp["messageid"], 101)
        self.assertEqual(resp["token"], b"\x11\x22")

        senml = json.loads(resp["payload"])
        self.assertIsInstance(senml, list)
        self.assertEqual(len(senml), 2)

        keys = {item["n"] for item in senml}
        self.assertEqual(keys, {"temperature", "humidity"})

        for item in senml:
            self.assertIn("n", item)
            self.assertIn("u", item)
            self.assertIn("v", item)
            self.assertIn("t", item)
            self.assertEqual(item["t"], "2026-09-26T14:00:00")
            if item["n"] == "temperature":
                self.assertEqual(item["v"], 24.5)
                self.assertEqual(item["u"], "Cel")
            elif item["n"] == "humidity":
                self.assertEqual(item["v"], 55.0)
                self.assertEqual(item["u"], "%")

    def test_info_endpoint(self):
        """Verify GET /info returns 2.05 Content with device metadata and status."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=102, token=b"\x33\x44")
        self.server._handle_info(req, "192.168.1.50", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[0]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        self.assertEqual(resp["content_format"], COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON)
        self.assertEqual(resp["messageid"], 102)

        info = json.loads(resp["payload"])
        self.assertIsInstance(info, dict)
        self.assertEqual(info["device_id"], "esp32c6-test")
        self.assertEqual(info["device_type"], "esp32c6")
        self.assertEqual(info["temperature"], 24.5)
        self.assertEqual(info["humidity"], 55.0)
        self.assertEqual(info["status"], "ok")
        self.assertEqual(info["requests_served"], 1)

    def test_dynamic_single_metric_endpoints(self):
        """Verify dynamic endpoints /sensors/temperature and /sensors/humidity return valid SenML items."""
        req_temp = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=103)
        self.server._handle_single_metric(req_temp, "192.168.1.50", 5683, "temperature")

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[-1]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        temp_data = json.loads(resp["payload"])
        self.assertEqual(temp_data["n"], "temperature")
        self.assertEqual(temp_data["v"], 24.5)
        self.assertEqual(temp_data["u"], "Cel")

        # Unknown metric
        req_unknown = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=104)
        self.server._handle_single_metric(req_unknown, "192.168.1.50", 5683, "unknown_metric")
        resp_unknown = self.sent_responses[-1]
        self.assertEqual(resp_unknown["code"], COAP_RESPONSE_CODE.COAP_NOT_FOUND)

    def test_well_known_core_advertises_sensors_and_info(self):
        """Verify GET .well-known/core returns RFC 6690 links advertising /sensors and /info."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=105)
        self.server._handle_well_known_core(req, "192.168.1.50", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[0]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        self.assertEqual(resp["content_format"], COAP_CONTENT_FORMAT.COAP_APPLICATION_LINK_FORMAT)

        link_text = resp["payload"]
        self.assertIn('</sensors>;rt="sensor-collection"', link_text)
        self.assertIn('</info>;rt="info"', link_text)
        self.assertIn('</sensors/temperature>;rt="temperature"', link_text)
        self.assertIn('</sensors/humidity>;rt="humidity"', link_text)
        self.assertIn('</id>;rt="core.d"', link_text)

    def test_method_not_allowed(self):
        """Verify invalid methods return 4.05 Method Not Allowed."""
        post_req = DummyPacket(method=COAP_METHOD.COAP_POST, messageid=106)
        self.server._handle_sensors_collection(post_req, "192.168.1.50", 5683)
        method_not_allowed_code = getattr(COAP_RESPONSE_CODE, "COAP_METHOD_NOT_ALLOWED", getattr(COAP_RESPONSE_CODE, "COAP_METHOD_NOT_ALLOWD", 133))
        self.assertEqual(self.sent_responses[-1]["code"], method_not_allowed_code)

        put_req = DummyPacket(method=COAP_METHOD.COAP_PUT, messageid=107)
        self.server._handle_info(put_req, "192.168.1.50", 5683)
        self.assertEqual(self.sent_responses[-1]["code"], method_not_allowed_code)

    def test_semi_sleep_on_demand_read(self):
        """Verify that when in MODE_SEMI_SLEEP, GET /sensors or /info triggers an on-demand synchronous read."""
        self.app_state.mode = MODE_SEMI_SLEEP
        initial_reads = self.sensor_driver.read_count

        # Simulate updated hardware values on the sensor
        self.sensor_driver.temp_val = 26.8
        self.sensor_driver.hum_val = 48.2

        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=108)
        self.server._handle_sensors_collection(req, "192.168.1.50", 5683)

        # Ensure sensor driver read() was called on-demand
        self.assertGreater(self.sensor_driver.read_count, initial_reads)

        # Check payload has fresh values
        resp = self.sent_responses[-1]
        senml = json.loads(resp["payload"])
        val_map = {item["n"]: item["v"] for item in senml}
        self.assertEqual(val_map["temperature"], 26.8)
        self.assertEqual(val_map["humidity"], 48.2)


if __name__ == "__main__":
    unittest.main()

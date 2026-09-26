"""Unit tests for Pico 2 W modular sensor migration, CoAP endpoints, and telemetry schema verification."""

import json
import os
import sys
import unittest

PICO2W_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PICO2W_LIB_DIR = os.path.abspath(os.path.join(PICO2W_DIR, "lib"))
if PICO2W_LIB_DIR not in sys.path:
    sys.path.insert(0, PICO2W_LIB_DIR)
if PICO2W_DIR not in sys.path:
    sys.path.insert(0, PICO2W_DIR)

from core.state import AppState, MODE_SENSOR_DISPLAY, MODE_SEMI_SLEEP, MODE_MESSAGE
from hardware.ui import UIController
from services.coap_server import CoapServer
from microcoapy import COAP_METHOD, COAP_RESPONSE_CODE, COAP_CONTENT_FORMAT


class DummyPacket:
    """Mock CoAP packet received by server callbacks."""
    def __init__(self, method=COAP_METHOD.COAP_GET, messageid=3001, token=b"\x03\x04", payload=b""):
        self.method = method
        self.messageid = messageid
        self.token = token
        self.payload = payload


class MockDHT22Driver:
    def __init__(self):
        self.name = "dht22"
        self.metrics = [
            {"key": "temperature", "unit": "Cel"},
            {"key": "humidity", "unit": "%RH"},
        ]
        self.read_count = 0
        self.temp_val = 21.5
        self.hum_val = 52.0

    def init(self):
        pass

    def read(self):
        self.read_count += 1
        return {"temperature": self.temp_val, "humidity": self.hum_val}


class MockLightDriver:
    def __init__(self):
        self.name = "light"
        self.metrics = [
            {"key": "light", "unit": "%"},
        ]
        self.read_count = 0
        self.light_val = 78.5

    def init(self):
        pass

    def read(self):
        self.read_count += 1
        return {"light": self.light_val}


class TestPico2wModularMigration(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()
        self.app_state.device_id = "pico-2w"
        self.app_state.device_type = "rp2350"
        self.dht_driver = MockDHT22Driver()
        self.light_driver = MockLightDriver()
        self.app_state.register_sensor(self.dht_driver)
        self.app_state.register_sensor(self.light_driver)

        # Initial reading
        self.app_state.read_registered_sensors(timestamp="2026-09-26T16:00:00")

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
        """Verify GET /sensors returns 2.05 Content with valid SenML including light."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=301, token=b"\x55\x66")
        self.server._handle_sensors_collection(req, "192.168.1.101", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        resp = self.sent_responses[0]
        self.assertEqual(resp["code"], COAP_RESPONSE_CODE.COAP_CONTENT)
        self.assertEqual(resp["content_format"], COAP_CONTENT_FORMAT.COAP_APPLICATION_JSON)

        senml = json.loads(resp["payload"])
        self.assertIsInstance(senml, list)
        self.assertEqual(len(senml), 3)

        temp_entry = next(item for item in senml if item["n"] == "temperature")
        hum_entry = next(item for item in senml if item["n"] == "humidity")
        light_entry = next(item for item in senml if item["n"] == "light")

        self.assertEqual(temp_entry["v"], 21.5)
        self.assertEqual(temp_entry["u"], "Cel")
        self.assertEqual(hum_entry["v"], 52.0)
        self.assertEqual(hum_entry["u"], "%RH")
        self.assertEqual(light_entry["v"], 78.5)
        self.assertEqual(light_entry["u"], "%")

    def test_info_endpoint_contains_backward_compatible_fields(self):
        """Verify GET /info returns device info with light_pct."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=302)
        self.server._handle_info(req, "192.168.1.101", 5683)

        self.assertEqual(len(self.sent_responses), 1)
        info = json.loads(self.sent_responses[0]["payload"])
        self.assertEqual(info["device_id"], "pico-2w")
        self.assertEqual(info["device_type"], "rp2350")
        self.assertEqual(info["temperature_c"], 21.5)
        self.assertEqual(info["humidity_pct"], 52.0)
        self.assertEqual(info["light_pct"], 78.5)
        self.assertEqual(info["status"], "ok")

        # Verify property access on AppState
        self.assertEqual(self.app_state.temperature_c, 21.5)
        self.assertEqual(self.app_state.humidity_pct, 52.0)
        self.assertEqual(self.app_state.light_pct, 78.5)

    def test_single_metric_endpoints(self):
        """Verify GET /sensors/temperature, /sensors/humidity, and /sensors/light."""
        req_l = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=303)
        self.server._handle_single_metric(req_l, "192.168.1.101", 5683, "light")
        l_data = json.loads(self.sent_responses[-1]["payload"])
        self.assertEqual(l_data["n"], "light")
        self.assertEqual(l_data["v"], 78.5)
        self.assertEqual(l_data["u"], "%")

    def test_well_known_core_links(self):
        """Verify .well-known/core links match spec including light, logger, and log."""
        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=304)
        self.server._handle_well_known_core(req, "192.168.1.101", 5683)
        links = self.sent_responses[0]["payload"]
        self.assertIn('</sensors>;rt="sensor-collection"', links)
        self.assertIn('</sensors/temperature>;rt="temperature"', links)
        self.assertIn('</sensors/humidity>;rt="humidity"', links)
        self.assertIn('</sensors/light>;rt="light"', links)
        self.assertIn('</id>;rt="core.d"', links)
        self.assertIn('</display>;rt="display"', links)
        self.assertIn('</logger>;rt="data-logger"', links)
        self.assertIn('</log>;rt="data-sync"', links)

    def test_semi_sleep_on_demand_sampling(self):
        """Verify semi-sleep triggers on-demand read across registered sensors."""
        self.app_state.mode = MODE_SEMI_SLEEP
        initial_dht_reads = self.dht_driver.read_count
        initial_light_reads = self.light_driver.read_count

        self.dht_driver.temp_val = 23.1
        self.light_driver.light_val = 85.0

        req = DummyPacket(method=COAP_METHOD.COAP_GET, messageid=305)
        self.server._handle_sensors_collection(req, "192.168.1.101", 5683)

        self.assertGreater(self.dht_driver.read_count, initial_dht_reads)
        self.assertGreater(self.light_driver.read_count, initial_light_reads)

        senml = json.loads(self.sent_responses[-1]["payload"])
        val_map = {item["n"]: item["v"] for item in senml}
        self.assertEqual(val_map["temperature"], 23.1)
        self.assertEqual(val_map["light"], 85.0)


if __name__ == "__main__":
    unittest.main()

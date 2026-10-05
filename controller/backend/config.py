"""Configuration for IoTMesh Controller Backend."""

import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "controller.db"
DB_PATH = Path(os.getenv("CONTROLLER_DB_PATH", str(DEFAULT_DB_PATH)))

# Identity
DEVICE_ID = os.getenv("CONTROLLER_DEVICE_ID", "controller-01")
DEVICE_TYPE = os.getenv("CONTROLLER_DEVICE_TYPE", "laptop")  # or "unoq-linux"

# HTTP API Service
HTTP_HOST = os.getenv("CONTROLLER_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("CONTROLLER_HTTP_PORT", "8000"))

# CoAP Configuration
COAP_PORT = int(os.getenv("CONTROLLER_COAP_PORT", "5683"))
COAP_BROADCAST_ADDR = os.getenv("CONTROLLER_COAP_BROADCAST_ADDR", "192.168.1.255")

# Poller Cadence & Synchronization
POLL_INTERVAL_S = int(os.getenv("CONTROLLER_POLL_INTERVAL_S", "300"))
LOG_PAGE_SIZE = int(os.getenv("CONTROLLER_LOG_PAGE_SIZE", "5"))
COAP_TIMEOUT_S = float(os.getenv("CONTROLLER_COAP_TIMEOUT_S", "2.0"))
COAP_MAX_RETRIES = int(os.getenv("CONTROLLER_COAP_MAX_RETRIES", "2"))

import socket

# MQTT Configuration
MQTT_HOST = os.getenv("CONTROLLER_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("CONTROLLER_MQTT_PORT", "1883"))
MQTT_TOPIC_LIVE = os.getenv("CONTROLLER_MQTT_TOPIC_LIVE", "iotmesh/+/live")
CONTROLLER_BROKER_HOST = os.getenv("CONTROLLER_BROKER_HOST")


def get_broker_address() -> str:
    """Returns <ip>:<port> for nodes to connect to this controller's Mosquitto broker."""
    host = CONTROLLER_BROKER_HOST
    if not host or host in ("0.0.0.0", ""):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            host = s.getsockname()[0]
            s.close()
        except Exception:
            host = "127.0.0.1"
    return f"{host}:{MQTT_PORT}"

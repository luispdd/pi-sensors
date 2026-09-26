"""Modular sensor package for Waveshare ESP32-C6-Zero."""

from settings import config
from hardware.sensors.dht22 import DHT22Sensor, create_sensor as create_dht22
from hardware.sensors.pir import PIRSensor, create_sensor as create_pir

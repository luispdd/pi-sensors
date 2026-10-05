# ESP32-C6 Environmental Sensor Node (`esp32c6`)

This directory contains the firmware for the `esp32c6` board (Waveshare ESP32-C6-Zero).
The board drives an SSD1306 OLED display, AM312 PIR motion sensor, MAX4466 microphone, and DHT22 temperature/humidity sensor, communicating via the `iotmesh` protocol over CoAP and HTTP.

## Structure

* `main.py` - Entry point and async orchestrator.
* `settings/` - `config.py` and `secrets.py` template.
* `services/` - `network_manager.py`, `webserver.py`, `coap_server.py`, `ntp_service.py`, `telemetry.py`.
* `hardware/` - Sensors and OLED UI controllers.
* `core/` - `state.py` application state management.
* `lib/` - Libraries: `ssd1306.py`, `microcoapy/`, `umqtt/`.
* `test/` - Unit tests for sensor and service validation.

## Dependencies & Installation

To install `umqtt.simple` via `mip`:

```bash
# Using mpremote CLI:
mpremote mip install umqtt.simple
```

Or from the MicroPython REPL:

```python
import mip
mip.install("umqtt.simple")
```

## Deployment

Copy the entire contents of `boards/esp32c6/` to the root of the ESP32-C6 filesystem:

```bash
# Example deployment using mpremote:
mpremote fs cp -r boards/esp32c6/* :
```

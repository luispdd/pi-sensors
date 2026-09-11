## Why

The Raspberry Pi Pico W enables low-power embedded environmental monitoring and local telemetry. A standalone environmental monitor is needed to read ambient temperature, humidity, and light conditions, display real-time readouts locally on an OLED display, and expose an HTTP JSON endpoint on the local WiFi network for home automation or data ingestion.

## What Changes

- Implement hardware drivers and sampling loops for the DHT22 sensor (GP15) and LM393 light sensor (GP14).
- Implement an I2C OLED display driver (SSD1306 on GP0/GP1) to show live sensor metrics, network connection status, and local IP address.
- Implement WiFi connection management with automatic reconnect logic for Pico W's CYW43439 module.
- Implement an asynchronous lightweight HTTP server exposing a `GET /sensors` endpoint returning structured JSON payload with sensor readings.
- Provide configuration management (`config.py` / `config.json`) for WiFi credentials, sensor polling intervals, and pin mappings.

## Capabilities

### New Capabilities
- `sensor-monitoring`: Periodic reading and validation of temperature, relative humidity (DHT22), and ambient light state (LM393).
- `display-service`: SSD1306 128x64/128x32 OLED rendering of sensor metrics, network state, and device IP.
- `wifi-http-service`: WiFi network attachment and local HTTP endpoint (`/sensors`) serving JSON formatted telemetry.

### Modified Capabilities
*(None - initial greenfield project)*

## Impact

- Target runtime: MicroPython on Raspberry Pi Pico W.
- Pin allocations:
  - 3V3 (Pin 36) & GND (Pin 38) for power rails.
  - I2C0: SDA on GP0 (Pin 1), SCL on GP1 (Pin 2) for SSD1306 OLED.
  - GPIO: GP15 (Pin 20) for DHT22 DAT.
  - GPIO: GP14 (Pin 19) for LM393 DO.
- External dependencies / libraries: MicroPython `ssd1306.py`, built-in `dht`, `machine`, `network`, `uasyncio`.

## 1. Project Foundation and Driver Setup

- [x] 1.1 Create `src/config.py` loading WiFi credentials from git-ignored `secrets.py` (with `src/secrets.py.example`), pin mappings, and polling intervals. Verify structure and syntax.
- [x] 1.2 Add the `stlehmann/micropython-ssd1306` driver in `src/lib/ssd1306.py` for I2C OLED control. Verify driver syntax and imports.

## 2. Sensor and Display Drivers

- [x] 2.1 Implement `src/sensors.py` providing `read_sensors()` for DHT22 temperature/humidity and LM393 digital light state with exception handling for read timeouts. Verify syntax and logic.
- [x] 2.2 Implement `src/display.py` with `OLEDDisplay` class importing driver from `lib/` to render telemetry, remote URL, hit count, and WiFi configuration errors when credentials are missing. Verify screen layout and coordinate bounds.

## 3. Networking and HTTP Server

- [x] 3.1 Implement `src/network_manager.py` to connect to WiFi using `network.WLAN`, validate credentials from `secrets.py`, and handle non-blocking reconnects. Verify connection workflow.
- [x] 3.2 Implement `src/webserver.py` using `uasyncio.start_server` to serve `GET /sensors` returning JSON formatted sensor readings with `requests_served` counter increment. Verify HTTP request parsing and response headers.

## 4. System Orchestration and Documentation

- [x] 4.1 Implement `src/main.py` launching concurrent `uasyncio` coroutines for sensor reading, OLED screen refresh with request stats, WiFi keepalive, and the HTTP server. Verify module integration.
- [x] 4.2 Create `README.md` documenting the wiring diagram, installation guide (using Thonny or mpremote), configuration instructions, OLED display layout, and test curl examples.

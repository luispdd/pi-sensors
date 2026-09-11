## 1. Project Foundation and Driver Setup

- [ ] 1.1 Create `config.py` defining WiFi credentials (`WIFI_SSID`, `WIFI_PASSWORD`), pin mappings (DHT22 on GP15, LM393 on GP14, I2C0 SDA on GP0, SCL on GP1), and polling interval. Verify structure and syntax.
- [ ] 1.2 Add the standard MicroPython `ssd1306.py` driver for I2C OLED control. Verify driver syntax and imports.

## 2. Sensor and Display Drivers

- [ ] 2.1 Implement `sensors.py` providing `read_sensors()` for DHT22 temperature/humidity and LM393 digital light state with exception handling for read timeouts. Verify syntax and logic.
- [ ] 2.2 Implement `display.py` with `OLEDDisplay` class to render temperature, humidity, light condition, and current IP address or WiFi connection status. Verify display layout calculations.

## 3. Networking and HTTP Server

- [ ] 3.1 Implement `network_manager.py` to connect to WiFi using `network.WLAN`, handle IP discovery, and support non-blocking reconnects. Verify connection workflow.
- [ ] 3.2 Implement `webserver.py` using `uasyncio.start_server` to serve `GET /sensors` returning JSON formatted sensor readings. Verify HTTP request parsing and response headers.

## 4. System Orchestration and Documentation

- [ ] 4.1 Implement `main.py` launching concurrent `uasyncio` coroutines for sensor reading, OLED screen refresh, WiFi keepalive, and the HTTP server. Verify module integration.
- [ ] 4.2 Create `README.md` documenting the wiring diagram, installation guide (using Thonny or mpremote), configuration instructions, and test curl examples.

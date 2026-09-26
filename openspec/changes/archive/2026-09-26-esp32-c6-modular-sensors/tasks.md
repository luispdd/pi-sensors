## 1. ESP32-C6-Zero Development with Modular Sensor Framework

- [x] 1.1 Create `boards/esp32c6/` directory structure and settings configuration for pinout (SDA on GPIO 0, SCL on GPIO 1, DHT22 on GPIO 2, Button on GPIO 3, WS2812 on GPIO 8) and verify config parses correctly
- [x] 1.2 Implement the modular DHT22 sensor driver in `boards/esp32c6/hardware/sensors/dht22.py` with internal pull-up and single transient retry, conforming to the duck-typed sensor protocol (declaring `metrics`, `interval_ms`, and `read()`) and verify unit execution
- [x] 1.3 Implement onboard WS2812 RGB LED controller in `boards/esp32c6/hardware/led.py` handling network and operational status colors on GPIO 8
- [x] 1.4 Implement isolated display layout and button state handling in `boards/esp32c6/hardware/ui.py` (`UIController`) supporting sensor view, sleep mode, and message display
- [x] 1.5 Implement sensor-agnostic `AppState` and dynamic sensor registry in `boards/esp32c6/core/state.py` and verify metric registration and SenML aggregation
- [x] 1.6 Implement generic CoAP server and HTTP server in `boards/esp32c6/services/` dynamically exposing registered sensor metrics and handling `SEMI_SLEEP` on-demand reads
- [x] 1.7 Assemble `boards/esp32c6/main.py` as a lean orchestrator delegating to decoupled service runners, integrating proactive heap garbage collection (`memory_task`) and verifying clean startup execution

## 2. End-to-End Validation with Controller Backend and Frontend

- [x] 2.1 Verify CoAP `/sensors` and `/info` endpoints on `esp32c6` with mock requests to ensure valid SenML formatting and response codes
- [x] 2.2 Validate node discovery, capability probe, and telemetry ingestion with the controller backend poller (`controller/backend/poller.py`)
- [x] 2.3 Verify frontend dashboard discovers and displays the `esp32c6` board, including real-time telemetry charts and capability tags alongside Pico boards

## 3. Migration of Pico 1 W to Modular Architecture

- [x] 3.1 Refactor `boards/pico-1w/hardware/sensors/dht22.py` to conform to the standard modular sensor protocol
- [x] 3.2 Refactor `boards/pico-1w/hardware/ui.py` into a standardized `UIController` isolating display rendering and button events
- [x] 3.3 Migrate `boards/pico-1w/core/state.py` and services to sensor-agnostic `AppState` and verify telemetry matches previous schema

## 4. Migration of Pico 2 W to Modular Architecture

- [x] 4.1 Refactor `boards/pico-2w/hardware/sensors/` (DHT22 and ADC light sensor) to conform to the standard modular sensor protocol
- [x] 4.2 Refactor `boards/pico-2w/hardware/ui.py` into a standardized `UIController` isolating TFT display and button events
- [x] 4.3 Update `boards/pico-2w/services/data_logger.py` to ingest metrics generically from `AppState` while preserving CSV format, and verify logging state machine
- [x] 4.4 Migrate `boards/pico-2w/core/state.py` and services to sensor-agnostic `AppState` and verify full regression-free operation with SD logging
